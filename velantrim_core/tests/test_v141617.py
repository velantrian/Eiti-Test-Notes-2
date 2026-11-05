"""v14.16.17: richer geo KB answers + grounded generated_fields / country↔city cross-links."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
IDX = json.loads((ROOT / "kb" / "index.json").read_text(encoding="utf-8"))
BUILD = (ROOT / "kb" / "build_kb.py").read_text(encoding="utf-8")
GEN = (ROOT / "kb" / "gen" / "gen_kb.py").read_text(encoding="utf-8")
REL = (ROOT / "local" / "eiti_related.js").read_text(encoding="utf-8")


def test_version_sync():
    # geo enrich remains; runtime version may advance past 14.16.17
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m, "missing runtime version"
    version = m.group(1)
    assert tuple(map(int, version.split("."))) >= (14, 16, 17)
    assert f"var CACHE = 'eiti-v{version}'" in SW
    assert f"version: '{version}'" in SW


def test_kb_still_exactly_150k():
    assert IDX["count"] == 150_000
    assert IDX["domains"]["countries"]["count"] == 197
    assert IDX["domains"]["cities"]["count"] >= 4000
    assert IDX["domains"]["admin_regions"]["count"] == 412


def _entry(domain, title):
    for name in IDX["domains"][domain]["packs"]:
        pack = json.loads((ROOT / "kb" / name).read_text(encoding="utf-8"))
        for entry in pack["entries"].values():
            if entry.get("q") and entry["q"][0] == title:
                return entry
    raise AssertionError("%s/%s missing" % (domain, title))


def test_country_answer_has_iso_area_and_geo_context():
    fr = _entry("countries", "Франция")
    assert "Код ISO: FR" in fr["a"]
    assert "Площадь:" in fr["a"]
    f = fr["f"]
    assert "городов" in f.get("count", "")
    assert "Париж" in f.get("detail", "")
    assert not f["short"].startswith("Справочная карточка")
    assert len(fr.get("rd") or []) >= 3


def test_city_answer_has_admin_and_country_link():
    paris = _entry("cities", "Париж")
    assert "Страна: Франция" in paris["a"]
    assert "Административно:" in paris["a"]
    assert "Франция" in paris["f"].get("detail", "")
    assert "Основан" in paris["f"].get("how", "") or "Основан:" in paris["a"]


def test_builders_and_renderer_hooks():
    assert "enrich_geo_fields" in BUILD
    assert "GEO_EXPECTED" in BUILD
    assert "wdt:P297" in GEN and "wdt:P2046" in GEN and "wdt:P131" in GEN
    assert "detailMissing" in REL
    assert "exact.slice(0, 5)" in REL
