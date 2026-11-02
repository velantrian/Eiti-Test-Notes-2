#!/usr/bin/env python3
"""Prioritized, source-grounded world entities for the lazy Wikidata longtail.

Records are selected only through explicit Wikidata class ancestry (P31/P279),
with facts copied only from direct properties. This is a broad, non-exhaustive
reference layer, not a legal or official register of every place or institution.
"""
import re
from collections import Counter, defaultdict, deque

from gen_kb import cap, clean, desc, lab, ok_label, q_items, sent, yr
from gen_more import BADL, GENERIC, NOISE, SEEN, known, norm

START_LABEL = re.compile(r'^[a-zа-яё0-9]', re.I)
SENSITIVE = re.compile(
    r'порно|порнограф|порностуд|эротическ|porn|adult website|fuck|shit|cunt|'
    r'на хуй|нахуй|бляд|пизд|ебал|ебат', re.I
)
CLASS_PATH = 'wdt:P31/wdt:P279*'
ADMIN_SIGNAL = re.compile(
    r'административ|департамент|субъект.{0,30}федерац|автономн.{0,25}округ|'
    r'провинц|област|округ|графств|муниципал|район|штат|кантон|'
    r'\badministrative\b|\bdistrict\b|\bcounty\b|\bprovince\b|\bprefecture\b|'
    r'\bdepartment\b|\bregion\b|\bautonomous\b|\bcanton\b', re.I
)


def _linked_fact(prefix, values, limit=6):
    items = sorted({clean(value) for value in values if clean(value)}, key=norm)
    if not items:
        return ''
    suffix = ', и другие' if len(items) > limit else ''
    return prefix + ', '.join(items[:limit]) + suffix + '.'

