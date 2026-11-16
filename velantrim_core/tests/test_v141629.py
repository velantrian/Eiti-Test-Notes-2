"""v14.16.29 (#26): storage isolation by deployment prefix (EitiNS) on a shared origin."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_version_sync():
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m and tuple(map(int, m.group(1).split("."))) >= (14, 16, 29)
    assert f"var CACHE = 'eiti-v{m.group(1)}'" in SW
    assert "14.16.29" in README


def test_ns_shim_is_first_script():
    first = HTML.index("<script")
    assert HTML.index("w.EitiNS = api;") > first
    assert HTML.index("w.EitiNS = api;") < HTML.index("<script", first + 1)


def test_idb_migrate_versions_match_open_calls():
    m = re.search(r"var IDB_MIGRATE = \{ eiti_v4: (\d+), eiti_offline: (\d+) \};", HTML)
    assert m
    v4 = set(re.findall(r"indexedDB\.open\('eiti_v4', (\d+)\)", HTML))
    off = set(re.findall(r"indexedDB\.open\('eiti_offline', (\d+)\)", HTML))
    assert v4 == {m.group(1)}
    assert off == {m.group(2)}


def test_migration_copies_and_never_deletes_originals():
    shim = HTML[HTML.index("v14.16.29 (#26)"):HTML.index("})(window);")]
    # legacy keys are copied, never removed; only the partial prefixed copy may be deleted
    assert "raw.removeItem(k)" not in shim
    assert "oDel.call(idb, P + name)" in shim
    assert "oDel.call(idb, name)" not in shim


def test_sw_deletes_only_own_prefixed_caches():
    assert "CACHE = NS_PREFIX + CACHE;" in SW
    assert "OFFLINE_CACHE = NS_PREFIX + OFFLINE_CACHE;" in SW
    assert "k.indexOf(NS_PREFIX + 'eiti-') === 0" in SW
    assert "keys.filter(swIsOwnStaleCache)" in SW
    assert "return k !== CACHE && k !== OFFLINE_CACHE; });" not in SW
