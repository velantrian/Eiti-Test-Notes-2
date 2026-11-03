#!/usr/bin/env python3
"""Build the EITI KB library from kb/src/*.txt.

Line format:  trigger1; trigger2 || RU answer [|| EN answer] [|| @key: text | key: text ...]
First line:   # Title RU | Title EN
v14.16.2: an optional segment starting with "@" holds grounded detail fields on curated KB entries, including kn_* concept cards:
  short detail ex why use how when origin count who verify  → stored in the pack as "f": {key: text}.
v14.16.2: "rd" embeds up to three same-domain related source records in each pack entry so offline detail
  answers never need to fetch a neighbour pack; these links are comparison context, not claims of causation.
Files whose second line starts with '# @generated' (w_*.txt, from kb/gen/gen_kb.py) may repeat a trigger
already used by a hand-written entry: the hand-written one wins and the repeat is dropped silently.
In hand-written files any duplicate is a warning (--strict → exit 1).

Output (v2, sharded — nothing of it loads at app start; kn_* shards are listed in "lazy" and load only on the
first concept question — EitiKBHost.concept):
  kb/index.json             manifest: domains, counts, shard + pack file names (small)
  kb/idx/<domain>.json      search shard: {"d": domain, "e": [[hash, triggers, keys, part], ...]}
  kb/packs/kb_<domain>[_<part>].json   full answers, ≤ PART entries per file
"""
import glob, gzip, hashlib, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from related import related as related_of
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'src')
PART = 400
# v14.16.18: EN answers + richer facts enlarge entries; keep soft cap high enough that
# adaptive sharding does not explode pack-file counts (manifest must stay ≤10 KiB gzip).
PACK_GZ_SOFT = 52000
FIELDS = ('short', 'detail', 'ex', 'why', 'use', 'how', 'when', 'origin', 'count', 'who', 'verify')

def parse_fields(seg):
    """'@ex: … | why: …' → ({'ex': '…', 'why': '…'}, [errors])"""
    out, errs = {}, []
    for chunk in seg.lstrip('@').split(' | '):
        chunk = chunk.strip()
        if not chunk: continue
        k, sep, v = chunk.partition(':')
        k, v = k.strip(), v.strip()
        if not sep or k not in FIELDS: errs.append('unknown field %r' % k); continue
        if not v: errs.append('empty field %r' % k); continue
        if k in out: errs.append('repeated field %r' % k); continue
        out[k] = v
    return out, errs


_FACT_RE = re.compile(
    r'(?:^|(?<=[.!?] ))([A-ZА-ЯЁÄÖÜ][^.:!?]{1,40}): ([^.!?]{1,160})(?=\.(?:\s|$))'
)

def _answer_facts(answer):
    """«Метка: значение.» → [(label, value), ...] — same shape as offline parseFacts."""
    facts, first = [], -1
    for m in _FACT_RE.finditer(answer or ''):
        if first < 0: first = m.start()
        facts.append((m.group(1).strip(), m.group(2).strip()))
    lead = (answer or '').strip() if first < 0 else (answer or '')[:first].strip()
    return lead, facts


def generated_fields(filename, title, trigger, answer, header):
    """Grounded short/detail/why from the saved answer — no invented QIDs or extra facts."""
    clean_trigger = re.sub(r'\s+', ' ', trigger).strip()
    clean_answer = re.sub(r'\s+', ' ', answer).strip()
    clean_title = re.sub(r'\s+', ' ', title).strip()
    lead, facts = _answer_facts(clean_answer)
    if 'Wikidata' in header and 'CC0' in header:
        origin = 'Wikidata CC0; generated source %s; individual QID is not recorded in this legacy row.' % filename
    else:
        origin = 'Generated source %s; provenance header: %s; individual item ID is not recorded.' % (
            filename, header.lstrip('# ').strip())
    # short: lead + up to 3 fact labels (what the card actually contains).
    # Не пишем «detail» на каждую из 150k записей — раздувает packs/index.gz; kbDetailCard
    # собирает подробности из ответа. detail добавляет только enrich_geo_fields для гео.
    if lead:
        short = lead if len(lead) <= 220 else lead[:217].rstrip() + '…'
        if facts:
            bits = '; '.join('%s — %s' % (k, v) for k, v in facts[:3])
            if bits and bits not in short:
                cand = (short.rstrip('.') + '. ' + bits + '.').strip()
                if len(cand) <= 360: short = cand
    else:
        short = 'Карточка «%s» из раздела «%s».' % (clean_trigger, clean_title)
    why = ('Карточка «%s» собрана из сохранённого ответа в разделе «%s»%s. '
           'Это содержание записи, а не отдельный вывод о полноте темы.') % (
               clean_trigger, clean_title,
               (('; поля: ' + ', '.join(k for k, _ in facts[:6])) if facts else ''))
    return {
        'short': short[:360],
        'why': why[:360],
        'origin': origin,
        'verify': 'Сверить название и факты «%s» с соответствующей записью Wikidata и первоисточниками; исходная строка %s не содержит QID.' %
                  (clean_answer[:200], filename),
    }


