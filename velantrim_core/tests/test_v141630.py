"""v14.16.30 (#27): exact CDN versions, SRI, vendored libraries, Content-Security-Policy."""
import base64
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
PAGES = (ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")
LOCAL_JS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "local").glob("*.js")))

# Hosts that appear only as links / headers / labels, never as fetch / WebSocket targets.
LINK_ONLY = {
    "docs.x.ai", "app.tavily.com", "ai.google.dev", "velantrim.eiti", "schemas.openxmlformats.org",
    "velantrian.github.io", "localhost",
}


def csp():
    m = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', HTML)
    assert m, "CSP meta missing"
    out = {}
    for part in m.group(1).split(";"):
        bits = part.split()
        if bits:
            out[bits[0]] = bits[1:]
    return m, out


def allowed(host, scheme, sources):
    for s in sources:
        if s in (scheme + ":",):
            return True
        mm = re.match(r"^(https?|wss?)://([^/:]+)", s)
        if not mm or mm.group(1) != scheme:
            continue
        pat = mm.group(2)
        if pat == host or (pat.startswith("*.") and host.endswith(pat[1:])):
            return True
    return False


def sri(path):
    return "sha384-" + base64.b64encode(hashlib.sha384(path.read_bytes()).digest()).decode()


def test_version_sync():
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m and tuple(map(int, m.group(1).split("."))) >= (14, 16, 30)
    assert f"var CACHE = 'eiti-v{m.group(1)}'" in SW


def test_csp_meta_before_any_script():
    m, pol = csp()
    assert m.start() < HTML.index("<script")
    assert pol["default-src"] == ["'self'"]
    assert pol["object-src"] == ["'none'"]
    assert pol["base-uri"] == ["'self'"]
    assert "'unsafe-eval'" not in pol["script-src"]
    assert "https:" not in pol["script-src"] and "*" not in pol["script-src"]
    assert "https:" not in pol["connect-src"] and "*" not in pol["connect-src"]


def test_every_used_endpoint_is_in_connect_src():
    _, pol = csp()
    src = HTML + "\n" + LOCAL_JS
    hosts = set(re.findall(r"['\"`](https|wss)://([a-z0-9.-]+)", src))
    # dynamically built Wikipedia URLs: 'https://' + lang + '.wikipedia.org'
    for lang in ("ru", "en"):
        hosts.add(("https", lang + ".wikipedia.org"))
    missing = sorted(f"{s}://{h}" for s, h in hosts
                     if h not in LINK_ONLY and not allowed(h, s, pol["connect-src"]) and not allowed(h, s, pol["script-src"]))
    assert not missing, "add to CSP connect-src (or LINK_ONLY): %s" % missing


def test_cdn_urls_have_exact_versions():
    for url in re.findall(r"https://(?:cdn\.jsdelivr\.net/npm|unpkg\.com|esm\.run)/[^'\"\s)]+", HTML):
        m = re.match(r"https://[^/]+(?:/npm)?/((?:@[^/@]+/)?[^/@?]+)@(\d+\.\d+\.\d+)(?:[/?+]|$)", url)
        assert m, "CDN URL without exact version: " + url
    assert "transformers@3'" not in HTML
    assert "@mlc-ai/web-llm/+esm" not in HTML and "@mlc-ai/web-llm'" not in HTML and "web-llm?module" not in HTML


def test_external_scripts_have_sri_and_crossorigin():
    tags = re.findall(r"<script[^>]*\ssrc=\"https?://[^\"]+\"[^>]*>", HTML)
    for tag in tags:
        assert 'integrity="sha384-' in tag, tag
        assert 'crossorigin="anonymous"' in tag, tag
    assert "s.integrity = EITI_MERMAID_SRI;" in HTML
    assert re.search(r"var EITI_MERMAID_SRI = 'sha384-[A-Za-z0-9+/=]{64}';", HTML)


def test_vendored_scripts_match_integrity_and_are_published():
    tags = re.findall(r'<script src="\./(vendor/[^"]+)" integrity="([^"]+)"', HTML)
    assert {t[0] for t in tags} >= {
        "vendor/dompurify/3.4.18/purify.min.js",
        "vendor/mammoth/1.13.0/mammoth.browser.min.js",
    }
    for rel, integ in tags:
        assert sri(ROOT / rel) == integ, rel
        assert f"'{rel}'" in PAGES, "build_pages REQUIRED_FILES: " + rel
        assert f"BASE + '{rel}'" in SW, "sw.js precache: " + rel
        assert (ROOT / rel).parent.joinpath("LICENSE").is_file()
    assert "cdnjs.cloudflare.com/ajax/libs/dompurify" not in HTML.split("</head>")[0].split("Content-Security-Policy")[1]
    assert "cdnjs.cloudflare.com/ajax/libs/mammoth" not in HTML
