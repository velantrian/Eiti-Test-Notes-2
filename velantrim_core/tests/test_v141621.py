"""v14.16.21: thinking collapse, DeepSeek show-thinking toggle, strip AI cmds, mobile CSS."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
MANIFEST = (ROOT / "manifest.json").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_version_sync():
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m, "missing runtime version"
    version = m.group(1)
    # Feature landed in 14.16.21; runtime may advance (e.g. seek-icons 14.16.22)
    assert tuple(map(int, version.split("."))) >= (14, 16, 21)
    assert f"eiti-v{version}" in SW and f"eiti-offline-v{version}" in SW
    assert f"version: '{version}'" in SW
    assert f"v{version}" in MANIFEST
    assert f"v{version}" in AGENTS
    assert "14.16.21" in README


def test_thinking_collapsed_by_default():
    assert "display: none; /* v14.16.21: always collapsed until user expands */" in HTML
    assert "keep body collapsed while streaming" in HTML
    assert "Thought for " in HTML
    assert "Размышлял " in HTML
    assert "body.style.display = 'none'" in HTML
    # Gemini finalize must collapse the panel (was missing before v14.16.21)
    assert "collapse thinking panel after Gemini stream" in HTML
    assert HTML.count("try { _eitiThinkDone(liveId); }") >= 3


def test_ds_show_thinking_toggle():
    assert 'id="ds-thinking-row"' in HTML
    assert "eitiIsDsShowThinking" in HTML
    assert "eitiToggleDsShowThinking" in HTML
    assert "eitiRenderDsThinking" in HTML
    assert "eitiThinkingPanelAllowed" in HTML
    assert "eiti_ds_show_thinking" in HTML
    assert "Неприменимо для Flash" in HTML
    assert "thinking = { type: 'disabled' }" in HTML or "thinking: { type: 'disabled' }" in HTML
    assert "body.thinking = { type: 'disabled' }" in HTML


def test_or_thinking_row_locks_unsupported():
    assert "kind === 'unsupported' || kind === 'mandatory'" in HTML
    assert "aria-disabled" in HTML
    assert "Thinking неприменимо для этой модели" in HTML


def test_strip_ai_commands_before_render():
    assert "function eitiStripAiCommands" in HTML
    assert r"/\[PKG_E:[^\]]*\]/g" in HTML
    assert "NOTE_WRITE" in HTML and "TASK_ADD" in HTML
    assert "MOSC_ADD" in HTML and "FL_SET" in HTML
    assert "strip service command tokens before markdown" in HTML
    assert "eitiStripAiCommands(text)" in HTML
    assert ".eiti-think-box" in HTML  # excluded from plain copy


def test_mobile_message_readability_css():
    assert "#messages .message.incoming .message-body" in HTML
    assert "@media (max-width: 480px)" in HTML
    assert "mobile-readable assistant answers" in HTML
