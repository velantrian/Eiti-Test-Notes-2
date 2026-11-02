#!/usr/bin/env python3
"""Generate Wikidata (CC0) long-tail KB entries up to exactly 150,000 records.

Run after the existing KB sources are present:
    python3 kb/gen/gen_longtail.py
    python3 kb/build_kb.py --strict

The long-tail index is split into 5k-entry lazy shards. Its questions are exact
"что такое …" lookups, so it cannot compete with unrelated KB searches.
"""
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, 'kb', 'src')
TARGET_COUNT = 150_000
MIN_SITELINKS = 5
PAGE_SIZE = 20_000
MAX_OFFSET = 600_000
SHARD_RECORDS = 5_000
OUT_PREFIX = 'w_longtail_'
PINNED_RECORDS = (
    ('что такое Tha Last Meal', 'Tha Last Meal — альбом Snoop Dogg.', ''),
)

sys.path.insert(0, HERE)
from gen_kb import cap, clean, desc, ok_label, sent  # noqa: E402
from gen_more import BADL, GENERIC, HAND, NOISE, SEEN, known, load_seen, norm  # noqa: E402
from wd import sparql  # noqa: E402
from world_entities import generate_world_entities  # noqa: E402
from world_peoples import build_people_region_source, fetch_people_items  # noqa: E402

MEDICAL = re.compile(
    r'болезн|заболеван|синдром|лекарств|препарат|лечени|медицин|диагност|'
    r'симптом|вакцин|фармацевт|расстройств|антибиотик|медикамент|дозиров', re.I
)
SENSITIVE = re.compile(
    r'порно|порнограф|порностуд|эротическ|porn|adult website|fuck|shit|cunt|'
    r'на хуй|нахуй|бляд|пизд|ебал|ебат', re.I
)
START_LABEL = re.compile(r'^[a-zа-яё0-9]', re.I)
TAIL_FILE = re.compile(r'^w_longtail(?:_\d{2})?\.txt$')


def is_longtail_file(name):
    return bool(TAIL_FILE.match(name))


def source_state(exclude_longtail=False, replacements=None):
    """Count records as build_kb.py does, optionally overlaying generated sources."""
    replacements = replacements or {}
    seen_t, seen_a = {}, set()
    total = 0
    files = sorted(set(os.listdir(SRC)) | set(replacements), key=lambda name: (name.startswith('w_'), name))
    for name in files:
        if not name.endswith('.txt') or (exclude_longtail and is_longtail_file(name)):
            continue
        path = os.path.join(SRC, name)
        lines = replacements[name] if name in replacements else open(path, encoding='utf-8')
        for line_no, line in enumerate(lines, 1):
            if not line.strip() or line.startswith('#'):
                continue
            parts = [part.strip() for part in line.split('||')]
            if len(parts) > 2 and parts[-1].startswith('@'):
                parts.pop()
            if len(parts) < 2 or not parts[1]:
                continue
            has_new_trigger = False
            for trigger in (part.strip() for part in parts[0].split(';')):
                nt = norm(trigger)
                if nt and nt not in seen_t:
                    seen_t[nt] = '%s:%d' % (name, line_no)
                    has_new_trigger = True
            answer = norm(parts[1])
            if answer in seen_a or not has_new_trigger:
                continue
            seen_a.add(answer)
            total += 1
    return total, seen_t, seen_a


def query_page(offset):
    query = (
        'SELECT ?x ?l ?d ?sl WHERE { '
        '?x wikibase:sitelinks ?sl . FILTER(?sl >= %d) '
        'FILTER NOT EXISTS { ?x wdt:P31 wd:Q5 } '
        '?x rdfs:label ?l . FILTER(LANG(?l)="ru") '
        '?x schema:description ?d . FILTER(LANG(?d)="ru") '
        'FILTER(STRLEN(STR(?l)) <= 60) '
        '} ORDER BY DESC(?sl) STR(?l) STR(?x) LIMIT %d OFFSET %d'
    ) % (MIN_SITELINKS, PAGE_SIZE, offset)
    tag = 'longtail_' + hashlib.sha1(query.encode('utf-8')).hexdigest()[:16]
    return sparql(query, tag)