# Ожидаемые поля — только для пометки «чего нет в записи» (без выдумывания значений).
# (ru_label, en_label) — en для двуязычного how, когда у записи есть en-ответ.
GEO_EXPECTED = {
    'countries': ('Столица', 'Часть света', 'Официальный язык', 'Валюта', 'Код ISO', 'Площадь', 'Соседние страны'),
    'cities': ('Страна', 'Административно', 'Основан'),
    'admin_regions': ('Страна', 'Административный центр'),
    'states': ('Столица', 'Официальный язык', 'Основано'),
}
DOMAIN_EXPECTED = {
    'countries': [('Столица', 'Capital'), ('Часть света', 'Continent'), ('Официальный язык', 'Official language'),
                  ('Валюта', 'Currency'), ('Код ISO', 'ISO code'), ('Площадь', 'Area'), ('Соседние страны', 'Neighboring countries')],
    'cities': [('Страна', 'Country'), ('Административно', 'Admin area'), ('Основан', 'Founded')],
    'admin_regions': [('Страна', 'Country'), ('Административный центр', 'Admin centre')],
    'states': [('Столица', 'Capital'), ('Официальный язык', 'Official language'), ('Основано', 'Founded')],
    'films': [('Режиссёр', 'Director'), ('Год выхода', 'Release year'), ('Жанр', 'Genre'), ('Страна', 'Country')],
    'books': [('Автор', 'Author'), ('Опубликовано', 'Published'), ('Жанр', 'Genre'), ('Язык', 'Language')],
    'elements': [('Символ', 'Symbol'), ('атомный номер', 'atomic number')],
    'rivers': [('Протекает по странам', 'Flows through'), ('Впадает в', 'Mouth'), ('Длина', 'Length')],
    'mountains': [('Высота', 'Elevation'), ('Страна', 'Country')],
    'lakes': [('Страна', 'Country'), ('Площадь', 'Area')],
    'islands': [('Государство', 'Country')],
    'languages': [('Семья/группа', 'Family/group'), ('Страны', 'Countries')],
    'people': [('Гражданство', 'Citizenship'), ('Род занятий', 'Occupation')],
    'companies': [('Страна', 'Country'), ('Основана', 'Founded')],
    'airports': [('Код IATA', 'IATA code'), ('Страна', 'Country'), ('Обслуживает', 'Serves')],
    'species': [('Входит в таксон', 'Parent taxon')],
    'dishes': [('Происхождение', 'Origin')],
    'games': [('Год выхода', 'Release year'), ('Разработчик', 'Developer')],
    'proglang': [('Появился', 'Introduced'), ('Автор', 'Designer')],
    'events': [('Год', 'Year'), ('Часть', 'Part of')],
    'wars': [('Годы', 'Years'), ('Участники', 'Participants')],
}

# Домены с более широким контекстом «Рассуждение» (до 5 соседних снимков).
RD_RICH = frozenset({
    'countries', 'cities', 'admin_regions', 'states',
    'films', 'books', 'people', 'elements', 'rivers', 'languages',
    'companies', 'airports', 'species', 'dinosaurs', 'mountains', 'lakes',
})


def _miss_how(miss_pairs, has_en):
    ru = ', '.join(r for r, _ in miss_pairs)
    en = ', '.join(e for _, e in miss_pairs)
    if has_en:
        return ('Not in this record / В этой записи нет: %s / %s. Do not invent missing fields.'
                % (en, ru))[:360]
    return ('В этой записи нет сохранённых полей: %s. Не заполняйте их из догадок.' % ru)[:360]


def _fact_keys(answer):
    _, facts = _answer_facts(answer or '')
    return {k.lower().replace('ё', 'е') for k, _ in facts}, (answer or '').lower().replace('ё', 'е')