# Quotas are prioritization ceilings, not claims of completeness. More candidate
# rows than each ceiling are requested so existing KB duplicates can be skipped.
WORLD_GROUPS = (
    {
        'key': 'countries', 'classes': 'wd:Q6256', 'basis': 'Q6256',
        'quota': 2000, 'page_size': 20000, 'max_pages': 4, 'kind': 'Страна или территория',
        'kind_en': 'country or territory',
        'minsl': 1, 'en': True,
        'short': 'Класс: страна или территория по Wikidata Q6256; независимость не предполагается.',
        'props': [('capital', 'wdt:P36', 'label'), ('continent', 'wdt:P30', 'label')],
        'facts': lambda it: [lab('Столица (P36): ', it['capital'], 1),
                             lab('Часть света (P30): ', it['continent'], 1)],
        'fallback': 'территориальное или политическое образование, отнесённое Wikidata к классу страны; этот класс может включать зависимости и особые территории',
        'why': 'Выбор по пути P31/P279 к Q6256; столица и часть света приводятся только при наличии прямых P36/P30. Класс сам по себе не подтверждает суверенитет или международное признание.',
    },
    {
        'key': 'places', 'classes': 'wd:Q515 wd:Q486972', 'basis': 'Q515/Q486972',
        'quota': 16000, 'page_size': 20000, 'max_pages': 4, 'kind': 'Город или населённое место',
        'kind_en': 'city or populated place',
        'short': 'Класс: город или населённое место по Wikidata Q515/Q486972.',
        'props': [('country', 'wdt:P17', 'label'), ('parent', 'wdt:P131', 'label')],
        'facts': lambda it: [lab('Страна (P17): ', it['country'], 1),
                             lab('Административно входит в (P131): ', it['parent'], 1)],
        'fallback': 'город или место постоянного проживания людей, классифицированное Wikidata как населённое место',
        'why': 'Выбор по пути P31/P279 к Q515/Q486972; страна и административная принадлежность берутся только из прямых P17/P131. Это не утверждение о границах или статусе города.',
    },
    {
        'key': 'admin1', 'classes': 'wd:Q10864048', 'basis': 'Q10864048',
        'quota': 8000, 'page_size': 20000, 'max_pages': 4, 'kind': 'Административная единица первого уровня (ADM1)',
        'kind_en': 'first-level administrative division',
        'minsl': 1, 'en': True,
        'short': 'Класс: административная единица первого уровня (ADM1), Wikidata Q10864048.',
        'props': [('country', 'wdt:P17', 'label'), ('parent', 'wdt:P131', 'label')],
        'facts': lambda it: [lab('Страна (P17): ', it['country'], 1),
                             lab('Входит в (P131): ', it['parent'], 1)],
        'fallback': 'административное деление первого уровня, напрямую подчинённое национальному правительству по описанию класса Wikidata',
        'why': 'Выбор по пути P31/P279 к Q10864048 (ADM1); страна и родительская территория добавляются только из прямых P17/P131. Национальные названия и полномочия могут различаться.',
    },
    {
        'key': 'admin2', 'classes': 'wd:Q56061', 'basis': 'Q56061 с прямым P131 к Q10864048',
        'quota': 9000, 'page_size': 16000, 'max_pages': 4,
        'kind': 'Административная единица с прямым родителем ADM1; местный ранг следует проверить',
        'kind_en': 'administrative division with an ADM1 parent',
        'short': 'Класс: административная единица с прямым родителем ADM1; точный национальный уровень не гарантирован.',
        'props': [('country', 'wdt:P17', 'label'), ('parent', 'wdt:P131', 'label')],
        'facts': lambda it: [lab('Страна (P17): ', it['country'], 1),
                             lab('Входит в (P131): ', it['parent'], 1)],
        'extra': ('?x wdt:P131 ?parent2 . ?parent2 wdt:P31/wdt:P279* wd:Q10864048 . '
                  'FILTER NOT EXISTS { ?x wdt:P31/wdt:P279* wd:Q515 } '
                  'FILTER NOT EXISTS { ?x wdt:P31/wdt:P279* wd:Q486972 } '
                  'FILTER NOT EXISTS { ?x wdt:P31/wdt:P279* wd:Q15284 }'),
        'minsl': 1, 'en': True, 'require_admin_signal': True,
        'fallback': 'административная единица, чей прямой родитель в Wikidata размечен как ADM1; точный местный юридический уровень не гарантирован',
        'why': 'Выбор по P31/P279 к Q56061 и прямой P131 к родителю класса Q10864048 (ADM1); это кандидат на подчинённую местную единицу, а не универсальное юридическое утверждение об ADM2. Страна и родитель берутся из прямых P17/P131.',
    },
    {
        'key': 'municipalities', 'classes': 'wd:Q15284', 'basis': 'Q15284',
        'quota': 12000, 'page_size': 16000, 'max_pages': 4, 'kind': 'Муниципалитет',
        'kind_en': 'municipality',
        'short': 'Класс: муниципалитет по Wikidata Q15284; полномочия зависят от страны.',
        'props': [('country', 'wdt:P17', 'label'), ('parent', 'wdt:P131', 'label')],
        'facts': lambda it: [lab('Страна (P17): ', it['country'], 1),
                             lab('Входит в (P131): ', it['parent'], 1)],
        'fallback': 'административная единица с корпоративным статусом, обычно обладающая местным самоуправлением или юрисдикцией согласно описанию класса Wikidata',
        'why': 'Выбор по пути P31/P279 к Q15284; страна и родительская территория берутся только из прямых P17/P131. Юридические полномочия муниципалитета зависят от национального права.',
    },
    {
        'key': 'admin_units', 'classes': 'wd:Q56061', 'basis': 'Q56061',
        'quota': 2500, 'page_size': 12000, 'max_pages': 4,
        'kind': 'Административно-территориальная единица',
        'kind_en': 'administrative division',
        'short': 'Класс: административная территория по Wikidata Q56061; уровень следует сверять по стране.',
        'props': [('country', 'wdt:P17', 'label'), ('parent', 'wdt:P131', 'label')],
        'facts': lambda it: [lab('Страна (P17): ', it['country'], 1),
                             lab('Входит в (P131): ', it['parent'], 1)],
        'fallback': 'территориальная единица для административных целей, с местным самоуправлением или без него по описанию класса Wikidata',
        'why': 'Выбор по пути P31/P279 к Q56061; страна и родительская территория добавляются только из прямых P17/P131. Конкретное название и уровень проверяйте по официальному реестру страны.',
    },
    {
        'key': 'institutions',
        'classes': ('wd:Q3914 wd:Q16917 wd:Q31855 wd:Q327333 wd:Q7075 wd:Q3918 wd:Q33506 '
                    'wd:Q24354 wd:Q861951 wd:Q1195942 wd:Q1137809 wd:Q43501 wd:Q1254933 wd:Q167346 wd:Q35054 wd:Q1248784'),
        'basis': 'школа/больница/исследовательский институт/госорган/библиотека/университет/музей/театр/полицейский участок/пожарная часть/здание суда/зоопарк/обсерватория/ботанический сад/почта/аэропорт',
        'quota': 12000, 'page_size': 20000, 'max_pages': 4,
        'kind': 'Учреждение или объект общественной инфраструктуры конкретного типа',
        'kind_en': 'institution or public facility',
        'short': 'Класс: учреждение конкретного типа по Wikidata P31/P279.',
        'props': [('country', 'wdt:P17', 'label'), ('parent', 'wdt:P131', 'label'),
                  ('founded', 'wdt:P571', 'year')],
        'facts': lambda it: [lab('Страна (P17): ', it['country'], 1),
                             lab('Расположено в (P131): ', it['parent'], 1),
                             ('Основано: %s.' % yr(it['founded'])) if yr(it['founded']) else ''],
        'fallback': 'учреждение или общественный объект, отнесённый Wikidata к типу школы, больницы, исследовательского института, госоргана, библиотеки, университета, музея, театра, полицейского участка, пожарной части, здания суда, зоопарка, обсерватории, ботанического сада, почты или аэропорта',
        'why': 'Выбор по P31/P279 от типа школы, больницы, исследовательского института, госоргана, библиотеки, университета, музея, театра, полицейского участка, пожарной части, здания суда, зоопарка, обсерватории, ботанического сада, почты или аэропорта. Место и год указываются только по прямым P131/P571.',
    },
    {
        'key': 'organizations', 'classes': 'wd:Q43229', 'basis': 'Q43229',
        'quota': 7000, 'page_size': 20000, 'max_pages': 4, 'kind': 'Организация',
        'kind_en': 'organization',
        'short': 'Класс: организация по Wikidata Q43229; запись не подтверждает текущую регистрацию.',
        'props': [('country', 'wdt:P17', 'label'), ('hq', 'wdt:P159', 'label'),
                  ('founded', 'wdt:P571', 'year')],
        'facts': lambda it: [lab('Страна (P17): ', it['country'], 1),
                             lab('Штаб-квартира (P159): ', it['hq'], 1),
                             ('Основана: %s.' % yr(it['founded'])) if yr(it['founded']) else ''],
        'fallback': 'социальная сущность, созданная для удовлетворения потребностей или достижения целей, по описанию класса Wikidata',
        'why': 'Выбор по пути P31/P279 к Q43229; страна, штаб-квартира и дата основания берутся только из прямых P17/P159/P571. Это не подтверждение действующей регистрации или текущей деятельности.',
    },
    {
        'key': 'peoples', 'classes': 'wd:Q41710', 'basis': 'Q41710 (прямой P31)',
        'quota': 8000, 'page_size': 10000, 'max_pages': 1, 'kind': 'Народ или этническая группа',
        'kind_en': 'people or ethnic group',
        'minsl': 1, 'en': True, 'cls_path': 'wdt:P31',
        'short': 'Класс: народ/этническая группа по прямому P31=Q41710.',
        'props': [('country', 'wdt:P17', 'label'), ('parent', 'wdt:P131', 'label')],
        'facts': lambda it: [_linked_fact('Страны, записанные в Wikidata (P17; не полный список расселения): ', it['country'], 6),
                             _linked_fact('Административные территории по P131: ', it['parent'], 4)],
        'fallback': 'народ или этническая группа, классифицированная Wikidata прямым P31=Q41710',
        'why': 'Отбор только по прямому P31=Q41710 (не транзитивному P279); страны P17 и административные территории P131 — записанные Wikidata-связи, а не полный перечень расселения.',
        'verify_rule': 'прямому P31=Q41710',
    },
)


