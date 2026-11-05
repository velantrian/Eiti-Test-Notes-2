"""v14.16.19: UI perf — version sync + i18n/stream/chat load guards in index.html."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
MANIFEST = (ROOT / "manifest.json").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def test_version_sync():
    import re
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m, "missing runtime version"
    version = m.group(1)
    assert tuple(map(int, version.split("."))) >= (14, 16, 19)
    assert f"eiti-v{version}" in SW and f"eiti-offline-v{version}" in SW
    assert f"v{version}" in MANIFEST and f"v{version}" in AGENTS


def test_perf_guards_present():
    assert "eitiCreateRafScroller" in HTML
    assert "createDocumentFragment()" in HTML
    assert "_inChatStream" in HTML
    assert "_watchFsOverlay" in HTML
    assert "observe(_histRoot" in HTML
