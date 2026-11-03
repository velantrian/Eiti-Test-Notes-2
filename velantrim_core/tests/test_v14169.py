"""v14.16.14: compact tabs — bottom bar only, header/icons untouched."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HTML=(ROOT/"index.html").read_text(encoding="utf-8")
SW=(ROOT/"sw.js").read_text(encoding="utf-8")
def test_version_sync():
    # compact-tabs feature remains; runtime version may advance past 14.16.14
    import re
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m and m.group(1) >= "14.16.14"
    assert f"var CACHE = 'eiti-v{m.group(1)}'" in SW
def test_compact_bottom_only():
    assert "eiti-compact-chrome" in HTML
    assert 'id="eiti-compact-chrome-toggle"' in HTML
    # must NOT shrink header/icons via compact class
    assert "html.eiti-compact-chrome .app-header" not in HTML
    assert "html.eiti-compact-chrome .tab-icon-wrapper" not in HTML
    assert "html.eiti-compact-chrome .tab-bar" in HTML
    # compact всегда с safe-area (Android жесты / iOS), не «голые» 96px
    assert "calc(96px + env(safe-area-inset-bottom" in HTML
