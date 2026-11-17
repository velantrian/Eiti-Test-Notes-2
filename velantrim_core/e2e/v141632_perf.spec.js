// v14.16.32 (item 3): лаги — в простое нет rAF-циклов (EQ/визуализатор), бесконечных анимаций только 1 (точка активной
// вкладки), в APK база знаний не грузится при запуске (по требованию) + «📥 Скачать всё по Wi-Fi».
const { test, expect } = require('@playwright/test');

async function boot(page, native) {
  await page.addInitScript((native) => {
    localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1'); localStorage.setItem('eiti_install_hint_seen', '1');
    if (native) { window.androidBridge = { postMessage() {} }; window.Capacitor = { isNativePlatform: () => true, getPlatform: () => 'android', Plugins: {} }; }
    let n = 0; const r0 = window.requestAnimationFrame; window.__raf = () => n;
    window.requestAnimationFrame = function (f) { n++; return r0.call(this, f); };
  }, native);
  await page.goto('/index.html');
  await page.waitForFunction(() => window.eitiChatReady === true, null, { timeout: 30000 });
}

test.describe('v14.16.32 perf', () => {
  test.use({ serviceWorkers: 'block', viewport: { width: 393, height: 873 } });
  test.setTimeout(90000);

  test('APK idle: no rAF loops, one infinite animation, no KB requests until the input is focused', async ({ page }) => {
    const kb = [];
    page.on('request', (r) => { if (/\/kb\/(idx|packs|index\.json)/.test(r.url())) kb.push(r.url()); });
    await boot(page, true);
    await page.waitForTimeout(7500); // сайт прогревает KB через 6 с
    const a = await page.evaluate(() => window.__raf());
    await page.waitForTimeout(2000);
    const r = await page.evaluate((a) => ({ raf: window.__raf() - a,
      anims: document.getAnimations().filter((x) => x.effect && x.effect.getTiming().iterations === Infinity && x.playState === 'running').map((x) => x.animationName) }), a);
    expect(r.raf).toBeLessThan(5);
    expect(r.anims).toEqual(['pulse']);
    expect(kb).toEqual([]);
    await page.locator('#input').focus();
    await expect.poll(() => kb.length, { timeout: 15000 }).toBeGreaterThan(1);
  });

  test('site keeps KB prewarm; player EQ restarts on play and stops on pause', async ({ page }) => {
    const kb = [];
    page.on('request', (r) => { if (/\/kb\/idx\//.test(r.url())) kb.push(r.url()); });
    await boot(page, false);
    await expect.poll(() => kb.length, { timeout: 20000 }).toBeGreaterThan(1);
    const stopped = await page.evaluate(() => !window._eitiEqAnimId);
    expect(stopped).toBe(true);
  });

  test('«Скачать всё по Wi-Fi» fetches every shard and pack and records the result', async ({ page }) => {
    await page.route('**/kb/index.json', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify({ domains: {
      a: { shard: 'idx/a.json', packs: ['packs/kb_a.json'] }, b: { shard: 'idx/b.json', packs: ['packs/kb_b_0.json', 'packs/kb_b_1.json'] } } }) }));
    const got = [];
    await page.route(/\/kb\/(idx|packs)\//, (r) => { got.push(new URL(r.request().url()).pathname.replace(/^.*\/kb\//, '')); r.fulfill({ contentType: 'application/json', body: '{"x":"' + 'y'.repeat(1000) + '"}' }); });
    await boot(page, true);
    const res = await page.evaluate(() => eitiKbDownloadAll({ force: true }));
    expect(res).toMatchObject({ files: 5, failed: 0 });
    expect(got.sort()).toEqual(['idx/a.json', 'idx/b.json', 'packs/kb_a.json', 'packs/kb_b_0.json', 'packs/kb_b_1.json']);
    expect(JSON.parse(await page.evaluate(() => localStorage.getItem('eiti_kb_all_downloaded'))).files).toBe(5);
    await expect(page.locator('#eiti-kb-dl-status')).toContainText('✅');
    // раздел только в APK
    expect(await page.evaluate(() => getComputedStyle(document.getElementById('eiti-kb-dl-settings')).display)).not.toBe('none');
  });
});
