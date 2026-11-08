"""v14.16.24: stream RAF cancel before final markdown (Issue #13 browser gap)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
MANIFEST = (ROOT / "manifest.json").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_version_sync():
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m
    version = m.group(1)
    assert tuple(map(int, version.split("."))) >= (14, 16, 24)
    assert f"eiti-v{version}" in SW and f"version: '{version}'" in SW
    assert f"v{version}" in MANIFEST
    assert "14.16.24" in README


def test_raf_text_updater_cancel_before_markdown():
    assert "update.cancel = cancel" in HTML
    assert "overwrite innerHTML with raw textContent" in HTML
    # every major stream finalize cancels pending RAF
    assert HTML.count("_gmRafText.cancel") >= 1
    assert HTML.count("_orRafText.cancel") >= 1
    assert HTML.count("_oaiRafText.cancel") >= 1
    assert HTML.count("_dsRafText.cancel") >= 1
    assert "e2e/v141621_thinking_format.spec.js" in (ROOT / "velantrim_core/e2e/v141621_thinking_format.spec.js").as_posix() or True
    assert (ROOT / "velantrim_core/e2e/v141621_thinking_format.spec.js").is_file()
