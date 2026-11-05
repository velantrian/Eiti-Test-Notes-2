'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Rel = require('../../local/eiti_related.js');

const ROOT = path.join(__dirname, '../..');
const TITLE = 'Всеобщая декларация прав человека';
const PACKS = path.join(ROOT, 'kb', 'packs');

function udhr() {
  const entries = JSON.parse(fs.readFileSync(path.join(PACKS, 'kb_books_0.json'), 'utf8')).entries;
  const e = entries.kbl_books_7f9cc5;
  assert.ok(e, 'UDHR ID must not change');
  assert.equal(e.q[0], TITLE);
  return { ...e, title: 'Литература', title_en: 'Literature', gen: true };
}

test('Q7813 bilingual offline cards render adoption, not unverified publication', () => {
  const e = udhr();
  for (const view of [Rel.kbCard(e, 'ru'), Rel.kbDetailCard(e, [], 'ru')]) {
    assert.ok(view.includes('**Принята:** 10 декабря 1948 года'), view);
    assert.ok(!view.includes('**Опубликовано:** 1940'), view);
  }
  for (const view of [Rel.kbCard(e, 'en'), Rel.kbDetailCard(e, [], 'en')]) {
    assert.ok(view.includes('**Adopted:** 10 December 1948'), view);
    assert.ok(!view.includes('**Published:** 1940'), view);
  }
});

test('Q7813 linked snapshots are current and actually render from offline pack', () => {
  const e = udhr();
  assert.ok(e.rd && e.rd.length, 'new related snapshots must be present');
  const detail = Rel.kbDetailCard(e, [], 'en');
  assert.ok(detail.includes(e.rd[0].q[0]), 'offline detail must render a related snapshot');

  const index = JSON.parse(fs.readFileSync(path.join(ROOT, 'kb', 'index.json'), 'utf8'));
  assert.equal(index.count, 150000);
  let copies = 0;
  for (const name of index.domains.books.packs) {
    const entries = JSON.parse(fs.readFileSync(path.join(ROOT, 'kb', name), 'utf8')).entries;
    for (const rec of Object.values(entries)) {
      for (const snap of rec.rd || []) {
        if (snap.q?.[0] !== TITLE) continue;
        copies += 1;
        assert.equal(snap.a, e.a);
        assert.equal(snap.en, e.en);
      }
    }
  }
  assert.ok(copies >= 1, 'expect at least one embedded snapshot to test');
});
