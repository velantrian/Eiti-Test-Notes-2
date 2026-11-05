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
PROPS = [("country", "wdt:P17", "country"), ("parent", "wdt:P131", "label")]
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
        for country in _p17_countries(it):
            groups[norm(country)].append((country, it))
    return groups


def _p17_countries(it):
    """P17 labels already restricted by q_items() to current Q6256 countries."""
    return sorted({clean(x) for x in it.get("country", []) if clean(x)}, key=norm)


def _primary_country_keys(it):
    """Heuristically find a described home country to filter obvious diaspora matches.

    This is only a relevance guard for continental summaries: P17 itself remains a
    recorded link, never evidence of population distribution or settlement.
    """
    words = re.findall(r"[a-zа-яё]+", norm(" ".join((it.get("l", ""), it.get("d", "")))))
    mentioned = set()
    for country in _p17_countries(it):
        for token in norm(country).split():
            if len(token) <= 3:
                found = token in words
            else:
                stem = token[:4]
                found = any(word.startswith(stem) for word in words)
            if found:
                mentioned.add(norm(country))
                break
    return mentioned


def _region_match(region, it):
    text = norm(" ".join([it.get("l", ""), it.get("d", ""), *it.get("parent", [])]))
    countries = _primary_country_keys(it) or {norm(c) for c in _p17_countries(it)}
    if region == "Сибирь":
        return bool(re.search(r"сибир|siberia|якут|тыва|тува|бурят|алтай|хакас|краснояр|иркут|омск|томск|новосибир|кемеров|забайкал", text, re.I))
    if region == "Кавказ":
        caucasus_countries = {norm(x) for x in ("Армения", "Азербайджан", "Грузия")}
        return bool(re.search(r"кавказ|caucas|дагестан|чечн|ингуш|осети|кабардин|черкес|адыге|абхаз", text, re.I)) or bool(countries & caucasus_countries)
    if region == "Центральная Азия":
        central = {norm(x) for x in "Казахстан Кыргызстан Таджикистан Туркменистан Узбекистан".split()}
        return any(norm(c) in central for c in it.get("country", []))
    return False


def _countries_for(it, preferred=(), allowed=()):
    preferred = {norm(x) for x in preferred}
    allowed = {norm(x) for x in allowed}
    vals = [x for x in _p17_countries(it) if not allowed or norm(x) in allowed]
    vals.sort(key=lambda value: (norm(value) not in preferred, norm(value)))
    return vals[:3]


TITLE_EN = {
    "Африка": "Africa", "Азия": "Asia", "Европа": "Europe",
    "Северная Америка": "North America", "Южная Америка": "South America", "Океания": "Oceania",
    "Россия": "Russia", "Китай": "China", "Сибирь": "Siberia", "Кавказ": "the Caucasus",
    "Центральная Азия": "Central Asia",
}


def _answer(title, selected, total, allowed_countries=(), preferred_countries=()):
    bits, bits_en, used = [], [], []
    for it in selected[:10]:
        countries = _countries_for(it, preferred_countries, allowed_countries)
        available = [x for x in _p17_countries(it)
                     if not allowed_countries or norm(x) in {norm(c) for c in allowed_countries}]
        suffix = (" (P17: " + ", ".join(countries) + (", и др." if len(available) > 3 else "") + ")") if countries else ""
        suffix_en = (" (P17: " + ", ".join(countries) + (", etc." if len(available) > 3 else "") + ")") if countries else ""
        if not countries and title in ("Сибирь", "Кавказ"):
            parents = sorted({clean(x) for x in it.get("parent", []) if clean(x)}, key=norm)
            if parents:
                suffix = " (административная связь P131: " + parents[0] + ")"
                suffix_en = " (admin link P131: " + parents[0] + ")"
        # Prefer EN label when present (q_items en=True); fall back to RU.
        name_en = (it.get("en") or it["l"]).strip() or it["l"]
        bits.append(f"{it['l']}{suffix}")
        bits_en.append(f"{name_en}{suffix_en}")
        used.append(it)
    display = TRIGGER_FORMS.get(title, (title, ""))[0]
    prefix = f"Народы {display} — выборка по записям Wikidata: "
    ending = f". Найдено {total}; P17/P131 и P30 — только записанные связи и приближение, не карта расселения и не полный список."
    title_en = TITLE_EN.get(title, title)
    prefix_en = f"Peoples of {title_en} — Wikidata sample: "
    ending_en = (f". Found {total}; P17/P131 and P30 are recorded links only — not a settlement map "
                 "or a complete list.")
    while bits and len(prefix + "; ".join(bits) + ending) > 690:
        bits.pop(); bits_en.pop(); used.pop()
    while bits_en and len(prefix_en + "; ".join(bits_en) + ending_en) > 690:
        bits_en.pop()
    ru = prefix + "; ".join(bits) + ending
    en = prefix_en + "; ".join(bits_en) + ending_en if bits_en else ""
    return ru, en, used


