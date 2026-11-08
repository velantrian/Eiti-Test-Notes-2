// @ts-check
/**
 * v14.16.23 / PR #17: «Нижние табы» in chat «+» menu — browser regression.
 * Unit tests cover CSS/API stubs only; this exercises the real mobile UI.
 * Not covered by Issue #13 / v141621_thinking_format.spec.js.
 */
const { test, expect } = require('@playwright/test');

const VIEW = { width: 390, height: 844 };
const NON_CHAT = ['journal', 'history', 'player', 'files', 'notes', 'timeline', 'settings'];

async function boot(page, storage) {
  await page.setViewportSize(VIEW);
  await page.addInitScript((kv) => {
    localStorage.setItem('eiti_onboarded', 'true');
    localStorage.setItem('eiti_locale', 'ru');
    localStorage.setItem('eiti_toured_v7', '1');
    localStorage.setItem('eiti_install_hint_seen', '1');
    for (const [k, v] of Object.entries(kv || {})) {
      if (v == null) localStorage.removeItem(k);
      else localStorage.setItem(k, String(v));
    }
  }, storage || {});
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => window.eitiChatReady === true, null, { timeout: 30_000 });
  await expect(page.locator('#splash')).toBeHidden({ timeout: 15_000 });
  await page.addStyleTag({ content: '#eiti-pin-modal,#eiti-onboarding,#pwa-install-banner,.toast{display:none!important}' });
  await page.evaluate(() => {
    document.querySelectorAll('#eiti-onboarding,#eiti-pin-modal,.toast,#pwa-install-banner').forEach((e) => e.remove());
  });
}

async function openPlus(page) {
  await page.locator('#chat-plus-btn').click();
  await expect(page.locator('#chat-plus-popup.open')).toBeVisible();
  await expect(page.locator('#chat-plus-popup .chat-plus-tabs-rail')).toBeVisible();
  await expect(page.locator('#chat-plus-popup .cpi-tabs-pin')).toBeVisible();
}

async function visibleTabViews(page) {
  return page.evaluate(() => {
    return Array.from(document.querySelectorAll('.tab-bar .tab-item')).filter((el) => {
      const s = getComputedStyle(el);
      return s.display !== 'none' && s.visibility !== 'hidden' && el.getBoundingClientRect().width > 0;
    }).map((el) => el.getAttribute('data-view'));
  });
}

async function tabBarHeight(page) {
  return page.locator('.tab-bar').evaluate((el) => el.getBoundingClientRect().height);
}

async function messagesBottom(page) {
  return page.locator('#messages').evaluate((el) => el.getBoundingClientRect().bottom);
}

test.describe('PR #17 chat-only bottom tabs', () => {
  test.use({ viewport: VIEW, serviceWorkers: 'block' });

  test('«+» → Нижние табы OFF hides non-chat tabs and shrinks bar; ON restores', async ({ page }) => {
    await boot(page);
    expect(await page.evaluate(() => document.documentElement.classList.contains('eiti-chat-only-tabs'))).toBe(false);

    const beforeTabs = await visibleTabViews(page);
    expect(beforeTabs).toContain('chat');
    expect(beforeTabs.filter((v) => v !== 'chat').length).toBeGreaterThan(3);
    const hBefore = await tabBarHeight(page);
    const msgBefore = await messagesBottom(page);

    await openPlus(page);
    const pin = page.locator('#chat-plus-popup .cpi-tabs-pin');
    await expect(pin).toHaveClass(/on/);
    await pin.click();

    await expect.poll(() => page.evaluate(() => localStorage.getItem('eiti_chat_only_tabs'))).toBe('1');
    await expect.poll(() => page.evaluate(() => document.documentElement.classList.contains('eiti-chat-only-tabs'))).toBe(true);

    const only = await visibleTabViews(page);
    expect(only).toEqual(['chat']);
    for (const v of NON_CHAT) {
      await expect(page.locator(`.tab-item[data-view="${v}"]`)).toBeHidden();
    }

    const hAfter = await tabBarHeight(page);
    expect(hAfter).toBeLessThan(hBefore);
    expect(hAfter).toBeLessThanOrEqual(70); // ~56px (+ safe-area slack)
    const msgAfter = await messagesBottom(page);
    // more room for chat: messages area extends further down when tab bar shrinks
    expect(msgAfter).toBeGreaterThan(msgBefore - 1);

    // restore via same switch (popup may still be open after re-render — don't toggle «+» closed)
    const pop = page.locator('#chat-plus-popup');
    if (!(await pop.evaluate((el) => el.classList.contains('open')))) {
      await openPlus(page);
    }
    await expect(page.locator('#chat-plus-popup .cpi-tabs-pin')).not.toHaveClass(/on/);
    await page.locator('#chat-plus-popup .cpi-tabs-pin').click();
    await expect.poll(() => page.evaluate(() => localStorage.getItem('eiti_chat_only_tabs'))).toBe(null);
    const restored = await visibleTabViews(page);
    expect(restored).toContain('chat');
    expect(restored.filter((v) => v !== 'chat').length).toBeGreaterThan(3);
    expect(await tabBarHeight(page)).toBeGreaterThanOrEqual(hBefore - 1);
  });

  test('chat-only persists across reload (early <head> class)', async ({ page }) => {
    await boot(page, { eiti_chat_only_tabs: '1' });
    expect(await page.evaluate(() => document.documentElement.classList.contains('eiti-chat-only-tabs'))).toBe(true);
    expect(await visibleTabViews(page)).toEqual(['chat']);

    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => window.eitiChatReady === true, null, { timeout: 30_000 });
    await page.evaluate(() => document.querySelectorAll('#eiti-onboarding,#eiti-pin-modal,.toast').forEach((e) => e.remove()));

    expect(await page.evaluate(() => localStorage.getItem('eiti_chat_only_tabs'))).toBe('1');
    expect(await page.evaluate(() => document.documentElement.classList.contains('eiti-chat-only-tabs'))).toBe(true);
    expect(await visibleTabViews(page)).toEqual(['chat']);
  });

  test('enabling chat-only from another view returns to Chat', async ({ page }) => {
    await boot(page);
    await page.evaluate(() => {
      if (typeof openView === 'function') openView('notes');
      else if (typeof window._eitiSwitchView === 'function') window._eitiSwitchView('notes');
    });
    await expect(page.locator('#view-notes')).toHaveClass(/active/);
    await expect(page.locator('.tab-item[data-view="notes"]')).toHaveClass(/active/);

    // composer «+» lives on chat view — switch API still available; call toggle directly
    await page.evaluate(() => window.eitiSetChatOnlyTabs(true));

    await expect.poll(() => page.evaluate(() => {
      const v = document.querySelector('#view-chat');
      return !!(v && v.classList.contains('active'));
    })).toBe(true);
    await expect(page.locator('.tab-item[data-view="chat"]')).toHaveClass(/active/);
    expect(await visibleTabViews(page)).toEqual(['chat']);
  });
});
