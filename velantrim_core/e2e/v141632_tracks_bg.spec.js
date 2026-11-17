// v14.16.32: треки плеера по умолчанию (только APK) + «🔋 Фон и батарея» + кнопки плеера в шторке (нативный плагин EitiBackground).
// mp3 в репозитории нет — в тесте подменяем media/default/*.mp3 короткой тишиной (fixtures/silence.mp3).
const path = require('path');
const fs = require('fs');
const { test, expect } = require('@playwright/test');
const SILENCE = fs.readFileSync(path.join(__dirname, 'fixtures', 'silence.mp3'));

async function boot(page, native, extra) {
  await page.route('**/media/default/*.mp3', (r) => r.fulfill({ status: 200, contentType: 'audio/mpeg', body: SILENCE }));
  await page.addInitScript(([native, extra]) => {
    localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1');
    localStorage.setItem('eiti_offline_mode', '0');
    if (extra && !sessionStorage.getItem('__seeded')) { Object.keys(extra).forEach((k) => localStorage.setItem(k, extra[k])); sessionStorage.setItem('__seeded', '1'); }
    window.__bg = [];
    if (native) {
      window.androidBridge = { postMessage() {} };
      // capacitor-eiti.js (мост APK) в репозитории сайта не подключается — эмулируем его API EitiCap.bg (как в www/ APK)
      const rec = (m) => (a) => { window.__bg.push({ m, a: JSON.parse(JSON.stringify(a || {})) }); return Promise.resolve(m === 'status' ? { running: true, ignoringBattery: false } : {}); };
      window.EitiCap = { native: true, bg: { available: true, start: rec('start'), stop: rec('stop'), status: rec('status'), requestIgnoreBattery: rec('requestIgnoreBattery'),
        openBatterySettings: rec('openBatterySettings'), deviceInfo: rec('deviceInfo'), media: rec('updateMedia'), clearMedia: rec('clearMedia') } };
      window.__bgFire = (action) => window.dispatchEvent(new CustomEvent('eiti-media-action', { detail: { action } }));
      window.Capacitor = { isNativePlatform: () => true, getPlatform: () => 'android', Plugins: {} };
    }
  }, [native, extra || null]);
  await page.goto('/index.html');
  await page.waitForFunction(() => window.eitiChatReady === true, null, { timeout: 30000 });
}
const listText = (page) => page.evaluate(() => (document.getElementById('player-track-list') || {}).textContent || '');