def _field_text(group, qid, label, source_description):
    page = 'https://www.wikidata.org/wiki/' + qid
    relation = group.get('verify_rule', 'P31/P279')
    detail = ('описание Wikidata: «%s»' % source_description if source_description else
              'русское описание Wikidata отсутствует; ответ ограничен классификацией и прямыми фактами')
    why = 'Карточка «%s»: %s. Объект отобран по %s; %s.' % (
        label, detail, relation, group['why'])
    return ('@short: %s | why: %s | origin: Открытые данные Wikidata, лицензия CC0; '
            'идентификатор %s; страница %s. | verify: Сверить название «%s», описание, тип по %s к %s, '
            'прямые свойства и первоисточники; юридический статус проверить у официального органа.') % (
                group['short'], why, qid, page, label, relation, group['basis'])


def _answer(group, item, label, description):
    facts = group['facts'](item)
    return sent('%s — %s.' % (cap(label), description.rstrip('.')), *facts,
                'Тип сущности: %s.' % group['kind'])


def _interleave_by_country(items):
    """Round-robin candidate rows by recorded P17 label to reduce popular-country bias."""
    buckets = defaultdict(deque)
    for item in items:
        countries = sorted({norm(clean(x)) for x in item.get('country', []) if clean(x)})
        buckets[countries[0] if countries else '~unknown'].append(item)
    keys = sorted(buckets, key=lambda key: (key == '~unknown', key))
    out = []
    while any(buckets[key] for key in keys):
        for key in keys:
            if buckets[key]:
                out.append(buckets[key].popleft())
    return out