def preserved_world_records(old_files, seen_triggers, seen_answers, added_labels):
    """Keep previously generated typed world cards; generic tail is refillable."""
    records = []
    for name in old_files:
        path = os.path.join(SRC, name)
        for line in open(path, encoding='utf-8'):
            if not line.strip() or line.startswith('#'):
                continue
            parts = [part.strip() for part in line.split('||')]
            if len(parts) < 3 or not parts[-1].startswith('@short:') or 'Класс:' not in parts[-1]:
                continue
            fields = parts[-1]
            if not all(marker in fields for marker in ('why:', 'origin:', 'verify:')):
                continue
            trigger_text, answer = parts[0], parts[1]
            trigger_pairs = [(text.strip(), norm(text)) for text in trigger_text.split(';')]
            trigger_pairs = [(text, key) for text, key in trigger_pairs if key]
            answer_key = norm(answer)
            if not answer_key or answer_key in seen_answers or not trigger_pairs:
                continue
            if any(key in seen_triggers for _, key in trigger_pairs):
                continue
            records.append((trigger_text, answer, fields))
            for text, key in trigger_pairs:
                seen_triggers[key] = 'preserved_world'
                if text.lower().startswith('что такое '):
                    added_labels.add(norm(text[len('что такое '):].strip()))
            seen_answers.add(answer_key)
    return records


def write_sources(records, old_files, replacements=None):
    """Replace prior long-tail output atomically enough to restore it on failure."""
    replacements = replacements or {}
    affected = set(old_files) | set(replacements)
    backups = {}
    for name in affected:
        path = os.path.join(SRC, name)
        backups[name] = open(path, 'rb').read() if os.path.exists(path) else None
    new_names = []
    try:
        for name in old_files:
            os.remove(os.path.join(SRC, name))
        for name, lines in replacements.items():
            path = os.path.join(SRC, name)
            new_names.append(name)
            with open(path, 'w', encoding='utf-8') as out:
                for line in lines:
                    out.write(str(line).rstrip('\n') + '\n')
        for shard_no, start in enumerate(range(0, len(records), SHARD_RECORDS)):
            domain = 'longtail_%02d' % shard_no
            name = OUT_PREFIX + '%02d.txt' % shard_no
            batch = records[start:start + SHARD_RECORDS]
            path = os.path.join(SRC, name)
            new_names.append(name)
            with open(path, 'w', encoding='utf-8') as out:
                out.write('# Энциклопедические темы | Encyclopedia topics\n')
                out.write('# @generated from Wikidata (CC0) by kb/gen/gen_longtail.py — do not edit by hand\n')
                for record in batch:
                    trigger, answer = record[:2]
                    fields = record[2] if len(record) > 2 else ''
                    suffix = (' || ' + fields) if fields else ''
                    out.write('%s || %s%s\n' % (trigger, answer, suffix))
        actual, _, _ = source_state()
        if actual != TARGET_COUNT:
            raise RuntimeError('source count mismatch: expected %d, got %d' % (TARGET_COUNT, actual))
    except Exception:
        for name in new_names:
            path = os.path.join(SRC, name)
            if os.path.exists(path):
                os.remove(path)
        for name, content in backups.items():
            path = os.path.join(SRC, name)
            if content is None:
                if os.path.exists(path):
                    os.remove(path)
            else:
                with open(path, 'wb') as out:
                    out.write(content)
        raise


