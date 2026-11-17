// v14.16.29 (#26): копии EITI на общем origin (velantrian.github.io/<repo>/) не делят
// localStorage / IndexedDB / Cache Storage. Сервер отдаёт репозиторий и в корне
// («старая» копия без префикса, как velantrim-eiti), и под /Eiti-Test-Notes-2/ и /other-copy/.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const REPO = path.resolve(__dirname, '../..');
const PORT = 8131;
const ORIGIN = 'http://127.0.0.1:' + PORT;
const NS = 'Eiti-Test-Notes-2';
let srv, root;

test.use({ baseURL: ORIGIN });

test.beforeAll(async () => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), 'eiti-ns-'));
  for (const name of fs.readdirSync(REPO)) {
    if (name === '.git' || name === 'folklore') continue;
    fs.symlinkSync(path.join(REPO, name), path.join(root, name));
  }
  fs.symlinkSync(REPO, path.join(root, NS));
  fs.symlinkSync(REPO, path.join(root, 'other-copy'));
  fs.writeFileSync(path.join(root, 'probe.html'), '<!doctype html><meta charset="utf-8"><title>probe</title>');
  srv = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1', '--directory', root], { stdio: 'ignore' });
  for (let i = 0; i < 100; i++) {
    try { const r = await fetch(ORIGIN + '/probe.html'); if (r.ok) return; } catch (e) {}
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error('ns test server did not start');
});
test.afterAll(() => { if (srv) srv.kill(); });

async function boot(page, url) {
  await page.addInitScript(() => {
    if (location.pathname.endsWith('probe.html')) return;
    localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1'); localStorage.setItem('eiti_install_hint_seen', '1');
  });
  await page.goto(url);
  await page.waitForFunction(() => typeof eitiDb !== 'undefined' && !!eitiDb, null, { timeout: 30000 });
}
const putNote = (page, id) => page.evaluate((id) => new Promise((r) => {
  const tx = eitiDb.transaction('notes', 'readwrite');
  tx.objectStore('notes').put({ id, title: id, content: id, created: new Date().toISOString(), updated: new Date().toISOString() });
  tx.oncomplete = () => r(true);
}), id);
const hasNote = (page, id) => page.evaluate((id) => new Promise((r) => {
  const q = eitiDb.transaction('notes', 'readonly').objectStore('notes').get(id);
  q.onsuccess = () => r(!!q.result);
}), id);
// «сырой» доступ к общему origin — со страницы без EITI
const rawNote = (page, db, id) => page.evaluate(([db, id]) => new Promise((r) => {
  const o = indexedDB.open(db);
  o.onsuccess = () => { const d = o.result; if (!d.objectStoreNames.contains('notes')) { d.close(); return r(null); }
    const q = d.transaction('notes', 'readonly').objectStore('notes').get(id); q.onsuccess = () => { d.close(); r(!!q.result); }; };
}), [db, id]);

