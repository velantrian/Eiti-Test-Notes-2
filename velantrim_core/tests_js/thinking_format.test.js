'use strict';
/**
 * v14.16.21: strip AI command markers + DeepSeek thinking params / panel gate.
 */
const assert = require('assert');
const { loadFunctions } = require('./harness');

function withLS(map, fn) {
  const store = Object.assign({}, map);
  const ls = {
    getItem: (k) => (Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; }
  };
  return fn(ls, store);
}

(function testStripAiCommands() {
  const s = loadFunctions(['eitiStripAiCommands', 'eitiStripMarkers']);
  const raw = 'Ответ.\n[PKG_E:foo|bar]\n[MEM_ADD:name=X]\n[NOTE_WRITE:id=1]\n[TASK_ADD:do]\nКонец ✨';
  const out = s.eitiStripAiCommands(raw);
  assert.ok(!/PKG_E|MEM_ADD|NOTE_WRITE|TASK_ADD/.test(out), out);
  assert.ok(out.indexOf('Ответ') !== -1);
  assert.ok(out.indexOf('Конец') !== -1);
  assert.ok(out.indexOf('✨') !== -1);
  const marked = 'Текст\n⟦EITIFOOT⟧подп⟦/EITIFOOT⟧\n[PKG_E:x]';
  const stripped = s.eitiStripMarkers(marked);
  assert.ok(stripped.indexOf('EITIFOOT') === -1);
  assert.ok(stripped.indexOf('PKG_E') === -1);
  console.log('ok strip');
})();

(function testDsChatParamsRespectToggle() {
  withLS({ eiti_ds_model: 'deepseek-v4-pro-high', eiti_ds_show_thinking: '1' }, function(ls) {
    const s = loadFunctions([
      'eitiNormalizeDsSelection', 'eitiGetDsSelection', 'eitiGetDsModel',
      'eitiGetDsReasoningEffort', 'eitiIsDsReasoningMode', 'eitiIsDsShowThinking',
      'eitiApplyDsChatParams'
    ], {
      localStorage: ls,
      eitiMigrateSavedModel: function(_p, raw) { return raw; },
      eitiModelCatalog: function() { return { deepseek: { defaultSel: 'deepseek-flash' } }; }
    });
    // re-bind helpers that call each other via free names already in sandbox
    const on = s.eitiApplyDsChatParams({ messages: [], stream: true });
    assert.strictEqual(on.model, 'deepseek-v4-pro');
    assert.strictEqual(on.reasoning_effort, 'high');
    assert.strictEqual(on.thinking && on.thinking.type, 'enabled');
  });

  withLS({ eiti_ds_model: 'deepseek-v4-pro-high', eiti_ds_show_thinking: '0' }, function(ls) {
    const s = loadFunctions([
      'eitiNormalizeDsSelection', 'eitiGetDsSelection', 'eitiGetDsModel',
      'eitiGetDsReasoningEffort', 'eitiIsDsReasoningMode', 'eitiIsDsShowThinking',
      'eitiApplyDsChatParams'
    ], {
      localStorage: ls,
      eitiMigrateSavedModel: function(_p, raw) { return raw; },
      eitiModelCatalog: function() { return { deepseek: { defaultSel: 'deepseek-flash' } }; }
    });
    const off = s.eitiApplyDsChatParams({ messages: [] });
    assert.strictEqual(off.model, 'deepseek-v4-pro');
    assert.strictEqual(off.reasoning_effort, undefined);
    assert.strictEqual(off.thinking && off.thinking.type, 'disabled');
  });

  withLS({ eiti_ds_model: 'deepseek-flash' }, function(ls) {
    const s = loadFunctions([
      'eitiNormalizeDsSelection', 'eitiGetDsSelection', 'eitiGetDsModel',
      'eitiGetDsReasoningEffort', 'eitiIsDsReasoningMode', 'eitiIsDsShowThinking',
      'eitiApplyDsChatParams', 'eitiThinkingPanelAllowed'
    ], {
      localStorage: ls,
      eitiMigrateSavedModel: function(_p, raw) { return raw; },
      eitiModelCatalog: function() { return { deepseek: { defaultSel: 'deepseek-flash' } }; }
    });
    const flash = s.eitiApplyDsChatParams({});
    assert.strictEqual(flash.model, 'deepseek-flash');
    assert.strictEqual(flash.thinking, undefined);
    assert.strictEqual(s.eitiThinkingPanelAllowed(), false);
  });
  console.log('ok ds params');
})();

(function testPanelGateProviders() {
  withLS({ eiti_ai_provider: 'gemini', eiti_gemini_thinking: '0' }, function(ls) {
    const s = loadFunctions(['eitiIsGeminiThinking', 'eitiThinkingPanelAllowed', 'eitiIsDsShowThinking'], {
      localStorage: ls,
      eitiORThinkingActive: function() { return true; },
      eitiIsDsReasoningMode: function() { return true; }
    });
    assert.strictEqual(s.eitiThinkingPanelAllowed(), false);
  });
  withLS({ eiti_ai_provider: 'openrouter', eiti_or_thinking: '0' }, function(ls) {
    const s = loadFunctions(['eitiThinkingPanelAllowed', 'eitiIsDsShowThinking'], {
      localStorage: ls,
      eitiORThinkingActive: function() { return false; },
      eitiIsGeminiThinking: function() { return false; },
      eitiIsDsReasoningMode: function() { return true; }
    });
    assert.strictEqual(s.eitiThinkingPanelAllowed(), false);
  });
  console.log('ok panel gate');
})();

console.log('thinking_format.test.js: all ok');
