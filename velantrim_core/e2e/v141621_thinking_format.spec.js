// @ts-check
/**
 * v14.16.21 / Issue #13 regression (browser):
 * collapsed thinking, provider toggles, strip service markers, clean copy,
 * mobile-readable markdown — DeepSeek / Gemini / OpenRouter via network stubs.
 *
 * No real API keys / paid calls. Synthetic SSE only.
 */
const { test, expect } = require('@playwright/test');

const MD_ANSWER =
  '## Заголовок\n\nПервый абзац ответа.\n\n> цитата модели\n\n1. пункт один\n2. пункт два\n\n```js\nconst x = 1;\n```\n\nКонец ✨';

const MARKER_TAIL =
  '\n[PKG_E:demo|x]\n[MEM_ADD:name=Test]\n[NOTE_WRITE:id=1]\n[TASK_ADD:do]\n[MOSC_ADD:a|b|1]\n[KB_ADD:c|t|ans]\n[FL_SET:threshold=0.7]';

function dsSse(parts) {
  // parts: [{ reasoning?, content? }, ...]
  let out = '';
  for (const p of parts) {
    const delta = {};
    if (p.reasoning) delta.reasoning_content = p.reasoning;
    if (p.content != null) delta.content = p.content;
    out += 'data: ' + JSON.stringify({ choices: [{ delta }] }) + '\n\n';
  }
  out += 'data: [DONE]\n\n';
  return out;
}

function orSse(parts) {
  let out = '';
  for (const p of parts) {
    const delta = {};
    if (p.reasoning) delta.reasoning = p.reasoning;
    if (p.content != null) delta.content = p.content;
    out += 'data: ' + JSON.stringify({ choices: [{ delta }] }) + '\n\n';
  }
  out += 'data: [DONE]\n\n';
  return out;
}

function geminiSse(parts) {
  // parts: [{ thought?: string, text?: string }]
  let out = '';
  for (const p of parts) {
    const part = p.thought
      ? { text: p.thought, thought: true }
      : { text: p.text || '' };
    out +=
      'data: ' +
      JSON.stringify({ candidates: [{ content: { parts: [part] } }] }) +
      '\n\n';
  }
  out += 'data: [DONE]\n\n';
  return out;
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {Record<string,string>} [extra]
 */
async function boot(page, extra) {
  await page.addInitScript((kv) => {
    localStorage.setItem('eiti_onboarded', 'true');
    localStorage.setItem('eiti_locale', 'ru');
    localStorage.setItem('eiti_toured_v7', '1');
    localStorage.setItem('eiti_install_hint_seen', '1');
    localStorage.setItem('eiti_offline_mode', '0');
    localStorage.removeItem('eiti_ds_off');
    for (const [k, v] of Object.entries(kv || {})) {
      if (v === null) localStorage.removeItem(k);
      else localStorage.setItem(k, v);
    }
  }, extra || {});
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => window.eitiChatReady === true && typeof window._obfKey === 'function', null, {
    timeout: 30_000,
  });
  await expect(page.locator('#splash')).toBeHidden({ timeout: 15_000 });
  await page.addStyleTag({ content: '#eiti-pin-modal,#eiti-onboarding,.toast{display:none!important}' });
  await page.evaluate(() => {
    document.querySelectorAll('#eiti-onboarding,#eiti-pin-modal,.toast').forEach((e) => e.remove());
  });
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
}

async function setProviderKeys(page, provider) {
  await page.evaluate(({ provider: p }) => {
    localStorage.setItem('eiti_ai_provider', p);
    localStorage.setItem('eiti_offline_mode', '0');
    localStorage.removeItem('eiti_ds_off');
    if (p === 'deepseek') {
      localStorage.setItem('deepseek_api_key', window._obfKey('sk-test-ds'));
      localStorage.setItem('eiti_ds_model', 'deepseek-v4-pro-high');
      localStorage.setItem('eiti_ds_show_thinking', '1');
    } else if (p === 'gemini') {
      localStorage.setItem('eiti_gemini_key', window._obfKey('AIza-test-gm'));
      localStorage.setItem('eiti_gemini_thinking', '1');
    } else if (p === 'openrouter') {
      localStorage.setItem('eiti_or_key', window._obfKey('sk-or-test'));
      localStorage.setItem('eiti_or_model', 'anthropic/claude-sonnet-5.5');
      localStorage.setItem('eiti_or_thinking', '1');
    }
  }, { provider });
}

async function sendChat(page, text) {
  await page.locator('#input').fill(text);
  await page.locator('#send').click();
}

async function lastAssistant(page) {
  return page.locator('#messages .message.incoming').last();
}