def main():
    os.makedirs(SRC, exist_ok=True)
    old_files = sorted(name for name in os.listdir(SRC) if is_longtail_file(name))
    load_seen(skip=set(old_files))
    hand_words = {word for phrase in HAND for word in phrase.strip().split()}
    added_labels = set()
    people_items = fetch_people_items()
    people_source = build_people_region_source(people_items)
    replacements = {'w_peoples_regions.txt': people_source}
    current, seen_triggers, seen_answers = source_state(exclude_longtail=True, replacements=replacements)
    needed = TARGET_COUNT - current
    if needed <= 0:
        raise SystemExit('Base KB already has %d records; target is %d.' % (current, TARGET_COUNT))

    pinned_records = list(PINNED_RECORDS)
    record_budget = needed - len(pinned_records)
    if record_budget < 0:
        raise SystemExit('Pinned longtail records exceed the available KB capacity.')
    for trigger, answer, _fields in pinned_records:
        label = trigger[len('что такое '):] if trigger.startswith('что такое ') else ''
        trigger_key, answer_key = norm(trigger), norm(answer)
        if not label or trigger_key in seen_triggers or answer_key in seen_answers:
            raise SystemExit('Pinned longtail record collides with the base KB: %s' % trigger)
        seen_triggers[trigger_key] = 'pinned longtail record'
        seen_answers.add(answer_key)
        added_labels.add(norm(label))

    records = preserved_world_records(old_files, seen_triggers, seen_answers, added_labels)
    print('preserved existing typed world entries', len(records), flush=True)
    remaining = record_budget - len(records)
    if remaining < 0:
        raise SystemExit('Existing typed world entries (%d) exceed remaining longtail slots (%d).' %
                         (len(records), record_budget))
    new_world = generate_world_entities(remaining, seen_triggers, seen_answers, added_labels, hand_words,
                                        people_items=people_items)
    records.extend(new_world)
    print('new prioritized world entities', len(new_world), 'total typed world entities', len(records), flush=True)
    offset = 0
    while len(records) < record_budget and offset < MAX_OFFSET:
        rows = query_page(offset)
        if not rows:
            break
        print('Wikidata page offset=%d: %d candidates' % (offset, len(rows)), flush=True)
        for row in rows:
            label = clean(row.get('l', '')).strip()
            description = desc({'d': clean(row.get('d', ''))})
            if not label or not description or not ok_label(label) or not START_LABEL.match(label):
                continue
            if len(label) > 60:
                continue
            if (BADL.search(label) or GENERIC.search(label) or NOISE.search(label) or NOISE.search(description)
                    or MEDICAL.search(label) or MEDICAL.search(description)
                    or SENSITIVE.search(label) or SENSITIVE.search(description)):
                continue
            label_key = norm(label)
            if not label_key or label_key in added_labels or label_key in SEEN or known(label_key):
                continue
            if len(label_key.split()) == 1 and label_key in hand_words:
                continue
            answer = sent('%s — %s.' % (cap(label), description.rstrip('.')))
            answer_key = norm(answer)
            trigger = 'что такое ' + label
            trigger_key = norm(trigger)
            if len(answer) < 25 or len(answer) > 600:
                continue
            if answer_key in seen_answers or trigger_key in seen_triggers:
                continue
            records.append((trigger, answer, ''))
            seen_triggers[trigger_key] = 'w_longtail:%d' % len(records)
            seen_answers.add(answer_key)
            added_labels.add(label_key)
            if len(records) >= record_budget:
                break
        offset += len(rows)
        if len(rows) < PAGE_SIZE:
            break

    if len(records) != record_budget:
        raise SystemExit('Only %d new records qualified; need %d generated records plus %d pinned records to reach %d. Existing tail files left untouched.' %
                         (len(records), record_budget, len(pinned_records), TARGET_COUNT))

    records.extend(pinned_records)
    write_sources(records, old_files, replacements=replacements)
    print('records', TARGET_COUNT, 'added', len(records), 'longtail shards',
          (len(records) + SHARD_RECORDS - 1) // SHARD_RECORDS)


if __name__ == '__main__':
    main()
