#!/usr/bin/env python3
"""Generate kb/src/w_*.txt from Wikidata (CC0) — stable, structured facts only.
Each item: Russian label + Russian description + a few unambiguous properties.
Multi-valued years are skipped, numbers are only used where stable (atomic number, peak elevation).
Run: python3 kb/gen/gen_kb.py   (cached in kb/gen/cache/, not committed)
"""
import os, re, sys
from wd import sparql
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')

def q_items(cls, minsl, props, extra='', limit=6000, tag=None, cls_path='wdt:P31', en=False, offset=0):
    sel, body = [], []
    for name, p, kind in props:
        if kind == 'label':
            if en:
                # RU + EN labels of linked items; COALESCE prefers RU for `name`, EN kept in nameEn.
                body.append(('OPTIONAL { ?x %s ?%s_ . '
                             'OPTIONAL { ?%s_ rdfs:label ?%sRu FILTER(LANG(?%sRu)="ru") } '
                             'OPTIONAL { ?%s_ rdfs:label ?%s_en FILTER(LANG(?%s_en)="en") } '
                             'BIND(COALESCE(?%sRu, ?%s_en) AS ?%s) }') %
                            (p, name, name, name, name, name, name, name, name, name, name))
                sel.append('(GROUP_CONCAT(DISTINCT STR(?%s_en); SEPARATOR="|") AS ?%sEns)' % (name, name))
            else:
                body.append('OPTIONAL { ?x %s ?%s_ . ?%s_ rdfs:label ?%s FILTER(LANG(?%s)="ru") }' % (p, name, name, name, name))
        elif kind == 'country':
            body.append(('OPTIONAL { ?x %s ?%s_ . ?%s_ wdt:P31/wdt:P279* wd:Q6256 . '
                         'FILTER NOT EXISTS { ?%s_ wdt:P576 ?country_end } '
                         'OPTIONAL { ?%s_ rdfs:label ?%s_ru FILTER(LANG(?%s_ru)="ru") } '
                         'OPTIONAL { ?%s_ rdfs:label ?%s_en FILTER(LANG(?%s_en)="en") } '
                         'BIND(COALESCE(?%s_ru, ?%s_en) AS ?%s) }') %
                        (p, name, name, name, name, name, name, name, name, name, name, name, name))
            if en:
                sel.append('(GROUP_CONCAT(DISTINCT STR(?%s_en); SEPARATOR="|") AS ?%sEns)' % (name, name))
        elif kind == 'year':
            body.append('OPTIONAL { ?x %s ?%s_ . BIND(YEAR(?%s_) AS ?%s) }' % (p, name, name, name))
        else:
            body.append('OPTIONAL { ?x %s ?%s }' % (p, name))
        sel.append('(GROUP_CONCAT(DISTINCT STR(?%s); SEPARATOR="|") AS ?%ss)' % (name, name))
    if ' ' in cls: cls_stmt = 'VALUES ?cls { %s } ?x %s ?cls .' % (cls, cls_path)
    else: cls_stmt = '?x %s %s .' % (cls_path, cls)
    if en:
        lang_cols = '?le ?de'
        label_stmt = ('OPTIONAL { ?x rdfs:label ?lr FILTER(LANG(?lr)="ru") } '
                      'OPTIONAL { ?x rdfs:label ?le FILTER(LANG(?le)="en") } '
                      'BIND(COALESCE(?lr, ?le) AS ?l) FILTER(BOUND(?l)) ')
        desc_stmt = ('OPTIONAL { ?x schema:description ?d FILTER(LANG(?d)="ru") } '
                     'OPTIONAL { ?x schema:description ?de FILTER(LANG(?de)="en") } ')
    else:
        lang_cols = ''
        label_stmt = '?x rdfs:label ?l FILTER(LANG(?l)="ru") '
        desc_stmt = 'OPTIONAL { ?x schema:description ?d FILTER(LANG(?d)="ru") } '
    # ?le/?de must be in SELECT (not only GROUP BY) or EN label/description never reach the row dict.
    q = ('SELECT ?x ?l ?d ?sl %s %s WHERE { %s ?x wikibase:sitelinks ?sl . FILTER(?sl >= %d) '
         + '%s%s%s %s } GROUP BY ?x ?l ?d ?sl %s ORDER BY DESC(?sl) LIMIT %d') % (
             ' '.join(sel), lang_cols, cls_stmt, minsl, label_stmt, desc_stmt, extra, ' '.join(body), lang_cols, limit)
    if offset:
        q += ' OFFSET %d' % int(offset)
    rows = sparql(q, tag or ('it_' + __import__('hashlib').sha1(q.encode()).hexdigest()[:12]))
    out, seen = [], set()
    for r in rows:
        qid = r['x'].rsplit('/', 1)[1]
        if qid in seen: continue
        seen.add(qid)
        it = {'qid': qid, 'l': clean(r['l']), 'd': clean(r.get('d', '')), 'sl': int(r['sl']),
              'en': clean(r.get('le', '')), 'den': clean(r.get('de', ''))}
        for name, _, kind in props:
            v = [clean(x) for x in (r.get(name + 's') or '').split('|') if x.strip()]
            it[name] = [x for x in v if x and not re.match(r'^Q\d+$', x) and not x.startswith('http')]
            if en and kind in ('label', 'country'):
                ve = [clean(x) for x in (r.get(name + 'Ens') or '').split('|') if x.strip()]
                it[name + 'En'] = [x for x in ve if x and not re.match(r'^Q\d+$', x) and not x.startswith('http')]
        out.append(it)
    return out

