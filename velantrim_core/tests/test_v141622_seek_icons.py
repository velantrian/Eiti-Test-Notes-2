"""v14.16.22: precise seek icons + correct back/forward wiring (port of PR #4)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")


def test_version_sync():
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m, "missing runtime version"
    version = m.group(1)
    # Feature landed in 14.16.22; runtime may advance
    assert tuple(map(int, version.split("."))) >= (14, 16, 22)
    assert f"eiti-v{version}" in SW
    assert f"version: '{version}'" in SW


def test_seek_svg_and_directions():
    assert "function _eitiSeekSvg(dir)" in HTML
    assert 'class="eiti-seek-ico"' in HTML
    assert "bk.onclick=function(){ var a=document.getElementById('audio'); if(a) a.currentTime=Math.max(0,(a.currentTime||0)-_step);" in HTML
    assert "fw.onclick=function(){ var a=document.getElementById('audio'); if(a) a.currentTime=Math.min(a.duration||0,(a.currentTime||0)+_step);" in HTML
