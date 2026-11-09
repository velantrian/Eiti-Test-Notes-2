"""v14.16.25: chat-only tab bar height beats compact-chrome (!important)."""
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
    assert tuple(map(int, version.split("."))) >= (14, 16, 25)
    assert f"eiti-v{version}" in SW and f"version: '{version}'" in SW
    assert "14.16.25" in README


def test_chat_only_beats_compact_chrome():
    # v14.16.27: bar is fully hidden (display:none), including under compact-chrome
    assert "html.eiti-chat-only-tabs.eiti-compact-chrome .tab-bar" in HTML
    assert "html.eiti-chat-only-tabs .tab-bar," in HTML
    assert "display: none !important" in HTML
    assert (ROOT / "velantrim_core/e2e/v141623_chat_only_tabs.spec.js").is_file()