test.describe('v14.16.29 storage isolation (#26)', () => {
  test.use({ serviceWorkers: 'block' });
  test.setTimeout(120000);

  test('prefix, one-time copy migration, legacy data untouched, copies isolated', async ({ page }) => {
    // 1) «основная» копия без префикса (корень origin) пишет свои данные
    await boot(page, '/index.html');
    expect(await page.evaluate(() => [EitiNS.ns, EitiNS.active, eitiDb.name])).toEqual(['', false, 'eiti_v4']);
    await putNote(page, 'n_legacy');
    await page.evaluate(() => { localStorage.setItem('eiti_ns_probe', 'legacy'); localStorage.setItem('eiti_gemini_key', 'LEGACYKEY'); });

    // 2) тестовая копия: префикс, данные скопированы
    await page.goto('/' + NS + '/index.html');
    await page.waitForFunction(() => typeof eitiDb !== 'undefined' && !!eitiDb, null, { timeout: 30000 });
    const st = await page.evaluate(() => EitiNS.ready.then(() => ({ ns: EitiNS.ns, status: EitiNS.status, db: eitiDb.name })));
    expect(st).toEqual({ ns: NS, status: 'done', db: NS + '@@eiti_v4' });
    expect(await hasNote(page, 'n_legacy')).toBe(true);
    expect(await page.evaluate(() => [localStorage.getItem('eiti_ns_probe'), localStorage.getItem('eiti_gemini_key')])).toEqual(['legacy', 'LEGACYKEY']);
    // запись идёт только в свой неймспейс; API Storage работает как обычно
    await putNote(page, 'n_copy');
    const lsApi = await page.evaluate(() => {
      localStorage.setItem('eiti_ns_probe', 'copy');
      localStorage.eiti_ns_prop = 'p';
      const keys = Object.keys(localStorage);
      const viaKey = []; for (let i = 0; i < localStorage.length; i++) viaKey.push(localStorage.key(i));
      return { prop: localStorage.eiti_ns_prop, inOp: 'eiti_ns_probe' in localStorage, noPrefix: keys.every((k) => !k.includes('@@')),
        same: JSON.stringify(keys.slice().sort()) === JSON.stringify(viaKey.slice().sort()), hasProbe: keys.includes('eiti_ns_probe') };
    });
    expect(lsApi).toEqual({ prop: 'p', inOp: true, noPrefix: true, same: true, hasProbe: true });
    expect(await page.evaluate(() => indexedDB.databases().then((l) => l.map((d) => d.name).sort()))).toEqual(expect.arrayContaining(['eiti_v4']));

    // 3) общий origin «сырыми» глазами: оригиналы не изменены
    await page.goto('/probe.html');
    expect(await page.evaluate((ns) => [localStorage.getItem('eiti_ns_probe'), localStorage.getItem(ns + '@@eiti_ns_probe'), localStorage.getItem('eiti_ns_prop')], NS))
      .toEqual(['legacy', 'copy', null]);
    expect(await rawNote(page, 'eiti_v4', 'n_legacy')).toBe(true);
    expect(await rawNote(page, 'eiti_v4', 'n_copy')).toBe(false);
    expect(await rawNote(page, NS + '@@eiti_v4', 'n_copy')).toBe(true);

    // 4) третья копия получает исходные данные, но не данные тестовой копии
    await page.goto('/other-copy/index.html');
    await page.waitForFunction(() => typeof eitiDb !== 'undefined' && !!eitiDb, null, { timeout: 30000 });
    expect(await page.evaluate(() => eitiDb.name)).toBe('other-copy@@eiti_v4');
    expect(await hasNote(page, 'n_legacy')).toBe(true);
    expect(await hasNote(page, 'n_copy')).toBe(false);
    expect(await page.evaluate(() => localStorage.getItem('eiti_ns_probe'))).toBe('legacy');

    // 5) повторный запуск не перезаписывает данные копии
    await page.goto('/' + NS + '/index.html');
    await page.waitForFunction(() => typeof eitiDb !== 'undefined' && !!eitiDb, null, { timeout: 30000 });
    expect(await hasNote(page, 'n_copy')).toBe(true);
    expect(await page.evaluate(() => localStorage.getItem('eiti_ns_probe'))).toBe('copy');
  });
});

test.describe('v14.16.29 SW caches (#26)', () => {
  test.setTimeout(120000);
  test('activate deletes only this deployment\'s stale caches', async ({ page }) => {
    await page.goto('/probe.html');
    await page.evaluate((ns) => Promise.all(['eiti-v0.0.1', 'other-copy@@eiti-v0.0.1', ns + '@@eiti-v0.0.1', ns + '@@transformers-cache']
      .map((n) => caches.open(n))), NS);
    await boot(page, '/' + NS + '/index.html');
    await page.evaluate(() => navigator.serviceWorker.ready);
    await page.goto('/probe.html');
    await expect.poll(() => page.evaluate(() => caches.keys().then((k) => k.sort())), { timeout: 30000 })
      .toEqual(expect.arrayContaining(['eiti-v0.0.1', 'other-copy@@eiti-v0.0.1', NS + '@@transformers-cache']));
    await expect.poll(() => page.evaluate((ns) => caches.keys().then((k) => k.includes(ns + '@@eiti-v0.0.1')), NS), { timeout: 30000 }).toBe(false);
    const own = await page.evaluate((ns) => caches.keys().then((k) => k.filter((x) => x.startsWith(ns + '@@eiti-v1'))), NS);
    expect(own.length).toBeGreaterThan(0);
  });
});
