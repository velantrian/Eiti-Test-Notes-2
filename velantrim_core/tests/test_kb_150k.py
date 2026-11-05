"""Regression for the exact combined core + Wikidata KB size."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_preserves_legacy_longtail_article_in_generated_pack():
    trigger = "что такое Tha Last Meal"
    answer = "Tha Last Meal — альбом Snoop Dogg."
    source = ROOT / "kb/src/w_longtail_23.txt"
    source_lines = source.read_text(encoding="utf-8").splitlines()
    line = next(line for line in source_lines if line.startswith(f"{trigger} || {answer}"))
    parts = [part.strip() for part in line.split("||")]
    assert parts[1] == answer
    assert parts[2] == "Tha Last Meal — an album by Snoop Dogg."
    fields = {}
    for chunk in parts[-1].lstrip("@").split(" | "):
        key, sep, value = chunk.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    assert {"why", "origin", "verify"} <= set(fields)

    index = json.loads((ROOT / "kb/index.json").read_text(encoding="utf-8"))
    packs = index["domains"]["longtail_23"]["packs"]
    assert any(
        record.get("q") == [trigger] and record.get("a") == answer
        and record.get("en") == "Tha Last Meal — an album by Snoop Dogg."
        and {"why", "origin", "verify"} <= set(record.get("f", {}))
        for pack in packs
        for record in json.loads((ROOT / "kb" / pack).read_text(encoding="utf-8"))["entries"].values()
    )


def test_kb_index_has_exactly_150k_records():
    index = json.loads((ROOT / "kb/index.json").read_text(encoding="utf-8"))
    longtail = [name for name in index["domains"] if name.startswith("longtail_")]
    longtail_count = sum(index["domains"][name]["count"] for name in longtail)
    core_count = sum(meta["count"] for name, meta in index["domains"].items() if not name.startswith("longtail_"))
    assert index["count"] == 150_000
    assert len(longtail) == 24
    assert core_count == 33131   # v14.16.18: обогащение разделов (+people/geo/culture/…)
    assert longtail_count == 116869
    assert core_count + longtail_count == index["count"]
    assert core_count > 0
    assert longtail_count > 100_000
