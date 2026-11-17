// v14.16.32 (item 2): совместимость экранов — Galaxy S21…S25 (base/+/Ultra), Xiaomi / Honor / Huawei флагманы,
// Redmi Note 13 Pro+; CSS-ширины 320…480 dp. В APK-режиме (Capacitor safe-area) и на сайте.
const { test, expect } = require('@playwright/test');

// [имя, ширина, высота, DPR] — CSS-пиксели (dp) при стандартном масштабе экрана
const SCREENS = [
  ['small 320', 320, 640, 2],
  ['Galaxy S21/S22/S23 (6.1–6.2")', 360, 780, 3],
  ['Galaxy S21+/S22+/S23+ (6.6–6.7")', 384, 832, 2.8125],
  ['Galaxy S21 Ultra…S25 Ultra (6.8–6.9")', 384, 824, 3.75],
  ['Redmi Note 13 Pro+ (6.67")', 393, 873, 2.75],
  ['Xiaomi 14/15 Ultra, Honor Magic 6/7 Pro, Huawei Mate 60/70 Pro (6.7–6.8")', 412, 915, 3.5],
  ['Galaxy Z Fold (outer → inner)', 480, 900, 2.6],
];

for (const native of [true, false]) {
  for (const [name, w, h, dpr] of SCREENS) {
    test(`${native ? 'APK' : 'site'} · ${name} · ${w}×${h}`, async ({ browser }) => {
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: dpr, serviceWorkers: 'block', isMobile: true, hasTouch: true });
      const page = await ctx.newPage();
      await page.addInitScript((native) => {
        localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1'); localStorage.setItem('eiti_install_hint_seen', '1');
        if (native) { window.androidBridge = { postMessage() {} }; window.Capacitor = { isNativePlatform: () => true, getPlatform: () => 'android', Plugins: {} }; }
      }, native);
      await page.goto('/index.html');
      await page.waitForFunction(() => window.eitiChatReady === true, null, { timeout: 30000 });
      if (native) await page.evaluate(() => { const s = document.documentElement.style; s.setProperty('--safe-area-inset-top', '36px'); s.setProperty('--safe-area-inset-bottom', '24px'); });
      await page.evaluate(() => document.querySelectorAll('#eiti-onboarding,.toast').forEach((e) => e.remove()));
      for (const view of ['chat', 'journal', 'notes', 'history', 'player', 'files', 'settings']) {
        await page.evaluate((v) => { const t = document.querySelector('.tab-item[data-view="' + v + '"]'); if (t) t.click(); }, view);
        await page.waitForTimeout(250);
        const r = await page.evaluate(() => {
          const vw = innerWidth, vh = innerHeight;
          const hdr = document.querySelector('.app-header').getBoundingClientRect();
          const h1 = document.querySelector('.app-header h1').getBoundingClientRect();
          const bar = document.querySelector('.tab-bar').getBoundingClientRect();
          const tabs = [...document.querySelectorAll('.tab-bar .tab-item')].filter((t) => t.offsetParent !== null).map((t) => t.getBoundingClientRect());
          const comp = document.querySelector('.chat-composer-shell');
          const cr = comp && comp.offsetParent ? comp.getBoundingClientRect() : null;
          // первый видимый заголовок/кнопка активного экрана (шапка приложения или своя шапка вкладки)
          const act = document.querySelector('.view.active, [id^="view-"].active') || document.body;
          const firsts = [...document.querySelectorAll('.app-header h1, .app-header .header-btn, #view-notes .notes-header *, #view-journal button, .view.active button, .view.active h2, .view.active h3')]
            .filter((e) => e.offsetParent !== null && e.getBoundingClientRect().height > 0).map((e) => e.getBoundingClientRect().top);
          const topMost = firsts.length ? Math.min(...firsts) : 999;
          return { topMost, docOverflow: document.documentElement.scrollWidth - vw, bodyOverflow: document.body.scrollWidth - vw,
                   h1Top: h1.top, h1Right: h1.right, h1Left: h1.left, hdrBottom: hdr.bottom, vw, vh,
                   barBottom: bar.bottom, barTop: bar.top, tabsOut: tabs.filter((t) => t.left < -1 || t.right > vw + 1).length, tabs: tabs.length,
                   composer: cr && { left: cr.left, right: cr.right, bottom: cr.bottom } };
        });
        expect(r.docOverflow, view).toBeLessThanOrEqual(0);
        expect(r.bodyOverflow, view).toBeLessThanOrEqual(0);
        expect(r.h1Left).toBeGreaterThanOrEqual(0);
        expect(r.h1Right).toBeLessThanOrEqual(r.vw + 1);
        if (native) expect(r.topMost, view + ': controls below the status bar').toBeGreaterThanOrEqual(36);
        expect(Math.round(r.barBottom)).toBeLessThanOrEqual(r.vh);
        expect(r.tabs).toBeGreaterThanOrEqual(6);
        expect(r.tabsOut).toBe(0);
        if (view === 'chat' && r.composer) {
          expect(r.composer.left).toBeGreaterThanOrEqual(0);
          expect(r.composer.right).toBeLessThanOrEqual(r.vw + 1);
          expect(r.composer.bottom).toBeLessThanOrEqual(r.barTop + 1);
        }
      }
      await ctx.close();
    });
  }
}