# Латиница, визуально совпадающая с кириллицей (часто в описаниях Wikidata: «cтолица»).
_LATIN_CYR = str.maketrans({
    'a': 'а', 'A': 'А', 'c': 'с', 'C': 'С', 'e': 'е', 'E': 'Е', 'o': 'о', 'O': 'О',
    'p': 'р', 'P': 'Р', 'x': 'х', 'X': 'Х', 'y': 'у', 'Y': 'У', 'H': 'Н', 'K': 'К',
    'M': 'М', 'T': 'Т', 'B': 'В',
})

def clean(s):
    s = re.sub(r'\s+', ' ', str(s or '')).replace('|', '/').replace(';', ',').strip()
    # чинить смешанные слова: латинская «c» перед кириллицей → «с» и т.п.
    def fix_mixed(m):
        w = m.group(0)
        if re.search(r'[а-яёА-ЯЁ]', w) and re.search(r'[A-Za-z]', w):
            return w.translate(_LATIN_CYR)
        return w
    s = re.sub(r'[A-Za-zА-Яа-яЁё]+', fix_mixed, s)
    return s

def one(v):
    return v[0] if len(v) == 1 else ''

def few(v, n=3):
    """Join up to n values; if more exist, still show the first n (sample, not require exact size)."""
    if not v: return ''
    return ', '.join(v[:n])

def yr(v):
    """single unambiguous year (all values agree)."""
    ys = set(x for x in v if re.match(r'^-?\d{1,4}$', x))
    if len(ys) != 1: return ''
    y = int(ys.pop())
    return ('%d до н. э.' % (-y + 1)) if y <= 0 else str(y)

BAD_LABEL = re.compile(r'^(Q\d+|.*[a-z]{2,}.*\(.*\))$')
def ok_label(l):
    return l and len(l) <= 60 and not BAD_LABEL.match(l) and re.search(r'[A-Za-zА-Яа-яЁё]', l)

def desc(it):
    d = it['d']
    if not d or len(d) < 4 or re.search(r'страница значений|Викимедиа|wikimedia|категория', d, re.I): return ''
    if re.search(r'["!?]|похвал|https?:', d): return ''   # вандализм/мусор в описаниях
    return d

def sent(*parts):
    s = ' '.join(p.strip() for p in parts if p and p.strip())
    return re.sub(r'\s+', ' ', s).strip()

def cap(s): return s[:1].upper() + s[1:] if s else s

class Out:
    def __init__(self, dom, title, title_en):
        self.dom, self.title, self.title_en, self.lines, self.trig = dom, title, title_en, [], set()
    def add(self, triggers, answer):
        tt = []
        for t in triggers:
            t = clean(t).strip(' ,.')
            k = t.lower().replace('ё', 'е')
            if t and k not in self.trig and len(t) <= 80: self.trig.add(k); tt.append(t)
        if isinstance(answer, tuple):
            ru, en = (answer[0] or ''), (answer[1] if len(answer) > 1 else '') or ''
            if not tt or len(ru) < 20: return
            line = '%s || %s' % ('; '.join(tt), ru[:600])
            if en and len(en) >= 20: line += ' || %s' % en[:600]
            self.lines.append(line)
            return
        if not tt or len(answer) < 20: return
        self.lines.append('%s || %s' % ('; '.join(tt), answer[:600]))
    def write(self):
        p = os.path.join(SRC, 'w_%s.txt' % self.dom)
        with open(p, 'w', encoding='utf-8') as f:
            f.write('# %s | %s\n# @generated from Wikidata (CC0) by kb/gen/gen_kb.py — do not edit by hand\n' % (self.title, self.title_en))
            f.write('\n'.join(self.lines) + '\n')
        print(self.dom, len(self.lines))

def lab_en(prefix, v, n=3):
    s = few(v, n)
    return (prefix + s + '.') if s else ''

def en_vals(it, name):
    """Prefer English linked labels; fall back to RU so EN answers still keep grounded facts."""
    return it.get(name + 'En') or it.get(name) or []

def maybe_pair(ru, en):
    return (ru, en) if en and len(en) >= 20 else ru

def yr_en(v):
    """English year string from the same unambiguous year helper."""
    ys = set(x for x in v if re.match(r'^-?\d{1,4}$', x))
    if len(ys) != 1: return ''
    y = int(ys.pop())
    return ('%d BC' % (-y + 1)) if y <= 0 else str(y)

