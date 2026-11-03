#!/usr/bin/env python3
"""v14.3.0: new Wikidata (CC0) sections for the KB library. Run AFTER gen_kb.py:
   python3 kb/gen/gen_more.py [section ...]
Every item whose label is already a trigger anywhere in kb/src (hand-written or generated, incl. earlier
sections of this script) is skipped, so new sections add only new entities. Stable facts only:
no events/missions after 2019, diseases are reference-only (description + «справочно»).
"""
import os, re, sys, glob
from gen_kb import q_items, WORKS, plain_title, ok_label, desc, sent, cap, lab, yr, one, few, clean, SRC

def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-zа-я0-9+#²³ ]+', ' ', s.lower().replace('ё', 'е'))).strip()

SEEN = set()
HAND = []
PREF = re.compile(r'^(?:город|река|гора|остров|озеро|фильм|элемент|страна|столица|кто такой|кто такая|кто написал|блюдо|язык программирования|язык|что такое|планета|созвездие|звезда|спутник) ')
def known(n):
    if n in SEEN or PREF.sub('', n) in SEEN: return True
    if len(n) >= 4 and ' ' in n:   # многословное название внутри ручного триггера; одно слово («марс») — нет
        k = ' ' + n + ' '
        return any(k in h for h in HAND)
    return False
def load_seen(skip=()):
    SEEN.clear(); HAND.clear()
    for f in glob.glob(os.path.join(SRC, '*.txt')):
        if os.path.basename(f) in skip: continue
        for line in open(f, encoding='utf-8'):
            if line.startswith('#') or '||' not in line: continue
            for t in line.split('||')[0].split(';'):
                n = norm(t)
                if not n: continue
                SEEN.add(n); SEEN.add(PREF.sub('', n))
                if not os.path.basename(f).startswith('w_'): HAND.append(' ' + n + ' ')

BADL = re.compile(r'^\(|^S/|\d{3,}|:|^\d')
GENERIC = re.compile(r'^(Городской|Национальный|Исторический|Художественный|Государственный|Центральный|Краеведческий|Археологический|Морской) музей$|^Музей (современного искусства|изобразительных искусств|естественной истории|истории|искусств)$')
NOISE = re.compile(r'страница значений|Викимедиа|wikimedia|список |категория|шаблон|сезон|выпуск|эпизод|турнир 20|чемпионат 20|около \d{5} м', re.I)

class Sec:
    def __init__(self, dom, title, title_en):
        self.dom, self.title, self.title_en, self.lines, self.own = dom, title, title_en, [], set()
    def add(self, triggers, answer):
        main = norm(triggers[0])
        if main and known(main) and len(triggers) > 1:
            # омоним уже занятого названия (опера «Кармен», клуб «Барселона») — только с уточняющим префиксом
            triggers = triggers[1:]; main = norm(triggers[0])
        ra = answer[0] if isinstance(answer, tuple) else answer
        if not main or known(main) or main in self.own or len(ra) < 25 or NOISE.search(ra): return
        tt, ks = [], set()
        for t in triggers:
            t = clean(t).strip(' ,.'); k = norm(t)
            w = k.split()
            if len(w) > 1 and w[0] == w[1]: continue
            if t and k and not known(k) and k not in self.own and k not in ks and len(t) <= 80: ks.add(k); tt.append(t)
        if not tt: return
        self.own |= ks
        if isinstance(answer, tuple):
            ru, en = answer
            self.lines.append('%s || %s' % ('; '.join(tt), ru[:600]) + (' || %s' % en[:600] if en else ''))
        else: self.lines.append('%s || %s' % ('; '.join(tt), answer[:600]))
    def write(self):
        p = os.path.join(SRC, 'w_%s.txt' % self.dom)
        with open(p, 'w', encoding='utf-8') as f:
            f.write('# %s | %s\n# @generated from Wikidata (CC0) by kb/gen/gen_more.py — do not edit by hand\n' % (self.title, self.title_en))
            f.write('\n'.join(self.lines) + '\n')
        SEEN.update(self.own)
        print(self.dom, len(self.lines))

def run(dom, title, title_en, specs):
    """specs: list of (cls, minsl, props, fmt, trig, opts)."""
    # только ручные, разделы gen_kb.py и более ранние разделы этого скрипта — порядок ORDER детерминирован
    later = ORDER[ORDER.index(dom):] if dom in ORDER else [dom]
    load_seen(skip={'w_%s.txt' % k for k in later})
    o = Sec(dom, title, title_en)
    for cls, minsl, props, fmt, trig, opts in specs:
        its = q_items(cls, minsl, props, limit=opts.get('limit', 3000), extra=opts.get('extra', ''), cls_path=opts.get('path', 'wdt:P31'))
        if opts.get('facts'): enrich(its, opts['facts'])
        cnt = {}
        for it in its: cnt[norm(it['l'])] = cnt.get(norm(it['l']), 0) + 1
        for it in its:
            if cnt[norm(it['l'])] > 1: continue   # неоднозначное название — пропускаем
            if GENERIC.search(it['l']) or re.search(r'МКС-(6[2-9]|[7-9]\d)', it['l']): continue
            if it['d'].lower().startswith(it['l'].lower()): it['d'] = re.sub(r'^[\s\-—–]*(это\s+)?', '', it['d'][len(it['l']):])
            l, d = it['l'], desc(it)
            if not ok_label(l) or not d: continue
            if BADL.search(l): continue
            if opts.get('dre') and not re.search(opts['dre'], d, re.I): continue
            if opts.get('dno') and re.search(opts['dno'], d, re.I): continue
            if opts.get('maxyear') and any(x.lstrip('-').isdigit() and int(x) > opts['maxyear'] for k in ('y', 's') for x in it.get(k, [])): continue
            if opts.get('maxyear') and re.search(r'20[2-9]\d', l + ' ' + d): continue
            a = fmt(it, l, d)
            if not a or (isinstance(a, tuple) and not a[0]): continue
            tt = trig(it, l)
            if dom in WORKS and plain_title(l) and len(tt) > 1: tt = tt[1:]
            o.add(tt, a)
    o.write()

