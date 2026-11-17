// v14.16.32 (items 7, 8): markdown без двойных зазоров вокруг пунктов/заголовков, висячий отступ, перенос длинных слов.
const { test, expect } = require('@playwright/test');

test.use({ serviceWorkers: 'block', viewport: { width: 393, height: 873 } });

test('markdown spacing: no <br> stacks around blocks, hanging indent, wraps long words', async ({ page }) => {
  await page.addInitScript(() => { localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1'); });
  await page.goto('/index.html');
  await page.waitForFunction(() => window.eitiChatReady === true && typeof eitiRenderMarkdown === 'function', null, { timeout: 30000 });
  const src = 'Вот что я умею ✨\n\n\n\nПамять и контекст\n· Помню наш профиль и прошлые сессии (дайджесты)\n\n· Ищу по истории чатов, если скажешь «посмотри историю»\n\n\nЗаметки 📝\n- Создать, дописать\n- Поиск\n\n## Файлы\n1. Создаю txt\n2. Читаю\n\nС чего начнём? 🚀\n';
  const r = await page.evaluate((src) => {
    const html = eitiRenderMarkdown(src);
    const host = document.createElement('div'); host.className = 'message incoming'; host.style.width = '300px';
    host.innerHTML = '<div class="message-body">' + html + eitiRenderMarkdown('https://example.com/' + 'a'.repeat(120)) + '</div>';
    document.getElementById('messages').appendChild(host);
    const li = host.querySelector('.md-li');
    return { html, brAfterDiv: /<\/div>(<br>)+/.test(html), brBeforeDiv: /(<br>){1,}<div/.test(html), triple: /(<br>){3,}/.test(html),
             gaps: (html.match(/md-gap/g) || []).length, indent: getComputedStyle(li).textIndent,
             overflow: host.scrollWidth > host.clientWidth + 1, h: host.getBoundingClientRect().height };
  }, src);
  expect(r.brAfterDiv).toBe(false);
  expect(r.brBeforeDiv).toBe(false);
  expect(r.triple).toBe(false);
  expect(r.gaps).toBeGreaterThan(0);
  expect(r.indent).toBe('-10px');
  expect(r.overflow).toBe(false);
  expect(r.html.startsWith('Вот что я умею ✨')).toBe(true);
});
