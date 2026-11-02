"""v14.16.2: подробные офлайн-ответы KB — синхронизация версии и кеша SW."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")


def test_version_sync():
    # v14.16.2 functionality must keep working as the runtime version advances.
    match = re.search(r'var EITI_VERSION = "(\\d+\\.\\d+\\.\\d+)"', HTML)
    assert match, "missing runtime version"
    version = match.group(1)
    assert tuple(map(int, version.split("."))) >= (14, 16, 2), "version regressed before v14.16.2"
    assert f"var CACHE = 'eiti-v{version}'" in SW
    assert f"var OFFLINE_CACHE = 'eiti-offline-v{version}'" in SW
    assert f"version: '{version}'" in SW
    assert f"// VELANTRIM EITI — Service Worker v{version}" in SW
    assert f"EITI_VERSION {version}" in SW
    assert f"v{version}" in json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["description"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"version-{version}-gold" in readme
    assert f"Что нового в v{version}" in readme
    assert readme.index("Что нового в v14.16.2") < readme.index("Что нового в v14.16.0") < readme.index("Что нового в v14.15.2")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert f"v{version}" in agents
    assert "v14.16.2" in agents


def test_new_modules_precached():
    assert "local/eiti_action_gate.js" in SW
    assert "local/eiti_care.js" in SW
