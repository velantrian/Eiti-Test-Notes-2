/* v14.16.32: EitiTransfer — перенос настроек и данных между копиями EITI (сайт → APK и обратно).
 * Без DOM. Пакет eiti.transfer.v1 = localStorage (через EitiNS — только своя копия) + IndexedDB eiti_v4.
 * Blob/File/ArrayBuffer/Date кодируются в JSON. API-ключи — только по явной галочке.
 * Каналы (providers): «file» работает сейчас; Google Drive / Dropbox — подключаемые, пока НЕ подключены
 * (нужны OAuth-клиенты: Google — Android-клиент com.velantrim.eiti + SHA-1 подписи; Dropbox — app key).
 */
(function (root) {
    'use strict';
    var FORMAT = 'eiti.transfer.v1';
    var IDB_DBS = ['eiti_v4'];
    var SKIP_STORES = { tts_cache: 1, backups: 1 };          // кэш озвучки и локальные бэкапы — не переносим
    var SKIP_LS = /^(__eiti_ns_|eiti_or_catalog_v1$|eiti_kb_all_downloaded$|eiti_default_tracks_removed$|webllm|mlc|eiti_settings_audience_mode_v1$|eiti_drive_(?!client_id$))/; // вход в Drive у каждой копии свой
    var SECRET_LS = /(^|_)(key|apikey|api_key|token|secret|password|pass)(s)?($|_)|_key_|oauth|refresh/i;

    var NOT_SECRET = /^eiti_token_(budget|stats)$|^eiti_keys_migrated_v1$/;
    function isSecretKey(k) { return SECRET_LS.test(k) && !NOT_SECRET.test(k); }

    // ── кодирование значений ──
    function b64(buf) {
        var bytes = new Uint8Array(buf), s = '', CH = 0x8000;
        for (var i = 0; i < bytes.length; i += CH) s += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
        return (typeof btoa === 'function') ? btoa(s) : Buffer.from(s, 'binary').toString('base64');
    }
    function unb64(str) {
        var bin = (typeof atob === 'function') ? atob(str) : Buffer.from(str, 'base64').toString('binary');
        var out = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
        return out;
    }
    function encode(v) {
        if (v == null || typeof v !== 'object') return Promise.resolve(v);
        if (typeof Blob !== 'undefined' && v instanceof Blob) {
            return v.arrayBuffer().then(function (ab) {
                var o = { __eiti: 'blob', type: v.type || '', data: b64(ab) };
                if (typeof File !== 'undefined' && v instanceof File) { o.__eiti = 'file'; o.name = v.name; o.lastModified = v.lastModified; }
                return o;
            });
        }
        if (v instanceof Date) return Promise.resolve({ __eiti: 'date', v: v.getTime() });
        if (v instanceof ArrayBuffer) return Promise.resolve({ __eiti: 'ab', data: b64(v) });
        if (ArrayBuffer.isView(v)) return Promise.resolve({ __eiti: 'ta', t: v.constructor.name, data: b64(v.buffer.slice(v.byteOffset, v.byteOffset + v.byteLength)) });
        if (Array.isArray(v)) return Promise.all(v.map(encode));
        var keys = Object.keys(v);
        return Promise.all(keys.map(function (k) { return encode(v[k]); })).then(function (vals) {
            var o = {}; keys.forEach(function (k, i) { o[k] = vals[i]; }); return o;
        });
    }
    function decode(v) {
        if (v == null || typeof v !== 'object') return v;
        if (Array.isArray(v)) return v.map(decode);
        switch (v.__eiti) {
            case 'date': return new Date(v.v);
            case 'ab': return unb64(v.data).buffer;
            case 'ta': { var C = root[v.t] || Uint8Array; var u = unb64(v.data); return new C(u.buffer, 0, u.byteLength / (C.BYTES_PER_ELEMENT || 1)); }
            case 'blob': return new Blob([unb64(v.data)], { type: v.type });
            case 'file': return (typeof File !== 'undefined') ? new File([unb64(v.data)], v.name, { type: v.type, lastModified: v.lastModified }) : new Blob([unb64(v.data)], { type: v.type });
        }
        var o = {}; Object.keys(v).forEach(function (k) { o[k] = decode(v[k]); }); return o;
    }

    // ── IndexedDB ──
    function idbOpen(name) {
        return new Promise(function (res, rej) {
            var idb = root.indexedDB; if (!idb) return rej(new Error('IndexedDB недоступен'));
            var r = idb.open(name);
            r.onsuccess = function () { res(r.result); };
            r.onerror = function () { rej(r.error); };
            r.onupgradeneeded = function () { /* БД ещё не создана этой копией — пусто */ };
        });
    }
    function reqP(r) { return new Promise(function (res, rej) { r.onsuccess = function () { res(r.result); }; r.onerror = function () { rej(r.error); }; }); }
    function dumpDb(name) {
        return idbOpen(name).then(function (db) {
            var stores = Array.prototype.slice.call(db.objectStoreNames).filter(function (s) { return !SKIP_STORES[s]; });
            return Promise.all(stores.map(function (s) {
                var tx = db.transaction(s, 'readonly'), os = tx.objectStore(s);
                return Promise.all([reqP(os.getAll()), os.keyPath == null ? reqP(os.getAllKeys()) : Promise.resolve(null)]).then(function (r) {
                    return encode(r[0]).then(function (vals) { return { name: s, keyPath: os.keyPath, rows: vals, keys: r[1] }; });
                });
            })).then(function (list) { db.close(); var o = {}; list.forEach(function (x) { o[x.name] = x; }); return o; });
        });
    }
    function loadDb(name, stores, mode) {
        return idbOpen(name).then(function (db) {
            var report = {};
            var names = Object.keys(stores).filter(function (s) { return db.objectStoreNames.contains(s) && !SKIP_STORES[s]; });
            return names.reduce(function (p, s) {
                return p.then(function () {
                    return new Promise(function (res, rej) {
                        var tx = db.transaction(s, 'readwrite'), os = tx.objectStore(s), src = stores[s], n = 0;
                        if (mode === 'replace') os.clear();
                        (src.rows || []).forEach(function (row, i) {
                            var val = decode(row);
                            if (os.keyPath == null && src.keys) os.put(val, src.keys[i]); else os.put(val);
                            n++;
                        });
                        tx.oncomplete = function () { report[s] = n; res(); };
                        tx.onerror = function () { rej(tx.error); };
                        tx.onabort = function () { rej(tx.error || new Error('abort ' + s)); };
                    });
                });
            }, Promise.resolve()).then(function () { db.close(); return report; });
        });
    }

    // ── пакет ──
    function collect(opts) {
        opts = opts || {};
        var ls = root.localStorage, out = {}, skippedSecrets = 0;
        for (var i = 0; i < ls.length; i++) {
            var k = ls.key(i);
            if (!k || SKIP_LS.test(k)) continue;
            if (isSecretKey(k) && !opts.includeSecrets) { skippedSecrets++; continue; }
            out[k] = ls.getItem(k);
        }
        var dbs = opts.dbs || IDB_DBS;
        return Promise.all(dbs.map(function (d) { return dumpDb(d).catch(function () { return null; }); })).then(function (dumps) {
            var idb = {}; dbs.forEach(function (d, i) { if (dumps[i]) idb[d] = dumps[i]; });
            return {
                format: FORMAT, app: 'VELANTRIM EITI', version: root.EITI_VERSION || '', created: new Date().toISOString(),
                from: root.EITI_NATIVE ? 'apk' : 'site', secrets: !!opts.includeSecrets, skippedSecrets: skippedSecrets,
                ls: out, idb: idb
            };
        });
    }
    function validate(b) {
        if (!b || typeof b !== 'object' || b.format !== FORMAT) return 'Это не файл переноса EITI (' + FORMAT + ')';
        if (typeof b.ls !== 'object' || typeof b.idb !== 'object') return 'Файл повреждён';
        return '';
    }
    function apply(b, opts) {
        opts = opts || {};
        var err = validate(b); if (err) return Promise.reject(new Error(err));
        var ls = root.localStorage, nLs = 0;
        Object.keys(b.ls).forEach(function (k) {
            if (SKIP_LS.test(k)) return;
            if (isSecretKey(k) && opts.keepLocalSecrets && ls.getItem(k)) return; // не затираем ключи, уже введённые на этом устройстве
            try { ls.setItem(k, b.ls[k]); nLs++; } catch (e) {}
        });
        var dbs = Object.keys(b.idb).filter(function (d) { return IDB_DBS.indexOf(d) !== -1; });
        return dbs.reduce(function (p, d) {
            return p.then(function (acc) { return loadDb(d, b.idb[d], opts.mode || 'merge').then(function (r) { acc[d] = r; return acc; }); });
        }, Promise.resolve({})).then(function (idb) { return { ls: nLs, idb: idb }; });
    }
    function toBlob(b) { return new Blob([JSON.stringify(b)], { type: 'application/json' }); }
    function fileName() { return 'eiti-transfer-' + new Date().toISOString().slice(0, 10) + '.eiti.json'; }

    // ── каналы переноса ──
    var providers = {};
    function registerProvider(p) {
        if (!p || !p.id) throw new Error('provider.id');
        providers[p.id] = p; return p;
    }
    registerProvider({
        id: 'file', label: '📁 Файл', available: function () { return true; },
        save: function (blob, name, env) { return (env && env.download ? env.download(blob, name) : Promise.reject(new Error('download()'))); },
        load: function (env) { return (env && env.pick ? env.pick() : Promise.reject(new Error('pick()'))); }
    });
    // Заглушки-описания, честно недоступные, пока нет OAuth-клиентов (никаких фейковых «успешно»).
    registerProvider({ id: 'gdrive', label: '☁️ Google Drive', needs: 'OAuth-клиент Google (Android: com.velantrim.eiti + SHA-1 подписи релиза; веб: origin сайта)',
        available: function () { return false; }, save: function () { return Promise.reject(new Error('Google Drive для переноса ещё не подключён')); }, load: function () { return Promise.reject(new Error('Google Drive для переноса ещё не подключён')); } });
    registerProvider({ id: 'dropbox', label: '📦 Dropbox', needs: 'Dropbox App key (PKCE, redirect velantrim-eiti://)',
        available: function () { return false; }, save: function () { return Promise.reject(new Error('Dropbox ещё не подключён')); }, load: function () { return Promise.reject(new Error('Dropbox ещё не подключён')); } });

    var api = { FORMAT: FORMAT, collect: collect, apply: apply, validate: validate, toBlob: toBlob, fileName: fileName,
        encode: encode, decode: decode, isSecretKey: isSecretKey, providers: providers, registerProvider: registerProvider };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    root.EitiTransfer = api;
})(typeof window !== 'undefined' ? window : globalThis);
