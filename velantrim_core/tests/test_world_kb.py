"""World-entity generation, geography, provenance and size regressions."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "kb" / "src"
sys.path.insert(0, str(ROOT / "kb" / "gen"))
sys.path.insert(0, str(ROOT / "kb"))
import gen_kb  # noqa: E402
import gen_longtail  # noqa: E402
import world_entities  # noqa: E402
import world_peoples  # noqa: E402

CATEGORY_MARKERS = {
    "countries": "Класс: страна или территория",
    "places": "Класс: город или населённое место",
    "admin1": "Класс: административная единица первого уровня",
    "admin2": "Класс: административная единица с прямым родителем ADM1",
    "municipalities": "Класс: муниципалитет",
    "admin_units": "Класс: административная территория",
    "institutions": "Класс: учреждение",
    "organizations": "Класс: организация",
    "peoples": "Класс: народ/этническая группа",
}
CATEGORY_FLOORS = {
    "countries": 350,
    "places": 25_000,
    "admin1": 4_000,
    "admin2": 6_000,
    "municipalities": 8_000,
    "admin_units": 550,
    "institutions": 10_000,
    "organizations": 4_000,
    "peoples": 8_000,
}


def _parse_fields(segment):
    fields = {}
    for chunk in segment.lstrip("@").split(" | "):
        key, sep, value = chunk.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def _source_record(line):
    parts = [part.strip() for part in line.split("||")]
    fields = _parse_fields(parts[-1]) if parts and parts[-1].startswith("@") else {}
    body = parts[:-1] if parts and parts[-1].startswith("@") else parts
    return {
        "trigger": body[0] if body else "",
        "answer": body[1] if len(body) > 1 else "",
        "english": body[2] if len(body) > 2 else "",
        "fields": fields,
    }


def _world_cards():
    cards = []
    for path in sorted(SRC.glob("w_longtail_*.txt")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            record = _source_record(line)
            if record["fields"].get("short", "").startswith("Класс:"):
                cards.append((path.name, line_no, record))
    return cards


def _all_tail_cards():
    cards = []
    for path in sorted(SRC.glob("w_longtail_*.txt")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip() and not line.startswith("#"):
                cards.append((path.name, line_no, _source_record(line)))
    return cards


def _generated_pack_entries(domain):
    index = json.loads((ROOT / "kb" / "index.json").read_text(encoding="utf-8"))
    meta = index["domains"][domain]
    for filename in meta["packs"]:
        data = json.loads((ROOT / "kb" / filename).read_text(encoding="utf-8"))
        yield from data["entries"].values()


def test_world_entities_have_entity_specific_reasoning_and_category_floors():
    cards = _world_cards()
    assert len(cards) >= 71_386, f"only {len(cards)} typed world-entity cards"
    counts = Counter()
    for _, _, record in cards:
        fields = record["fields"]
        for category, marker in CATEGORY_MARKERS.items():
            if marker in fields.get("short", ""):
                counts[category] += 1
    for category, floor in CATEGORY_FLOORS.items():
        assert counts[category] >= floor, f"{category}: {counts[category]} < {floor}"

    for filename, line_no, record in cards:
        location = f"{filename}:{line_no}"
        fields = record["fields"]
        assert {"short", "why", "origin", "verify"} <= set(fields), location
        qids = re.findall(r"\bQ\d+\b", fields["origin"])
        assert "CC0" in fields["origin"], location
        assert qids, location
        assert f"https://www.wikidata.org/wiki/{qids[0]}" in fields["origin"], location
        entity_label = next((t.strip()[len("что такое "):]
                             for t in record["trigger"].split(";")
                             if t.strip().lower().startswith("что такое ")), None)
        assert entity_label and entity_label.lower() in fields["why"].lower(), location
        assert "P31/P279" in fields["verify"] or "P31=Q41710" in fields["verify"], location
        assert "первоисточник" in fields["verify"].lower(), location
        if "Q41710" in fields["short"]:
            assert "P31=Q41710" in fields["why"], location


def test_all_longtail_rows_have_explanations_and_english_answer():
    cards = _all_tail_cards()
    assert len(cards) == 118_091   # v14.16.15: −200 строк хвоста под регионы (admin_regions)
    for filename, line_no, record in cards:
        location = f"{filename}:{line_no}"
        assert record["english"], location
        assert {"why", "origin", "verify"} <= set(record["fields"]), location
        assert record["fields"]["why"], location
        assert record["fields"]["origin"], location
        assert record["fields"]["verify"], location


def test_every_generated_wikidata_pack_card_has_explanation_fields():
    index = json.loads((ROOT / "kb" / "index.json").read_text(encoding="utf-8"))
    generated = [p for p in sorted(SRC.glob("w_*.txt"))
                 if len(p.read_text(encoding="utf-8").splitlines()) > 1
                 and p.read_text(encoding="utf-8").splitlines()[1].startswith("# @generated")]
    checked = 0
    expected = 0
    for source in generated:
        domain = source.stem[2:]
        if domain not in index["domains"]:
            continue
        expected += index["domains"][domain]["count"]
        for entry in _generated_pack_entries(domain):
            fields = entry.get("f", {})
            assert {"short", "why", "origin", "verify"} <= set(fields), f"{source.name}:{entry.get('q')}"
            checked += 1
    assert checked == expected
    assert checked >= 148_000


def test_legacy_cities_and_countries_are_explained_in_packs():
    for domain in ("cities", "countries"):
        entries = list(_generated_pack_entries(domain))
        assert entries
        for entry in entries:
            fields = entry.get("f", {})
            assert {"why", "origin", "verify"} <= set(fields), (domain, entry.get("q"))
            assert fields["why"] and fields["origin"] and fields["verify"]


def test_people_region_aggregates_filter_false_geography_and_separate_p17_p131():
    path = SRC / "w_peoples_regions.txt"
    records = [_source_record(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.startswith("#")]
    assert len(records) >= 100
    triggers = "\n".join(record["trigger"] for record in records)
    for phrase in (
        "народы Африки", "народности в Африке", "расскажи о народах Африки",
        "народы России", "народности в России", "народы Китая", "народности в Китае",
        "народы Сибири", "народы Кавказа", "народы Центральной Азии",
    ):
        assert phrase in triggers, f"missing people-list query: {phrase}"

    africa = next(record for record in records if "народы Африки" in record["trigger"])
    africa_text = africa["answer"].lower()
    assert "итальянцы" not in africa_text
    assert "литовцы" not in africa_text

    siberia = next(record for record in records if "народы Сибири" in record["trigger"])
    nenets = next((part for part in siberia["answer"].split("; ") if part.lower().startswith("ненцы")), None)
    assert nenets, "Nenets should remain in the Siberia sample"
    assert "P17: Россия" in nenets
    assert "Воркута" not in nenets
    assert "Городской округ Архангельск" not in nenets
    assert "не карта расселения" in siberia["answer"]

    for record in records:
        fields = record["fields"]
        qids = re.findall(r"\bQ\d+\b", fields.get("origin", ""))
        assert qids and len(record["answer"].split("; ")) == len(qids) + 1
        assert "Wikidata CC0" in fields["origin"]
        assert "P31=Q41710" in fields["why"]
        assert "P30 классифицирует страну, а не группу" in fields["origin"]
        assert "P30" in fields["verify"]
        assert "P131 остаётся отдельной административной связью" in fields["why"]
        assert "без утверждения о расселении" in fields["why"]
        assert len(record["answer"]) <= 700


def test_p131_is_never_rendered_as_a_country():
    item = {"qid": "Q166176", "l": "ненцы", "country": [],
            "parent": ["Воркута", "Городской округ Архангельск"], "d": "народ Сибири", "sl": 10}
    answer, used = world_peoples._answer("Сибирь", [item], 1,
                                         allowed_countries={"Россия"}, preferred_countries={"Россия"})
    assert used == [item]
    assert "P17: Воркута" not in answer
    assert "административная связь P131: Воркута" in answer


def test_continent_relevance_uses_described_primary_p17_country():
    italian = {"l": "итальянцы", "d": "народ романской языковой группы, основное население Италии",
               "country": ["ЮАР", "Италия"]}
    lithuanian = {"l": "литовцы", "d": "народ балтийской группы, основное население Литвы",
                  "country": ["ЮАР", "Литва"]}
    assert world_peoples._primary_country_keys(italian) == {"италия"}
    assert world_peoples._primary_country_keys(lithuanian) == {"литва"}
    assert world_peoples._primary_country_keys(italian).isdisjoint({"юар"})
    assert world_peoples._primary_country_keys(lithuanian).isdisjoint({"юар"})


def test_q_items_filters_p17_to_current_country_class_and_exposes_english(monkeypatch):
    captured = {}

    def fake_sparql(query, tag):
        captured["query"] = query
        return [{"x": "http://www.wikidata.org/entity/Q166176", "l": "ненцы", "d": "народ Сибири",
                 "le": "Nenets", "de": "Siberian people", "sl": "61", "countrys": "Россия"}]

    monkeypatch.setattr(gen_kb, "sparql", fake_sparql)
    rows = gen_kb.q_items("wd:Q41710", 1, [("country", "wdt:P17", "country")], limit=10, en=True)
    assert "?country_ wdt:P31/wdt:P279* wd:Q6256" in captured["query"]
    assert "FILTER NOT EXISTS { ?country_ wdt:P576 ?country_end }" in captured["query"]
    assert rows[0]["country"] == ["Россия"]
    assert rows[0]["en"] == "Nenets"
    assert rows[0]["den"] == "Siberian people"


def test_generic_longtail_uses_english_label_and_description_fallback(monkeypatch):
    captured = {}

    def fake_sparql(query, tag):
        captured["query"] = query
        return [{"x": "http://www.wikidata.org/entity/Q999", "l": "Only English Label",
                 "le": "Only English Label", "de": "An English-language description", "sl": "8"}]

    monkeypatch.setattr(gen_longtail, "sparql", fake_sparql)
    rows = gen_longtail.query_page(0)
    assert 'LANG(?le)="en"' in captured["query"]
    assert 'LANG(?de)="en"' in captured["query"]
    row = rows[0]
    assert row["qid"] == "Q999"
    assert row["l"] == "Only English Label"
    assert row["den"] == "An English-language description"
    ru, en = gen_longtail.generic_answers(row["l"], row["d"], row["den"], row["en"])
    assert "русское описание отсутствует" in ru
    assert en == "Only English Label — An English-language description."
    assert "Wikidata CC0" in gen_longtail.generic_fields(row, row["l"], row["d"], row["den"])


def test_unavailable_first_world_page_is_skipped_without_losing_prior_cards(monkeypatch, capsys):
    group = {"key": "temporary", "classes": "wd:Q6256", "quota": 10,
             "page_size": 10, "max_pages": 1, "props": []}
    monkeypatch.setattr(world_entities, "WORLD_GROUPS", (group,))

    def unavailable(*args, **kwargs):
        raise SystemExit("sparql failed test")

    monkeypatch.setattr(world_entities, "q_items", unavailable)
    records = world_entities.generate_world_entities(10, {}, set(), set(), set())
    assert records == []
    assert "skipping new candidates and keeping prior generated cards" in capsys.readouterr().out


def test_preserved_typed_card_without_english_gets_entity_specific_fallback(monkeypatch, tmp_path):
    source = tmp_path / "w_longtail_00.txt"
    source.write_text(
        "# source\nчто такое Древний город || описание объекта. || "
        "@short: Класс: город или населённое место | why: правило отбора | "
        "origin: Wikidata CC0; QID Q123 | verify: сверить P31/P279 и первоисточник\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gen_longtail, "SRC", str(tmp_path))
    records = gen_longtail.preserved_world_records([source.name], {}, set(), set())
    assert len(records) == 1
    assert "Древний город" in records[0][2]
    assert "English description is unavailable" in records[0][2]
    assert "Древний город" in records[0][3]


def test_preserved_generic_fallback_keeps_answer_and_discloses_missing_qid(monkeypatch, tmp_path):
    source = tmp_path / "w_longtail_00.txt"
    answer = "Старая сущность — сохранённое описание из локального снимка."
    source.write_text(f"что такое Старая сущность || {answer}\n", encoding="utf-8")
    monkeypatch.setattr(gen_longtail, "SRC", str(tmp_path))
    records = gen_longtail.preserved_generic_records([source.name], {}, set(), set(), 1)
    assert len(records) == 1
    assert records[0][1] == answer
    assert "English description unavailable" in records[0][2]
    assert "QID" in records[0][3]
    assert "verify:" in records[0][3]


def test_source_generator_keeps_exact_kb_size():
    total, _, _ = gen_longtail.source_state()
    assert total == 150_000


def test_world_reasoning_fields_are_embedded_in_lazy_pack():
    index = json.loads((ROOT / "kb" / "index.json").read_text(encoding="utf-8"))
    assert "longtail_00" in index["lazy"]
    assert "longtail_00" not in index["order"]
    entries = list(_generated_pack_entries("longtail_00"))
    world_entries = [entry for entry in entries if entry.get("f", {}).get("short", "").startswith("Класс:")]
    assert world_entries, "first lazy longtail pack must contain a typed world entity"
    fields = world_entries[0]["f"]
    assert {"short", "why", "origin", "verify"} <= set(fields)
    assert "CC0" in fields["origin"]
    assert "Карточка «" in fields["why"]
