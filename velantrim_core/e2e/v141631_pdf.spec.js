// v14.16.31 (#28): PDF.js 6.5.438 из vendor/ (ES-модуль, воркер с того же origin);
// импорт PDF работает, getDocument получает isEvalSupported:false, cdnjs не запрашивается.
const { test, expect } = require('@playwright/test');

function minimalPdf(text) {
  const objs = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
    null,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ];
  const stream = 'BT /F1 18 Tf 20 80 Td (' + text + ') Tj ET';
  objs[3] = '<< /Length ' + stream.length + ' >>\nstream\n' + stream + '\nendstream';
  let out = '%PDF-1.4\n';
  const offs = [];
  objs.forEach((o, i) => { offs.push(out.length); out += (i + 1) + ' 0 obj\n' + o + '\nendobj\n'; });
  const xref = out.length;
  out += 'xref\n0 ' + (objs.length + 1) + '\n0000000000 65535 f \n' + offs.map((o) => String(o).padStart(10, '0') + ' 00000 n \n').join('');
  out += 'trailer\n<< /Size ' + (objs.length + 1) + ' /Root 1 0 R >>\nstartxref\n' + xref + '\n%%EOF\n';
  return out;
}

test.describe('v14.16.31 PDF.js (#28)', () => {
  test.use({ serviceWorkers: 'block' });
  test.setTimeout(90000);

  test('vendored PDF.js parses a PDF with safe options and no CDN / CSP issues', async ({ page }) => {
    const cdn = [];
    page.on('request', (r) => { if (/cdnjs\.cloudflare\.com|pdf\.js\/3\.11/.test(r.url())) cdn.push(r.url()); });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.addInitScript(() => {
      localStorage.setItem('eiti_onboarded', 'true'); localStorage.setItem('eiti_toured_v7', '1'); localStorage.setItem('eiti_install_hint_seen', '1');
      window.__csp = [];
      document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));
    });
    await page.goto('/index.html');
    await page.waitForFunction(() => window.eitiChatReady === true && !!window.pdfjsLib, null, { timeout: 30000 });
    const info = await page.evaluate(() => ({ v: pdfjsLib.version, worker: pdfjsLib.GlobalWorkerOptions.workerSrc }));
    expect(info.v).toBe('6.5.438');
    expect(info.worker).toMatch(/^http:\/\/127\.0\.0\.1:8099\/vendor\/pdfjs\/6\.5\.438\/pdf\.worker\.min\.mjs$/);
    const pdf = minimalPdf('Hello EITI PDF 6');
    const res = await page.evaluate(async (pdf) => {
      const seen = [];
      const orig = pdfjsLib.getDocument;
      // module namespace is frozen → wrap through window.pdfjsLib
      window.pdfjsLib = Object.assign({}, pdfjsLib, { getDocument: (o) => { seen.push({ isEvalSupported: o.isEvalSupported, enableXfa: o.enableXfa }); return orig(o); } });
      const bytes = new Uint8Array(pdf.length); for (let i = 0; i < pdf.length; i++) bytes[i] = pdf.charCodeAt(i);
      const file = new File([bytes], 'probe.pdf', { type: 'application/pdf' });
      const r = await eitiParseFile(file);
      return { text: r.text, method: r.method, seen };
    }, pdf);
    expect(res.method).toBe('PDF.js');
    expect(res.text).toContain('Hello EITI PDF 6');
    expect(res.seen).toEqual([{ isEvalSupported: false, enableXfa: false }]);
    expect(cdn).toEqual([]);
    expect(await page.evaluate(() => window.__csp)).toEqual([]);
    expect(errors.filter((e) => /pdf/i.test(e))).toEqual([]);
  });
});
