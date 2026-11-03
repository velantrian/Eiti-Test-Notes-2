// v14.16.15: регионы первого уровня (kb/src/w_admin_regions.txt) — субъекты РФ, области, земли, штаты, провинции → карточка 📘 KB.
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const F = require(path.join(ROOT, 'local', 'eiti_frames.js'));
F.load(JSON.parse(fs.readFileSync(path.join(ROOT, 'local', 'eiti_frames.json'), 'utf8')));
const C = require(path.join(ROOT, 'kb', 'tests', 'concept.js'))();
const SRC = fs.readFileSync(path.join(ROOT, 'kb', 'src', 'w_admin_regions.txt'), 'utf8');
function pass(q) { const h = C.engine.search(q, 3); return Promise.resolve(h[0] && C.engine.confident(h[0]) ? '🧠 KB ' + h[0].id : null); }
const ask = (q) => F.respond(q, F.create(), { lookup: C.lookup, pass });

test('regions: questions about subdivisions return a 📘 KB card with centre and country', async () => {
  const cases = [
    ['расскажи о Татарстане', 'Казань'], ['что такое Свердловская область', 'Екатеринбург'], ['расскажи про Баварию', 'Мюнхен'],
    ['что такое Калифорния', 'Сакраменто'], ['расскажи о Якутии', 'Якутск'], ['что такое Краснодарский край', 'Краснодар'],
  ];
  for (const [q, c] of cases) {
    const r = String(await ask(q));
    assert.match(r, /^📘 /, q + ' → ' + r.slice(0, 80));
    assert.ok(r.indexOf(c) >= 0, q + ' → ' + r.slice(0, 160));
  }
  // города не перехвачены регионами
  assert.match(String(await ask('расскажи о Москве')), /^📘 \*\*Москва\*\*[\s\S]*столица/);
});

test('regions: all 89 Russian federal subjects, cyrillic only, no invented population', () => {
  const lines = SRC.split('\n').filter((l) => l && !l.startsWith('#'));
  const ru = lines.filter((l) => /субъект Российской Федерации|считает её субъектом РФ/.test(l.split('||')[1]));
  assert.strictEqual(ru.length, 89, 'Russian federal subjects');
  for (const l of lines) {
    for (const w of l.split(/\s+/)) assert.ok(!(/[а-яё]/i.test(w) && /[a-z]/i.test(w)), 'mixed latin/cyrillic word: ' + w);
    assert.doesNotMatch(l.split('||')[1], /населени|жител/i, 'no population figures');
  }
});