def S(cls, minsl, props, fmt, trig, **opts): return (cls, minsl, props, fmt, trig, opts)
def basic(prefix=None, extra_lab=None):
    def f(it, l, d): return sent('%s — %s.' % (cap(l), d), *(lab(p, it[k], n) for k, p, n in (extra_lab or [])))
    def t(it, l): return [l] + ([prefix % l] if prefix else [])
    return f, t
P = 'wdt:P31/wdt:P279*'
PS = '(wdt:P31|wdt:P279)/wdt:P279*'   # и экземпляры, и подклассы (болезни и органы в Wikidata часто подклассы)

def person_fmt(it, l, d):
    """RU (+ EN when enrich() filled le/de / F). Occupation from first-pass or F."""
    from gen_kb import yr_en
    b, e = yr(it['b']), yr(it['e'])
    if b.isdigit() and int(b) >= 2005: return ''   # дети/подростки — не публикуем
    if not b or not b.isdigit() or int(b) < 1500: b = e = ''
    life = ('(%s–%s)' % (b, e) if e else '(род. %s)' % b) if b else ''
    occ_ru = few(it.get('occ') or [], 3)
    if not occ_ru and it.get('F', {}).get('occ'):
        occ_ru = ', '.join(v[0] for v in it['F']['occ'][:3] if v[0])
    ru = sent('%s — %s.' % (sent(l, life), d),
              ('Гражданство: %s.' % few(it['c'], 2)) if b and few(it['c'], 2) else '',
              ('Род занятий: %s.' % occ_ru) if occ_ru else '')
    le, de = it.get('le', ''), it.get('de', '')
    en = ''
    if le and de and not re.search(r'wikimedia|disambiguation', de, re.I):
        be, ee = (yr_en(it['b']), yr_en(it['e'])) if b else ('', '')
        life_en = ('(%s–%s)' % (be, ee) if ee else '(b. %s)' % be) if be else ''
        cit = [v[1] for v in it.get('F', {}).get('c', [])[:2] if v[1]] or list(it.get('c') or [])[:2]
        occ_en = [v[1] for v in it.get('F', {}).get('occ', [])[:3] if v[1]]
        en = sent('%s — %s.' % (sent(le, life_en), de),
                  ('Citizenship: %s.' % ', '.join(cit)) if b and cit else '',
                  ('Occupation: %s.' % ', '.join(occ_en)) if occ_en else '')
    return (ru, en) if en else ru
PP = [('b', 'wdt:P569', 'year'), ('e', 'wdt:P570', 'year'), ('c', 'wdt:P27', 'label'), ('occ', 'wdt:P106', 'label')]
PERSON_FACTS = [('c', 'P27', 'item', 'Гражданство', 'Citizenship', 2),
                ('occ', 'P106', 'item', 'Род занятий', 'Occupation', 3)]
def occ(q): return '?x wdt:P106 ?oc . ?oc wdt:P279* %s .' % q
def ptrig(it, l):
    tt = [l, 'кто такой ' + l] if ' ' in l else [l]
    le = it.get('le', '')
    if le and re.search(r'[A-Za-z]', le) and norm(le) != norm(l) and len(le) <= 60:
        tt += [le, 'who is ' + le] if ' ' in le else [le]
    return tt

SECTIONS = {}
def sec(name):
    def deco(fn): SECTIONS[name] = fn; return fn
    return deco

