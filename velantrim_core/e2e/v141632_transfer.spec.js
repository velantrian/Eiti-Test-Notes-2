// v14.16.32: перенос настроек и данных сайт → APK одним файлом (eiti.transfer.v1). Drive/Dropbox — честно «скоро».
const fs = require('fs');
const { test, expect } = require('@playwright/test');

async function boot(page, native) {
  await page.addInitScript((native) => {
    localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1'); localStorage.setItem('eiti_offline_mode', '0');
    window.__eitiTransferNoConfirm = true; window.__eitiTransferNoReload = true;
    if (native) { window.androidBridge = { postMessage() {} }; window.Capacitor = { isNativePlatform: () => true, getPlatform: () => 'android', Plugins: {} }; }
  }, native);
  await page.goto('/index.html');
  await page.waitForFunction(() => window.eitiChatReady === true && !!window.EitiTransfer, null, { timeout: 30000 });
}
const idbGet = (page, store, key) => page.evaluate(([store, key]) => new Promise((res) => {
  const r = indexedDB.open('eiti_v4'); r.onsuccess = () => { const g = r.result.transaction(store).objectStore(store).get(key); g.onsuccess = () => res(g.result || null); g.onerror = () => res(null); };
}), [store, key]);

test.describe('v14.16.32 transfer site → APK', () => {
  test.use({ serviceWorkers: 'block', viewport: { width: 393, height: 873 } });
  test.setTimeout(120000);

  test('export on site, import in APK: notes + settings move, API keys only when asked', async ({ browser }) => {
    const site = await (await browser.newContext()).newPage();
    await boot(site, false);
    await site.evaluate(() => new Promise((res) => {
      localStorage.setItem('eiti_theme', 'gold-test'); localStorage.setItem('eiti_header_size', 'large'); localStorage.setItem('eiti_deepseek_key', 'sk-SECRET');
      const r = indexedDB.open('eiti_v4');
      r.onsuccess = () => { const tx = r.result.transaction('notes', 'readwrite'); tx.objectStore('notes').put({ id: 'n-transfer-1', title: 'Перенос', content: 'Привет из сайта', ts: Date.now(), att: new Blob(['x'], { type: 'text/plain' }) }); tx.oncomplete = () => res(); };
    }));
    // каналы: Drive / Dropbox видны, но недоступны (нужны OAuth-клиенты)
    const prov = await site.evaluate(() => [...document.querySelectorAll('#eiti-transfer-providers [data-provider]')].map((b) => [b.dataset.provider, b.disabled]));
    expect(prov).toEqual([['gdrive', true], ['dropbox', true]]);
    const [dl] = await Promise.all([site.waitForEvent('download'), site.evaluate(() => window.eitiTransferExport())]);
    expect(dl.suggestedFilename()).toMatch(/^eiti-transfer-\d{4}-\d{2}-\d{2}\.eiti\.json$/);
    const file = await dl.path();
    const bundle = JSON.parse(fs.readFileSync(file, 'utf8'));
    expect(bundle.format).toBe('eiti.transfer.v1'); expect(bundle.from).toBe('site');
    expect(bundle.ls.eiti_theme).toBe('gold-test');
    expect(bundle.ls.eiti_deepseek_key).toBeUndefined(); expect(bundle.skippedSecrets).toBeGreaterThan(0);
    expect(bundle.idb.eiti_v4.tts_cache).toBeUndefined();

    const apk = await (await browser.newContext()).newPage();
    await boot(apk, true);
    expect(await idbGet(apk, 'notes', 'n-transfer-1')).toBeNull();
    await apk.setInputFiles('#eiti-transfer-file', file);
    await apk.waitForFunction(() => /Перенесено/.test(document.getElementById('eiti-transfer-status').textContent), null, { timeout: 20000 });
    const note = await idbGet(apk, 'notes', 'n-transfer-1');
    expect(note && note.content).toBe('Привет из сайта');
    expect(await apk.evaluate(async () => { const r = await idbGetBlob(); return r; async function idbGetBlob() { return new Promise((res) => { const o = indexedDB.open('eiti_v4'); o.onsuccess = () => { const g = o.result.transaction('notes').objectStore('notes').get('n-transfer-1'); g.onsuccess = async () => res(g.result.att instanceof Blob ? await g.result.att.text() : null); }; }); } })).toBe('x');
    expect(await apk.evaluate(() => [localStorage.getItem('eiti_theme'), localStorage.getItem('eiti_header_size'), localStorage.getItem('eiti_deepseek_key')])).toEqual(['gold-test', 'large', null]);

    // с галочкой «включить API-ключи» — ключ переносится
    await site.evaluate(() => { document.getElementById('eiti-transfer-secrets').checked = true; });
    const b2 = await site.evaluate(() => window.eitiTransferExport().then((b) => b.ls.eiti_deepseek_key));
    expect(b2).toBe('sk-SECRET');
  });

  test('wrong file is rejected without changes', async ({ page }) => {
    await boot(page, true);
    await page.setInputFiles('#eiti-transfer-file', { name: 'x.json', mimeType: 'application/json', buffer: Buffer.from('{"version":"eiti.v5","kb":{}}') });
    await page.waitForFunction(() => /❌/.test(document.getElementById('eiti-transfer-status').textContent), null, { timeout: 10000 });
    expect(await page.evaluate(() => document.getElementById('eiti-transfer-status').textContent)).toContain('не файл переноса');
  });
});
