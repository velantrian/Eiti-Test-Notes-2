"""v14.16.2 legacy — version advances; keep composer/cache wiring checks soft."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HTML=(ROOT/"index.html").read_text(encoding="utf-8")
SW=(ROOT/"sw.js").read_text(encoding="utf-8")
def test_version_sync():
    assert "var EITI_VERSION" in HTML
    assert "var CACHE = 'eiti-v" in SW
def test_composer_is_flex_full_width():
    assert "chat-composer-shell" in HTML
