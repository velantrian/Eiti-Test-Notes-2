'use strict';
// v14.16.23: «Нижние табы» — hide all bottom tabs except Chat from «+» menu.

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const vm = require('vm');
const { INDEX_HTML } = require('./harness');

const SRC = fs.readFileSync(INDEX_HTML, 'utf8');
const HEAD = SRC.slice(0, SRC.indexOf('</head>'));

test('ранний <head>: eiti_chat_only_tabs=1 → класс eiti-chat-only-tabs до отрисовки', () => {
  assert.match(HEAD, /eiti_chat_only_tabs/);
  assert.match(HEAD, /eiti-chat-only-tabs/);
  const needle = "try{if(localStorage.getItem('eiti_chat_only_tabs')==='1')document.documentElement.classList.add('eiti-chat-only-tabs');}catch(e){}";
  assert.ok(HEAD.includes(needle), 'early class apply present');

  const cls = new Set();
  const root = { classList: { add: (c) => cls.add(c) } };
  const ctx = {
    document: { documentElement: root },
    localStorage: { getItem: (k) => (k === 'eiti_chat_only_tabs' ? '1' : null) },
  };
  vm.runInNewContext(needle, ctx);
  assert.equal(cls.has('eiti-chat-only-tabs'), true);
});

test('ранний <head>: без ключа класс не ставится', () => {
  const needle = "try{if(localStorage.getItem('eiti_chat_only_tabs')==='1')document.documentElement.classList.add('eiti-chat-only-tabs');}catch(e){}";
  const cls = new Set();
  const root = { classList: { add: (c) => cls.add(c) } };
  const ctx = {
    document: { documentElement: root },
    localStorage: { getItem: () => null },
  };
  vm.runInNewContext(needle, ctx);
  assert.equal(cls.has('eiti-chat-only-tabs'), false);
});

test('CSS: скрыты все табы кроме chat + компактный tab-bar', () => {
  assert.match(SRC, /html\.eiti-chat-only-tabs \.tab-bar \.tab-item:not\(\[data-view="chat"\]\)/);
  // v14.16.25: must beat eiti-compact-chrome's 96px !important
  assert.match(SRC, /html\.eiti-chat-only-tabs\.eiti-compact-chrome \.tab-bar/);
  assert.match(SRC, /height:\s*56px\s*!important/);
  assert.match(SRC, /cpi-tabs-pin/);
});

test('меню «+» рендерит правую колонку Нижние табы с переключателем', () => {
  assert.match(SRC, /Нижние табы/);
  assert.match(SRC, /chat-plus-tabs-rail/);
  assert.match(SRC, /chat-plus-main/);
  assert.match(SRC, /eitiSetChatOnlyTabs\(!eitiIsChatOnlyTabs\(\)\)/);
  assert.match(SRC, /cpi-tabs-pin/);
  assert.match(SRC, /Показать или скрыть Дневник, История, Плеер, Файлы, Заметки, Настройки/);
});

test('API: eitiSetChatOnlyTabs пишет ключ и класс, возвращает на chat', () => {
  const start = SRC.indexOf('// v14.16.23: «Нижние табы» — скрыть все табы кроме Чата');
  assert.ok(start > 0, 'api block marker');
  const end = SRC.indexOf('// ═══ v14.15.2: «📱 Экран телефона»', start);
  assert.ok(end > start);
  const block = SRC.slice(start, end);

  const store = {};
  const htmlCls = new Set();
  const bodyCls = new Set();
  let switched = null;
  const pins = [];
  const ctx = {
    localStorage: {
      getItem: (k) => (Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    },
    document: {
      documentElement: {
        classList: {
          toggle: (c, on) => { if (on) htmlCls.add(c); else htmlCls.delete(c); },
        },
      },
      body: {
        classList: {
          toggle: (c, on) => { if (on) bodyCls.add(c); else bodyCls.delete(c); },
        },
      },
      querySelector: (sel) => {
        if (sel === '.tab-item.active') return { getAttribute: () => 'settings' };
        return null;
      },
      querySelectorAll: (sel) => (sel === '.cpi-tabs-pin' ? pins : []),
      getElementById: () => null,
      addEventListener: () => {},
    },
    window: {},
    showToast: () => {},
    openView: (v) => { switched = v; },
  };
  ctx.window = ctx;
  // pin element mutated by apply
  pins.push({
    classList: { toggle: () => {} },
    setAttribute: () => {},
  });

  vm.runInNewContext(
    block + '\nthis.eitiIsChatOnlyTabs=eitiIsChatOnlyTabs;this.eitiSetChatOnlyTabs=eitiSetChatOnlyTabs;this.eitiApplyChatOnlyTabs=eitiApplyChatOnlyTabs;',
    ctx
  );

  assert.equal(ctx.eitiIsChatOnlyTabs(), false);
  ctx.eitiSetChatOnlyTabs(true);
  assert.equal(store.eiti_chat_only_tabs, '1');
  assert.equal(htmlCls.has('eiti-chat-only-tabs'), true);
  assert.equal(bodyCls.has('eiti-chat-only-tabs'), true);
  assert.equal(switched, 'chat');
  assert.equal(ctx.eitiIsChatOnlyTabs(), true);

  ctx.eitiSetChatOnlyTabs(false);
  assert.equal(store.eiti_chat_only_tabs, undefined);
  assert.equal(htmlCls.has('eiti-chat-only-tabs'), false);
  assert.equal(ctx.eitiIsChatOnlyTabs(), false);
});
