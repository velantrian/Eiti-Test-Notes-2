"""v14.16.23: chat-only bottom tabs toggle in «+» menu."""
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
    assert tuple(map(int, version.split("."))) >= (14, 16, 23)
    assert f"eiti-v{version}" in SW and f"eiti-offline-v{version}" in SW
    assert f"version: '{version}'" in SW
    assert f"v{version}" in MANIFEST
    assert f"v{version}" in AGENTS
    assert "14.16.23" in README


def test_chat_only_tabs_wiring():
    assert "eiti_chat_only_tabs" in HTML
    assert "eiti-chat-only-tabs" in HTML
    assert "function eitiSetChatOnlyTabs" in HTML
    assert "function eitiIsChatOnlyTabs" in HTML
    assert "function eitiApplyChatOnlyTabs" in HTML
    assert "cpi-tabs-pin" in HTML
    assert "_t('icons')" in HTML
    # v14.16.27: CSS hides the entire bottom bar (including Chat), not per-tab
    assert "html.eiti-chat-only-tabs .tab-bar" in HTML
    assert "display: none !important" in HTML
    assert '.tab-item:not([data-view="chat"])' not in HTML
    # Early head apply before first paint
    assert "localStorage.getItem('eiti_chat_only_tabs')==='1'" in HTML
    # i18n (legacy key kept; primary label is «icons»)
    assert '"icons": "icons"' in HTML
    assert "Нижние табы" in HTML