test.describe('Issue #13 thinking + format (stubbed providers)', () => {
  test.use({
    viewport: { width: 390, height: 844 },
    serviceWorkers: 'block',
  });

  test('DeepSeek Pro: thinking collapsed, markers gone, markdown readable, copy clean', async ({ page }) => {
    const seenBodies = [];
    await page.route('https://api.deepseek.com/**', async (route) => {
      const req = route.request();
      try {
        seenBodies.push(JSON.parse(req.postData() || '{}'));
      } catch (_) {
        seenBodies.push({});
      }
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: dsSse([
          { reasoning: 'Сначала оценю вопрос… ' },
          { reasoning: 'Потом составлю ответ с заголовком.' },
          { content: MD_ANSWER + MARKER_TAIL },
        ]),
      });
    });

    await boot(page);
    await setProviderKeys(page, 'deepseek');
    await sendChat(page, 'короткий вопрос');

    const msg = await lastAssistant(page);
    await expect(msg.locator('.eiti-think-box')).toBeVisible({ timeout: 15_000 });
    await expect(msg.locator('.eiti-think-status')).toContainText(/Размышлял/i);
    const thinkBody = msg.locator('.eiti-think-body');
    await expect(thinkBody).toBeHidden();
    // expand works
    await msg.locator('.eiti-think-head').click();
    await expect(thinkBody).toBeVisible();
    await expect(thinkBody).toContainText('оценю вопрос');
    await msg.locator('.eiti-think-head').click();
    await expect(thinkBody).toBeHidden();

    const text = msg.locator('[id$="-text"]');
    // eitiRenderMarkdown turns ## into bold <div>, not <h2>
    await expect.poll(async () => text.innerHTML(), { timeout: 10_000 }).toMatch(/font-weight:\s*700/);
    await expect(text).toContainText('Заголовок');
    await expect(text).toContainText(/цитата|Первый абзац/i);
    await expect(text).toContainText(/пункт/i);
    await expect(text).toContainText('Конец');
    await expect(text).toContainText('✨');
    await expect(text).not.toContainText('##');
    await expect(text).not.toContainText('PKG_E');
    await expect(text).not.toContainText('MEM_ADD');
    await expect(text).not.toContainText('NOTE_WRITE');
    await expect(text).not.toContainText('MOSC_ADD');
    await expect(text).not.toContainText('FL_SET');

    // request asked for thinking enabled
    expect(seenBodies.some((b) => b.thinking && b.thinking.type === 'enabled')).toBe(true);

    // copy button → clipboard without thinking / markers
    await msg.locator('.message-controls .msg-btn[title="Копировать"]').click();
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    expect(clip).toMatch(/Заголовок|Первый абзац/);
    expect(clip).not.toMatch(/PKG_E|MEM_ADD|NOTE_WRITE|оценю вопрос|Размышлял/);
  });

  test('DeepSeek Pro thinking OFF: no panel; request uses thinking:disabled', async ({ page }) => {
    const seenBodies = [];
    await page.route('https://api.deepseek.com/**', async (route) => {
      try {
        seenBodies.push(JSON.parse(route.request().postData() || '{}'));
      } catch (_) {
        seenBodies.push({});
      }
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        // even if API returned reasoning, UI must ignore when toggle off
        body: dsSse([
          { reasoning: 'это не должно появиться' },
          { content: 'Короткий ответ без панели.' },
        ]),
      });
    });

    await boot(page, { eiti_ds_show_thinking: '0', eiti_ds_model: 'deepseek-v4-pro-high' });
    await setProviderKeys(page, 'deepseek');
    await page.evaluate(() => localStorage.setItem('eiti_ds_show_thinking', '0'));
    await sendChat(page, 'привет');

    const msg = await lastAssistant(page);
    await expect(msg.locator('[id$="-text"]')).toContainText('Короткий ответ', { timeout: 15_000 });
    await expect(msg.locator('.eiti-think-box')).toHaveCount(0);
    expect(seenBodies.some((b) => b.thinking && b.thinking.type === 'disabled')).toBe(true);
  });

  test('DeepSeek Flash: thinking toggle N/A and no panel even if reasoning arrives', async ({ page }) => {
    await page.route('https://api.deepseek.com/**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: dsSse([{ reasoning: 'flash leak' }, { content: 'Flash ответ.' }]),
      })
    );
    await boot(page, { eiti_ds_model: 'deepseek-flash' });
    await setProviderKeys(page, 'deepseek');
    await page.evaluate(() => {
      localStorage.setItem('eiti_ds_model', 'deepseek-flash');
      if (typeof eitiRenderDsThinking === 'function') eitiRenderDsThinking();
    });

    // settings row note
    await page.evaluate(() => {
      if (typeof openView === 'function') openView('settings');
    });
    await expect(page.locator('#ds-thinking-note')).toContainText(/Неприменимо для Flash|Flash/i);
    await page.evaluate(() => {
      if (typeof openView === 'function') openView('chat');
    });

    await sendChat(page, 'flash q');
    const msg = await lastAssistant(page);
    await expect(msg.locator('[id$="-text"]')).toContainText('Flash ответ', { timeout: 15_000 });
    await expect(msg.locator('.eiti-think-box')).toHaveCount(0);
  });

  test('Gemini: thought parts → collapsed panel; answer markdown without markers', async ({ page }) => {
    const seenBodies = [];
    await page.route('https://generativelanguage.googleapis.com/**', async (route) => {
      try {
        seenBodies.push(JSON.parse(route.request().postData() || '{}'));
      } catch (_) {
        seenBodies.push({});
      }
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: geminiSse([
          { thought: 'Внутренний ход мыслей Gemini…' },
          { text: '## Gemini\n\nОтвет с **акцентом**.\n\n- пункт A\n- пункт B' + MARKER_TAIL },
        ]),
      });
    });

    await boot(page, { eiti_gemini_thinking: '1' });
    await setProviderKeys(page, 'gemini');
    await sendChat(page, 'gemini q');

    const msg = await lastAssistant(page);
    await expect(msg.locator('.eiti-think-box')).toBeVisible({ timeout: 15_000 });
    await expect(msg.locator('.eiti-think-body')).toBeHidden();
    await expect(msg.locator('.eiti-think-status')).toContainText(/Размышлял/i);
    const text = msg.locator('[id$="-text"]');
    await expect.poll(async () => text.innerHTML(), { timeout: 10_000 }).toMatch(/font-weight:\s*700|<b>/);
    await expect(text).toContainText('Gemini');
    await expect(text).toContainText('пункт');
    await expect(text).not.toContainText('##');
    await expect(text).not.toContainText('PKG_E');
    expect(
      seenBodies.some(
        (b) => b.generationConfig && b.generationConfig.thinkingConfig && b.generationConfig.thinkingConfig.includeThoughts
      )
    ).toBe(true);
  });

  test('Gemini thinking OFF: no panel', async ({ page }) => {
    await page.route('https://generativelanguage.googleapis.com/**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: geminiSse([{ thought: 'hidden' }, { text: 'Только ответ Gemini.' }]),
      })
    );
    await boot(page, { eiti_gemini_thinking: '0' });
    await setProviderKeys(page, 'gemini');
    await page.evaluate(() => localStorage.setItem('eiti_gemini_thinking', '0'));
    await sendChat(page, 'gm off');
    const msg = await lastAssistant(page);
    await expect(msg.locator('[id$="-text"]')).toContainText('Только ответ', { timeout: 15_000 });
    await expect(msg.locator('.eiti-think-box')).toHaveCount(0);
  });

  test('OpenRouter: reasoning collapsed; markers stripped; toggle off hides panel', async ({ page }) => {
    const seenBodies = [];
    await page.route('https://openrouter.ai/**', async (route) => {
      const url = route.request().url();
      if (url.includes('/models')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ data: [{ id: 'anthropic/claude-sonnet-5.5' }] }),
        });
        return;
      }
      try {
        seenBodies.push(JSON.parse(route.request().postData() || '{}'));
      } catch (_) {
        seenBodies.push({});
      }
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: orSse([
          { reasoning: 'OR internal chain…' },
          { content: '### OpenRouter\n\nЧитаемый абзац.' + MARKER_TAIL },
        ]),
      });
    });

    await boot(page, { eiti_or_thinking: '1', eiti_or_model: 'anthropic/claude-sonnet-5.5' });
    await setProviderKeys(page, 'openrouter');
    await sendChat(page, 'or q');

    const msg = await lastAssistant(page);
    await expect(msg.locator('.eiti-think-box')).toBeVisible({ timeout: 15_000 });
    await expect(msg.locator('.eiti-think-body')).toBeHidden();
    const orText = msg.locator('[id$="-text"]');
    await expect.poll(async () => orText.innerHTML(), { timeout: 10_000 }).toMatch(/font-weight:\s*700/);
    await expect(orText).toContainText('OpenRouter');
    await expect(orText).not.toContainText('###');
    await expect(orText).not.toContainText('PKG_E');

    // toggle off + new message → no panel
    await page.evaluate(() => localStorage.setItem('eiti_or_thinking', '0'));
    await sendChat(page, 'or q2');
    const msg2 = await lastAssistant(page);
    await expect(msg2.locator('[id$="-text"]')).toContainText(/OpenRouter|Читаемый/i, { timeout: 15_000 });
    await expect(msg2.locator('.eiti-think-box')).toHaveCount(0);
  });

  test('plain text without markdown stays tidy on mobile width', async ({ page }) => {
    await page.route('https://api.deepseek.com/**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: dsSse([
          {
            content:
              'Строка один без разметки.\n\nСтрока два тоже обычный текст, довольно длинная, чтобы проверить перенос на узком экране телефона.',
          },
        ]),
      })
    );
    await boot(page, { eiti_ds_model: 'deepseek-flash', eiti_ds_show_thinking: '0' });
    await setProviderKeys(page, 'deepseek');
    await page.evaluate(() => localStorage.setItem('eiti_ds_model', 'deepseek-flash'));
    await sendChat(page, 'plain');
    const text = (await lastAssistant(page)).locator('[id$="-text"]');
    await expect(text).toContainText('Строка один', { timeout: 15_000 });
    const box = await text.boundingBox();
    expect(box).toBeTruthy();
    expect(box.width).toBeLessThanOrEqual(390);
    const cs = await text.evaluate((el) => {
      const s = getComputedStyle(el);
      return { fontSize: parseFloat(s.fontSize), lineHeight: s.lineHeight };
    });
    expect(cs.fontSize).toBeGreaterThanOrEqual(15);
  });
});