test.describe('v14.16.32 default tracks + background', () => {
  test.use({ serviceWorkers: 'block', viewport: { width: 393, height: 873 } });
  test.setTimeout(90000);

  test('site: default tracks are not fetched or seeded', async ({ page }) => {
    let fetched = 0;
    page.on('request', (r) => { if (/media\/default\//.test(r.url())) fetched++; });
    await boot(page, false);
    await page.waitForTimeout(2000);
    expect(await listText(page)).not.toContain('Native Lands');
    expect(fetched).toBe(0);
    expect(await page.evaluate(() => getComputedStyle(document.getElementById('eiti-bg-settings')).display)).toBe('none');
  });

  test('APK: seeding, titles, removal persists across reload, restore', async ({ page }) => {
    await boot(page, true, { eiti_default_tracks_removed: '[]' });
    await page.waitForFunction(() => /Native Lands/.test((document.getElementById('player-track-list') || {}).textContent || ''), null, { timeout: 15000 });
    expect(await listText(page)).toContain('Velan – Seul');
    expect(await page.evaluate(() => window.EITI_DEFAULT_TRACKS.map((t) => t.title))).toEqual(['Seul', 'Native Lands']);
    // шторка: метаданные трека 1 → updateMedia {title:'Seul', artist:'Velan'}
    await page.waitForFunction(() => window.__bg.some((c) => c.m === 'updateMedia'), null, { timeout: 10000 });
    const media = await page.evaluate(() => window.__bg.filter((c) => c.m === 'updateMedia').pop().a);
    expect(media.title).toBe('Seul'); expect(media.artist).toBe('Velan');
    // MediaSession (web) тоже с названием/исполнителем
    const ms = await page.evaluate(() => navigator.mediaSession && navigator.mediaSession.metadata ? [navigator.mediaSession.metadata.title, navigator.mediaSession.metadata.artist] : null);
    if (ms) { expect(ms[0]).toBe('Seul'); expect(ms[1]).toBe('Velan'); }
    // удалить «Native Lands»
    await page.evaluate(() => {
      const rows = [...document.querySelectorAll('#player-track-list [data-track-idx]')];
      const row = rows.find((r) => /Native Lands/.test(r.textContent));
      row.parentElement.querySelector('.eiti-track-del').click(); // красная кнопка «Удалить» (открывается свайпом)
    });
    await page.waitForFunction(() => !/Native Lands/.test(document.getElementById('player-track-list').textContent), null, { timeout: 5000 });
    expect(JSON.parse(await page.evaluate(() => localStorage.getItem('eiti_default_tracks_removed')))).toEqual(['native-lands']);
    // перезапуск: удалённый не возвращается, второй на месте
    await page.reload();
    await page.waitForFunction(() => window.eitiChatReady === true, null, { timeout: 30000 });
    await page.waitForFunction(() => /Velan – Seul/.test((document.getElementById('player-track-list') || {}).textContent || ''), null, { timeout: 15000 });
    await page.waitForTimeout(800);
    expect(await listText(page)).not.toContain('Native Lands');
    // «Вернуть треки по умолчанию»
    const n = await page.evaluate(() => window.eitiRestoreDefaultTracks());
    expect(n).toBe(1);
    expect(await listText(page)).toContain('Native Lands');
    expect(await page.evaluate(() => (document.getElementById('player-track-list').textContent.match(/Velan – Seul/g) || []).length)).toBe(1);
    expect(await page.evaluate(() => localStorage.getItem('eiti_default_tracks_removed'))).toBeNull();
  });

  test('APK: background notification on by default, toggle, battery buttons, shade actions', async ({ page }) => {
    await boot(page, true);
    await page.waitForTimeout(1800);
    const r = await page.evaluate(() => ({
      visible: getComputedStyle(document.getElementById('eiti-bg-settings')).display !== 'none',
      checked: document.getElementById('eiti-bg-notify').checked,
      status: document.getElementById('eiti-bg-status').textContent,
    }));
    expect(r.visible).toBe(true); expect(r.checked).toBe(true);
    expect(r.status).toContain('Работает в фоне');
    await page.evaluate(() => { window.eitiBgSetEnabled(false); window.eitiBgBattery(true); window.eitiBgBattery(false); });
    await page.waitForTimeout(200);
    const calls = await page.evaluate(() => window.__bg.map((c) => c.m));
    expect(calls).toContain('stop'); expect(calls).toContain('requestIgnoreBattery'); expect(calls).toContain('openBatterySettings');
    expect(await page.evaluate(() => localStorage.getItem('eiti_bg_notify'))).toBe('0');
    // автозапуск и кнопка «Выключить» в самом уведомлении — в мосте APK (velantrim-eiti-android/test/shim-smoke.cjs)
    await page.reload(); await page.waitForFunction(() => window.eitiChatReady === true, null, { timeout: 30000 });
    expect(await page.evaluate(() => document.getElementById('eiti-bg-notify').checked)).toBe(false);
    // шторка «⏭» → следующий трек
    await page.waitForFunction(() => /Native Lands/.test((document.getElementById('player-track-list') || {}).textContent || ''), null, { timeout: 15000 });
    const before = await page.evaluate(() => document.getElementById('track').textContent);
    await page.evaluate(() => window.__bgFire('next'));
    await page.waitForTimeout(400);
    const after = await page.evaluate(() => document.getElementById('track').textContent);
    expect(after).not.toBe(before);
    expect(after).toContain('Native Lands');
  });
});
