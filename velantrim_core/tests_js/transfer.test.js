// v14.16.32: перенос сайт ⇄ APK (local/eiti_transfer.js)
const test = require('node:test');
const assert = require('node:assert');
const T = require('../../local/eiti_transfer.js');

test('API keys and tokens are secret; ordinary settings are not', () => {
  ['eiti_deepseek_key', 'eiti_or_key', 'eiti_apikey_openai', 'eiti_emb_key_jina', 'eiti_drive_token', 'openrouter_api_key'].forEach((k) => assert.ok(T.isSecretKey(k), k));
  ['eiti_theme', 'eiti_header_size', 'eiti_token_budget', 'eiti_token_stats', 'eiti_keyboard_mode', 'eiti_bg_notify'].forEach((k) => assert.ok(!T.isSecretKey(k), k));
});

test('Blob / Date / typed arrays survive JSON round-trip', async () => {
  const enc = await T.encode({ b: new Blob(['hello'], { type: 'text/plain' }), d: new Date(42), u: new Float32Array([1.5, 2.5]), n: [1, { x: 'y' }] });
  const dec = T.decode(JSON.parse(JSON.stringify(enc)));
  assert.equal(await dec.b.text(), 'hello'); assert.equal(dec.b.type, 'text/plain');
  assert.equal(dec.d.getTime(), 42);
  assert.deepEqual(Array.from(dec.u), [1.5, 2.5]); assert.ok(dec.u instanceof Float32Array);
  assert.deepEqual(dec.n, [1, { x: 'y' }]);
});

test('validate + providers: file works, Drive/Dropbox honestly unavailable', async () => {
  assert.match(T.validate({ version: 'eiti.v5' }), /не файл переноса/);
  assert.equal(T.validate({ format: 'eiti.transfer.v1', ls: {}, idb: {} }), '');
  assert.equal(T.providers.file.available(), true);
  for (const id of ['gdrive', 'dropbox']) {
    assert.equal(T.providers[id].available(), false);
    assert.ok(T.providers[id].needs);
    await assert.rejects(T.providers[id].save());
  }
});