def gen_people():
    o = Out('people', 'Личности', 'People')
    # v14.16.18: + род занятий (P106); EN label/desc + citizenship/occupation EN labels
    its = q_items('wd:Q5', 62, [('b', 'wdt:P569', 'year'), ('e', 'wdt:P570', 'year'),
                                ('c', 'wdt:P27', 'label'), ('occ', 'wdt:P106', 'label')], limit=6000, en=True)
    last = {}
    for it in its:
        w = it['l'].split()
        if len(w) > 1: last[w[-1].lower()] = last.get(w[-1].lower(), 0) + 1
    for rank, it in enumerate(its):
        l, d = it['l'], desc(it)
        if not ok_label(l) or not d: continue
        w = l.split()
        # самые известные (верхние 1500 по числу статей) с уникальной фамилией: «кто такой Ленин» → Владимир Ильич Ленин
        it['alias'] = w[-1] if rank < 1500 and len(w) > 1 and len(w[-1]) >= 4 and last.get(w[-1].lower()) == 1 and w[-1].lower().replace('ё', 'е') not in other_labels() and re.match(r'^[А-ЯЁ][а-яё-]+$', w[-1]) else ''
        b, e = yr(it['b']), yr(it['e'])
        if not b or (b.isdigit() and int(b) >= 2005): continue   # без даты рождения и без детей/подростков
        if not b.isdigit() or int(b) < 1500:   # древние даты приблизительны — не указываем
            b = e = ''
        life = ('(%s–%s)' % (b, e) if e else '(род. %s)' % b) if b else ''
        be, ee = yr_en(it['b']), yr_en(it['e'])
        if not b: be = ee = ''
        life_en = ('(%s–%s)' % (be, ee) if ee else '(b. %s)' % be) if be else ''
        ru = sent('%s — %s.' % (sent(l, life), d),
                  ('Гражданство: %s.' % few(it['c'], 2)) if b and few(it['c'], 2) else '',
                  lab('Род занятий: ', it.get('occ') or [], 3))
        le, de = it.get('en') or '', it.get('den') or ''
        en = ''
        if le and de and not re.search(r'wikimedia|disambiguation', de, re.I):
            en = sent('%s — %s.' % (sent(le, life_en), de),
                      lab_en('Citizenship: ', en_vals(it, 'c'), 2) if b else '',
                      lab_en('Occupation: ', en_vals(it, 'occ'), 3))
        o.add(([l, 'кто такой ' + l] if ' ' in l else [l])
              + (['кто такой ' + it['alias']] if it.get('alias') else [])
              + ([le, 'who is ' + le] if le and le.lower() != l.lower() and ' ' in le else []),
              maybe_pair(ru, en))
    o.write()

def gen_simple(dom, title, title_en, cls, minsl, props, fmt, trig=None, limit=6000, extra='', cls_path='wdt:P31', need_desc=True, en=False):
    o = Out(dom, title, title_en)
    for it in q_items(cls, minsl, props, extra=extra, limit=limit, cls_path=cls_path, en=en):
        l, d = it['l'], desc(it)
        if dom in ('events', 'wars') and (re.search(r'20[2-9]\d', l + d) or any(x.isdigit() and int(x) >= 2020 for k in ('y', 's', 'e') for x in it.get(k, []))):
            continue   # недавние/текущие события — нестабильные факты, пропускаем
        # Recent films are unstable and bare titles collide with people («Наполеон» 2023).
        if dom == 'films' and any(x.isdigit() and int(x) >= 2021 for x in it.get('y', [])):
            continue
        if not ok_label(l) or (need_desc and not d): continue
        a = fmt(it, l, d)
        if not a or (isinstance(a, tuple) and not a[0]): continue
        tt = trig(it, l) if trig else [l]
        if dom in WORKS and plain_title(l) and len(tt) > 1: tt = tt[1:]   # «Собака», «Доброе утро» — только «картина/фильм/кто написал …»
        # Bare EN titles for works steal person/place hits («napoleon» → film). Keep prefixed EN only.
        if dom in WORKS and it.get('en'):
            le = it['en']
            pref = {'films': 'film ', 'books': 'who wrote ', 'paintings': 'painting ',
                    'music': 'piece ', 'games': 'game ', 'stage': 'stage '}.get(dom, '')
            tt = [t for t in tt if t.lower() != le.lower()]
            if pref and le and (pref + le) not in tt: tt.append(pref + le)
        o.add(tt, a)
    o.write()

