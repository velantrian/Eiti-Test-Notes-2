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

test('runtime version is 14.16.19 and synced in SW/AGENTS', () => {
  assert.match(HTML, /EITI_VERSION\s*=\s*"14\.16\.19"/);
  assert.match(SW, /eiti-v14\.16\.19/);
  assert.match(SW, /eiti-offline-v14\.16\.19/);
  assert.ok(AGENTS.includes('v14.16.19'));
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
