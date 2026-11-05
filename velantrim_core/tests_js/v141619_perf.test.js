// v14.16.19: UI performance guards — i18n stream skip, RAF scroller, DocumentFragment chat load.
'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const HTML = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const SW = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
const AGENTS = fs.readFileSync(path.join(ROOT, 'AGENTS.md'), 'utf8');

test('runtime version is at least 14.16.19 and synced in SW/AGENTS', () => {
  const m = HTML.match(/EITI_VERSION\s*=\s*"(\d+\.\d+\.\d+)"/);
  assert.ok(m, 'missing EITI_VERSION');
  const parts = m[1].split('.').map(Number);
  assert.ok(parts[0] > 14 || (parts[0] === 14 && parts[1] > 16) || (parts[0] === 14 && parts[1] === 16 && parts[2] >= 19), m[1]);
  assert.match(SW, new RegExp("eiti-v" + m[1].replace(/\./g, '\\.')));
  assert.match(SW, new RegExp("eiti-offline-v" + m[1].replace(/\./g, '\\.')));
  assert.ok(AGENTS.includes('v' + m[1]));
});

test('i18n MutationObserver skips RU locale and chat-stream characterData', () => {
  assert.match(HTML, /state\.locale === 'ru'/);
  assert.match(HTML, /_inChatStream/);
  assert.match(HTML, /_eitiIsStreaming/);
  assert.match(HTML, /WeakSet/);
  assert.match(HTML, /v14\.16\.19: RU is the source locale/);
});

test('chat load uses DocumentFragment; stream scroll uses RAF scroller', () => {
  assert.match(HTML, /createDocumentFragment\(\)/);
  assert.match(HTML, /function eitiCreateRafScroller/);
  assert.match(HTML, /_orScroll/);
  assert.match(HTML, /_oaiScroll/);
});

test('history and note fullscreen observers are narrowed off document.body attributes', () => {
  assert.match(HTML, /observe\(_histRoot/);
  assert.match(HTML, /_watchFsOverlay/);
  assert.match(HTML, /watch only the note overlay/);
  // old body-wide class attribute observer must be gone
  assert.doesNotMatch(HTML, /observe\(document\.body,\s*\{\s*subtree:\s*true,\s*attributes:\s*true,\s*attributeFilter:\s*\['class'\]\s*\}\)/);
});