WORKS = {'books', 'films', 'paintings', 'music', 'games', 'stage'}
CHAT = set("""привет как дела|как дела|доброе утро|добрый день|добрый вечер|спокойной ночи|спасибо|пока|до свидания|я тебя люблю|люблю тебя|
я устал|мне грустно|мне скучно|мне одиноко|что делать|не знаю|давай поговорим|расскажи сказку|что нового|как тебя зовут|ты кто|кто ты|
скажи что-нибудь|всё хорошо|все хорошо|всё будет хорошо|все будет хорошо|я здесь|где ты|ты где|помоги мне|помогите|прости|извини|
с днём рождения|с днем рождения|с новым годом|ничего|почему|зачем|что это|кто я|я не знаю|давай|поехали|ну и что|и что|вот так|
мама|папа|собака|кошка|кот|лошадь|птица|рыба|человек|мир|война|мать|отец|дети|идиот|дурак|подарок|сюрприз|тишина|одиночество|дом|семья|друг|друзья|любовь|жизнь|счастье|сон|если|когда|утро|вечер|ночь|день|время|музыка|игра|работа|школа|дождь|снег|погода""".replace('\n', '').split('|'))
_COMMON = None
def common_words():
    """нарицательные слова, уже известные библиотеке (виды, блюда, понятия, ручные триггеры) — в нижнем регистре."""
    global _COMMON
    if _COMMON is None:
        _COMMON = set()
        for f in os.listdir(SRC):
            if not f.endswith('.txt') or f in ('w_books.txt', 'w_films.txt', 'w_paintings.txt', 'w_music.txt', 'w_games.txt', 'w_stage.txt'): continue
            for line in open(os.path.join(SRC, f), encoding='utf-8'):
                if '||' in line and not line.startswith('#'):
                    for t in line.split('||')[0].split(';'):
                        t = t.strip()
                        if t and t == t.lower(): _COMMON.add(t.replace('ё', 'е'))
    return _COMMON

_LABELS = None
def other_labels():
    """все триггеры других разделов (в нижнем регистре) — фамилия-псевдоним не должна их перекрывать («Марс», «Сатурн»)."""
    global _LABELS
    if _LABELS is None:
        _LABELS = set()
        for f in os.listdir(SRC):
            if not f.endswith('.txt') or f == 'w_people.txt': continue
            for line in open(os.path.join(SRC, f), encoding='utf-8'):
                if '||' in line and not line.startswith('#'):
                    for t in line.split('||')[0].split(';'):
                        t = t.strip().lower().replace('ё', 'е')
                        _LABELS.add(t)
                        for w in t.split(): _LABELS.add(w)
    return _LABELS

def plain_title(l):
    """название-реплика («Доброе утро») или одно обычное слово («Собака») — легко путается с репликой в чате."""
    n = re.sub(r'[^а-яёa-z0-9 -]+', ' ', l.lower()).split()
    k = ' '.join(n)
    return k in CHAT or k.startswith('язык программирования') or (len(n) == 1 and k.replace('ё', 'е') in common_words())

def lab(prefix, v, n=3):
    s = few(v, n)
    return (prefix + s + '.') if s else ''