@sec('space')
def _():
    fx_orb = [('p', 'P397', 'item', 'Обращается вокруг', 'Orbits', 1)]
    fx_star = [('cn', 'P59', 'item', 'Созвездие', 'Constellation', 1)]
    fx_sc = [('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2)]
    run('space', 'Космос: планеты, спутники, звёзды, созвездия', 'Space objects', [
        RS('wd:Q634 wd:Q3504248 wd:Q2537 wd:Q1022867 wd:Q121750 wd:Q3504248', 8, fx_orb, rtrig(),
           props=[('p', 'wdt:P397', 'label')], dre=r'планет|спутник', dno=r'астероид|^объект|экзопланет', path=P),
        RS('wd:Q8928', 1, fx_sc, rtrig('созвездие %s'), dre='созвезди'),
        RS('wd:Q523', 25, fx_star, rtrig('звезда %s'), props=[('cn', 'wdt:P59', 'label')], path=P, dre=r'звезд', dno=r'астероид|галактик'),
        RS('wd:Q318 wd:Q3863 wd:Q1931185 wd:Q204107', 25, fx_sc, rtrig(), path=P, dre=r'галактик|туманност|скоплени|комет'),
    ])

@sec('missions')
def _():
    fx = [('y', 'P619', 'year', 'Запуск', 'Launch', 1), ('op', 'P137', 'item', 'Оператор', 'Operator', 2)]
    run('missions', 'Космические миссии', 'Space missions', [
        RS('wd:Q2133344 wd:Q40218 wd:Q5916 wd:Q752783', 20, fx, rtrig('миссия %s'),
           props=[('y', 'wdt:P619', 'year'), ('op', 'wdt:P137', 'label')],
           path=P, maxyear=2019, dre=r'косми|спутник|станци|зонд|корабл|аппарат|миссия|ракет|телескоп|программ|полёт|ровер|луноход|марсоход'),
    ])

@sec('minerals')
def _():
    fx = [('f', 'P274', 'str', 'Формула', 'Formula', 1), ('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2)]
    run('minerals', 'Минералы и горные породы', 'Minerals and rocks', [
        RS('wd:Q12089225 wd:Q7946', 15, fx, rtrig('минерал %s'), props=[('f', 'wdt:P274', 'v')], dre=r'минерал|камень|самоцвет'),
        RS('wd:Q8063', 20, [('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2)], rtrig('горная порода %s'), path=P, dre=r'пород|камень|минерал'),
    ])

DINO = r'^(род|вид|семейство|клада|отряд|подотряд|инфраотряд|надсемейство|группа|класс|триба)\b|динозавр|ящер|вымерш'
@sec('dinosaurs')
def _():
    fx = [('lat', 'P225', 'str', 'Латинское название', 'Latin name', 1),
          ('par', 'P171', 'item', 'Входит в таксон', 'Parent taxon', 1)]
    run('dinosaurs', 'Динозавры и древние животные', 'Dinosaurs and prehistoric animals', [
        RS('wd:Q16521 wd:Q23038290', 7, fx, rtrig(), props=[('lat', 'wdt:P225', 'v')],
           extra='?x wdt:P171+ wd:Q430 . FILTER NOT EXISTS { ?x wdt:P171+ wd:Q5113 }', dre=DINO),
        RS('wd:Q16521 wd:Q23038290', 12, fx, rtrig(), props=[('lat', 'wdt:P225', 'v')],
           extra='{ ?x wdt:P171+ wd:Q3238275 } UNION { ?x wdt:P171+ wd:Q216590 } UNION { ?x wdt:P171+ wd:Q19362 }', dre=DINO),
    ])

@sec('diseases')
def _():
    fx = [('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2), ('sym', 'P780', 'item', 'Симптомы', 'Symptoms', 3)]
    f = rich(fx)
    def g(it, l, d):
        ru, en = f(it, l, d)
        return (sent(ru, 'Справочная информация, не заменяет консультацию врача.') if ru else '',
                sent(en, 'Reference only, not medical advice.') if en else '')
    run('diseases', 'Болезни (справочно)', 'Diseases (reference only)', [
        S('wd:Q12136 wd:Q18123741 wd:Q929833', 35, [], g, rtrig('болезнь %s'), facts=fx, path=PS, limit=2500,
          dre=r'болезн|заболеван|инфекц|синдром|расстройств|воспален|опухол|рак|недостаточност|патолог|диабет|грипп', dno=r'фильм|песн|альбом|групп'),
    ])

@sec('anatomy')
def _():
    fx = [('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2), ('pt', 'P361', 'item', 'Часть', 'Part of', 2)]
    run('anatomy', 'Анатомия человека', 'Human anatomy', [
        RS('wd:Q712378 wd:Q265868 wd:Q4936952 wd:Q7884789 wd:Q103637', 30, fx, rtrig('орган %s'), path=PS,
          extra='FILTER NOT EXISTS { ?x wdt:P31 wd:Q16521 }', limit=1500,
          dre=r'орган|кост|мышц|желез|часть|отдел|ткан|сосуд|артери|вен[аы]|нерв|систем|полост|сустав|клетк|мозг',
          dno=r'фильм|песн|альбом|групп|птиц|животн|насеком|растени|рыб|рак |опухол|болезн|заболеван|синдром|воспален'),
    ])

@sec('companies')
def _():
    fx = [('y', 'P571', 'year', 'Основана', 'Founded', 1), ('c', 'P17', 'item', 'Страна', 'Country', 1),
          ('fo', 'P112', 'item', 'Основатели', 'Founders', 3), ('ind', 'P452', 'item', 'Отрасль', 'Industry', 2)]
    run('companies', 'Компании и бренды', 'Companies and brands', [
        RS('wd:Q783794 wd:Q4830453 wd:Q891723 wd:Q6881511 wd:Q167037 wd:Q270791 wd:Q46970 wd:Q22687 wd:Q210167', 35, fx,
           rtrig('компания %s'),
           props=[('y', 'wdt:P571', 'year'), ('c', 'wdt:P17', 'label'), ('fo', 'wdt:P112', 'label')],
           limit=2500, extra='FILTER NOT EXISTS { ?x wdt:P576 ?end }',
           dre=r'компани|корпораци|производител|концерн|предприяти|бренд|банк|авиакомпани|ритейл|разработчик|холдинг|автопроизводител|издател|торгов|сеть',
           dno=r'город|коммун|департамент|штат|организаци объединённых|деревн'),
    ])

@sec('science')
def _():
    fx = [('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2), ('nm', 'P138', 'item', 'Названо в честь', 'Named after', 2)]
    fx_inv = [('inv', 'P61', 'item', 'Изобретатель', 'Inventor', 2), ('y', 'P571', 'year', 'Год', 'Year', 1)]
    run('science', 'Научные законы, теории и изобретения', 'Scientific laws, theories, inventions', [
        RS('wd:Q408891 wd:Q7949 wd:Q17737 wd:Q65943 wd:Q1503859', 18, fx, rtrig('что такое %s'), path=P, limit=1500,
           dre=r'закон|теори|принцип|уравнени|эффект|постулат|правил|гипотез|теорем|парадокс|модель',
           dno=r'идеолог|политич|орден|фильм|альбом|песн|заговор|конспиролог|антисемит|международных отношений|пропаганд'),
        RS('wd:Q15401930 wd:Q39546 wd:Q11019', 45, fx_inv, rtrig('кто изобрел %s'),
           props=[('inv', 'wdt:P61', 'label')], path=P, limit=1500,
           dre=r'изобрет|устройств|прибор|механизм|машин|двигател|аппарат|инструмент|оборудован|техник', dno=r'фильм|альбом|песн|древнее'),
    ])

@sec('holidays')
def _():
    fx = [('c', 'P17', 'item', 'Страна', 'Country', 2), ('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2)]
    run('holidays', 'Праздники и фестивали', 'Holidays and festivals', [
        RS('wd:Q1445650 wd:Q132241 wd:Q2633344 wd:Q15275719', 25, fx, rtrig('праздник %s'), path=P, maxyear=2019, limit=1500,
          extra='FILTER NOT EXISTS { ?x wdt:P585 ?pt }',
          dre=r'праздник|фестивал|торжеств|карнавал|памятн(ый|ая) дата|день |годовщин|обряд|традиц',
          dno=r'Олимпийск|кубок|чемпионат|регат|вики|спортивн|високосн'),
    ])

@sec('landmarks')
def _():
    fx = [('loc', 'P131', 'item', 'Где', 'Location', 1), ('c', 'P17', 'item', 'Страна', 'Country', 1),
          ('y', 'P571', 'year', 'Основан/построен', 'Built', 1)]
    run('landmarks', 'Памятники, здания и достопримечательности', 'Monuments and buildings', [
        RS('wd:Q4989906 wd:Q16560 wd:Q12518 wd:Q2977 wd:Q23413 wd:Q44539 wd:Q11303 wd:Q12280 wd:Q57821 wd:Q1081138 wd:Q570116 wd:Q839954', 50, fx,
           rtrig('где находится %s'),
           props=[('c', 'wdt:P17', 'label'), ('loc', 'wdt:P131', 'label'), ('y', 'wdt:P571', 'year')],
           path=P, limit=2500,
           dre=r'памятник|дворец|башн|собор|замок|храм|мечеть|мост|монумент|крепост|здани|небоскрёб|пирамид|статуя|церковь|монастыр|ворота|стадион|театр|достопримечат|сооружен|архитектур|кремль|арка'),
    ])

@sec('museums')
def _():
    fx = [('loc', 'P131', 'item', 'Где', 'Location', 1), ('c', 'P17', 'item', 'Страна', 'Country', 1),
          ('y', 'P571', 'year', 'Основан', 'Founded', 1)]
    run('museums', 'Музеи', 'Museums', [
        RS('wd:Q33506', 30, fx, rtrig('музей %s'),
           props=[('loc', 'wdt:P131', 'label'), ('c', 'wdt:P17', 'label')], path=P, limit=1500,
           dre=r'музе|галере|выставоч|собрани|коллекци'),
    ])

@sec('universities')
def _():
    fx = [('loc', 'P131', 'item', 'Где', 'Location', 1), ('c', 'P17', 'item', 'Страна', 'Country', 1),
          ('y', 'P571', 'year', 'Основан', 'Founded', 1)]
    run('universities', 'Университеты', 'Universities', [
        RS('wd:Q3918 wd:Q875538 wd:Q38723 wd:Q902104', 28, fx, rtrig('университет %s'),
           props=[('loc', 'wdt:P131', 'label'), ('c', 'wdt:P17', 'label'), ('y', 'wdt:P571', 'year')],
           path=P, limit=1500, dre=r'университет|институт|колледж|академи|высш|учебн|школ'),
    ])

@sec('waters')
def _():
    fx = [('c', 'P17', 'item', 'Страна', 'Country', 3), ('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2)]
    run('waters', 'Моря, океаны, заливы и проливы', 'Seas, oceans, gulfs, straits', [
        RS('wd:Q165 wd:Q9430 wd:Q1322134 wd:Q37901 wd:Q39594', 20, fx, rtrig(), path=P, limit=1500,
           dre=r'мор[ея]|океан|залив|пролив|бухт|лагун'),
    ])

@sec('deserts')
def _():
    fx = [('c', 'P17', 'item', 'Страна', 'Country', 3), ('h', 'P2044', 'qty', 'Высота', 'Elevation', 1)]
    # height as plain v via first-pass; qty needs unit map — keep country via rich + height from props in custom? use str via first-pass only in rich year/str.
    # Use item/str facts only; elevation stays best-effort via custom wrapper.
    fx2 = [('c', 'P17', 'item', 'Страна', 'Country', 3)]
    f = rich(fx2)
    def g(it, l, d):
        ru, en = f(it, l, d)
        h = ''
        if one(it.get('h')) and 'вулкан' in (d or ''):
            try:
                m = round(float(one(it['h'])))
                ru = sent(ru, 'Высота — около %d м.' % m)
                if en: en = sent(en, 'Elevation — about %d m.' % m)
            except (TypeError, ValueError): pass
        return ru, en
    run('deserts', 'Пустыни, вулканы и природные объекты', 'Deserts, volcanoes, landforms', [
        S('wd:Q8514 wd:Q8072 wd:Q34038 wd:Q35666 wd:Q150784 wd:Q35509', 20,
          [('c', 'wdt:P17', 'label'), ('h', 'wdt:P2044', 'v')], g, rtrig(),
          facts=fx2, path=P, limit=1500, dre=r'пустын|вулкан|каньон|ледник|пещер|водопад|ущель|плато|кратер|гейзер|долин|равнин|нагорь'),
    ])

@sec('games')
def _():
    fx = [('y', 'P577', 'year', 'Год выхода', 'Release year', 1), ('dev', 'P178', 'item', 'Разработчик', 'Developer', 2),
          ('g', 'P136', 'item', 'Жанр', 'Genre', 2), ('plat', 'P400', 'item', 'Платформа', 'Platform', 3)]
    run('games', 'Видеоигры', 'Video games', [
        RS('wd:Q7889', 35, fx, rtrig('игра %s'),
           props=[('y', 'wdt:P577', 'year'), ('dev', 'wdt:P178', 'label')], maxyear=2020, limit=1500, dre=r'игр'),
    ])

@sec('stage')
def _():
    fx = [('a', 'P86', 'item', 'Композитор', 'Composer', 2), ('y', 'P577', 'year', 'Год', 'Year', 1),
          ('lang', 'P407', 'item', 'Язык', 'Language', 1)]
    run('stage', 'Оперы, балеты и мюзиклы', 'Operas, ballets, musicals', [
        RS('wd:Q58483083 wd:Q15079786 wd:Q785522 wd:Q1344 wd:Q2743', 10, fx, rtrig(),
           props=[('a', 'wdt:P86', 'label')], limit=1500, dre=r'опер|балет|мюзикл'),
    ])

@sec('myths')
def _():
    fx = [('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2), ('from', 'P361', 'item', 'Часть', 'Part of', 2),
          ('myth', 'P2596', 'item', 'Культура', 'Culture', 2)]
    run('myths', 'Мифология и легендарные персонажи', 'Mythology', [
        RS('wd:Q178885 wd:Q4271324 wd:Q22989102 wd:Q15410431 wd:Q24334685', 25, fx, rtrig('кто такой %s'), path=P, limit=2000,
           dre=r'миф|бог|богин|божеств|легенд|персонаж|демон|герой|титан|нимф|дух|чудовищ|существо|сказ|эпос|ангел|архангел',
           dno=r'поэт|писател|фильм|альбом|песн|компьютерн|комикс|игр'),
    ])

@sec('religions')
def _():
    fx = [('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2), ('found', 'P112', 'item', 'Основатель', 'Founder', 2)]
    run('religions', 'Религии и учения', 'Religions and belief systems', [
        RS('wd:Q9174 wd:Q879146 wd:Q13414953 wd:Q12909644', 35, fx, rtrig('что такое %s'), path=P, limit=1000,
           dre=r'религи|учени|вероучени|конфесси|течени|верован|культ|церк|деноминаци|ветвь'),
    ])

for key, title, title_en, q, sl, dre in (
        ('writers', 'Писатели и поэты', 'Writers and poets', 'wd:Q36180', 38, r'писател|поэт|прозаик|драматург|романист|литератор|сценарист|публицист|баснописец'),
        ('composers', 'Композиторы и музыканты', 'Composers and musicians', 'wd:Q639669', 45, r'композитор|музыкант|певе|певиц|пианист|скрипач|виолончел|гитарист|дирижёр|рэпер|исполнител|автор песен|барабанщ|вокалист|бас-гитарист|диджей'),
        ('painters', 'Художники, скульпторы и архитекторы', 'Artists and architects', 'wd:Q1028181 wd:Q1281618 wd:Q42973', 30, r'художни|живопис|скульптор|архитектор|график|иллюстратор|гравёр|акварел'),
        ('philosophers', 'Философы', 'Philosophers', 'wd:Q4964182', 30, r'философ|мыслител|богослов|теолог'),
        ('scientists', 'Учёные и изобретатели', 'Scientists and inventors', 'wd:Q901', 30, r'учён|физик|химик|математик|биолог|астроном|инженер|изобретател|географ|геолог|медик|врач|экономист|историк|лингвист|психолог|генетик|естествоиспыт|ботаник|зоолог|физиолог|археолог'),
        ('athletes', 'Спортсмены', 'Athletes', 'wd:Q2066131', 50, r'спортсмен|футболист|хоккеист|теннисист|шахматист|боксёр|баскетболист|гонщик|пловец|пловчих|лыжник|бегун|легкоатлет|гимнаст|борец|фигурист|велогонщик|волейболист|биатлонист|конькобеж|тренер|игрок|атлет|прыгун|тяжелоатлет|фехтовальщ|бейсболист|регбист|гольфист|боец|дзюдоист|каратист|альпинист|игрок в')):
    def mk(key=key, title=title, title_en=title_en, q=q, sl=sl, dre=dre):
        ex = '?x wdt:P106 ?oc . VALUES ?t { %s } ?oc wdt:P279* ?t .' % q
        run(key, title, title_en, [S('wd:Q5', sl, PP, person_fmt, ptrig, extra=ex, limit=2500, dre=dre, facts=PERSON_FACTS)])
    SECTIONS[key] = mk

@sec('nobel')
def _():
    def f(it, l, d):
        a = person_fmt(it, l, d)
        if not a: return ''
        if isinstance(a, tuple):
            ru, en = a
            return (sent(ru, 'Лауреат Нобелевской премии.'),
                    sent(en, 'Nobel Prize laureate.') if en else '')
        return sent(a, 'Лауреат Нобелевской премии.')
    run('nobel', 'Нобелевские лауреаты', 'Nobel laureates', [
        S('wd:Q5', 20, PP, f, ptrig, extra='?x wdt:P166 ?pr . ?pr (wdt:P31|wdt:P279)* wd:Q7191 .', limit=2000, facts=PERSON_FACTS),
    ])

@sec('airports')
def _():
    fx = [('iata', 'P238', 'str', 'Код IATA', 'IATA code', 1), ('city', 'P931', 'item', 'Обслуживает', 'Serves', 2),
          ('c', 'P17', 'item', 'Страна', 'Country', 1)]
    run('airports', 'Аэропорты', 'Airports', [
        RS('wd:Q1248784 wd:Q644371', 30, fx, rtrig('аэропорт %s'),
           props=[('city', 'wdt:P931', 'label'), ('iata', 'wdt:P238', 'v'), ('c', 'wdt:P17', 'label')],
           path=P, limit=1500, dre=r'аэропорт|аэродром'),
    ])

@sec('sports')
def _():
    fx = [('loc', 'P131', 'item', 'Город', 'City', 1), ('c', 'P17', 'item', 'Страна', 'Country', 1),
          ('y', 'P571', 'year', 'Основан', 'Founded', 1)]
    run('sports', 'Спортивные клубы и соревнования', 'Sports clubs and competitions', [
        RS('wd:Q476028 wd:Q847017 wd:Q13393265', 45, fx, rtrig('клуб %s'),
           props=[('loc', 'wdt:P131', 'label'), ('c', 'wdt:P17', 'label'), ('y', 'wdt:P571', 'year')],
           path=P, limit=1200, dre=r'клуб|команд'),
        RS('wd:Q15991303 wd:Q500834 wd:Q1079023', 40, [('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2)],
           rtrig(), path=P, limit=600,
           extra='FILTER NOT EXISTS { ?x wdt:P585 ?pt } FILTER NOT EXISTS { ?x wdt:P580 ?st . FILTER(YEAR(?st) > 2019) }',
           dre=r'турнир|соревновани|чемпионат|кубок|лига|игры|гонк|марафон', dno=r'20[0-2]\d|19\d\d'),
    ])

ORDER = ['space', 'missions', 'minerals', 'dinosaurs', 'diseases', 'anatomy', 'companies', 'science', 'holidays', 'landmarks', 'museums',
         'universities', 'waters', 'deserts', 'games', 'stage', 'myths', 'religions', 'writers', 'composers', 'painters', 'philosophers',
         'scientists', 'nobel', 'athletes', 'sports', 'airports']

# ── content/kb-expansion: natural-science, medicine-reference, tech and history gaps ──
# «Rich» sections: RU || EN answers. Second pass per section fetches EN label/description and a few
# Wikidata facts (ru+en labels of items, unique years, unique quantities in known units). Nothing is
# composed beyond Wikidata values; a fact with ambiguous/missing values is simply left out.
from wd import sparql
WD, WDP = 'http://www.wikidata.org/prop/direct/', 'http://www.wikidata.org/prop/'
UNITS = {'Q483261': ('Да', 'Da'), 'Q28924753': ('г/моль', 'g/mol'), 'Q25267': ('°C', '°C'), 'Q11579': ('K', 'K'),
         'Q13147228': ('г/см³', 'g/cm³'), 'Q844211': ('кг/м³', 'kg/m³')}
def _batches(xs, n=400):
    for k in range(0, len(xs), n): yield xs[k:k + n]
def _pv(prop): return '<%s%s>' % (WD, prop)
def enrich(its, facts):
    """it['le'], it['de'] — EN label/description; it['F'][key] — list of (ru, en) values."""
    qids = sorted(it['qid'] for it in its)
    E, F = {}, {}
    for b in _batches(qids):
        vals = ' '.join('wd:' + q for q in b)
        rows = sparql('SELECT ?x ?le ?de WHERE { VALUES ?x { %s } OPTIONAL { ?x rdfs:label ?le FILTER(LANG(?le)="en") } '
                      'OPTIONAL { ?x schema:description ?de FILTER(LANG(?de)="en") } }' % vals, 'en_' + __import__('hashlib').sha1(vals.encode()).hexdigest()[:12])
        for r in rows:
            q = r['x'].rsplit('/', 1)[1]
            E.setdefault(q, {}).update({k: clean(r[k]) for k in ('le', 'de') if r.get(k)})
        for key, prop, kind, *_ in facts:
            if kind == 'item':
                q = ('SELECT ?x ?v ?vr ?ve WHERE { VALUES ?x { %s } ?x %s ?v . OPTIONAL { ?v rdfs:label ?vr FILTER(LANG(?vr)="ru") } '
                     'OPTIONAL { ?v rdfs:label ?ve FILTER(LANG(?ve)="en") } }') % (vals, _pv(prop))
            elif kind == 'qty':
                q = ('SELECT ?x ?a ?u WHERE { VALUES ?x { %s } ?x <%s%s> ?st . ?st <%sstatement/value/%s> ?vn . '
                     '?vn <http://wikiba.se/ontology#quantityAmount> ?a . ?vn <http://wikiba.se/ontology#quantityUnit> ?u . }') % (vals, WDP, prop, WDP, prop)
            elif kind == 'year':
                q = 'SELECT ?x ?y WHERE { VALUES ?x { %s } ?x %s ?t . BIND(YEAR(?t) AS ?y) }' % (vals, _pv(prop))
            else:
                q = 'SELECT ?x ?v WHERE { VALUES ?x { %s } ?x %s ?v . }' % (vals, _pv(prop))
            rows = sparql(q, 'f_%s_' % prop + __import__('hashlib').sha1(q.encode()).hexdigest()[:12])
            for r in rows:
                x = r['x'].rsplit('/', 1)[1]; d = F.setdefault(x, {}).setdefault(key, [])
                try:
                    if kind == 'item':
                        if 'v' not in r: continue
                        v = (clean(r.get('vr', '')), clean(r.get('ve', '')), r['v'])
                    elif kind == 'qty':
                        if 'a' not in r or 'u' not in r: continue
                        u = UNITS.get(r['u'].rsplit('/', 1)[1])
                        if not u: v = ('?', '?', 'bad')
                        else:
                            a = float(r['a']); t = ('%.3f' % a).rstrip('0').rstrip('.')
                            v = (t.replace('.', ',') + ' ' + u[0], t + ' ' + u[1], t + u[1])
                    elif kind == 'year':
                        if 'y' not in r or r['y'] in ('', None): continue
                        y = int(float(r['y'])); v = (yr([str(y)]), ('%d BC' % (-y + 1)) if y <= 0 else str(y), str(y))
                    else:
                        if 'v' not in r: continue
                        v = (clean(r['v']), clean(r['v']), r['v'])
                except (TypeError, ValueError, KeyError):
                    continue
                if v not in d: d.append(v)
    for it in its:
        it.update(E.get(it['qid'], {})); it['F'] = F.get(it['qid'], {})

def _lc(d): return d[:1].lower() + d[1:] if d and not (len(d) > 1 and (d[1].isupper() or d[1].isdigit())) else d
def rich(facts):
    """fmt → (ru, en); facts: (key, prop, kind, ru_prefix, en_prefix, max_n)."""
    def f(it, l, d):
        ru, en = ['%s — %s.' % (cap(l), _lc(d).rstrip('.'))], []
        le, de = it.get('le', ''), it.get('de', '')
        if le and de and not re.search(r'wikimedia|disambiguation', de, re.I): en = ['%s — %s.' % (cap(le), de.rstrip('.'))]
        for key, prop, kind, pr, pe, n in facts:
            vs = it['F'].get(key, [])
            if kind in ('year', 'qty', 'str') and len({v[2] for v in vs}) != 1: continue   # only an unambiguous value
            if kind == 'qty' and vs[0][2] == 'bad': continue
            if kind == 'year' and re.search(r'\d{3,4}', d + ' ' + de): continue   # description already dates it; avoid conflicting dates
            if kind == 'item' and not (0 < len(vs) <= n): continue
            r_ = [v[0] for v in vs if v[0] and not re.match(r'^Q\d+$', v[0])]
            e_ = [v[1] for v in vs if v[1] and not re.match(r'^Q\d+$', v[1])]
            if r_ and len(r_) == len(vs) and pr: ru.append('%s: %s.' % (pr, ', '.join(r_)))
            if e_ and len(e_) == len(vs) and pe and en: en.append('%s: %s.' % (pe, ', '.join(e_)))
        def fit(parts):
            out = parts[0]
            for x in parts[1:]:
                if len(out) + 1 + len(x) <= 600: out += ' ' + x
            return out if len(out) <= 600 else ''
        return fit(ru), (fit(en) if en else '')
    return f
def rtrig(extra_ru=None, en_prefix=None):
    """RU triggers + optional EN. If en_prefix set (e.g. 'film '), only prefixed EN is added — bare EN titles steal person/place hits."""
    def t(it, l):
        tt = [l] + ([extra_ru % l] if extra_ru else [])
        le = it.get('le', '')
        if le and re.search(r'[A-Za-z]', le) and norm(le) != norm(l) and len(le) <= 60 and not re.search(r'[;|]', le):
            if en_prefix: tt.append(en_prefix + le)
            else: tt.append(le)
        return tt
    return t

def RS(cls, minsl, facts, trig, props=(), **opts):
    opts['facts'] = facts   # props: first-pass columns (kept only so the cached first-pass query stays identical)
    return S(cls, minsl, list(props), rich(facts), trig, **opts)

@sec('compounds')
def _():
    fx = [('f', 'P274', 'str', 'Формула', 'Formula', 1), ('m', 'P2067', 'qty', 'Молярная масса', 'Molar mass', 1),
          ('mp', 'P2101', 'qty', 'Температура плавления', 'Melting point', 1), ('bp', 'P2102', 'qty', 'Температура кипения', 'Boiling point', 1),
          ('use', 'P366', 'item', 'Применение', 'Use', 3), ('dis', 'P61', 'item', 'Открыл(и)', 'Discovered by', 2)]
    run('compounds', 'Химические вещества и соединения', 'Chemical compounds', [
        RS('wd:Q11173', 30, fx, rtrig('что такое %s'), props=[('f', 'wdt:P274', 'v')], path=PS, limit=2500, dre=r'соединени|вещество|кислот|оксид|соль|газ|спирт|углевод|кислота|амин|эфир|гидроксид|органическ|неорганическ|полимер|алкан|алкен|белок|гормон|витамин|жидкост|минерал', dno=r'фильм|альбом|песн|групп'),
    ])

@sec('particles')
def _():
    fx = [('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2), ('dis', 'P61', 'item', 'Открыл(и)', 'Discovered by', 2), ('y', 'P575', 'year', 'Открыта', 'Discovered', 1),
          ('sym', 'P416', 'str', 'Обозначение', 'Symbol', 1)]
    run('particles', 'Элементарные частицы и физические величины', 'Particles and physical quantities', [
        RS('wd:Q43116 wd:Q173078', 12, fx, rtrig('что такое %s'), path=P, limit=600, dre=r'частиц|бозон|фермион|лептон|кварк|адрон|мезон|барион|нейтрино|квазичастиц'),
        RS('wd:Q107715', 20, fx, rtrig('что такое %s'), path='(wdt:P31|wdt:P279)', limit=1000, dre=r'величин|характеристик|мера|параметр|отношени|скорост|энерги|сила|плотност|давлени|физическ'),
    ])

@sec('mathematics')
def _():
    fx = [('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2), ('pt', 'P361', 'item', 'Часть', 'Part of', 2), ('nm', 'P138', 'item', 'Названо в честь', 'Named after', 2),
          ('dis', 'P61', 'item', 'Открыл(и)', 'Discovered by', 2)]
    run('mathematics', 'Математические понятия', 'Mathematical concepts', [
        RS('wd:Q1936384 wd:Q173227', 20, fx, rtrig('что такое %s'), path='wdt:P31', limit=1000, dre=r'математ|геометр|алгебр|функци|числ|множеств|фигур|многоугольник|многогранник|операци|матриц|уравнени|кривая|поверхност|пространств|последовательност|теори|интеграл|производн|вектор|топологи', dno=r'фильм|альбом|песн'),
    ])

@sec('drugs')
def _():
    fx = [('tr', 'P2175', 'item', 'Применяется при', 'Used for', 3), ('f', 'P274', 'str', 'Формула', 'Formula', 1), ('dis', 'P61', 'item', 'Открыл(и)', 'Discovered by', 2),
          ('y', 'P575', 'year', 'Год открытия', 'Discovered', 1)]
    f = rich(fx)
    def g(it, l, d):
        ru, en = f(it, l, d)
        return (sent(ru, 'Справочная информация, не заменяет консультацию врача.') if ru else '', sent(en, 'Reference only, not medical advice.') if en else '')
    run('drugs', 'Лекарственные вещества (справочно)', 'Medicines (reference only)', [
        S('wd:Q12140', 40, [], g, rtrig('что такое %s'), facts=fx, path=PS, limit=1500, dre=r'лекарств|препарат|средств|антибиотик|анальгетик|гормон|витамин|вакцин|ингибитор|антагонист|агонист|противо|алкалоид|соединени|вещество', dno=r'фильм|альбом|песн|групп|наркотик'),
    ])

@sec('biomolecules')
def _():
    fx = [('sc', 'P279', 'item', 'Подкласс', 'Subclass of', 2), ('pt', 'P361', 'item', 'Часть', 'Part of', 2), ('dis', 'P61', 'item', 'Открыл(и)', 'Discovered by', 2)]
    run('biomolecules', 'Клетки, ткани и биомолекулы', 'Cells, tissues, biomolecules', [
        RS('wd:Q8054 wd:Q8047 wd:Q11364 wd:Q34956 wd:Q8066 wd:Q7187 wd:Q189094 wd:Q40397 wd:Q11367', 30, fx, rtrig('что такое %s'), path=PS, limit=1500, dre=r'белок|фермент|гормон|витамин|аминокислот|ген\b|клетк|органелл|ткан|молекул|нуклеот|кислот|рецептор|липид|углевод', dno=r'фильм|альбом|песн|групп|болезн|синдром'),
    ])

@sec('formats')
def _():
    fx = [('dev', 'P178', 'item', 'Разработчик', 'Developer', 2), ('y', 'P571', 'year', 'Появился', 'Introduced', 1), ('ext', 'P1195', 'str', 'Расширение файла', 'File extension', 1)]
    run('formats', 'Технологии, протоколы и форматы', 'Technologies, protocols, file formats', [
        RS('wd:Q235557 wd:Q15836568 wd:Q1331793 wd:Q192776 wd:Q8366', 25, fx, rtrig('что такое %s'), path=P, limit=1500, dre=r'формат|протокол|стандарт|алгоритм|технологи|интерфейс|спецификаци|кодек|сеть|шифр|кодировк', dno=r'фильм|альбом|песн|групп|компани'),
    ])

@sec('states')
def _():
    fx = [('cap', 'P36', 'item', 'Столица', 'Capital', 2), ('s', 'P571', 'year', 'Основано', 'Founded', 1), ('e', 'P576', 'year', 'Прекратило существование', 'Dissolved', 1),
          ('lang', 'P37', 'item', 'Официальный язык', 'Official language', 2)]
    run('states', 'Исторические государства и империи', 'Historical states and empires', [
        RS('wd:Q3024240 wd:Q48349 wd:Q1250464', 45, fx, rtrig('что такое %s'), props=[('s', 'wdt:P571', 'year'), ('e', 'wdt:P576', 'year')], path=P, limit=1500, dre=r'государств|импери|царств|королевств|княжеств|ханств|султанат|халифат|республик|династи|держав|конфедераци|союз', dno=r'фильм|альбом|песн|групп'),
    ])

@sec('battles')
def _():
    fx = [('y', 'P585', 'year', 'Год', 'Year', 1), ('pt', 'P361', 'item', 'Часть', 'Part of', 1), ('loc', 'P276', 'item', 'Место', 'Location', 1),
          ('par', 'P710', 'item', 'Участники', 'Participants', 3)]
    run('battles', 'Сражения и исторические события', 'Battles', [
        RS('wd:Q178561 wd:Q188055', 30, fx, rtrig('что такое %s'), props=[('y', 'wdt:P585', 'year')], path=P, limit=1500, maxyear=2019, dre=r'сражени|битв|осад|бой|штурм|операци', dno=r'фильм|альбом|песн|игр'),
    ])

ORDER += ['compounds', 'particles', 'mathematics', 'drugs', 'biomolecules', 'formats', 'states', 'battles']

if __name__ == '__main__':
    want = sys.argv[1:] or ORDER
    for k in ORDER:
        if k in want:
            try: SECTIONS[k]()
            except SystemExit as e: print('FAILED', k, e)
