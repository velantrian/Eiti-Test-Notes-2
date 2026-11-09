"""v14.16.28: compact chrome API + phone-screen notch visibility."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_version_sync():
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m
    version = m.group(1)
    assert tuple(map(int, version.split("."))) >= (14, 16, 28)
    assert f"eiti-v{version}" in SW
    assert "14.16.28" in README


def test_compact_chrome_api_exists():
    assert "function eitiSetCompactChrome" in HTML
    assert "function eitiIsCompactChrome" in HTML
    assert "function eitiApplyCompactChrome" in HTML
    assert "eiti-compact-chrome-toggle-btn" in HTML
    assert "eitiSetCompactChrome(!eitiIsCompactChrome())" in HTML


def test_phone_screen_notch_visibility():
    assert "body.view-phone-screen .app-header" in HTML
    assert "html.eiti-phone .subview-header" in HTML
    assert "html.eiti-phone .app-header h1 { margin-top: 0 !important; }" in HTML
    assert 'html.eiti-phone[data-eiti-phone="iphone-notch"] .app-header::before' in HTML
