#!/usr/bin/env python3
"""Aggregate cards for peoples, based on direct Wikidata P31=Q41710.

``fetch_people_items() -> list[dict]`` performs only the cached query for direct
ethnic-group instances and returns normalized q_items records.
``build_people_region_source(items=None) -> list[str]`` returns source lines
(including the RU/EN header and CC0 provenance line); it never writes a file.
The cards are a compact, non-exhaustive selection: P17 is a recorded Wikidata
country link and P131 is a recorded administrative-parent link, not a census or
claim of complete settlement. P172 is deliberately not used as distribution
 evidence. Continental grouping follows the countries' P30 classification.
"""
import re
from collections import defaultdict

from gen_kb import clean, ok_label, q_items
from gen_more import BADL, GENERIC, NOISE, norm

CLASS = "wd:Q41710"
PROPS = [("country", "wdt:P17", "label"), ("parent", "wdt:P131", "label")]
SENSITIVE = re.compile(r"порно|porn|эрот|adult|fuck|shit|cunt|пизд|бляд|ебал|ебат", re.I)

def fetch_people_items():
    """Return ``list[dict]`` from the cached direct ``P31=Q41710`` query."""
    return q_items(CLASS, 1, PROPS, limit=10000, en=True)


def fetch_country_continents():
    """Map Russian country labels to P30 continent labels from Wikidata."""
    rows = q_items("wd:Q6256", 1, [("capital", "wdt:P36", "label"), ("continent", "wdt:P30", "label")],
                   limit=4000, cls_path="wdt:P31/wdt:P279*", en=True)
    mapping = defaultdict(set)
    for row in rows:
        country = norm(row.get("l", ""))
        if country:
            mapping[country].update(norm(x) for x in row.get("continent", []) if norm(x))
    return mapping


def _valid_items(items):
    out, seen_qid, seen_label = [], set(), set()
    for raw in items:
        qid, label = clean(raw.get("qid", "")), clean(raw.get("l", ""))
        if not re.fullmatch(r"Q\d+", qid) or not ok_label(label):
            continue
        key = norm(label)
        text = label + " " + clean(raw.get("d", ""))
        if qid in seen_qid or key in seen_label or BADL.search(label) or GENERIC.search(label):
            continue
        if NOISE.search(text) or SENSITIVE.search(text):
            continue
        countries = [clean(x) for x in raw.get("country", []) if ok_label(clean(x))]
        parents = [clean(x) for x in raw.get("parent", []) if clean(x)]
        if not countries and not parents:
            continue
        item = dict(raw, qid=qid, l=label, country=countries, parent=parents)
        out.append(item); seen_qid.add(qid); seen_label.add(key)
    return out


def _country_groups(items):
    groups = defaultdict(list)
    for it in items:
        for country in it["country"]:
            groups[norm(country)].append((country, it))
    return groups


def _region_match(region, it):
    text = norm(" ".join([it.get("l", ""), it.get("d", ""), *it.get("parent", [])]))
    countries = {norm(c) for c in it.get("country", [])}
    if region == "Сибирь":
        return bool(re.search(r"сибир|siberia|якут|тыва|тува|бурят|алтай|хакас|краснояр|иркут|омск|томск|новосибир|кемеров|забайкал", text, re.I))
    if region == "Кавказ":
        caucasus_countries = {norm(x) for x in ("Армения", "Азербайджан", "Грузия")}
        return bool(re.search(r"кавказ|caucas|дагестан|чечн|ингуш|осети|кабардин|черкес|адыге|абхаз", text, re.I)) or bool(countries & caucasus_countries)
    if region == "Центральная Азия":
        central = {norm(x) for x in "Казахстан Кыргызстан Таджикистан Туркменистан Узбекистан".split()}
        return any(norm(c) in central for c in it.get("country", []))
    return False


def _countries_for(it, preferred=()):
    preferred = {norm(x) for x in preferred}
    vals = sorted({clean(x) for x in it.get("country", []) if clean(x)},
                  key=lambda value: (norm(value) not in preferred, norm(value)))
    return vals[:3]


def _answer(title, selected, total, preferred_countries=()):
    bits = []
    used = []
    for it in selected[:10]:
        countries = _countries_for(it, preferred_countries)
        suffix = (" (" + ", ".join(countries) + (", и др." if len(it.get("country", [])) > 3 else "") + ")") if countries else ""
        if not countries and title in ("Сибирь", "Кавказ"):
            parents = sorted({clean(x) for x in it.get("parent", []) if clean(x)}, key=norm)
            if parents:
                suffix = " (P131: " + parents[0] + ")"
        bits.append(f"{it['l']}{suffix}")
        used.append(it)
    display = TRIGGER_FORMS.get(title, (title, ""))[0]
    prefix = f"Народы {display} — выборка: "
    ending = f". В выборке Wikidata найдено {total} записей, но список не полный: связи P17/P131 не задают полного расселения."
    while bits and len(prefix + "; ".join(bits) + ending) > 690:
        bits.pop()
        used.pop()
    return prefix + "; ".join(bits) + ending, used


