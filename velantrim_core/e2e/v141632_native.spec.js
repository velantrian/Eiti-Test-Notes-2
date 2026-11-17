// v14.16.32: Android APK (Capacitor) — шапка не уходит под статус-бар (safe-area), компактная шапка по умолчанию,
// без кнопки/баннера установки PWA и без предупреждения «установите как PWA». На сайте всё как раньше.
const { test, expect } = require('@playwright/test');

async function boot(page, native, extra) {
  await page.addInitScript(([native, extra]) => {
    localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1');
    localStorage.setItem('eiti_offline_mode', '0');
    if (extra) Object.keys(extra).forEach((k) => localStorage.setItem(k, extra[k]));
    if (native) {
      window.androidBridge = { postMessage() {} };
      window.Capacitor = { isNativePlatform: () => true, getPlatform: () => 'android', Plugins: {} };
    }
  }, [native, extra || null]);
  await page.goto('/index.html');
  await page.waitForFunction(() => window.eitiChatReady === true, null, { timeout: 30000 });
  if (native) await page.evaluate(() => {
    // как SystemBars в Capacitor 8 (insetsHandling: css): реальные отступы — CSS-переменными на <html>
    document.documentElement.style.setProperty('--safe-area-inset-top', '40px');
    document.documentElement.style.setProperty('--safe-area-inset-bottom', '48px');
  });
}

test.describe('v14.16.32 native shell', () => {
  test.use({ serviceWorkers: 'block', viewport: { width: 393, height: 873 } });
  test.setTimeout(90000);

  test('APK: header below status bar, compact, no PWA install UI', async ({ page }) => {
    await boot(page, true);
    await page.waitForTimeout(2600); // кнопка установки раньше появлялась через 1,5 с, баннер — через 2,5 с
    const r = await page.evaluate(() => {
      const de = document.documentElement, hdr = document.querySelector('.app-header'), h1 = hdr.querySelector('h1');
      const btn = document.getElementById('btn-pwa-install');
      return {
        native: de.classList.contains('eiti-native'), preset: de.getAttribute('data-eiti-phone'),
        compact: de.classList.contains('eiti-compact-header'),
        padTop: parseFloat(getComputedStyle(hdr).paddingTop), hdrH: hdr.getBoundingClientRect().height,
        h1Top: h1.getBoundingClientRect().top,
        btnVisible: !!btn && getComputedStyle(btn).display !== 'none' && btn.offsetParent !== null,
        banner: !!document.getElementById('pwa-install-banner'),
        tabPadBottom: parseFloat(getComputedStyle(document.querySelector('.tab-bar')).paddingBottom),
      };
    });
    expect(r.native).toBe(true);
    expect(r.preset).toBe('native');
    expect(r.compact).toBe(true);
    expect(r.padTop).toBe(40);
    expect(r.h1Top).toBeGreaterThanOrEqual(40);
    expect(r.hdrH).toBeLessThan(88 + 40);
    expect(r.btnVisible).toBe(false);
    expect(r.banner).toBe(false);
    expect(r.tabPadBottom).toBeGreaterThanOrEqual(48);
    // «👑 Большая золотая шапка» — опция
    await page.evaluate(() => eitiSetHeaderLarge(true));
    const big = await page.evaluate(() => ({ compact: document.documentElement.classList.contains('eiti-compact-header'), h: document.querySelector('.app-header').getBoundingClientRect().height, key: localStorage.getItem('eiti_header_size') }));
    expect(big).toEqual({ compact: false, h: 128, key: 'large' });
  });

  test('site: unchanged defaults (large header, no native preset)', async ({ page }) => {
    await boot(page, false);
    const r = await page.evaluate(() => ({
      native: document.documentElement.classList.contains('eiti-native'),
      phone: document.documentElement.classList.contains('eiti-phone'),
      compact: document.documentElement.classList.contains('eiti-compact-header'),
      h: document.querySelector('.app-header').getBoundingClientRect().height,
      isNative: window.eitiIsNative(),
    }));
    expect(r).toEqual({ native: false, phone: false, compact: false, h: 88, isNative: false });
  });

  test('Notes AI: no empty band above the tab bar (item 10)', async ({ page }) => {
    await boot(page, true, { eiti_notes_ai_enabled: '1' });
    const pad = async () => page.evaluate(() => {
      const overlay = document.getElementById('noteEditorOverlay');
      overlay.classList.add('active');
      window.eitiNotesAIOnEditorOpen(); window.eitiNotesAITogglePanel(true);
      const p = document.getElementById('notesAiPanel');
      return { panel: parseFloat(getComputedStyle(p).paddingBottom),
               tags: parseFloat(getComputedStyle(overlay.querySelector('.note-tags-row')).paddingBottom) };
    });
    expect(await pad()).toEqual({ panel: 0, tags: 60 });
    // таб-бара нет (полноэкранный редактор) → системный отступ нужен
    await page.evaluate(() => document.getElementById('noteEditorOverlay').classList.add('editor-fullscreen'));
    expect((await pad()).panel).toBe(48);
  });
});
