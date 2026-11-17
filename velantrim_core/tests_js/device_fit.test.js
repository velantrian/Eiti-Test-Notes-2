// v14.16.32: EitiDeviceFit — оценка, потянет ли устройство офлайн-модель
const test = require('node:test');
const assert = require('node:assert');
const path = require('path');
const F = require(path.join(__dirname, '..', '..', 'local', 'eiti_device_fit.js'));

const gpu = { ok: true, f16: true, maxBufferMB: 2048, maxStorageMB: 2048 };
const byId = (id) => F.CATALOG.find((m) => m.id === id);

test('catalog: tiers 0.8–2B / ~4B / 8–9B, unique WebLLM ids', () => {
  const ids = F.CATALOG.map((m) => m.id);
  assert.equal(new Set(ids).size, ids.length);
  ['fast', 'smart', 'large'].forEach((t) => assert.ok(F.CATALOG.some((m) => m.tier === t), t));
  assert.ok(ids.includes('Qwen3.5-0.8B-q4f16_1-MLC') && ids.includes('Qwen3.5-4B-q4f16_1-MLC') && ids.includes('Qwen3.5-9B-q4f16_1-MLC'));
  ids.forEach((id) => assert.match(id, /-MLC$/));
});

test('12 GB phone (APK native RAM): 9B ok, recommend the large one', async () => {
  const dev = await F.probe({ navigator: { hardwareConcurrency: 8, gpu: { requestAdapter: async () => ({ limits: { maxBufferSize: 2 ** 31, maxStorageBufferBindingSize: 2 ** 30 }, features: new Set(['shader-f16']) }) } },
    nativeInfo: { manufacturer: 'Xiaomi', model: '23090RA98G', totalRam: 12 * 2 ** 30, freeStorage: 100 * 2 ** 30, cores: 8 } });
  assert.equal(dev.ramGB, 12); assert.equal(dev.ramExact, true); assert.ok(dev.gpu.ok && dev.gpu.f16);
  assert.equal(F.rate(byId('Qwen3.5-9B-q4f16_1-MLC'), dev).level, 'ok');
  assert.equal(F.recommend(dev).tier, 'large');
  assert.match(F.summary(dev), /Xiaomi 23090RA98G · ОЗУ 12 ГБ/);
});

test('6 GB phone: 4B tight, 9B no, recommend a fast/medium one', () => {
  const dev = { ramGB: 6, ramExact: true, freeGB: 40, gpu };
  assert.equal(F.rate(byId('Qwen3.5-9B-q4f16_1-MLC'), dev).level, 'no');
  assert.equal(F.rate(byId('Qwen3.5-4B-q4f16_1-MLC'), dev).level, 'tight');
  assert.equal(F.rate(byId('Qwen3.5-0.8B-q4f16_1-MLC'), dev).level, 'ok');
  const r = F.recommend(dev);
  assert.ok(r && r.vramMB <= 6 * 1024 * 0.55, r && r.id);
});

test('browser caps deviceMemory at 8: large models are «tight», not «no»', () => {
  const dev = { ramGB: 8, ramCapped: true, freeGB: 50, gpu };
  assert.equal(F.rate(byId('Qwen3.5-9B-q4f16_1-MLC'), dev).level, 'tight');
});

test('no WebGPU → no; low storage → no; no f16 → tight', () => {
  assert.equal(F.rate(byId('Qwen3.5-0.8B-q4f16_1-MLC'), { ramGB: 8, gpu: { ok: false } }).level, 'no');
  const low = F.rate(byId('Qwen3.5-9B-q4f16_1-MLC'), { ramGB: 16, ramExact: true, freeGB: 3, gpu });
  assert.equal(low.level, 'no'); assert.match(low.reason, /мало места/);
  assert.equal(F.rate(byId('Qwen3.5-0.8B-q4f16_1-MLC'), { ramGB: 12, ramExact: true, gpu: Object.assign({}, gpu, { f16: false }) }).level, 'tight');
  assert.equal(F.recommend({ ramGB: 8, gpu: { ok: false } }), null);
});
