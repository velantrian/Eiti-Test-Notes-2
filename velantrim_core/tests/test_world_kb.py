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
        assert "P31/P279" in fields["why"], location
        assert "P31/P279" in fields["verify"], location
        assert "первоисточник" in fields["verify"].lower(), location


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
