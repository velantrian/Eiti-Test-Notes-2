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

# Keep this previously shipped entry stable across regenerated Wikidata windows.
# Its slot is reserved after the prioritized world-entity and generic tail rows.
PINNED_RECORDS = (
    ('что такое Tha Last Meal', 'Tha Last Meal — альбом Snoop Dogg.', ''),
)

sys.path.insert(0, HERE)
from gen_kb import cap, clean, desc, ok_label, sent  # noqa: E402
from gen_more import BADL, GENERIC, HAND, NOISE, SEEN, known, load_seen, norm  # noqa: E402
from wd import sparql  # noqa: E402
from world_entities import generate_world_entities  # noqa: E402

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


def source_state(exclude_longtail=False):
    """Count records exactly as build_kb.py does; optionally omit old tail files."""
    seen_t, seen_a = {}, set()
    total = 0
    files = sorted(os.listdir(SRC), key=lambda name: (name.startswith('w_'), name))
    for name in files:
        if not name.endswith('.txt') or (exclude_longtail and is_longtail_file(name)):
            continue
        path = os.path.join(SRC, name)
        for line_no, line in enumerate(open(path, encoding='utf-8'), 1):
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


def write_sources(records, old_files):
    """Replace prior long-tail output atomically enough to restore it on failure."""
    backups = {name: open(os.path.join(SRC, name), 'rb').read() for name in old_files}
    new_names = []
    try:
        for name in old_files:
            os.remove(os.path.join(SRC, name))
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
            with open(os.path.join(SRC, name), 'wb') as out:
                out.write(content)
        raise


def main():
    os.makedirs(SRC, exist_ok=True)
    current, seen_triggers, seen_answers = source_state(exclude_longtail=True)
    needed = TARGET_COUNT - current
    if needed <= 0:
        raise SystemExit('Base KB already has %d records; target is %d.' % (current, TARGET_COUNT))
    pinned_records = list(PINNED_RECORDS)
    record_budget = needed - len(pinned_records)
    if record_budget < 0:
        raise SystemExit('Pinned longtail records exceed the available KB capacity.')

    old_files = sorted(name for name in os.listdir(SRC) if is_longtail_file(name))
    load_seen(skip=set(old_files))
    hand_words = {word for phrase in HAND for word in phrase.strip().split()}
    added_labels = set()
    for trigger, answer, _fields in pinned_records:
        label = trigger[len('что такое '):] if trigger.startswith('что такое ') else ''
        trigger_key, answer_key = norm(trigger), norm(answer)
        if not label or trigger_key in seen_triggers or answer_key in seen_answers:
            raise SystemExit('Pinned longtail record collides with the base KB: %s' % trigger)
        seen_triggers[trigger_key] = 'pinned longtail record'
        seen_answers.add(answer_key)
        added_labels.add(norm(label))

    records = []
    records.extend(generate_world_entities(record_budget, seen_triggers, seen_answers, added_labels, hand_words))
    print('prioritized world entities', len(records), flush=True)
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
    write_sources(records, old_files)
    print('records', TARGET_COUNT, 'added', len(records), 'longtail shards',
          (len(records) + SHARD_RECORDS - 1) // SHARD_RECORDS)


if __name__ == '__main__':
    main()
