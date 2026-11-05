"""v14.16.19: UI perf — version sync + i18n/stream/chat load guards in index.html."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
MANIFEST = (ROOT / "manifest.json").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def test_version_sync():
    assert 'EITI_VERSION = "14.16.19"' in HTML or 'EITI_VERSION="14.16.19"' in HTML
    assert "eiti-v14.16.19" in SW and "eiti-offline-v14.16.19" in SW
    assert "v14.16.19" in MANIFEST and "v14.16.19" in AGENTS


def test_perf_guards_present():
    assert "eitiCreateRafScroller" in HTML
    assert "createDocumentFragment()" in HTML
    assert "_inChatStream" in HTML
    assert "_watchFsOverlay" in HTML
    assert "observe(_histRoot" in HTML