def _mark_missing(r, expected_pairs):
    if not expected_pairs: return
    f = r.setdefault('f', {})
    have, a_low = _fact_keys(r.get('a') or '')
    # EN answer labels also count as present
    have_en, a_en = _fact_keys(r.get('en') or '')
    miss = []
    for ru, en in expected_pairs:
        rk = ru.lower().replace('ё', 'е')
        ek = en.lower()
        if rk in have or ek in have_en: continue
        # lead-style «Столица — X.» / «Symbol — Au»
        if rk in a_low or ('%s —' % rk) in a_low or ('%s:' % rk) in a_low: continue
        if ek in a_en or ('%s —' % ek) in a_en or ('%s:' % ek) in a_en: continue
        if ru == 'атомный номер' and 'атомный номер' in a_low: continue
        if ru == 'Символ' and 'символ —' in a_low: continue
        if ru == 'Высота' and 'высота' in a_low: continue
        if ru == 'Годы' and 'годы:' in a_low: continue
        miss.append((ru, en))
    if miss:
        f['how'] = _miss_how(miss, bool(r.get('en')))


def enrich_geo_fields(domains_recs):
    """Cross-link + missing-field marks for geo and other enriched domains.

    domains_recs: {domain: [(eid, hash, rec), ...]} — mutates rec['f'] in place. Never invents facts:
    only lists titles already present in other domains that share an explicit «Страна: X» / lead name.
    """
    by_country = {'cities': {}, 'admin_regions': {}}
    country_names = set()
    for _, _, r in domains_recs.get('countries') or []:
        name = (r.get('q') or [''])[0]
        if name: country_names.add(name)
    for dom in ('cities', 'admin_regions'):
        for _, _, r in domains_recs.get(dom) or []:
            lead, facts = _answer_facts(r.get('a') or '')
            country = ''
            for k, v in facts:
                if k.lower().replace('ё', 'е') == 'страна':
                    country = v.split(',')[0].strip(); break
            if not country: continue
            by_country[dom].setdefault(country, []).append((r.get('q') or ['?'])[0])
    for _, _, r in domains_recs.get('countries') or []:
        name = (r.get('q') or [''])[0]
        if not name: continue
        f = r.setdefault('f', {})
        cities = by_country['cities'].get(name) or []
        regs = by_country['admin_regions'].get(name) or []
        bits = []
        if cities:
            bits.append('В этой офлайн-базе города этой страны (выборка): ' + ', '.join(cities[:12])
                        + ('…' if len(cities) > 12 else '') + ' (всего %d).' % len(cities))
        if regs:
            bits.append('Регионы/области в базе: ' + ', '.join(regs[:10])
                        + ('…' if len(regs) > 10 else '') + ' (всего %d).' % len(regs))
        if bits:
            extra = ' '.join(bits)
            # компактный detail только для гео (список городов/регионов) — не дублируем lead
            base = (f.get('detail') or '').strip()
            f['detail'] = ((base + ' ' if base else '') + extra).strip()[:900]
            f['count'] = ('В офлайн-базе: городов %d, регионов/областей %d по явной метке «Страна: %s».'
                          % (len(cities), len(regs), name))[:360]
        _mark_missing(r, DOMAIN_EXPECTED.get('countries') or [])
    for dom in ('cities', 'admin_regions'):
        for _, _, r in domains_recs.get(dom) or []:
            f = r.setdefault('f', {})
            _, facts = _answer_facts(r.get('a') or '')
            _mark_missing(r, DOMAIN_EXPECTED.get(dom) or [])
            # city → hint country card exists
            country = ''
            for k, v in facts:
                if k.lower().replace('ё', 'е') == 'страна':
                    country = v.split(',')[0].strip(); break
            if country and country in country_names:
                tip = 'Связанная карточка страны в базе: «%s» (раздел «Страны мира»).' % country
                f['detail'] = ((f.get('detail') or '').rstrip() + ' ' + tip).strip()[:500]
    # v14.16.18: missing-field marks for other enriched domains (no invented values)
    for dom, expected in DOMAIN_EXPECTED.items():
        if dom in ('countries', 'cities', 'admin_regions'): continue
        for _, _, r in domains_recs.get(dom) or []:
            _mark_missing(r, expected)

def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-zа-я0-9+#²³ ]+', ' ', s.lower().replace('ё', 'е'))).strip()

def keys(ans, n):
    a = re.sub(r'\s+', ' ', ans)
    return a[:n].rsplit(' ', 1)[0] if len(a) > n else a

def compact_row(hh, r, k, px):
    """[hash, triggers, keys]: trigger «<prefix><first>» → «~N» (px[N] + first); keys keep only words not in triggers."""
    first, out = r['q'][0], [r['q'][0]]
    for t in r['q'][1:]:
        if len(t) > len(first) and t.endswith(first):
            pre = t[:-len(first)]
            if pre not in px: px[pre] = len(px)
            out.append('~%d' % px[pre])
        else: out.append(t)
    tw = set(norm(' '.join(r['q'])).split())
    return [hh, '|'.join(out), ' '.join(w for w in norm(k).split() if w not in tw)]

