// v14.16.32: 🧊 объём (по умолчанию только в APK) и ✨ 3D-иконки таб-бара Fluent Emoji 3D (MIT) — локально, без CDN,
// с текстовым эмодзи как запасным вариантом.
const { test, expect } = require('@playwright/test');

async function boot(page, { native = false, extra = null } = {}) {
  await page.addInitScript(([native, extra]) => {
    localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1');
    localStorage.setItem('eiti_offline_mode', '0');
    if (extra) Object.keys(extra).forEach((k) => localStorage.setItem(k, extra[k]));
    if (native) {
      window.androidBridge = { postMessage() {} };
      window.Capacitor = { isNativePlatform: () => true, getPlatform: () => 'android', Plugins: {} };
    }
  }, [native, extra]);
  await page.goto('/index.html');
  await page.waitForFunction(() => window.eitiChatReady === true, null, { timeout: 30000 });
}
const state = (page) => page.evaluate(() => {
  const de = document.documentElement, ic = document.querySelector('.tab-item[data-view="notes"] .tab-icon');
  const cs = getComputedStyle(ic);
  return { depth: de.classList.contains('eiti-depth'), icons: de.classList.contains('eiti-3d-icons'),
           bg: cs.backgroundImage, color: cs.color, text: ic.textContent,
           composerShadow: getComputedStyle(document.querySelector('.chat-composer-shell')).boxShadow };
});

test.describe('v14.16.32 depth + Fluent 3D icons', () => {
  test.use({ serviceWorkers: 'block', viewport: { width: 393, height: 873 } });
  test.setTimeout(90000);

  test('APK: depth on, 3D icons load from vendor/, no third-party image requests', async ({ page }) => {
    const ext = [], fluent = [];
    page.on('request', (r) => {
      const u = new URL(r.url());
      if (u.hostname !== '127.0.0.1' && ['image', 'font', 'stylesheet'].includes(r.resourceType())) ext.push(r.url());
      if (u.pathname.includes('/vendor/fluent-emoji-3d/')) fluent.push(u.pathname);
    });
    const failed = [];
    page.on('response', (r) => { if (r.url().includes('fluent-emoji-3d') && r.status() !== 200) failed.push(r.url()); });
    await boot(page, { native: true });
    await page.waitForFunction(() => document.documentElement.classList.contains('eiti-3d-icons'), null, { timeout: 10000 });
    const s = await state(page);
    expect(s.depth).toBe(true);
    expect(s.bg).toContain('vendor/fluent-emoji-3d/memo.webp');
    expect(s.color).toBe('rgba(0, 0, 0, 0)');
    expect(s.text).toBe('📝'); // эмодзи остаётся в DOM (доступность / запасной вариант)
    expect(s.composerShadow).toContain('inset');
    expect(new Set(fluent).size).toBe(8);
    expect(failed).toEqual([]);
    expect(ext).toEqual([]);
    // все 8 иконок действительно декодируются
    const sizes = await page.evaluate(() => Promise.all(['speech_balloon', 'notebook', 'books', 'musical_note', 'file_folder', 'memo', 'calendar', 'gear']
      .map((n) => new Promise((res) => { const i = new Image(); i.onload = () => res(i.naturalWidth); i.onerror = () => res(0); i.src = 'vendor/fluent-emoji-3d/' + n + '.webp'; }))));
    expect(sizes).toEqual([96, 96, 96, 96, 96, 96, 96, 96]);
    // переключатели в Настройках
    await page.evaluate(() => { eitiSetPref('depth', false); eitiSetPref('icons3d', false); });
    const off = await state(page);
    expect([off.depth, off.icons]).toEqual([false, false]);
  });

  test('site: depth off by default; icons fall back to emoji when the asset fails', async ({ page }) => {
    await page.route('**/vendor/fluent-emoji-3d/gear.webp', (r) => r.abort());
    await boot(page);
    await page.waitForTimeout(1500);
    const s = await state(page);
    expect(s.depth).toBe(false);
    expect(s.icons).toBe(false);
    expect(s.color).not.toBe('rgba(0, 0, 0, 0)');
  });

  test('iPhone: system emoji kept (3D icons off by default); other icon packs untouched', async ({ browser }) => {
    const ctx = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 390, height: 844 },
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 19_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/19.1 Mobile/15E148 Safari/604.1' });
    const page = await ctx.newPage();
    await boot(page);
    await page.waitForTimeout(1000);
    expect((await state(page)).icons).toBe(false);
    await ctx.close();
    const p2 = await browser.newPage();
    await boot(p2, { extra: { velantrim_messenger_ui_v1: JSON.stringify({ iconPack: 'kim3' }) } });
    await p2.waitForTimeout(1000);
    expect((await state(p2)).icons).toBe(false);
    await p2.close();
  });
});
