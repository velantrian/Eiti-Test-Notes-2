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
