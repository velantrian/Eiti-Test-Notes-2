#!/usr/bin/env python3
"""v14.16.15: kb/src/w_admin_regions.txt из ручной таблицы kb/gen/regions_data.py (регионы первого уровня + их центры).
Триггеры, уже занятые другими файлами KB, отбрасываются (кроме STEAL), чтобы не перехватывать города и страны."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regions_data import *
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, 'src'); OUT = os.path.join(SRC, 'w_admin_regions.txt')
STEAL = {'бавария'}   # «Бавария» — футбольный клуб в w_sports; запрос о земле важнее
# v14.16.18: English answers for offline reasoning (same curated facts, no invented data).
COUNTRY_EN = {
    'Россия': 'Russia', 'Украина': 'Ukraine', 'Беларусь': 'Belarus', 'Казахстан': 'Kazakhstan',
    'Германия': 'Germany', 'США': 'United States', 'Китай': 'China', 'Индия': 'India',
    'Канада': 'Canada', 'Бразилия': 'Brazil', 'Франция': 'France', 'Италия': 'Italy',
    'Испания': 'Spain', 'Польша': 'Poland', 'Япония': 'Japan',
}
KIND_EN = {
    'республика': 'republic', 'область': 'oblast', 'край': 'krai',
    'автономная область': 'autonomous oblast', 'автономный округ': 'autonomous okrug',
    'федеральная земля': 'federal state', 'штат': 'state', 'провинция': 'province',
    'автономный район': 'autonomous region', 'территория': 'territory',
    'регион': 'region', 'область (регион)': 'region', 'автономное сообщество': 'autonomous community',
    'воеводство': 'voivodeship', 'префектура': 'prefecture',
    'префектура (губернаторство)': 'prefecture',
}
norm = lambda s: re.sub(r'\s+', ' ', re.sub(r'[^a-zа-я0-9+#²³ ]+', ' ', s.lower().replace('ё', 'е'))).strip()
taken = set(); taken_all = set()
for fn in os.listdir(SRC):
    if not fn.endswith('.txt') or fn == 'w_admin_regions.txt': continue
    for line in open(os.path.join(SRC, fn), encoding='utf-8'):
        if line.startswith('#') or '||' not in line: continue
        for t in line.split('||')[0].split(';'):
            t = re.sub(r'^\d+:', '', t.strip())
            if t:
                taken_all.add(norm(t))
                if not fn.startswith('w_longtail_'): taken.add(norm(t))   # слабые longtail-карточки уступают регионам
rows, mine, stats = [], set(), {}
def add(country, trig, ans, short, verify, en=''):
    q = []
    for t in trig:
        n = norm(t)
        if not n or n in mine or (n in taken and n not in STEAL): continue
        mine.add(n); q.append(t)
    if not q: return False
    mid = (' || %s' % en) if en else ''
    rows.append('%s || %s%s || @short: %s | origin: ручная таблица kb/gen/regions_data.py (официальные названия и центры регионов, сверка с Википедией и Wikidata, ноябрь 2026); численность не указана намеренно. | verify: %s' % ('; '.join(q), ans, mid, short, verify))
    stats[country] = stats.get(country, 0) + 1; return True
caps = []   # (город, регион в род. падеже/описание, страна)
def reg(country, full, alias, kind, center, extra, where, cityof=None):
    tr = [full] + alias + ['что такое ' + full]
    ans = '%s — %s%s. Административный центр: %s. Страна: %s.%s' % (full, kind, where, center, country, (' ' + extra) if extra else '')
    ans = ans[0].upper() + ans[1:]
    ce, ke = COUNTRY_EN.get(country, country), KIND_EN.get(kind, kind)
    en = '%s — %s of %s. Administrative centre: %s. Country: %s.' % (full, ke, ce, center, ce)
    add(country, tr, ans, '%s, %s; центр — %s.' % (kind, country, center),
        'Сверить статус и центр «%s» с официальными источниками страны %s.' % (full, country), en=en)
    if cityof: caps.append((center, cityof, country))
for full, al, kind, c, fd, note in RU:
    reg('Россия', full, al, kind, c, note, ', субъект Российской Федерации в составе %s федерального округа' % FD[fd], full)
for n, c, fd in OBL:
    full = n + ' область'
    reg('Россия', full, [n[:-2] + 'ая обл.'] if False else OBL_ALIAS.get(n, []), 'область', c, OBL_NOTE.get(n, ''), ', субъект Российской Федерации в составе %s федерального округа' % FD[fd], full)
for c, fd in FEDCITY:
    note = (' Включён в состав России по законодательству РФ в 2014 году; большинство государств — членов ООН считают его частью Украины.') if c == 'Севастополь' else ''
    add('Россия', ['город федерального значения ' + c, 'субъект ' + c],
        '%s — город федерального значения, субъект Российской Федерации в составе %s федерального округа. Страна: Россия.%s' % (c, FD[fd], note),
        'город федерального значения России.', 'Сверить со статьёй 65 Конституции РФ.',
        en='%s — federal city of Russia, a federal subject. Country: Russia.' % c)
for full, al, kind, c, fd in AO:
    reg('Россия', full, al, kind, c, '', ', субъект Российской Федерации в составе %s федерального округа' % FD[fd], full)
for n, c in UA:
    reg('Украина', n + ' область', [], 'область', c, UA_NOTE.get(n, ''), ' Украины', n + ' область')
for n, c, note in UA_RU:
    reg('Украина', n + ' область', [], 'область', c, 'С 2022 года Россия по своему законодательству считает её субъектом РФ в составе Южного федерального округа; большинство государств — членов ООН признают её частью Украины. ' + note, ' на юге Украины', n + ' область')
add('Украина', ['Автономная Республика Крым', 'АР Крым'],
    'Автономная Республика Крым — по законодательству Украины автономная республика в её составе. Центр: Симферополь. С 2014 года территорию контролирует Россия, считающая её Республикой Крым.',
    'автономная республика в составе Украины по её законодательству.',
    'Сверить с Конституцией Украины и резолюцией ГА ООН 68/262.',
    en='Autonomous Republic of Crimea — autonomous republic within Ukraine under Ukrainian law; centre: Simferopol. Since 2014 the territory has been controlled by Russia, which treats it as the Republic of Crimea.')
add('Украина', ['город со специальным статусом Киев'],
    'Киев — столица Украины, город со специальным статусом, не входит в Киевскую область. Страна: Украина.',
    'город со специальным статусом.', 'Сверить с Конституцией Украины.',
    en='Kyiv — capital of Ukraine, a city with special status, not part of Kyiv Oblast. Country: Ukraine.')
for n, c in BY:
    reg('Беларусь', n + ' область', [], 'область', c, 'Минск — отдельная административная единица и в область не входит.' if n == 'Минская' else '', ' Беларуси', n + ' область')
for n, c, al in KZ:
    reg('Казахстан', n + ' область', al, 'область', c, 'Образована в 2022 году.' if n in KZ_NEW else ('Центр перенесён в Конаев в 2022 году.' if n == 'Алматинская' else ''), ' Казахстана', n + ' область')
for c in ('Астана', 'Алматы', 'Шымкент'):
    add('Казахстан', ['город республиканского значения ' + c],
        '%s — город республиканского значения Казахстана, отдельная административная единица первого уровня. Страна: Казахстан.' % c,
        'город республиканского значения.', 'Сверить с административным делением Казахстана.',
        en='%s — city of republican significance in Kazakhstan, a first-level administrative unit. Country: Kazakhstan.' % c)
for n, c in DE:
    reg('Германия', n, ['земля ' + n, 'федеральная земля ' + n], 'федеральная земля', c, '', ' Германии', 'земля ' + n)
for c in DE_CITY:
    add('Германия', ['земля ' + c, 'федеральная земля ' + c],
        '%s — город-земля, одна из 16 федеральных земель Германии. Страна: Германия.' % c,
        'город-земля Германии.', 'Сверить с Основным законом ФРГ.',
        en='%s — city-state, one of the 16 federal states of Germany. Country: Germany.' % c)
for n, c in US:
    reg('США', 'штат ' + n, [n], 'штат', c, '', ' Соединённых Штатов Америки', None)
for n, c, k in CN:
    full = n if 'район' in n else n
    reg('Китай', full, CN_ALIAS.get(n, []) + ([('провинция ' + n)] if k == 'провинция' else []), k, c, '', ' Китайской Народной Республики', None)
for n, c in IN:
    reg('Индия', 'штат ' + n, [n], 'штат', c, 'Чандигарх — общая столица штатов Пенджаб и Харьяна, сам является союзной территорией.' if c == 'Чандигарх' else '', ' Индии', None)
for n, c, k in CA:
    reg('Канада', n, [k + ' ' + n], k, c, '', ' Канады', None)
for n, c in BR:
    reg('Бразилия', 'штат ' + n, [n], 'штат', c, '', ' Бразилии', None)
add('Бразилия', ['Федеральный округ Бразилии'],
    'Федеральный округ — особая административная единица Бразилии, где находится столица страны Бразилиа. Страна: Бразилия.',
    'федеральный округ Бразилии.', 'Сверить с Конституцией Бразилии.',
    en='Federal District — special administrative unit of Brazil that contains the capital Brasília. Country: Brazil.')
for n, c in FR:
    reg('Франция', n, ['регион ' + n], 'регион', c, '', ' Франции (один из 13 регионов метрополии с 2016 года)', None)
for n, c in IT:
    reg('Италия', n, ['область ' + n, 'регион ' + n], 'область (регион)', c, '', ' Италии', None)
for n, c in ES:
    reg('Испания', 'автономное сообщество ' + n if n in ('Мадрид', 'Мурсия', 'Валенсия') else n, ['автономное сообщество ' + n], 'автономное сообщество', c, '', ' Испании', None)
for n, c in PL:
    reg('Польша', n + ' воеводство', [], 'воеводство', c, '', ' Польши', None)
for n, c in list(JP_DIFF.items()) + [(s, s) for s in JP_SAME]:
    reg('Япония', 'префектура ' + n, [n] if n != c else [], 'префектура' if n != 'Хоккайдо' else 'префектура (губернаторство)', c, '', ' Японии', None)
# центры регионов как отдельные города, если их ещё нет в KB
cities = 0
for city, of, country in caps:
    if norm(city) in taken_all or norm('город ' + city) in taken_all or norm('что такое ' + city) in taken_all: continue
    ce = COUNTRY_EN.get(country, country)
    if add(country + ' (города)', [city, 'город ' + city],
           '%s — город, административный центр: %s. Страна: %s.' % (city, of, country),
           'город, центр региона «%s».' % of, 'Сверить статус центра «%s» с официальными источниками.' % of,
           en='%s — city, administrative centre of %s. Country: %s.' % (city, of, ce)):
        cities += 1
open(OUT, 'w', encoding='utf-8').write('# Регионы и области мира | Regions and subdivisions\n# @generated by kb/gen/gen_regions.py from the curated table kb/gen/regions_data.py — do not edit by hand\n' + '\n'.join(rows) + '\n')
for k, v in stats.items(): print(k, v)
print('total', len(rows))