def main():
    which = set(sys.argv[1:])
    def want(k): return not which or k in which
    if want('people'): gen_people()
    if want('concepts'): gen_concepts()
    if want('countries'):
        # v14.16.17: + ISO/площадь/соседи; v14.16.18: EN-ответы
        def fmt_country(it, l, d):
            area = area_en = ''
            if one(it.get('area')):
                try:
                    km2 = round(float(one(it['area'])))
                    if 1 <= km2 <= 20000000:
                        area = 'Площадь: около %s км².' % f'{km2:,}'.replace(',', ' ')
                        area_en = 'Area: about %s km².' % f'{km2:,}'
                except (TypeError, ValueError): pass
            iso = one(it.get('iso')).upper() if one(it.get('iso')) else ''
            ru = sent('%s — %s.' % (l, d or 'государство'),
                      lab('Столица — ', it['cap'], 1), lab('Часть света: ', it['cont'], 2),
                      lab('Официальный язык: ', it['lang'], 3), lab('Валюта: ', it['cur'], 2),
                      ('Код ISO: %s.' % iso) if iso else '', area, lab('Соседние страны: ', it.get('nb') or [], 5))
            le, de = it.get('en') or '', it.get('den') or ''
            en = ''
            if le:
                en = sent('%s — %s.' % (le, de or 'sovereign state'),
                          lab_en('Capital: ', en_vals(it, 'cap'), 1), lab_en('Continent: ', en_vals(it, 'cont'), 2),
                          lab_en('Official language: ', en_vals(it, 'lang'), 3), lab_en('Currency: ', en_vals(it, 'cur'), 2),
                          ('ISO code: %s.' % iso) if iso else '', area_en, lab_en('Neighboring countries: ', en_vals(it, 'nb'), 5))
            return maybe_pair(ru, en)
        gen_simple('countries', 'Страны мира', 'Countries', 'wd:Q3624078', 1,
                   [('cap', 'wdt:P36', 'label'), ('cont', 'wdt:P30', 'label'), ('lang', 'wdt:P37', 'label'),
                    ('cur', 'wdt:P38', 'label'), ('iso', 'wdt:P297', 'v'), ('area', 'wdt:P2046', 'v'),
                    ('nb', 'wdt:P47', 'label')],
                   fmt_country,
                   trig=lambda it, l: [l, 'столица ' + l, 'страна ' + l]
                   + (['валюта ' + l] if it['cur'] else [])
                   + (['язык ' + l, 'официальный язык ' + l] if it['lang'] else [])
                   + (['код ' + one(it['iso']).upper(), 'ISO ' + one(it['iso']).upper()] if one(it.get('iso')) else [])
                   + ([it['en'], 'country ' + it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   extra='FILTER NOT EXISTS { ?x wdt:P576 ?end }', need_desc=False, en=True)
    if want('cities'):
        def fmt_city(it, l, d):
            founded = founded_en = ''
            y = yr(it.get('fd') or [])
            if y.isdigit() and 500 <= int(y) <= 2020:
                founded = 'Основан: %s.' % y
                founded_en = 'Founded: %s.' % y
            ru = sent('%s — %s.' % (l, d), lab('Страна: ', it['c'], 1),
                      lab('Административно: ', it.get('adm') or [], 2), founded)
            le, de = it.get('en') or '', it.get('den') or ''
            en = ''
            if le and de:
                en = sent('%s — %s.' % (le, de), lab_en('Country: ', en_vals(it, 'c'), 1),
                          lab_en('Admin area: ', en_vals(it, 'adm'), 2), founded_en)
            return maybe_pair(ru, en)
        gen_simple('cities', 'Города мира', 'Cities', 'wd:Q515', 36,
                   [('c', 'wdt:P17', 'label'), ('adm', 'wdt:P131', 'label'), ('fd', 'wdt:P571', 'year')],
                   fmt_city,
                   trig=lambda it, l: [l, 'город ' + l]
                   + ([it['en'], 'city ' + it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   cls_path='wdt:P31/wdt:P279*', en=True)
    if want('elements'):
        def fmt_el(it, l, d):
            sym, n = one(it['sym']), one(it['n'])
            ru = sent('%s — химический элемент.' % l,
                      ('Символ — %s, атомный номер %s.' % (sym, n)) if sym and n else '',
                      lab('Группа/класс: ', it.get('grp') or [], 2),
                      cap(d) + '.' if d and 'элемент' not in d else '')
            le, de = it.get('en') or l, it.get('den') or ''
            en = sent('%s — chemical element.' % (le or l),
                      ('Symbol — %s, atomic number %s.' % (sym, n)) if sym and n else '',
                      lab_en('Group/class: ', en_vals(it, 'grp'), 2),
                      (cap(de) + '.' if de and 'element' not in de.lower() else ''))
            return maybe_pair(ru, en)
        gen_simple('elements', 'Химические элементы', 'Chemical elements', 'wd:Q11344', 1,
                   [('sym', 'wdt:P246', 'v'), ('n', 'wdt:P1086', 'v'), ('grp', 'wdt:P279', 'label')],
                   fmt_el,
                   trig=lambda it, l: [l, 'элемент ' + l, 'атомный номер ' + l]
                   + (['символ ' + one(it['sym'])] if one(it['sym']) else [])
                   + ([it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   need_desc=False, en=True,
                   extra='?x wdt:P1086 ?an . FILTER(xsd:integer(?an) >= 1 && xsd:integer(?an) <= 118)')
    if want('rivers'):
        def fmt_river(it, l, d):
            length = length_en = ''
            if one(it.get('len')):
                try:
                    km = round(float(one(it['len'])))
                    if 10 <= km <= 10000:
                        length = 'Длина: около %s км.' % f'{km:,}'.replace(',', ' ')
                        length_en = 'Length: about %s km.' % f'{km:,}'
                except (TypeError, ValueError): pass
            ru = sent('%s — %s.' % (l, d), lab('Протекает по странам: ', it['c'], 4),
                      lab('Впадает в: ', it['m'], 1), length)
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('%s — %s.' % (le, de), lab_en('Flows through: ', en_vals(it, 'c'), 4),
                      lab_en('Mouth: ', en_vals(it, 'm'), 1), length_en) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('rivers', 'Реки', 'Rivers', 'wd:Q4022', 22,
                   [('c', 'wdt:P17', 'label'), ('m', 'wdt:P403', 'label'), ('len', 'wdt:P2043', 'v')],
                   fmt_river, trig=lambda it, l: ['река ' + l, l]
                   + ([it['en'], 'river ' + it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('mountains'):
        def fmt_mt(it, l, d):
            h = h_en = ''
            if one(it['h']):
                try:
                    m = round(float(one(it['h'])))
                    h = 'Высота — около %d м.' % m
                    h_en = 'Elevation — about %d m.' % m
                except (TypeError, ValueError): pass
            ru = sent('%s — %s.' % (l, d), h, lab('Страна: ', it['c'], 3), lab('Горный хребет: ', it.get('rng') or [], 1))
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('%s — %s.' % (le, de), h_en, lab_en('Country: ', en_vals(it, 'c'), 3),
                      lab_en('Mountain range: ', en_vals(it, 'rng'), 1)) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('mountains', 'Горы и вершины', 'Mountains', 'wd:Q8502', 22,
                   [('c', 'wdt:P17', 'label'), ('h', 'wdt:P2044', 'v'), ('rng', 'wdt:P4552', 'label')],
                   fmt_mt, trig=lambda it, l: ['гора ' + l, l]
                   + (['вулкан ' + l] if re.search(r'вулкан|volcano', (it.get('d') or '') + (it.get('den') or ''), re.I) else [])
                   + (['mountain ' + it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   cls_path='wdt:P31/wdt:P279*', en=True)
    if want('lakes'):
        def fmt_lake(it, l, d):
            area = area_en = ''
            if one(it.get('area')):
                try:
                    km2 = round(float(one(it['area'])))
                    if 1 <= km2 <= 400000:
                        area = 'Площадь: около %s км².' % f'{km2:,}'.replace(',', ' ')
                        area_en = 'Area: about %s km².' % f'{km2:,}'
                except (TypeError, ValueError): pass
            ru = sent('%s — %s.' % (l, d), lab('Страна: ', it['c'], 4), area)
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('%s — %s.' % (le, de), lab_en('Country: ', en_vals(it, 'c'), 4), area_en) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('lakes', 'Озёра, моря и острова', 'Lakes, seas, islands', 'wd:Q23397', 25,
                   [('c', 'wdt:P17', 'label'), ('area', 'wdt:P2046', 'v')],
                   fmt_lake, trig=lambda it, l: ['озеро ' + l, l]
                   + ([it['en'], 'lake ' + it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('islands'):
        def fmt_isl(it, l, d):
            ru = sent('%s — %s.' % (l, d), lab('Государство: ', it['c'], 2), lab('Архипелаг: ', it.get('arch') or [], 1))
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('%s — %s.' % (le, de), lab_en('Country: ', en_vals(it, 'c'), 2),
                      lab_en('Archipelago: ', en_vals(it, 'arch'), 1)) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('islands', 'Острова', 'Islands', 'wd:Q23442', 28,
                   [('c', 'wdt:P17', 'label'), ('arch', 'wdt:P361', 'label')],
                   fmt_isl, trig=lambda it, l: ['остров ' + l, l]
                   + ([it['en'], 'island ' + it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('species'):
        def fmt_sp(it, l, d):
            lat = one(it['lat'])
            ru = sent('%s%s — %s.' % (l, (' (лат. %s)' % lat) if lat and lat.lower() != l.lower() else '', d),
                      lab('Входит в таксон: ', it['par'], 1), lab('Ранг: ', it.get('rank') or [], 1))
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('%s%s — %s.' % (le, (' (lat. %s)' % lat) if lat and lat.lower() != (le or '').lower() else '', de),
                      lab_en('Parent taxon: ', en_vals(it, 'par'), 1),
                      lab_en('Rank: ', en_vals(it, 'rank'), 1)) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('species', 'Животные и растения', 'Animals and plants', 'wd:Q16521', 42,
                   [('lat', 'wdt:P225', 'v'), ('par', 'wdt:P171', 'label'), ('rank', 'wdt:P105', 'label')],
                   fmt_sp, trig=lambda it, l: [l] + ([one(it['lat'])] if one(it['lat']) else [])
                   + ([it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('books'):
        def fmt_book(it, l, d):
            ru = sent('«%s» — %s.' % (l, d), lab('Автор: ', it['a'], 2),
                      ('Опубликовано: %s.' % yr(it['y'])) if yr(it['y']) else '',
                      lab('Жанр: ', it.get('g') or [], 2), lab('Язык: ', it.get('lang') or [], 2),
                      lab('Страна: ', it.get('c') or [], 1))
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('"%s" — %s.' % (le, de), lab_en('Author: ', en_vals(it, 'a'), 2),
                      ('Published: %s.' % yr_en(it['y'])) if yr_en(it['y']) else '',
                      lab_en('Genre: ', en_vals(it, 'g'), 2), lab_en('Language: ', en_vals(it, 'lang'), 2),
                      lab_en('Country: ', en_vals(it, 'c'), 1)) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('books', 'Литература', 'Literature', 'wd:Q7725634 wd:Q47461344 wd:Q25379 wd:Q8261 wd:Q5185279', 22,
                   [('a', 'wdt:P50', 'label'), ('y', 'wdt:P577', 'year'), ('g', 'wdt:P136', 'label'),
                    ('lang', 'wdt:P407', 'label'), ('c', 'wdt:P495', 'label')],
                   fmt_book, trig=lambda it, l: [l, 'кто написал ' + l]
                   + ([it['en'], 'who wrote ' + it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('paintings'):
        def fmt_paint(it, l, d):
            ru = sent('«%s» — %s.' % (l, d), lab('Автор: ', it['a'], 1),
                      ('Создана: %s.' % yr(it['y'])) if yr(it['y']) else '', lab('Собрание: ', it['m'], 1),
                      lab('Страна: ', it.get('c') or [], 1))
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('"%s" — %s.' % (le, de), lab_en('Artist: ', en_vals(it, 'a'), 1),
                      ('Created: %s.' % yr_en(it['y'])) if yr_en(it['y']) else '',
                      lab_en('Collection: ', en_vals(it, 'm'), 1),
                      lab_en('Country: ', en_vals(it, 'c'), 1)) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('paintings', 'Живопись', 'Paintings', 'wd:Q3305213', 14,
                   [('a', 'wdt:P170', 'label'), ('y', 'wdt:P571', 'year'), ('m', 'wdt:P195', 'label'),
                    ('c', 'wdt:P495', 'label')],
                   fmt_paint, trig=lambda it, l: [l, 'картина ' + l]
                   + ([it['en'], 'painting ' + it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('music'):
        def fmt_music(it, l, d):
            ru = sent('«%s» — %s.' % (l, d), lab('Композитор: ', it['a'], 2), lab('Исполнитель: ', it['p'], 2),
                      ('Год: %s.' % yr(it['y'])) if yr(it['y']) else '', lab('Жанр: ', it.get('g') or [], 2))
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('"%s" — %s.' % (le, de), lab_en('Composer: ', en_vals(it, 'a'), 2),
                      lab_en('Performer: ', en_vals(it, 'p'), 2),
                      ('Year: %s.' % yr_en(it['y'])) if yr_en(it['y']) else '',
                      lab_en('Genre: ', en_vals(it, 'g'), 2)) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('music', 'Музыкальные произведения', 'Music', 'wd:Q105543609', 30,
                   [('a', 'wdt:P86', 'label'), ('p', 'wdt:P175', 'label'), ('y', 'wdt:P577', 'year'),
                    ('g', 'wdt:P136', 'label')],
                   fmt_music, trig=lambda it, l: [l, 'произведение ' + l]
                   + ([it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('films'):
        def fmt_film(it, l, d):
            dur = dur_en = ''
            if one(it.get('dur')):
                try:
                    mins = round(float(one(it['dur'])))
                    if 20 <= mins <= 400:
                        dur = 'Длительность: около %d мин.' % mins
                        dur_en = 'Runtime: about %d min.' % mins
                except (TypeError, ValueError): pass
            ru = sent('«%s» — %s.' % (l, d), lab('Режиссёр: ', it['a'], 2),
                      ('Год выхода: %s.' % yr(it['y'])) if yr(it['y']) else '',
                      lab('Жанр: ', it.get('g') or [], 3), lab('Страна: ', it.get('c') or [], 2), dur)
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('"%s" — %s.' % (le, de), lab_en('Director: ', en_vals(it, 'a'), 2),
                      ('Release year: %s.' % yr_en(it['y'])) if yr_en(it['y']) else '',
                      lab_en('Genre: ', en_vals(it, 'g'), 3), lab_en('Country: ', en_vals(it, 'c'), 2),
                      dur_en) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('films', 'Кино', 'Films', 'wd:Q11424', 42,
                   [('a', 'wdt:P57', 'label'), ('y', 'wdt:P577', 'year'), ('g', 'wdt:P136', 'label'),
                    ('c', 'wdt:P495', 'label'), ('dur', 'wdt:P2047', 'v')],
                   fmt_film, trig=lambda it, l: [l, 'фильм ' + l]
                   + ([it['en'], 'film ' + it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('battles'):
        def fmt_ev(it, l, d):
            y = yr(it['y']) or yr(it['s'])
            ru = sent('%s — %s.' % (l, d), ('Год: %s.' % y) if y else '', lab('Часть: ', it['pt'], 1),
                      lab('Место: ', it.get('loc') or [], 1), lab('Участники: ', it.get('par') or [], 3))
            le, de = it.get('en') or '', it.get('den') or ''
            ye = yr_en(it['y']) or yr_en(it['s'])
            en = sent('%s — %s.' % (le, de), ('Year: %s.' % ye) if ye else '',
                      lab_en('Part of: ', en_vals(it, 'pt'), 1), lab_en('Location: ', en_vals(it, 'loc'), 1),
                      lab_en('Participants: ', en_vals(it, 'par'), 3)) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('events', 'Войны и сражения', 'Wars and battles', 'wd:Q178561', 30,
                   [('y', 'wdt:P585', 'year'), ('s', 'wdt:P580', 'year'), ('e', 'wdt:P582', 'year'),
                    ('pt', 'wdt:P361', 'label'), ('loc', 'wdt:P276', 'label'), ('par', 'wdt:P710', 'label')],
                   fmt_ev, trig=lambda it, l: [l]
                   + ([it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('wars'):
        def fmt_war(it, l, d):
            ru = sent('%s — %s.' % (l, d),
                      ('Годы: %s–%s.' % (yr(it['s']), yr(it['e']))) if yr(it['s']) and yr(it['e']) else '',
                      lab('Участники: ', it.get('par') or [], 4), lab('Место: ', it.get('loc') or [], 2))
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('%s — %s.' % (le, de),
                      ('Years: %s–%s.' % (yr_en(it['s']), yr_en(it['e']))) if yr_en(it['s']) and yr_en(it['e']) else '',
                      lab_en('Participants: ', en_vals(it, 'par'), 4),
                      lab_en('Location: ', en_vals(it, 'loc'), 2)) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('wars', 'Войны', 'Wars', 'wd:Q198 wd:Q103495', 30,
                   [('s', 'wdt:P580', 'year'), ('e', 'wdt:P582', 'year'),
                    ('par', 'wdt:P710', 'label'), ('loc', 'wdt:P276', 'label')],
                   fmt_war, trig=lambda it, l: [l]
                   + ([it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('dishes'):
        def fmt_dish(it, l, d):
            ru = sent('%s — %s.' % (l, d), lab('Происхождение: ', it['c'], 2),
                      lab('Ингредиенты: ', it.get('ing') or [], 4))
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('%s — %s.' % (le, de), lab_en('Origin: ', en_vals(it, 'c'), 2),
                      lab_en('Ingredients: ', en_vals(it, 'ing'), 4)) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('dishes', 'Блюда и кухня', 'Dishes', 'wd:Q746549 wd:Q19861951', 40,
                   [('c', 'wdt:P495', 'label'), ('ing', 'wdt:P527', 'label')],
                   fmt_dish, trig=lambda it, l: [l, 'блюдо ' + l]
                   + ([it['en'], 'dish ' + it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('languages'):
        def fmt_lang(it, l, d):
            ru = sent('%s — %s.' % (cap(l), d), lab('Семья/группа: ', it.get('f') or [], 2),
                      lab('Страны: ', it.get('c') or [], 3), lab('Письменность: ', it.get('w') or [], 2))
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('%s — %s.' % (cap(le), de), lab_en('Family/group: ', en_vals(it, 'f'), 2),
                      lab_en('Countries: ', en_vals(it, 'c'), 3),
                      lab_en('Writing system: ', en_vals(it, 'w'), 2)) if le and de else ''
            return maybe_pair(ru, en)
        gen_simple('languages', 'Языки мира', 'Languages', 'wd:Q34770', 40,
                   [('f', 'wdt:P279', 'label'), ('c', 'wdt:P17', 'label'), ('w', 'wdt:P282', 'label')],
                   fmt_lang, trig=lambda it, l: [l]
                   + ([it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   en=True)
    if want('proglang'):
        def fmt_pl(it, l, d):
            ru = sent('%s — %s.' % (l, d or 'язык программирования'),
                      ('Появился: %s.' % yr(it['y'])) if yr(it['y']) else '', lab('Автор: ', it['a'], 3),
                      lab('Под влиянием: ', it.get('inf') or [], 3))
            le, de = it.get('en') or l, it.get('den') or ''
            en = sent('%s — %s.' % (le, de or 'programming language'),
                      ('Introduced: %s.' % yr_en(it['y'])) if yr_en(it['y']) else '',
                      lab_en('Designer: ', en_vals(it, 'a'), 3),
                      lab_en('Influenced by: ', en_vals(it, 'inf'), 3))
            return maybe_pair(ru, en)
        gen_simple('proglang', 'Языки программирования', 'Programming languages', 'wd:Q9143', 12,
                   [('y', 'wdt:P571', 'year'), ('a', 'wdt:P287', 'label'), ('inf', 'wdt:P737', 'label')],
                   fmt_pl, trig=lambda it, l: [l, 'язык программирования ' + l]
                   + ([it['en'], 'programming language ' + it['en']] if it.get('en') and it['en'].lower() != l.lower() else []),
                   cls_path='wdt:P31/wdt:P279*', need_desc=False, en=True)

def gen_concepts():
    o = Out('concepts', 'Понятия: единицы, спорт, математика, инструменты', 'Concepts')
    # v14.16.18: EN label/desc + English prefix triggers (unit/sport/term/tool/concept)
    tpl_en = {'единица %s': 'unit %s', 'спорт %s': 'sport %s', 'термин %s': 'term %s',
              'инструмент %s': 'instrument %s', 'понятие %s': 'concept %s'}
    for cls, sl, path, tpl in (('wd:Q47574', 25, 'wdt:P31/wdt:P279*', 'единица %s'), ('wd:Q31629', 25, 'wdt:P31', 'спорт %s'),
                               ('wd:Q24034552', 30, 'wdt:P31', 'термин %s'), ('wd:Q34379', 30, 'wdt:P31/wdt:P279*', 'инструмент %s'),
                               ('wd:Q151885', 60, 'wdt:P31', 'понятие %s')):
        for it in q_items(cls, sl, [], limit=1500, cls_path=path, tag='cc_%s_%d' % (cls[3:], sl), en=True):
            l, d = it['l'], desc(it)
            if not (ok_label(l) and d): continue
            ru = sent('%s — %s.' % (cap(l), d))
            le, de = it.get('en') or '', it.get('den') or ''
            en = sent('%s — %s.' % (cap(le), de)) if le and de and not re.search(r'wikimedia|disambiguation', de, re.I) else ''
            tt = [l, tpl % l]
            if le and le.lower() != l.lower():
                tt.append(le)
                te = tpl_en.get(tpl)
                if te: tt.append(te % le)
            o.add(tt, maybe_pair(ru, en))
    o.write()

if __name__ == '__main__':
    main()
