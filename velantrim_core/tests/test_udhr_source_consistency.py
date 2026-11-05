"""UDHR Q7813 provenance/semantics, RU+EN packs and embedded snapshot regression.

Wikidata Q7813: P577=1940 (unreferenced), P571=1948-12-10.
UN primary source: resolution 217 A (III), adopted 1948-12-10.
https://www.un.org/en/about-us/udhr/history-of-the-declaration
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TITLE = "Всеобщая декларация прав человека"
DATE_RU = "Принята: 10 декабря 1948 года."
DATE_EN = "Adopted: 10 December 1948."


def test_udhr_wikidata_exception_keeps_event_types_separate():
    sys.path.insert(0, str(ROOT / "kb" / "gen"))
    from gen_kb import book_date_parts

    # Wikidata truthy P577 does contain this year; treating it as verified is wrong.
    assert book_date_parts({"qid": "Q7813", "y": ["1940"]}) == (DATE_RU, DATE_EN)
    # Do not globally rewrite ordinary books or equate publication and adoption.
    assert book_date_parts({"qid": "Q999999", "y": ["1940"]}) == (
        "Опубликовано: 1940.", "Published: 1940."
    )


def _books():
    index = json.loads((ROOT / "kb/index.json").read_text(encoding="utf-8"))
    recs = []
    for part in index["domains"]["books"]["packs"]:
        data = json.loads((ROOT / "kb" / part).read_text(encoding="utf-8"))
        for eid, entry in data["entries"].items():
            recs.append((eid, eid.removeprefix("kbl_books_"), entry))
    return index, recs


def test_udhr_source_and_all_pack_snapshots_are_bilingual_and_consistent():
    source = (ROOT / "kb/src/w_books.txt").read_text(encoding="utf-8").splitlines()
    rows = [x for x in source if x.startswith(TITLE + ";")]
    assert len(rows) == 1
    parts = [p.strip() for p in rows[0].split("||")]
    assert DATE_RU in parts[1] and DATE_EN in parts[2]
    assert "Опубликовано: 1940." not in parts[1]
    assert "Published: 1940." not in parts[2]
    assert "Опубликовано: 1948." not in parts[1]  # adoption != publication
    assert "Published: 1948." not in parts[2]

    index, recs = _books()
    assert index["count"] == 150_000
    assert len(recs) == index["domains"]["books"]["count"] == 1308
    target = [(eid, entry) for eid, _, entry in recs if entry["q"][0] == TITLE]
    assert len(target) == 1
    eid, entry = target[0]
    assert eid == "kbl_books_7f9cc5"
    assert entry["a"] == parts[1]
    assert entry["en"] == parts[2]
    assert "Принята — 10 декабря 1948 года" in entry["f"]["short"]
    assert "1940" not in entry["f"]["short"]
    assert "1940" not in entry["f"]["verify"]

    copied = 0
    for _, _, rec in recs:
        for snapshot in rec.get("rd", []):
            if snapshot["q"] == [TITLE]:
                copied += 1
                assert snapshot["a"] == entry["a"]
                assert snapshot["en"] == entry["en"]
                assert "1940" not in snapshot["a"]
                assert "1940" not in snapshot["en"]
    assert copied >= 1, "regression needs to cover embedded linked snapshots"


def test_books_related_graph_and_snapshots_match_deterministic_builder():
    sys.path.insert(0, str(ROOT / "kb"))
    from related import related

    _, recs = _books()
    rel = related(recs)
    by_hash = {h: entry for _, h, entry in recs}
    for _, h, entry in recs:
        expected_rel = rel.get(h, [])
        assert entry.get("r", []) == expected_rel, h
        expected_snapshots = []
        for near in expected_rel[:5]:
            other = by_hash[near]
            snap = {"q": other["q"][:1], "a": other["a"]}
            if other.get("en"):
                snap["en"] = other["en"]
            expected_snapshots.append(snap)
        assert entry.get("rd", []) == expected_snapshots, h
