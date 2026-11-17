// v14.16.32 (item 11): правки длинного текста в Notes AI как в Notion — патч edits[], просмотр изменений с ✔/✖ по кускам,
// «Принять всё», «⚡ Применять сразу» для мелких правок, отмена ИИ-правки, поток SSE.
const { test, expect } = require('@playwright/test');
test.use({ locale: 'ru-RU', serviceWorkers: 'block' });

const LONG = Array.from({ length: 300 }, (_, i) => `Абзац ${i}: тут текст номер ${i}.`).join('\n\n');

function sseJson(obj) {
  const s = JSON.stringify(obj), a = s.slice(0, 40), b = s.slice(40);
  return ['data: ' + JSON.stringify({ choices: [{ delta: { content: a } }] }), 'data: ' + JSON.stringify({ choices: [{ delta: { content: b }, finish_reason: 'stop' }] }), 'data: [DONE]', ''].join('\n\n');
}

async function open(page, reply, applyNow) {
  const seen = [];
  await page.route('https://api.deepseek.com/**', (route) => { seen.push(JSON.parse(route.request().postData())); route.fulfill({ status: 200, contentType: 'text/event-stream', body: sseJson(reply) }); });
  await page.addInitScript((applyNow) => {
    localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1');
    localStorage.setItem('eiti_notes_ai_enabled', '1'); localStorage.setItem('eiti_notes_ai_apply_now', applyNow ? '1' : '0');
  }, applyNow);
  await page.setViewportSize({ width: 412, height: 915 });
  await page.goto('/index.html');
  await page.waitForFunction(() => typeof window.eitiNotesAISend === 'function' && typeof _obfKey === 'function' && !!window.EitiDocEdits && typeof eitiDb !== 'undefined' && !!eitiDb, null, { timeout: 30000 });
  await page.evaluate((LONG) => {
    localStorage.setItem('deepseek_api_key', _obfKey('sk-test')); localStorage.removeItem('eiti_ds_off');
    eitiNotesAISetModel('deepseek');
    const ob = document.getElementById('eiti-onboarding'); if (ob) ob.remove(); openView('notes');
    document.getElementById('notesNewBtn').click();
    const b = document.getElementById('noteEditorBody'); b.value = LONG; b.dispatchEvent(new Event('input', { bubbles: true }));
    document.getElementById('noteEditorTitle').value = 'Длинная';
    window.eitiNotesAIOnEditorOpen(); window.eitiNotesAITogglePanel(true);
  }, LONG);
  await page.waitForTimeout(900);
  return seen;
}

test('edits patch → diff preview; reject one hunk, apply selected; budget raised; stream', async ({ page }) => {
  const seen = await open(page, { reply: 'Исправила два абзаца', mutation: { action: 'edits', edits: [
    { find: 'Абзац 5: тут текст номер 5.', text: 'Абзац 5: ИСПРАВЛЕНО.' }, { find: 'Абзац 250: тут текст номер 250.', text: 'Абзац 250: ТОЖЕ.' }] } }, false);
  await page.evaluate(() => eitiNotesAISend('исправь абзацы 5 и 250'));
  const diff = page.locator('.notes-ai-diff');
  await expect(diff).toBeVisible({ timeout: 15000 });
  await expect(diff.locator('.nad-hunk')).toHaveCount(2);
  expect(await page.locator('#noteEditorBody').inputValue()).toBe(LONG); // ничего не применено до решения
  expect(seen[0].stream).toBe(true);
  expect(seen[0].max_tokens).toBeGreaterThanOrEqual(8000);
  expect(await page.evaluate(() => eitiDocAIOutputBudget(400000, 'deepseek'))).toBe(131072); // было ≤16K у DeepSeek
  expect(seen[0].messages[0].content).toContain('edits (edits — массив точечных правок');
  await diff.locator('.nad-hunk').nth(1).locator('.nad-no').click();
  await diff.locator('.nad-sel').click();
  await expect(diff).toHaveAttribute('data-done', '1');
  const body = await page.locator('#noteEditorBody').inputValue();
  expect(body).toContain('Абзац 5: ИСПРАВЛЕНО.');
  expect(body).toContain('Абзац 250: тут текст номер 250.');
  expect(body.length).toBe(LONG.length - 'тут текст номер 5.'.length + 'ИСПРАВЛЕНО.'.length);
  // ↩️ отмена правки ИИ
  await page.evaluate(() => eitiNotesAiUndoClick());
  await expect.poll(() => page.locator('#noteEditorBody').inputValue()).toBe(LONG);
});

test('«⚡ Применять сразу»: small edit applied without preview; missing fragment changes nothing', async ({ page }) => {
  await open(page, { reply: 'Готово', mutation: { action: 'edits', edits: [{ find: 'Абзац 9: тут', text: 'Абзац 9: здесь' }] } }, true);
  await page.evaluate(() => eitiNotesAISend('исправь абзац 9'));
  await expect.poll(() => page.locator('#noteEditorBody').inputValue(), { timeout: 15000 }).toContain('Абзац 9: здесь текст');
  await expect(page.locator('.notes-ai-diff')).toHaveCount(0);
});

test('fragment not found → no change, readable message', async ({ page }) => {
  await open(page, { reply: 'ок', mutation: { action: 'edits', edits: [{ find: 'Абзац 1: тут', text: 'X' }, { find: 'нет такого текста', text: 'Y' }] } }, false);
  await page.evaluate(() => eitiNotesAISend('исправь первый абзац'));
  await expect(page.locator('#notesAiMsgs')).toContainText('не найден', { timeout: 15000 });
  expect(await page.locator('#noteEditorBody').inputValue()).toBe(LONG);
});