def _fields(title, qids, basis):
    joined = ", ".join(qids)
    return (f"@short: агрегированный список народов для {title}; обычный домен, не longtail. | "
            f"why: прямой P31=Q41710 (ethnic group); группировка по recorded P17/P30/P131, "
            f"без P172 и без утверждения демографической полноты. | origin: Wikidata CC0; "
            f"QIDs в порядке списка: {joined}; {basis}. | verify: проверить карточки QID, P31, P17, P30 и P131; "
            "официальные этнографические источники использовать отдельно.")


TRIGGER_FORMS = {
    "Африка": ("Африки", "в Африке"), "Азия": ("Азии", "в Азии"),
    "Европа": ("Европы", "в Европе"), "Северная Америка": ("Северной Америки", "в Северной Америке"),
    "Южная Америка": ("Южной Америки", "в Южной Америке"), "Океания": ("Океании", "в Океании"),
    "Россия": ("России", "в России"), "Китай": ("Китая", "в Китае"),
    "Сибирь": ("Сибири", "в Сибири"), "Кавказ": ("Кавказа", "на Кавказе"),
    "Центральная Азия": ("Центральной Азии", "в Центральной Азии"),
}


def _triggers(title):
    """Return colloquial and inflected triggers; the KB stemmer handles the rest."""
    forms = TRIGGER_FORMS.get(title, (title, "в " + title))
    return [f"народы {forms[0]}", f"народы {forms[1]}", f"народности {forms[0]}", f"народности {forms[1]}",
            f"расскажи о народах {forms[0]}", f"перечисли народы {forms[0]}",
            f"какие народы живут {forms[1]}", f"какие народности {forms[0]}"]


def build_people_region_source(items=None):
    """Return ``list[str]``: complete ``w_peoples_regions.txt`` source lines; never writes a file."""
    valid = _valid_items(fetch_people_items() if items is None else items)
    groups = _country_groups(valid)
    country_continents = fetch_country_continents()
    cards = []
    # Explicit regions are added first so they cannot be crowded out by countries.
    region_countries = {
        "Сибирь": {norm("Россия")},
        "Кавказ": {norm(x) for x in ("Армения", "Азербайджан", "Грузия")},
        "Центральная Азия": {norm(x) for x in "Казахстан Кыргызстан Таджикистан Туркменистан Узбекистан".split()},
    }
    for region in ("Сибирь", "Кавказ", "Центральная Азия"):
        selected = [it for it in valid if _region_match(region, it)]
        selected.sort(key=lambda x: (-int(x.get("sl", 0)), norm(x["l"]), x["qid"]))
        if selected: cards.append((region, selected[:10], len(selected), region, region_countries[region]))
    continent_names = ("Африка", "Азия", "Европа", "Северная Америка", "Южная Америка", "Океания")
    for continent in continent_names:
        countries = {country for country, areas in country_continents.items() if norm(continent) in areas}
        selected = [it for it in valid if any(norm(c) in countries for c in it.get("country", []))]
        selected.sort(key=lambda x: (-int(x.get("sl", 0)), norm(x["l"]), x["qid"]))
        if selected: cards.append((continent, selected[:10], len(selected), "P30→P17", countries))
    for key, rows in sorted(groups.items()):
        if len(rows) < 3: continue
        selected = [it for _, it in rows]
        selected.sort(key=lambda x: (-int(x.get("sl", 0)), norm(x["l"]), x["qid"]))
        title = rows[0][0]
        cards.append((title, selected[:10], len(selected), "P17", {key}))
    lines = ["# Народы мира | Peoples of the world", "# @generated from Wikidata (CC0) — direct P31=Q41710; do not edit by hand"]
    for title, selected, total, basis, preferred in cards:
        answer, used = _answer(title, selected, total, preferred_countries=preferred)
        qids = [it["qid"] for it in used]
        lines.append("; ".join(_triggers(title)) + " || " + answer + " || " + _fields(title, qids, basis))
    return lines


if __name__ == "__main__":
    result = build_people_region_source()
    print("aggregate records:", max(0, len(result) - 2))
    print("\n".join(result[:5]))
