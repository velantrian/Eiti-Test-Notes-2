/* EITI Doc Edits — v14.16.32: точечные правки длинных текстов (как suggested edits в Notion).
 * Модель возвращает не весь текст, а патч: {"action":"edits","edits":[{"find":"старый фрагмент","text":"новый"}]}.
 *  - applyEdits(body, edits)   → атомарно: либо все фрагменты найдены однозначно, либо ничего не меняется;
 *                                 точное совпадение, затем «мягкое» (пробелы/переводы строк/кавычки/тире);
 *  - diffHunks(before, after)  → куски изменений по абзацам (для replace_note / append / любых правок);
 *  - applyHunks(before, hunks, accept) → текст только с принятыми кусками (✔/✖ по каждому);
 *  - changedParagraphs(hunks)  → сколько абзацев затронуто (порог «применять сразу»);
 *  - estimateTokens(chars)     → грубая оценка токенов.
 * Без DOM и без localStorage: тестируется в Node (velantrim_core/tests_js/doc_edits.test.js).
 */
(function (root, factory) {
    var M = factory();
    if (typeof module === 'object' && module.exports) module.exports = M;
    if (root && typeof root === 'object') root.EitiDocEdits = M;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function () {
    'use strict';

    // «мягкая» нормализация: одинаковые пробелы, кавычки и тире; карта позиций → исходный текст
    function softMap(s) {
        var out = '', map = [], prevSpace = false;
        for (var i = 0; i < s.length; i++) {
            var c = s[i];
            if (/\s/.test(c)) { if (prevSpace) continue; c = ' '; prevSpace = true; } else prevSpace = false;
            if (/[«»„“”"]/.test(c)) c = '"';
            else if (/[‘’']/.test(c)) c = "'";
            else if (/[–—−]/.test(c)) c = '-';
            else if (c === 'ё') c = 'е'; else if (c === 'Ё') c = 'Е';
            out += c; map.push(i);
        }
        map.push(s.length);
        return { s: out, map: map };
    }
    function softKey(s) { return softMap(String(s).trim()).s; }

    // все вхождения needle в hay → [{start, end}] в координатах исходного текста
    function findAll(hay, needle) {
        var res = [], at = hay.indexOf(needle);
        while (needle && at !== -1) { res.push({ start: at, end: at + needle.length, exact: true }); at = hay.indexOf(needle, at + 1); }
        if (res.length) return res;
        var H = softMap(hay), N = softKey(needle);
        if (!N) return res;
        var j = H.s.indexOf(N);
        while (j !== -1) { res.push({ start: H.map[j], end: H.map[j + N.length - 1] + 1, exact: false }); j = H.s.indexOf(N, j + 1); }
        return res;
    }

    function applyEdits(body, edits) {
        var text = String(body == null ? '' : body);
        if (!Array.isArray(edits) || !edits.length) return { ok: false, error: 'empty', message: 'Модель не прислала ни одной правки.' };
        var spans = [], errors = [];
        edits.forEach(function (e, i) {
            if (!e || typeof e !== 'object') { errors.push({ i: i, error: 'bad' }); return; }
            var find = typeof e.find === 'string' ? e.find : (typeof e.old === 'string' ? e.old : (typeof e.old_text === 'string' ? e.old_text : ''));
            var repl = typeof e.text === 'string' ? e.text : (typeof e.new === 'string' ? e.new : (typeof e.new_text === 'string' ? e.new_text : null));
            if (repl === null) { errors.push({ i: i, error: 'no_text' }); return; }
            if (!find && typeof e.from === 'string' && typeof e.to === 'string' && e.from && e.to) {
                // диапазон «от … до …» (раздел целиком, без повторения старого текста)
                var hf = findAll(text, e.from);
                if (hf.length !== 1) { errors.push({ i: i, error: hf.length ? 'ambiguous' : 'not_found', count: hf.length, find: e.from.slice(0, 80) }); return; }
                var rest = text.slice(hf[0].start), ht = findAll(rest, e.to);
                if (!ht.length) { errors.push({ i: i, error: 'not_found', find: e.to.slice(0, 80) }); return; }
                spans.push({ i: i, start: hf[0].start, end: hf[0].start + ht[0].end, text: repl, fuzzy: !hf[0].exact || !ht[0].exact }); return;
            }
            if (!find) {
                if (e.position === 'end' || e.append) { spans.push({ i: i, start: text.length, end: text.length, text: (text && !/\n$/.test(text) ? '\n\n' : '') + repl }); return; }
                errors.push({ i: i, error: 'no_find' }); return;
            }
            var hits = findAll(text, find);
            if (!hits.length) { errors.push({ i: i, error: 'not_found', find: find.slice(0, 80) }); return; }
            if (hits.length > 1) {
                var occ = typeof e.occurrence === 'number' ? e.occurrence : (e.all ? -1 : null);
                if (occ === -1) { hits.forEach(function (h) { spans.push({ i: i, start: h.start, end: h.end, text: repl }); }); return; }
                if (occ && hits[occ - 1]) { var hh = hits[occ - 1]; spans.push({ i: i, start: hh.start, end: hh.end, text: repl }); return; }
                errors.push({ i: i, error: 'ambiguous', count: hits.length, find: find.slice(0, 80) }); return;
            }
            spans.push({ i: i, start: hits[0].start, end: hits[0].end, text: repl, fuzzy: !hits[0].exact });
        });
        spans.sort(function (a, b) { return a.start - b.start || a.end - b.end; });
        for (var k = 1; k < spans.length; k++) if (spans[k].start < spans[k - 1].end) errors.push({ i: spans[k].i, error: 'overlap' });
        if (errors.length) {
            var e0 = errors[0];
            var why = e0.error === 'not_found' ? 'фрагмент не найден: «' + e0.find + '»'
                : e0.error === 'ambiguous' ? 'фрагмент встречается ' + e0.count + ' раз: «' + e0.find + '»'
                : e0.error === 'overlap' ? 'правки пересекаются' : 'неполная правка';
            return { ok: false, errors: errors, message: '⚠️ Правки не применены (текст не изменён): ' + why + '. Попроси уточнить место.' };
        }
        var out = '', pos = 0;
        spans.forEach(function (s) { out += text.slice(pos, s.start) + s.text; pos = s.end; });
        out += text.slice(pos);
        return { ok: true, body: out, count: spans.length, fuzzy: spans.filter(function (s) { return s.fuzzy; }).length };
    }

    // ── абзацный diff (LCS по абзацам; для очень длинных — общий префикс/суффикс + середина одним куском) ──
    function paras(s) { return String(s || '').split(/(\n{2,})/).reduce(function (acc, p, i, arr) { if (i % 2 === 0) acc.push(p + (arr[i + 1] || '')); return acc; }, []).filter(function (p, i, a) { return p !== '' || i < a.length - 1; }); }
    function diffHunks(before, after) {
        var A = paras(before), B = paras(after);
        var pre = 0; while (pre < A.length && pre < B.length && A[pre] === B[pre]) pre++;
        var suf = 0; while (suf < A.length - pre && suf < B.length - pre && A[A.length - 1 - suf] === B[B.length - 1 - suf]) suf++;
        var a = A.slice(pre, A.length - suf), b = B.slice(pre, B.length - suf);
        var ops = [];
        if (a.length * b.length <= 250000) {
            var n = a.length, m = b.length, L = [];
            for (var i = 0; i <= n; i++) { L.push(new Array(m + 1).fill(0)); }
            for (i = n - 1; i >= 0; i--) for (var j = m - 1; j >= 0; j--) L[i][j] = a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
            i = 0; j = 0;
            while (i < n || j < m) {
                if (i < n && j < m && a[i] === b[j]) { ops.push(['=', a[i]]); i++; j++; }
                else if (j < m && (i >= n || L[i][j + 1] >= L[i + 1][j])) { ops.push(['+', b[j]]); j++; }
                else { ops.push(['-', a[i]]); i++; }
            }
        } else { a.forEach(function (p) { ops.push(['-', p]); }); b.forEach(function (p) { ops.push(['+', p]); }); }
        // склеиваем соседние -/+ в куски; offset — позиция в исходном тексте
        var hunks = [], off = A.slice(0, pre).join('').length, cur = null;
        ops.forEach(function (op) {
            if (op[0] === '=') { if (cur) { hunks.push(cur); cur = null; } off += op[1].length; return; }
            if (!cur) cur = { start: off, end: off, old: '', text: '' };
            if (op[0] === '-') { cur.old += op[1]; cur.end += op[1].length; off += op[1].length; } else cur.text += op[1];
        });
        if (cur) hunks.push(cur);
        hunks.forEach(function (h, k) { h.id = k; h.paras = Math.max(paras(h.old).length, paras(h.text).length); });
        return hunks;
    }
    function applyHunks(before, hunks, accept) {
        var text = String(before || ''), out = '', pos = 0;
        (hunks || []).slice().sort(function (x, y) { return x.start - y.start; }).forEach(function (h) {
            out += text.slice(pos, h.start);
            out += (accept ? accept(h) : true) ? h.text : h.old;
            pos = h.end;
        });
        return out + text.slice(pos);
    }
    function changedParagraphs(hunks) { return (hunks || []).reduce(function (s, h) { return s + (h.paras || 1); }, 0); }
    function estimateTokens(chars) { return Math.ceil((Number(chars) || 0) / 2.6); }
    return { applyEdits: applyEdits, diffHunks: diffHunks, applyHunks: applyHunks, changedParagraphs: changedParagraphs, estimateTokens: estimateTokens, _softKey: softKey };
});