def _select_group(group, items, quota, seen_triggers, seen_answers, added_labels, hand_words):
    unique = {}
    for item in items:
        qid = item.get('qid', '')
        if qid and qid not in unique:
            unique[qid] = item
    items = _interleave_by_country(list(unique.values()))
    ambiguous = Counter(norm(it.get('l', '')) for it in items)
    trial_triggers = dict(seen_triggers)
    trial_answers = set(seen_answers)
    trial_labels = set(added_labels)
    records = []
    accepted = 0
    for item in items:
        label = clean(item.get('l', '')).strip()
        if not label or not ok_label(label) or not START_LABEL.match(label):
            continue
        if len(label) > 60 or BADL.search(label) or GENERIC.search(label):
            continue
        if NOISE.search(label) or SENSITIVE.search(label):
            continue
        label_key = norm(label)
        if not label_key or ambiguous[label_key] > 1:
            continue
        if label_key in trial_labels or label_key in SEEN or known(label_key):
            continue
        if len(label_key.split()) == 1 and label_key in hand_words:
            continue

        source_description = desc(item)
        if group.get('require_admin_signal') and not ADMIN_SIGNAL.search(label + ' ' + source_description):
            continue
        description = source_description or group['fallback']
        if NOISE.search(description) or SENSITIVE.search(description):
            continue
        answer = _answer(group, item, label, description)
        if len(answer) < 25 or len(answer) > 600:
            continue
        trigger = 'что такое ' + label
        trigger_key = norm(trigger)
        answer_key = norm(answer)
        if trigger_key in trial_triggers or answer_key in trial_answers:
            continue

        qid = item.get('qid', '')
        if not re.fullmatch(r'Q\d+', qid):
            continue
        english_label = clean(item.get('en', '')) or label
        english_description = desc({'d': clean(item.get('den', ''))})
        english_answer = ('%s — %s. Entity type: %s.' %
                          (cap(english_label), english_description.rstrip('.'),
                           group.get('kind_en', 'Wikidata-classified entity')) if english_description else
                          '%s — Wikidata-classified %s.' %
                          (cap(english_label), group.get('kind_en', 'entity')))
        records.append((trigger, answer, english_answer,
                        _field_text(group, qid, label, source_description)))
        trial_triggers[trigger_key] = 'world_%s:%d' % (group['key'], accepted + 1)
        trial_answers.add(answer_key)
        trial_labels.add(label_key)
        accepted += 1
        if accepted >= quota:
            break
    return records, trial_triggers, trial_answers, trial_labels, accepted


def generate_world_entities(needed, seen_triggers, seen_answers, added_labels, hand_words, people_items=None):
    """Return priority tuples (trigger, answer, fields), updating shared dedupe sets."""
    records = []
    for group in WORLD_GROUPS:
        quota = min(group['quota'], needed - len(records))
        if quota <= 0:
            break
        limit = min(20_000, group.get('page_size', quota * 2))
        max_pages = max(1, group.get('max_pages', 1))
        print('Wikidata world group %s: requesting up to %d candidates per page' % (group['key'], limit), flush=True)
        query_args = (group['classes'], group.get('minsl', 5), group['props'])
        query_kw = dict(extra=group.get('extra', ''), limit=limit,
                        cls_path=group.get('cls_path', CLASS_PATH), en=group.get('en', True))
        if group['key'] == 'peoples' and people_items is not None:
            page_items = list(people_items)
        else:
            try:
                page_items = q_items(*query_args, offset=0, **query_kw)
            except SystemExit as exc:
                print('Wikidata initial page unavailable for %s; skipping new candidates and keeping prior generated cards (%s)' %
                      (group['key'], exc), flush=True)
                continue
        all_items = list(page_items)
        group_records, trial_triggers, trial_answers, trial_labels, accepted = _select_group(
            group, all_items, quota, seen_triggers, seen_answers, added_labels, hand_words)
        page_no, offset = 1, len(page_items)
        while len(group_records) < quota and page_no < max_pages and page_items:
            try:
                page_items = q_items(*query_args, offset=offset, **query_kw)
            except SystemExit as exc:
                print('Wikidata optional page unavailable for %s; keeping prior candidates (%s)' %
                      (group['key'], exc), flush=True)
                break
            if not page_items:
                break
            all_items.extend(page_items)
            group_records, trial_triggers, trial_answers, trial_labels, accepted = _select_group(
                group, all_items, quota, seen_triggers, seen_answers, added_labels, hand_words)
            print('Wikidata world group %s: page offset=%d, candidates=%d' %
                  (group['key'], offset, len(page_items)), flush=True)
            offset += len(page_items)
            page_no += 1
        records.extend(group_records)
        seen_triggers.clear(); seen_triggers.update(trial_triggers)
        seen_answers.clear(); seen_answers.update(trial_answers)
        added_labels.clear(); added_labels.update(trial_labels)
        print('Wikidata world group %s: accepted %d / %d' % (group['key'], accepted, quota), flush=True)
    return records
