"""v14.16.26: «Нижние табы» right rail in chat «+» popup."""
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
    assert tuple(map(int, version.split("."))) >= (14, 16, 26)
    assert f"eiti-v{version}" in SW
    assert "14.16.26" in README


def test_plus_popup_tabs_rail_removed_in_favor_of_inline_icons():
    # v14.16.27 superseded the right-rail layout with an inline «icons» row
    assert "chat-plus-tabs-rail" not in HTML
    assert "cpi-tabs-rail-label" not in HTML
    assert "writing-mode: vertical-rl" not in HTML
    assert "cpi-tabs-pin" in HTML
    assert "_t('icons')" in HTML
