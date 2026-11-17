// v14.16.32: «Расширенные» → офлайн-модели под мощность устройства (WebGPU / ОЗУ / память).
const { test, expect } = require('@playwright/test');

async function boot(page, { gpu, mem, native }) {
  await page.addInitScript(([gpu, mem, native]) => {
    localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1'); localStorage.setItem('eiti_offline_mode', '0');
    localStorage.setItem('eiti_settings_audience_mode_v1', 'developer');
    Object.defineProperty(navigator, 'deviceMemory', { get: () => mem, configurable: true });
    Object.defineProperty(navigator, 'gpu', { get: () => (gpu ? { requestAdapter: async () => ({ limits: { maxBufferSize: 2 ** 31, maxStorageBufferBindingSize: 2 ** 30 }, features: new Set(['shader-f16']) }) } : undefined), configurable: true });
    if (native) window.EitiCap = { native: true, bg: { available: true, deviceInfo: async () => native, status: async () => ({}), start: async () => ({}), media: async () => ({}), clearMedia: async () => ({}) } };
  }, [gpu, mem, native || null]);
  await page.goto('/index.html');
  await page.waitForFunction(() => window.eitiChatReady === true && !!window.EitiDeviceFit, null, { timeout: 30000 });
}
async function fit(page) {
  await page.evaluate(() => window.eitiLLMFitRender(true));
  return page.evaluate(() => ({
    dev: document.getElementById('eiti-llm-fit-dev').textContent,
    items: [...document.querySelectorAll('#eiti-llm-fit-list .eiti-llm-fit-item')].map((l) => ({ id: l.querySelector('input').value, fit: l.dataset.fit, rec: l.dataset.rec === '1' })),
  }));
}

test.describe('v14.16.32 offline models by device', () => {
  test.use({ serviceWorkers: 'block', viewport: { width: 393, height: 873 } });
  test.setTimeout(90000);

  test('APK 12 GB phone: exact RAM, large 9B recommended, radios feed WebLLM', async ({ page }) => {
    await boot(page, { gpu: true, mem: 8, native: { manufacturer: 'Xiaomi', model: '23090RA98G', totalRam: 12 * 2 ** 30, freeStorage: 80 * 2 ** 30, cores: 8 } });
    const r = await fit(page);
    expect(r.dev).toContain('Xiaomi 23090RA98G'); expect(r.dev).toContain('ОЗУ 12 ГБ');
    expect(r.items.length).toBe(11);
    expect(r.items.find((i) => i.rec).id).toBe('Qwen3.5-9B-q4f16_1-MLC');
    expect(r.items.every((i) => i.fit !== 'no')).toBe(true);
    await page.evaluate(() => { const i = document.querySelector('#eiti-llm-fit-list input[value="Qwen3.5-2B-q4f16_1-MLC"]'); i.checked = true; i.dispatchEvent(new Event('change')); });
    expect(await page.evaluate(() => document.querySelector('input[name="llm-model"]:checked').value)).toBe('Qwen3.5-2B-q4f16_1-MLC');
  });

  test('browser 4 GB, WebGPU: large models blocked, fast one recommended', async ({ page }) => {
    await boot(page, { gpu: true, mem: 4 });
    const r = await fit(page);
    expect(r.items.filter((i) => /Qwen3\.5-9B|Qwen3-8B|gemma-2-9b/.test(i.id)).every((i) => i.fit === 'no')).toBe(true);
    const rec = r.items.find((i) => i.rec);
    expect(rec && /Qwen3\.5-0\.8B|Qwen3\.5-2B|Llama-3\.2-1B|gemma3-1b/.test(rec.id)).toBeTruthy();
  });

  test('no WebGPU: everything flagged, WASM fallback note', async ({ page }) => {
    await boot(page, { gpu: false, mem: 8 });
    const r = await fit(page);
    expect(r.dev).toContain('WebGPU ❌');
    expect(r.items.every((i) => i.fit === 'no')).toBe(true);
    expect(r.items.some((i) => i.rec)).toBe(false);
  });
});
