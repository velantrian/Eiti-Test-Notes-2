"""v14.16.18: richer non-geo KB answers in RU+EN + broader missing-field / rd hooks."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
IDX = json.loads((ROOT / "kb" / "index.json").read_text(encoding="utf-8"))
BUILD = (ROOT / "kb" / "build_kb.py").read_text(encoding="utf-8")
GEN = (ROOT / "kb" / "gen" / "gen_kb.py").read_text(encoding="utf-8")
MORE = (ROOT / "kb" / "gen" / "gen_more.py").read_text(encoding="utf-8")
REL = (ROOT / "local" / "eiti_related.js").read_text(encoding="utf-8")


def test_version_sync():
    # KB enrich remains; runtime version may advance past 14.16.18
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m, "missing runtime version"
    version = m.group(1)
    assert tuple(map(int, version.split("."))) >= (14, 16, 18)
    assert f"var CACHE = 'eiti-v{version}'" in SW
    assert f"version: '{version}'" in SW


def test_kb_still_exactly_150k():
    assert IDX["count"] == 150_000


def _entry(domain, title):
    for name in IDX["domains"][domain]["packs"]:
        pack = json.loads((ROOT / "kb" / name).read_text(encoding="utf-8"))
        for entry in pack["entries"].values():
            if entry.get("q") and entry["q"][0] == title:
                return entry
    raise AssertionError("%s/%s missing" % (domain, title))


def test_film_answer_has_genre_and_english():
    t = _entry("films", "Титаник")
    assert "Режиссёр:" in t["a"] or "режиссёр" in t["a"].lower()
    assert "Жанр:" in t["a"] or "Год выхода:" in t["a"]
    assert t.get("en"), "film should carry an English answer"
    assert "Director:" in t["en"] or "Release year:" in t["en"] or "Genre:" in t["en"]
    assert len(t.get("rd") or []) >= 3


def test_element_and_language_enrichment():
    au = _entry("elements", "золото")
    assert "атомный номер" in au["a"].lower() or "Атомный номер" in au["a"]
    assert au.get("en") and ("atomic number" in au["en"].lower() or "Symbol" in au["en"])
    lang = _entry("languages", "английский язык")
    assert "Семья" in lang["a"] or "язык" in lang["a"].lower()
    assert lang.get("en")


def test_builders_domain_expected_and_en_hooks():
    assert "DOMAIN_EXPECTED" in BUILD
    assert "RD_RICH" in BUILD
    assert "maybe_pair" in GEN and "lab_en" in GEN
    assert "PERSON_FACTS" in MORE
    assert "Not in this record" in REL or "Not in this record" in BUILD
    assert "(!useEn && e.f && typeof e.f.short === 'string')" in REL


def test_geo_still_has_iso_after_rebuild():
    fr = _entry("countries", "Франция")
    assert "Код ISO: FR" in fr["a"] or "ISO" in fr["a"]
    assert fr.get("en"), "countries gained EN answers in v14.16.18"


def test_remaining_sections_have_english():
    ady = _entry("admin_regions", "Республика Адыгея")
    assert ady.get("en") and "Administrative centre" in ady["en"]
    day = _entry("concepts", "сутки")
    assert day.get("en") and ("Day" in day["en"] or "day" in day["en"].lower())
    sib = _entry("peoples_regions", "народы Сибири")
    assert sib.get("en") and "Peoples of Siberia" in sib["en"]
