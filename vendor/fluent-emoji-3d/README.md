# Fluent Emoji 3D (vendored subset)

Source: https://github.com/microsoft/fluentui-emoji — `assets/<Name>/3D/<name>_3d.png`,
commit `1ffb34c752ecf5d402f04cfb4b392c77f57c54bc`. License: MIT © Microsoft Corporation (see `LICENSE`).

Resized 256 → 96 px (≈3× of the 30 px tab icon) and converted to WebP (q88) for EITI v14.16.32.
Served from this origin only (CSP `img-src 'self'`), precached by `sw.js`; no CDN requests.

| file | emoji | tab |
|---|---|---|
| speech_balloon.webp | 💬 | Чат |
| notebook.webp | 📓 | Дневник |
| books.webp | 📚 | История |
| musical_note.webp | 🎵 | Плеер |
| file_folder.webp | 📁 | Файлы |
| memo.webp | 📝 | Заметки |
| calendar.webp | 📅 | Лента |
| gear.webp | ⚙️ | Настройки |

## Ярлыки PWA (`shortcuts/`)
`manifest.json → shortcuts[].icons` (долгое нажатие на иконку EITI в лаунчере): PNG 96 и 192 px, `purpose: any`,
эмодзи занимает 84 % (поле от обрезки лаунчером). Пути относительные к `manifest.json` → работают и в подпапке
GitHub Pages (`/Eiti-Test-Notes-2/`). Те же картинки — в APK как статические ярлыки Android (`res/xml/shortcuts.xml`).

| file | emoji | ярлык |
|---|---|---|
| chat-96/192.png | 💬 | Чат (`#chat`) |
| notes-96/192.png | 📝 | Заметки (`#notes`) |
| player-96/192.png | 🎵 | Плеер (`#player`) |
| memory-96/192.png | 🧠 (`Brain/3D/brain_3d.png`) | Память (`#files`) |
