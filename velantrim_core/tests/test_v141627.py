"""v14.16.27: «icons» inline in «+» menu; hide entire bottom bar including Chat."""
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
    assert tuple(map(int, version.split("."))) >= (14, 16, 27)
    assert f"eiti-v{version}" in SW
    assert "14.16.27" in README


def test_icons_inline_no_rail():
    assert "chat-plus-tabs-rail" not in HTML
    assert "cpi-tabs-rail-label" not in HTML
    assert "writing-mode: vertical-rl" not in HTML
    assert "cpi-tabs-pin" in HTML
    assert "_t('icons')" in HTML
    assert "обычная строка списка" in HTML or "без rail" in HTML
    assert "html.eiti-chat-only-tabs .tab-bar" in HTML
    assert re.search(
        r"html\.eiti-chat-only-tabs[\s\S]{0,400}\.tab-bar[\s\S]{0,200}display:\s*none\s*!important",
        HTML,
    )


def test_cpi_icon_has_volume():
    assert "box-shadow: 0 2px 5px rgba(0,0,0,0.35)" in HTML
    assert "linear-gradient(160deg, rgba(255,255,255,0.16)" in HTML
