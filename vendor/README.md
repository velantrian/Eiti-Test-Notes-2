# vendor/ — сторонние библиотеки времени выполнения

v14.16.30 (#27): библиотеки, которые раньше грузились с CDN, лежат здесь с **точной версией в пути**.
`index.html` подключает их с атрибутом `integrity` (SRI, sha384), `sw.js` кэширует их офлайн,
`scripts/build_pages.py` публикует их по явному списку. Обновление = новая папка версии + новый хэш
(проверяется `velantrim_core/tests/test_v141630.py`). Файлы не редактировать вручную.

| Библиотека | Версия | Файл | Источник | Лицензия |
|---|---|---|---|---|
| DOMPurify | 3.4.18 | `dompurify/3.4.18/purify.min.js` | npm `dompurify@3.4.18` → `dist/purify.min.js` | Apache-2.0 / MPL-2.0 |
| PDF.js (pdfjs-dist, legacy build) | 6.5.438 | `pdfjs/6.5.438/pdf.min.mjs`, `pdf.worker.min.mjs` | npm `pdfjs-dist@6.5.438` → `legacy/build/` | Apache-2.0 |
| mammoth | 1.13.0 | `mammoth/1.13.0/mammoth.browser.min.js` | npm `mammoth@1.13.0` → `mammoth.browser.min.js` | BSD-2-Clause |
| Fluent Emoji 3D (8 иконок таб-бара) | git `1ffb34c` | `fluent-emoji-3d/*.webp` (96 px) | github.com/microsoft/fluentui-emoji → `assets/*/3D/*_3d.png`, см. `fluent-emoji-3d/README.md` | MIT |

PDF.js — ES-модули: `<script type="module">` в `index.html` импортирует `pdf.min.mjs` и ставит `window.pdfjsLib`; целостность модулей — через `integrity` в `<script type="importmap">` и `<link rel="modulepreload" integrity>` (браузеры без поддержки ключа его игнорируют). Legacy-сборка выбрана ради старых iOS Safari. Открытие PDF — только через `eitiPdfOpenOptions()` (`isEvalSupported:false`, `enableXfa:false`); в 6.x eval-путь шрифтов удалён полностью, флаг оставлен как защита при откате версии.

Пересчитать SRI: `echo "sha384-$(openssl dgst -sha384 -binary FILE | base64 -w0)"`.

## Что осталось на CDN и почему
- **transformers.js 3.8.1** и **web-llm 0.2.88** — динамический `import()` ES-модулей; `import()` не поддерживает SRI,
  а сами библиотеки догружают WASM/модели (onnxruntime-web, huggingface.co) — локальная копия не закрыла бы цепочку.
  Версии зафиксированы точно на всех резервных CDN, хосты ограничены CSP. Функции опциональные (локальные модели).
- **mermaid 11.4.1** — классический `<script>` по требованию, с `integrity` (`EITI_MERMAID_SRI`).
- **Google Identity Services** (`accounts.google.com/gsi/client`) — Google не публикует версионированные сборки, SRI невозможен.
