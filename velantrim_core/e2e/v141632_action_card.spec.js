// v14.16.32 (item 9): карточка «EITI просит подтверждения» после «✅ Выполнено» / «⛔ Отклонено» сворачивается
// в одну строку с «подробнее»; предпросмотр читаемый (текст факта, а не сырая команда KB_ADD arts|…|…).
const { test, expect } = require('@playwright/test');

function sse(text) { return 'data: ' + JSON.stringify({ choices: [{ delta: { content: text } }] }) + '\n\ndata: [DONE]\n\n'; }

async function boot(page, reply) {
  await page.route('https://api.deepseek.com/**', (route) => route.fulfill({ status: 200, contentType: 'text/event-stream', body: sse(reply) }));
  await page.addInitScript(() => {
    localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_locale', 'ru');
    localStorage.setItem('eiti_toured_v7', '1'); localStorage.setItem('eiti_install_hint_seen', '1');
  });
  await page.goto('/index.html');
  await page.waitForFunction(() => !!window.EitiActionGate && typeof window._obfKey === 'function' && window.eitiChatReady === true && !!window.eitiDb, null, { timeout: 30000 });
  await expect(page.locator('#splash')).toBeHidden({ timeout: 15000 });
  await page.addStyleTag({ content: '#eiti-pin-modal{display:none!important}' });
  await page.evaluate(() => {
    document.querySelectorAll('#eiti-onboarding, .toast').forEach((e) => e.remove());
    localStorage.setItem('eiti_ai_provider', 'deepseek');
    localStorage.setItem('deepseek_api_key', window._obfKey('sk-test-key-123'));
    localStorage.removeItem('eiti_ds_off');
    localStorage.setItem('eiti_strict_memory_mode', '0'); localStorage.setItem('eiti_offline_mode', '0');
  });
}

test('KB_ADD card: readable preview, collapses after done, expands on «подробнее»', async ({ page }) => {
  await boot(page, 'Запомнила. [KB_ADD:arts|есенин,стихи есенина|🌿 У Есенина чаще всего называют «Не жалею, не зову, не плачу…»]');
  await page.locator('#input').fill('Какой лучший стих Есенина?');
  await page.locator('#send').click();
  const card = page.locator('.eiti-action-card').first();
  await expect(card).toBeVisible({ timeout: 15000 });
  await expect(card.locator('.eiti-action-preview')).toHaveText('🌿 У Есенина чаще всего называют «Не жалею, не зову, не плачу…»');
  await expect(card.locator('.eiti-action-meta')).toHaveText('arts · есенин, стихи есенина');
  await expect(card.locator('.eiti-action-raw')).not.toHaveAttribute('open', '');
  const h0 = (await card.boundingBox()).height;
  await card.locator('.eiti-action-ok').click();
  await expect(card).toHaveAttribute('data-gate-state', 'done', { timeout: 10000 });
  await expect(card).toHaveAttribute('data-gate-collapsed', '1');
  await expect(card.locator('.eiti-action-body')).toBeHidden();
  await expect(card.locator('.eiti-action-sum-text')).toContainText('✅ Выполнено');
  const h1 = (await card.boundingBox()).height;
  expect(h1).toBeLessThan(44);
  expect(h1).toBeLessThan(h0 / 2);
  await card.locator('.eiti-action-more').click();
  await expect(card.locator('.eiti-action-body')).toBeVisible();
  await expect(card.locator('.eiti-action-more')).toHaveText('свернуть');
});

test('denied card collapses too', async ({ page }) => {
  await boot(page, 'Хорошо. [MEM_DEL:work|]');
  await page.evaluate(async () => { await memSaveEntry({ text: 'работа: Альфа', tag: 'work', source: 'user' }); });
  await page.locator('#input').fill('Как дела?');
  await page.locator('#send').click();
  const card = page.locator('.eiti-action-card[data-gate-type="MEM_DEL"]');
  await expect(card).toBeVisible({ timeout: 15000 });
  await card.locator('.eiti-action-no').click();
  await expect(card).toHaveAttribute('data-gate-collapsed', '1');
  await expect(card.locator('.eiti-action-sum-text')).toContainText('⛔ Отклонено');
});
