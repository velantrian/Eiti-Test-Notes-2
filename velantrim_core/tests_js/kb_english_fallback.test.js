const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const R = require(path.join(__dirname, '../../local/eiti_related.js'));

test('an English placeholder must not conceal original facts or related snapshots', () => {
  const e = {
    q: ['что такое Нидерланды'],
    a: 'Нидерланды — государство. Столица (P36): Амстердам.',
    en: 'Нидерланды — Wikidata entry; English description is unavailable in this preserved card.',
    title: 'Энциклопедические темы', title_en: 'Encyclopedia topics', gen: true,
    r: ['linked-Denmark'],
    rd: [{
      q: ['что такое Дания'],
      a: 'Дания — государство. Столица (P36): Копенгаген.',
      en: 'Дания — Wikidata entry; English description is unavailable.',
    }],
    f: { origin: 'Wikidata CC0; Q55; https://www.wikidata.org/wiki/Q55', verify: 'Verify P36 on Q55.' },
  };
  for (const card of [R.kbCard(e, 'en'), R.kbDetailCard(e, [], 'en')]) {
    assert.match(card, /No substantive English answer/);
    assert.match(card, /Столица \(P36\):(?:\*\*)? Амстердам/);
    assert.doesNotMatch(card, /Wikidata entry; English description is unavailable/);
    assert.match(card, /Source:/);
  }
  const detail = R.kbDetailCard(e, [], 'en');
  assert.match(detail, /Дания/);
  assert.match(detail, /Копенгаген/);
  assert.match(detail, /Wikidata CC0/);
  assert.match(detail, /Q55/);
});

test('missing English is disclosed and a substantive English answer is still preferred', () => {
  const e = {
    q: ['Франция'], a: 'Франция — государство. Столица: Париж.',
    en: 'France — country in Western Europe. Capital: Paris. ISO code: FR.',
    title_en: 'Countries', title: 'Страны мира', gen: true,
  };
  assert.match(R.kbDetailCard(e, [], 'en'), /Capital: Paris/);
  assert.doesNotMatch(R.kbDetailCard(e, [], 'en'), /No substantive English answer/);
  delete e.en;
  const fallback = R.kbDetailCard(e, [], 'en');
  assert.match(fallback, /No substantive English answer/);
  assert.match(fallback, /Столица: Париж/);
});
