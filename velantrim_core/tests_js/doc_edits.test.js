// v14.16.32: точечные правки длинных текстов (local/eiti_doc_edits.js)
const test = require('node:test');
const assert = require('node:assert');
const E = require('../../local/eiti_doc_edits.js');

const long = Array.from({ length: 400 }, (_, i) => `Абзац ${i}: текст про «тему» номер ${i} — важно.`).join('\n\n');

test('edits apply atomically: exact + fuzzy (quotes, dashes, spaces)', () => {
  const r = E.applyEdits(long, [
    { find: 'Абзац 7: текст', text: 'Абзац 7 (исправлен): текст' },
    { find: 'про "тему" номер 250 - важно.', text: 'про тему 250.' },
  ]);
  assert.equal(r.ok, true);
  assert.equal(r.count, 2);
  assert.equal(r.fuzzy, 1);
  assert.ok(r.body.includes('Абзац 7 (исправлен): текст'));
  assert.ok(r.body.includes('Абзац 250: текст про тему 250.'));
  assert.equal(r.body.length, long.length + 'Абзац 7 (исправлен): текст'.length - 'Абзац 7: текст'.length + 'про тему 250.'.length - 'про «тему» номер 250 — важно.'.length);
});

test('one missing fragment → nothing changes', () => {
  const r = E.applyEdits(long, [{ find: 'Абзац 1: текст', text: 'X' }, { find: 'нет такого', text: 'Y' }]);
  assert.equal(r.ok, false);
  assert.match(r.message, /не найден/);
});

test('ambiguous fragment needs occurrence or all', () => {
  const t = 'кот и кот';
  assert.equal(E.applyEdits(t, [{ find: 'кот', text: 'пёс' }]).ok, false);
  assert.equal(E.applyEdits(t, [{ find: 'кот', text: 'пёс', occurrence: 2 }]).body, 'кот и пёс');
  assert.equal(E.applyEdits(t, [{ find: 'кот', text: 'пёс', all: true }]).body, 'пёс и пёс');
});

test('overlapping edits rejected; append at end', () => {
  assert.equal(E.applyEdits('abcdef', [{ find: 'abc', text: 'x' }, { find: 'bcd', text: 'y' }]).ok, false);
  assert.equal(E.applyEdits('abc', [{ text: 'END', position: 'end' }]).body, 'abc\n\nEND');
});

test('diff hunks per paragraph; accept/reject each; round-trip', () => {
  const before = 'A\n\nB\n\nC\n\nD';
  const after = 'A\n\nB2\n\nC\n\nD\n\nE';
  const h = E.diffHunks(before, after);
  assert.equal(h.length, 2);
  assert.equal(E.applyHunks(before, h), after);
  assert.equal(E.applyHunks(before, h, () => false), before);
  assert.equal(E.applyHunks(before, h, (x) => x.id === 0), 'A\n\nB2\n\nC\n\nD');
  assert.equal(E.changedParagraphs(h), 3); // B→B2 (1) + «D» → «D, E» (2)
});

test('diff of a 400-paragraph text with 3 edits gives 3 hunks', () => {
  const r = E.applyEdits(long, [{ find: 'Абзац 3:', text: 'Абзац III:' }, { find: 'Абзац 200:', text: 'Абзац CC:' }, { find: 'Абзац 399:', text: 'Абзац last:' }]);
  const h = E.diffHunks(long, r.body);
  assert.equal(h.length, 3);
  assert.equal(E.applyHunks(long, h), r.body);
});

test('range edit from…to replaces a whole section without repeating it', () => {
  const t = '# A\nстарый раздел один\nконец A\n\n# B\nраздел два\nконец B';
  const r = E.applyEdits(t, [{ from: '# A', to: 'конец A', text: '# A\nновый раздел' }]);
  assert.equal(r.ok, true);
  assert.equal(r.body, '# A\nновый раздел\n\n# B\nраздел два\nконец B');
});