def _fields(title, qids, basis):
    joined = ", ".join(qids)
    return (f"@short: агрегированный список народов для {title}; обычный домен, не longtail. | "
            f"why: прямой P31=Q41710; группировка {basis}; P17 отфильтрован до объектов класса страны Q6256, "
            "P131 остаётся отдельной административной связью; без P172 и без утверждения о расселении. | "
            f"origin: Wikidata CC0; QIDs в порядке списка: {joined}; P30 классифицирует страну, а не группу. | "
            "verify: сверить QID, P31, P17, P30 и P131 в карточках Wikidata; для фактического расселения нужны отдельные этнографические источники.")


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
    tt = [f"народы {forms[0]}", f"народы {forms[1]}", f"народности {forms[0]}", f"народности {forms[1]}",
          f"расскажи о народах {forms[0]}", f"перечисли народы {forms[0]}",
          f"какие народы живут {forms[1]}", f"какие народности {forms[0]}"]
    en = TITLE_EN.get(title)
    if en:
        bare = en.replace("the ", "")
        tt += [f"peoples of {bare}", f"peoples in {bare}", f"who lives in {bare}"]
    return tt


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
        if selected: cards.append((region, selected[:10], len(selected), region,
                                   region_countries[region], region_countries[region]))
    continent_names = ("Африка", "Азия", "Европа", "Северная Америка", "Южная Америка", "Океания")
    for continent in continent_names:
        countries = {country for country, areas in country_continents.items() if norm(continent) in areas}
        selected = []
        for it in valid:
            # If label/description names a primary P17 country, do not let
            # unrelated diaspora links make the group an apparent continent match.
            relevant = _primary_country_keys(it) or {norm(c) for c in _p17_countries(it)}
            if relevant & countries:
                selected.append(it)
        selected.sort(key=lambda x: (-int(x.get("sl", 0)), norm(x["l"]), x["qid"]))
        if selected: cards.append((continent, selected[:10], len(selected), "P30→P17", countries, countries))
    for key, rows in sorted(groups.items()):
        if len(rows) < 3: continue
        selected = [it for _, it in rows]
        selected.sort(key=lambda x: (-int(x.get("sl", 0)), norm(x["l"]), x["qid"]))
        title = rows[0][0]
        cards.append((title, selected[:10], len(selected), "P17", {key}, {key}))
    lines = ["# Народы мира | Peoples of the world", "# @generated from Wikidata (CC0) — direct P31=Q41710; do not edit by hand"]
    for title, selected, total, basis, allowed, preferred in cards:
        answer, en, used = _answer(title, selected, total, allowed_countries=allowed,
                                   preferred_countries=preferred)
        qids = [it["qid"] for it in used]
        mid = (" || " + en) if en else ""
        lines.append("; ".join(_triggers(title)) + " || " + answer + mid + " || " + _fields(title, qids, basis))
    return lines


if __name__ == "__main__":
    result = build_people_region_source()
    print("aggregate records:", max(0, len(result) - 2))
    print("\n".join(result[:5]))