def gz(b): return len(gzip.compress(b, 9))

def dump(path, obj):
    b = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'wb').write(b); return b

def _write_domain(dom, title, gen, recs, domains, errors):
    """Attach related snapshots, shard+pack the domain, update domains[dom]."""
    # Population/region list cards are query aids; comparing entire lists as
    # "related records" is noisy and needlessly inflates their offline packs.
    rel = {} if dom == 'peoples_regions' else related_of(recs)
    rec_by_hash = {hh: r for _, hh, r in recs}
    # Rich domains keep more neighbours for offline «Рассуждение» (still same-domain only).
    rd_n = 5 if dom in RD_RICH else 3
    for _, hh, r in recs:
        if hh in rel:
            r['r'] = rel[hh]
            snapshots = []
            for rh in rel[hh][:rd_n]:
                other = rec_by_hash.get(rh)
                if not other: continue
                snap = {'q': other['q'][:1], 'a': other['a']}
                if other.get('en'): snap['en'] = other['en']
                snapshots.append(snap)
            if snapshots: r['rd'] = snapshots
    part = PART
    while True:   # adaptive part size: packs carry «r» (related) and must stay under PACK_GZ_SOFT
        nparts = (len(recs) + part - 1) // part
        chunks = [recs[pi * part:(pi + 1) * part] for pi in range(nparts)]
        payloads = [json.dumps({'v': 2, 'domain': dom, 'part': pi, 'entries': {e: r for e, _, r in c}}, ensure_ascii=False, separators=(',', ':')) for pi, c in enumerate(chunks)]
        max_gz = max(len(gzip.compress(p.encode(), 9)) for p in payloads)
        if max_gz <= PACK_GZ_SOFT: break
        if part <= 1:
            errors.append('%s: pack gzip %d exceeds soft limit %d' % (dom, max_gz, PACK_GZ_SOFT))
            break
        part = max(1, part - 50)
    pfiles, pgz, pbytes, shard, px = [], [], 0, [], {}
    for pi in range(nparts):
        chunk = chunks[pi]
        f = 'packs/kb_%s.json' % dom if nparts == 1 else 'packs/kb_%s_%d.json' % (dom, pi)
        b = dump(os.path.join(HERE, f), {'v': 2, 'domain': dom, 'part': pi, 'entries': {e: r for e, _, r in chunk}})
        pfiles.append(f); pgz.append(gz(b)); pbytes += len(b)
        kn = 40 if gen else 60 if dom.startswith('kn_') else 110
        for _, hh, r in chunk:
            if gen: shard.append(compact_row(hh, r, keys(r['a'], kn), px))
            else: shard.append([hh, '|'.join(r['q']), keys(r['a'], kn), pi])
    sf = 'idx/%s.json' % dom
    if gen:
        sb = dump(os.path.join(HERE, sf), {'v': 3, 'd': dom, 'g': 1, 'pp': part, 'px': [k for k, _ in sorted(px.items(), key=lambda x: x[1])], 'e': shard})
    else:
        sb = dump(os.path.join(HERE, sf), {'v': 2, 'd': dom, 'e': shard})
    domains[dom] = {'title': title[0].strip(), 'title_en': (title[1].strip() if len(title) > 1 else dom), 'gen': gen,
                    **({'lazy': 1} if dom.startswith('kn_') or dom.startswith('longtail_') else {}),
                    'count': len(recs), 'shard': sf, 'shard_gz': gz(sb), 'shard_bytes': len(sb),
                    'packs': pfiles, 'pack_gz_max': max(pgz), 'pack_bytes': pbytes}


