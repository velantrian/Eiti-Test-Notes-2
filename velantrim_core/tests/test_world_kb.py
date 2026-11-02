"""World-entity longtail entries must retain type, reasoning and provenance."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "kb" / "src"

CATEGORY_MARKERS = {
    "countries": "Класс: страна или территория",
    "places": "Класс: город или населённое место",
    "admin1": "Класс: административная единица первого уровня",
    "admin2": "Класс: административная единица с прямым родителем ADM1",
    "municipalities": "Класс: муниципалитет",
    "admin_units": "Класс: административная территория",
    "institutions": "Класс: учреждение конкретного типа",
    "organizations": "Класс: организация",
    "peoples": "Класс: народ/этническая группа",
}


def _parse_fields(segment):
    fields = {}
    for chunk in segment.lstrip("@").split(" | "):
        key, sep, value = chunk.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def _world_cards():
    cards = []
    for path in sorted(SRC.glob("w_longtail_*.txt")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("||")]
            if parts and parts[-1].startswith("@short:"):
                cards.append((path.name, line_no, _parse_fields(parts[-1])))
    return cards


def test_world_entities_have_grounded_reasoning_and_verifiable_qids():
    cards = _world_cards()
    assert len(cards) >= 1000, f"only {len(cards)} typed world-entity cards"
    assert all({"short", "why", "origin", "verify"} <= set(fields) for _, _, fields in cards)

    for category, marker in CATEGORY_MARKERS.items():
        count = sum(marker in fields["short"] for _, _, fields in cards)
        assert count > 0, f"missing world category: {category}"

    for filename, line_no, fields in cards:
        location = f"{filename}:{line_no}"
        origin = fields["origin"]
        qids = re.findall(r"\bQ\d+\b", origin)
        assert "CC0" in origin, location
        assert qids, location
        assert f"https://www.wikidata.org/wiki/{qids[0]}" in origin, location
        if "Q41710" in fields["short"]:
            assert "P31=Q41710" in fields["why"], location
            assert "P31=Q41710" in fields["verify"], location
        else:
            assert "P31/P279" in fields["why"], location
            assert "P31/P279" in fields["verify"], location
        assert "первоисточник" in fields["verify"].lower(), location


def test_people_region_aggregates_are_grounded_and_searchable_core_sources():
    path = SRC / "w_peoples_regions.txt"
    records = [line for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.startswith("#")]
    assert len(records) >= 100
    triggers = "\n".join(line.split("||")[0] for line in records)
    for phrase in (
        "народы Африки", "народности в Африке", "расскажи о народах Африки",
        "народы России", "народности в России", "народы Китая", "народности в Китае",
        "народы Сибири", "народы Кавказа", "народы Центральной Азии",
    ):
        assert phrase in triggers, f"missing people-list query: {phrase}"

    for line in records:
        parts = [part.strip() for part in line.split("||")]
        assert len(parts) >= 3
        answer = parts[1]
        fields = _parse_fields(parts[-1])
        assert len(answer) <= 700
        qids = re.findall(r"\bQ\d+\b", fields["origin"])
        assert qids and len(answer.split("; ")) == len(qids)
        assert "Wikidata CC0" in fields["origin"]
        assert "P31=Q41710" in fields["why"] and "P30" in fields["why"]


def test_world_reasoning_fields_are_embedded_in_lazy_pack():
    index = json.loads((ROOT / "kb" / "index.json").read_text(encoding="utf-8"))
    assert "longtail_00" in index["lazy"]
    assert "longtail_00" not in index["order"]
    pack = ROOT / "kb" / "packs" / "kb_longtail_00_0.json"
    data = json.loads(pack.read_text(encoding="utf-8"))
    world_entries = [entry for entry in data["entries"].values() if entry.get("f", {}).get("short", "").startswith("Класс:")]
    assert world_entries, "first lazy longtail pack must contain a typed world entity"
    fields = world_entries[0]["f"]
    assert {"short", "why", "origin", "verify"} <= set(fields)
    assert "CC0" in fields["origin"] and "P31/P279" in fields["why"]
