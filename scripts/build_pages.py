#!/usr/bin/env python3
"""Stage only EITI browser runtime assets for GitHub Pages.

The public repository can contain research materials, including folklore/.
Those files are not automatically authorized for application distribution.
This script creates a fresh, explicit Pages artifact without research folders.
"""

import argparse
import shutil
from pathlib import Path

REQUIRED_FILES = (
    '.nojekyll',
    'index.html',
    'manifest.json',
    'sw.js',
    'sql-wasm.js',
    'sql-wasm.wasm',
    'icon-192.png',
    'icon-192-maskable.png',
    'icon-512.png',
    'icon-512-maskable.png',
    'kb/eiti_kb.js',
    'kb/index.json',
    'offline/core.json',
    'local/eiti_typo_vocab.json',
    'local/eiti_frames.json',
    'offline_manifest.json',
    # v14.16.30 (#27): vendored third-party runtime (exact versions, SRI in index.html)
    'vendor/dompurify/3.4.18/purify.min.js',
    'vendor/dompurify/3.4.18/LICENSE',
    'vendor/mammoth/1.13.0/mammoth.browser.min.js',
    'vendor/mammoth/1.13.0/LICENSE',
    # v14.16.31 (#28): PDF.js 6.5.438 legacy ES modules (CVE-2024-4367 fix)
    'vendor/pdfjs/6.5.438/pdf.min.mjs',
    'vendor/pdfjs/6.5.438/pdf.worker.min.mjs',
    'vendor/pdfjs/6.5.438/LICENSE',
    # v14.16.32: Fluent Emoji 3D (MIT, Microsoft) — 3D-иконки нижнего таб-бара, локально (без CDN)
    'vendor/fluent-emoji-3d/LICENSE',
    # v14.16.32: иконки ярлыков PWA (manifest.json → shortcuts; долгое нажатие на иконку в лаунчере)
    'vendor/fluent-emoji-3d/shortcuts/chat-96.png',
    'vendor/fluent-emoji-3d/shortcuts/chat-192.png',
    'vendor/fluent-emoji-3d/shortcuts/notes-96.png',
    'vendor/fluent-emoji-3d/shortcuts/notes-192.png',
    'vendor/fluent-emoji-3d/shortcuts/player-96.png',
    'vendor/fluent-emoji-3d/shortcuts/player-192.png',
    'vendor/fluent-emoji-3d/shortcuts/memory-96.png',
    'vendor/fluent-emoji-3d/shortcuts/memory-192.png',
    'vendor/fluent-emoji-3d/README.md',
    'vendor/fluent-emoji-3d/speech_balloon.webp',
    'vendor/fluent-emoji-3d/notebook.webp',
    'vendor/fluent-emoji-3d/books.webp',
    'vendor/fluent-emoji-3d/musical_note.webp',
    'vendor/fluent-emoji-3d/file_folder.webp',
    'vendor/fluent-emoji-3d/memo.webp',
    'vendor/fluent-emoji-3d/calendar.webp',
    'vendor/fluent-emoji-3d/gear.webp',
)

# The explicit patterns reflect the currently documented browser runtime.
# Adding a new asset type requires a reviewed change to this allowlist.
REQUIRED_PATTERNS = (
    'data/*.json',
    'local/eiti_*.js',
    'kb/idx/*.json',
    'kb/packs/*.json',
    'offline/eiti_*.js',
    'offline/packs/*.json',
)


def stage_site(source_root: Path, output_root: Path) -> list[Path]:
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if output_root == source_root or output_root.is_relative_to(source_root):
        raise ValueError('Output must be outside the repository source tree')
    if not source_root.is_dir():
        raise FileNotFoundError(f'Missing source root: {source_root}')
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError('Output is not empty; refusing to publish stale files')

    relative_files = {Path(item) for item in REQUIRED_FILES}
    for pattern in REQUIRED_PATTERNS:
        matches = list(source_root.glob(pattern))
        if not matches:
            raise FileNotFoundError(f'Runtime asset pattern matched nothing: {pattern}')
        relative_files.update(match.relative_to(source_root) for match in matches)

    # Preflight everything before writing the first output file. Reject links:
    # following them could silently copy non-runtime research outside allowlist.
    for rel in sorted(relative_files):
        source = source_root / rel
        if not source.is_file():
            raise FileNotFoundError(f'Required runtime file missing: {rel}')
        for component in (source, *source.parents):
            if component == source_root.parent:
                break
            if component.is_symlink():
                raise ValueError(f'Symlink not allowed in Pages artifact: {rel}')
        if 'folklore' in rel.parts:
            raise ValueError(f'Research corpus may not be deployed: {rel}')

    for rel in sorted(relative_files):
        target = output_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / rel, target)
    return sorted(relative_files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    files = stage_site(args.source, args.output)
    print(f'Pages artifact: {len(files)} runtime files; folklore/ excluded')


if __name__ == '__main__':
    main()