def build():
    for d in ('packs', 'idx'):
        for f in glob.glob(os.path.join(HERE, d, '*.json')): os.remove(f)
    domains, seen_t, seen_a, seen_id, errors, dropped, total = {}, {}, {}, set(), [], 0, 0
    pending = []  # [(dom, title, gen, recs)]
    files = sorted(os.listdir(SRC), key=lambda f: (f.startswith('w_'), f))   # hand-written first
    for fn in files:
        if not fn.endswith('.txt'): continue
        dom = fn[:-4]
        lines = open(os.path.join(SRC, fn), encoding='utf-8').read().splitlines()
        title = lines[0].lstrip('# ').split('|')
        gen = len(lines) > 1 and lines[1].startswith('# @generated')
        source_header = lines[1] if len(lines) > 1 else ''
        if gen and dom.startswith('w_'): dom = dom[2:]
        recs = []
        for ln, line in enumerate(lines[1:], 2):
            if not line.strip() or line.startswith('#'): continue
            parts = [p.strip() for p in line.split('||')]
            fields = None
            if len(parts) > 2 and parts[-1].startswith('@'):
                fields, ferr = parse_fields(parts.pop())
                errors.extend('%s:%d %s' % (fn, ln, e) for e in ferr)
            if len(parts) < 2 or not parts[1]:
                errors.append('%s:%d bad line' % (fn, ln)); continue
            uniq = []
            for t in [t.strip() for t in parts[0].split(';') if t.strip()]:
                nt = norm(t)
                if not nt: continue
                if nt in seen_t:
                    if not gen: errors.append('%s:%d duplicate trigger %r (also %s)' % (fn, ln, t, seen_t[nt]))
                    continue
                seen_t[nt] = '%s:%d' % (fn, ln); uniq.append(t)
            na = norm(parts[1])
            if na in seen_a:
                if not gen: errors.append('%s:%d duplicate answer (also %s)' % (fn, ln, seen_a[na]))
                dropped += 1; continue
            if not uniq:
                dropped += 1; continue
            seen_a[na] = '%s:%d' % (fn, ln)
            h = hashlib.sha1(norm(uniq[0]).encode()).hexdigest()
            n = 6
            while 'kbl_%s_%s' % (dom, h[:n]) in seen_id: n += 2
            eid = 'kbl_%s_%s' % (dom, h[:n]); seen_id.add(eid)
            rec = {'q': uniq, 'a': parts[1]}
            if len(parts) > 2 and parts[2]: rec['en'] = parts[2]
            if gen:
                fields = fields or {}
                for key, value in generated_fields(fn, title[0], uniq[0], parts[1], source_header).items():
                    fields.setdefault(key, value)
            if fields: rec['f'] = fields
            recs.append((eid, h[:n], rec))
        if not recs: continue
        pending.append((dom, title, gen, recs))
    # v14.16.17: страны ↔ города ↔ области — контекст в f для офлайн-рассуждения (без выдуманных фактов)
    enrich_geo_fields({dom: recs for dom, _, _, recs in pending})
    for dom, title, gen, recs in pending:
        _write_domain(dom, title, gen, recs, domains, errors)
        total += len(recs)
    # hand-written shards load first; v14.14.0: карточки понятий (kn_*) — «ленивые»: не в order, грузятся при первом вопросе о понятии
    order = sorted((d for d in domains if not domains[d].get('lazy')), key=lambda d: (domains[d]['gen'], d))
    lazy = sorted(d for d in domains if domains[d].get('lazy'))
    idx = {'v': 2, 'format': 'eiti-kb-lib', 'count': total, 'order': order, 'lazy': lazy, 'domains': domains}
    dump(os.path.join(HERE, 'index.json'), idx)
    return idx, errors, dropped

def load_all(here=HERE):
    """Flat list of index entries (as the JS engine sees them) — for tests/tools."""
    idx = json.load(open(os.path.join(here, 'index.json'), encoding='utf-8'))
    out = []
    for d in idx['order'] + idx.get('lazy', []):
        sh = json.load(open(os.path.join(here, idx['domains'][d]['shard']), encoding='utf-8'))
        out += [{'i': 'kbl_%s_%s' % (d, e[0]), 'd': d, 't': e[1], 'k': e[2], 'p': e[3]} for e in sh['e']]
    return idx, out

if __name__ == '__main__':
    idx, errors, dropped = build()
    for e in errors: print('WARN', e)
    man = open(os.path.join(HERE, 'index.json'), 'rb').read()
    sg = sum(m['shard_gz'] for m in idx['domains'].values()); sb = sum(m['shard_bytes'] for m in idx['domains'].values())
    print('entries', idx['count'], 'domains', len(idx['domains']), 'dropped-generated-dups', dropped)
    print('manifest', len(man), 'gz', gz(man), '| shards raw', sb, 'gz', sg)
    for d in idx['order'] + idx.get('lazy', []):
        m = idx['domains'][d]; print('  %-12s %5d shard_gz %6d packs %d max_pack_gz %6d' % (d, m['count'], m['shard_gz'], len(m['packs']), m['pack_gz_max']))
    # v14.14.0: хеши пакетов для «🔄 Обновить базу офлайн-ответов» (offline_manifest.json)
    import subprocess
    subprocess.run([sys.executable, os.path.join(HERE, '..', 'scripts', 'build_offline_manifest.py')], check=False)
    sys.exit(1 if errors and '--strict' in sys.argv else 0)
