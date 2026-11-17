"""v14.16.32: Android APK (Capacitor) — нативная оболочка, UI-объём, производительность, длинные правки, модели."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
PAGES = (ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")


def test_version_sync():
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m and tuple(map(int, m.group(1).split("."))) >= (14, 16, 32)
    assert f"var CACHE = 'eiti-v{m.group(1)}'" in SW


# ── item 1: шапка / safe-area / PWA-установка в APK ──
def test_native_flag_early():
    head = HTML[: HTML.index("</head>")]
    assert "window.EITI_NATIVE=EN" in head
    assert "classList.add('eiti-native')" in head
    assert "eiti_header_size" in head


def test_capacitor_insets_preferred():
    assert "--eiti-env-top: var(--safe-area-inset-top, env(safe-area-inset-top, 0px));" in HTML
    assert 'data-eiti-phone="native"' in HTML


def test_pwa_install_hidden_in_native():
    assert "html.eiti-native #btn-pwa-install, html.eiti-native #pwa-install-banner { display: none !important; }" in HTML
    for frag in ("function eitiShowInstallBanner(customMsg, force) {\n            if (window.EITI_NATIVE) return;",
                 "function installPWA() {\n            if (window.EITI_NATIVE)"):
        assert frag in HTML
    assert "!window.EITI_NATIVE && !localStorage.getItem('eiti_storage_persistent_warned')" in HTML


def test_header_size_setting():
    assert 'id="eiti-header-size-btn"' in HTML
    assert "function eitiSetHeaderLarge(" in HTML and "function eitiIsHeaderLarge(" in HTML


# ── item 10: Заметки AI — без зазора над таб-баром ──
def test_notes_ai_no_double_safe_area():
    i = HTML.index(".notes-ai-panel {\n            display: none;")
    block = HTML[i: HTML.index("}", i)]
    assert "padding-bottom: 0;" in block and "env(safe-area-inset-bottom" not in block
    assert "--eiti-nai-sb: var(--eiti-bottom-inset, var(--eiti-env-bottom))" in HTML


# ── items 12 + 13: объём и Fluent Emoji 3D ──
FLUENT = ["speech_balloon", "notebook", "books", "musical_note", "file_folder", "memo", "calendar", "gear"]


def test_fluent_icons_vendored_with_license():
    d = ROOT / "vendor" / "fluent-emoji-3d"
    lic = (d / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in lic and "Microsoft Corporation" in lic
    for n in FLUENT:
        data = (d / f"{n}.webp").read_bytes()
        assert data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) < 8000
        assert f"vendor/fluent-emoji-3d/{n}.webp" in HTML
        assert f"BASE + 'vendor/fluent-emoji-3d/{n}.webp'" in SW
        assert f"'vendor/fluent-emoji-3d/{n}.webp'" in PAGES
    assert "'vendor/fluent-emoji-3d/LICENSE'" in PAGES


def test_fluent_icons_no_cdn():
    assert "fluentui-emoji" not in HTML.replace("Fluent Emoji 3D", "")
    assert not re.search(r"https://[^\"' ]*fluent[^\"' ]*\.(png|webp|svg)", HTML)


def test_depth_default_only_native():
    head = HTML[: HTML.index("</head>")]
    assert "if(DP==='1'||(DP!=='0'&&EN))document.documentElement.classList.add('eiti-depth')" in head
    assert "html.eiti-depth .chat-composer-shell {" in HTML
    assert 'id="eiti-depth-btn"' in HTML and 'id="eiti-icons3d-btn"' in HTML


# ── item 14: ярлыки PWA с 3D-иконками (а не белые квадраты) ──
def test_manifest_shortcut_icons():
    import json
    from PIL import Image
    m = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    sc = {s["url"]: s for s in m["shortcuts"]}
    want = {"./index.html#chat": "chat", "./index.html#notes": "notes", "./index.html#player": "player", "./index.html#files": "memory"}
    assert set(sc) == set(want)
    for url, name in want.items():
        icons = sc[url]["icons"]
        assert [i["sizes"] for i in icons] == ["96x96", "192x192"]
        for i in icons:
            assert i["purpose"] == "any" and i["type"] == "image/png"
            assert not i["src"].startswith(("/", "http")), "путь относительный к manifest.json (подпапка Pages)"
            assert i["src"] == f"vendor/fluent-emoji-3d/shortcuts/{name}-{i['sizes'].split('x')[0]}.png"
            assert f"'{i['src']}'" in PAGES
            im = Image.open(ROOT / i["src"])
            px = int(i["sizes"].split("x")[0])
            assert im.format == "PNG" and im.size == (px, px) and im.mode == "RGBA"
            # не пустой/белый квадрат: заметная доля непрозрачных цветных пикселей
            alpha = im.getchannel("A")
            opaque = sum(1 for a in alpha.getdata() if a > 128)
            assert opaque > px * px * 0.25
            assert im.getpixel((0, 0))[3] == 0  # прозрачные углы
