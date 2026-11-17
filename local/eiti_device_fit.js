/* v14.16.32: EitiDeviceFit — какие офлайн-модели ИИ потянет это устройство.
 * Без DOM. Источники: navigator.deviceMemory (браузер округляет и ограничивает 8 ГБ), hardwareConcurrency,
 * WebGPU (adapter.limits, shader-f16), navigator.storage.estimate(); в APK — точные ОЗУ/память/модель
 * из нативного плагина EitiBackground.deviceInfo().
 * Каталог — модели WebLLM 0.2.88 (prebuiltAppConfig: model_id и vram_required_MB взяты оттуда).
 */
(function (root) {
    'use strict';
    var GB = 1024 * 1024 * 1024;

    // tier: fast (0.8–2B) | smart (~4B) | large (8–9B, нужно ~12 ГБ ОЗУ). vramMB — из WebLLM; dlGB — примерный размер загрузки.
    var CATALOG = [
        { id: 'Qwen3.5-0.8B-q4f16_1-MLC', name: 'Qwen 3.5 — 0.8B', tier: 'fast', vramMB: 1629, dlGB: 0.6, langs: 'RU · EN · DE · 200+ языков', note: 'самая быстрая' },
        { id: 'Qwen3.5-2B-q4f16_1-MLC', name: 'Qwen 3.5 — 2B', tier: 'fast', vramMB: 2245, dlGB: 1.3, langs: 'RU · EN · DE', note: 'быстро и заметно умнее' },
        { id: 'Llama-3.2-1B-Instruct-q4f16_1-MLC', name: 'Llama 3.2 — 1B', tier: 'fast', vramMB: 879, dlGB: 0.7, langs: 'EN · DE · (RU слабее)', note: 'минимум памяти' },
        { id: 'gemma3-1b-it-q4f16_1-MLC', name: 'Gemma 3 — 1B', tier: 'fast', vramMB: 711, dlGB: 0.7, langs: 'RU · EN · DE', note: 'минимум памяти' },
        { id: 'Qwen3.5-4B-q4f16_1-MLC', name: 'Qwen 3.5 — 4B', tier: 'smart', vramMB: 3868, dlGB: 2.5, langs: 'RU · EN · DE', note: 'лучшая из средних' },
        { id: 'Phi-4-mini-instruct-q4f16_1-MLC', name: 'Phi-4 mini — 3.8B', tier: 'smart', vramMB: 3438, dlGB: 2.2, langs: 'EN · (RU/DE средне)', note: 'логика, код' },
        { id: 'Ministral-3-3B-Instruct-2512-BF16-q4f16_1-MLC', name: 'Ministral 3 — 3B', tier: 'smart', vramMB: 2864, dlGB: 1.9, langs: 'RU · EN · DE · FR', note: 'Mistral, европейские языки' },
        { id: 'gemma-4-E2B-it-q4f16_1-MLC', name: 'Gemma 4 — E2B', tier: 'smart', vramMB: 3387, dlGB: 2.0, langs: 'RU · EN · DE', note: 'Google, новая' },
        { id: 'Qwen3.5-9B-q4f16_1-MLC', name: 'Qwen 3.5 — 9B', tier: 'large', vramMB: 6433, dlGB: 5.3, langs: 'RU · EN · DE', note: 'самая умная офлайн · ~12 ГБ ОЗУ' },
        { id: 'Qwen3-8B-q4f16_1-MLC', name: 'Qwen 3 — 8B', tier: 'large', vramMB: 5696, dlGB: 4.6, langs: 'RU · EN · DE', note: 'рассуждения (thinking)' },
        { id: 'gemma-2-9b-it-q4f16_1-MLC', name: 'Gemma 2 — 9B', tier: 'large', vramMB: 6422, dlGB: 5.2, langs: 'RU · EN · DE', note: 'классика, ровные тексты' }
    ];
    // офлайн-эмбеддинги (поиск по смыслу), уже есть в «🧠 Офлайн-поиск»: многоязычные
    var EMBEDDINGS = [
        { id: 'paraphrase-multilingual-MiniLM-L12-v2', name: 'Multilingual MiniLM L12', ramMB: 300, dlGB: 0.12 },
        { id: 'multilingual-e5-small', name: 'multilingual-e5-small', ramMB: 300, dlGB: 0.12 },
        { id: 'LaBSE', name: 'LaBSE', ramMB: 900, dlGB: 0.47 }
    ];
    var TIERS = { fast: '⚡ Быстрые (0.8–2B)', smart: '🧠 Умнее (~4B)', large: '🏋️ Крупные (8–9B, до ~12 ГБ)' };

    function num(v) { v = Number(v); return isFinite(v) && v > 0 ? v : 0; }

    /** Собрать сведения об устройстве. env — для тестов (navigator, nativeInfo). */
    function probe(env) {
        env = env || {};
        var nav = env.navigator || (typeof navigator !== 'undefined' ? navigator : {});
        var nativeP = env.nativeInfo ? Promise.resolve(env.nativeInfo)
            : (root.EitiCap && root.EitiCap.bg && root.EitiCap.bg.available ? root.EitiCap.bg.deviceInfo().catch(function () { return null; }) : Promise.resolve(null));
        var gpuP = Promise.resolve(null);
        if (nav.gpu && typeof nav.gpu.requestAdapter === 'function') {
            gpuP = Promise.resolve().then(function () { return nav.gpu.requestAdapter(); }).then(function (a) {
                if (!a) return { ok: false };
                var L = a.limits || {};
                var f16 = !!(a.features && typeof a.features.has === 'function' && a.features.has('shader-f16'));
                return { ok: true, f16: f16, maxBufferMB: Math.round(num(L.maxBufferSize) / 1048576), maxStorageMB: Math.round(num(L.maxStorageBufferBindingSize) / 1048576) };
            }).catch(function () { return { ok: false }; });
        }
        var stP = (nav.storage && typeof nav.storage.estimate === 'function') ? nav.storage.estimate().catch(function () { return null; }) : Promise.resolve(null);
        return Promise.all([nativeP, gpuP, stP]).then(function (r) {
            var nat = r[0], gpu = r[1] || { ok: false }, st = r[2];
            var dev = {
                native: !!nat,
                model: nat ? [nat.manufacturer, nat.model].filter(Boolean).join(' ') : '',
                cores: num(nat && nat.cores) || num(nav.hardwareConcurrency),
                ramGB: 0, ramExact: false, freeGB: 0, gpu: gpu
            };
            if (nat && num(nat.totalRam)) { dev.ramGB = Math.round(num(nat.totalRam) / GB * 10) / 10; dev.ramExact = true; }
            else if (num(nav.deviceMemory)) { dev.ramGB = num(nav.deviceMemory); dev.ramCapped = dev.ramGB >= 8; } // браузер не сообщает больше 8
            if (nat && num(nat.freeStorage)) dev.freeGB = Math.round(num(nat.freeStorage) / GB * 10) / 10;
            else if (st && num(st.quota)) dev.freeGB = Math.round((num(st.quota) - num(st.usage)) / GB * 10) / 10;
            return dev;
        });
    }

    /** Оценка: { level: 'ok'|'tight'|'no'|'unknown', reason } */
    function rate(m, dev) {
        if (!dev) return { level: 'unknown', reason: '' };
        if (!dev.gpu || !dev.gpu.ok) return { level: 'no', reason: 'нет WebGPU — только WASM-модели' };
        var need = m.vramMB / 1024;
        if (dev.freeGB && dev.freeGB < m.dlGB * 1.3) return { level: 'no', reason: 'мало места: нужно ~' + (Math.ceil(m.dlGB * 1.3 * 10) / 10) + ' ГБ' };
        var reasons = [];
        var level = 'ok';
        if (dev.ramGB) {
            // телефон: память общая с системой — модели доступно ~55 % ОЗУ (впритык — до 75 %)
            var ram = dev.ramGB;
            if (dev.ramCapped && !dev.ramExact) {
                // браузер показал «8» — реальная может быть больше: крупные помечаем «впритык», а не «нет»
                if (need > ram * 0.75) { level = 'tight'; reasons.push('нужно ~' + Math.ceil(need / 0.55) + ' ГБ ОЗУ'); }
            } else if (need > ram * 0.75) return { level: 'no', reason: 'не хватит ОЗУ: нужно ~' + Math.ceil(need / 0.55) + ' ГБ, есть ' + ram + ' ГБ' };
            else if (need > ram * 0.55) { level = 'tight'; reasons.push('впритык по ОЗУ (' + ram + ' ГБ)'); }
        } else { level = need > 3 ? 'tight' : 'ok'; if (need > 3) reasons.push('ОЗУ неизвестно'); }
        if (dev.gpu.maxBufferMB && dev.gpu.maxBufferMB < 256 && need > 1) { level = level === 'ok' ? 'tight' : level; reasons.push('малый буфер GPU'); }
        if (!dev.gpu.f16 && /q4f16/.test(m.id)) { level = level === 'ok' ? 'tight' : level; reasons.push('GPU без shader-f16 — медленнее'); }
        return { level: level, reason: reasons.join(' · ') };
    }

    /** Лучшая модель для устройства: самая крупная «ok» (с языком RU) из fast → smart → large; иначе самая лёгкая «tight». */
    function recommend(dev, list) {
        list = list || CATALOG;
        var ok = list.filter(function (m) { return rate(m, dev).level === 'ok' && /RU/.test(m.langs) && !/слабее|средне/.test(m.langs); });
        if (ok.length) return ok.reduce(function (a, b) { return b.vramMB > a.vramMB ? b : a; });
        var tight = list.filter(function (m) { return rate(m, dev).level === 'tight'; });
        if (tight.length) return tight.reduce(function (a, b) { return b.vramMB < a.vramMB ? b : a; });
        return null;
    }

    function summary(dev) {
        if (!dev) return '';
        var p = [];
        if (dev.model) p.push('📱 ' + dev.model);
        if (dev.ramGB) p.push('ОЗУ ' + (dev.ramCapped && !dev.ramExact ? '≥ ' : '') + dev.ramGB + ' ГБ');
        if (dev.cores) p.push(dev.cores + ' ядер');
        p.push(dev.gpu && dev.gpu.ok ? 'WebGPU ✅' + (dev.gpu.f16 ? ' f16' : '') : 'WebGPU ❌');
        if (dev.freeGB) p.push('свободно ' + dev.freeGB + ' ГБ');
        return p.join(' · ');
    }

    var api = { CATALOG: CATALOG, EMBEDDINGS: EMBEDDINGS, TIERS: TIERS, probe: probe, rate: rate, recommend: recommend, summary: summary };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    root.EitiDeviceFit = api;
})(typeof window !== 'undefined' ? window : globalThis);
