"""v14.16.31 (#28): PDF.js 6.5.438 vendored (CVE-2024-4367), isEvalSupported:false."""
import base64
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
PAGES = (ROOT / "scripts" / "build_pages.py").read_text(encoding="utf-8")
V = "6.5.438"
PDF = f"vendor/pdfjs/{V}/pdf.min.mjs"
WORKER = f"vendor/pdfjs/{V}/pdf.worker.min.mjs"


def sri(rel):
    return "sha384-" + base64.b64encode(hashlib.sha384((ROOT / rel).read_bytes()).digest()).decode()


def test_version_sync():
    m = re.search(r'var EITI_VERSION = "(\d+\.\d+\.\d+)"', HTML)
    assert m and tuple(map(int, m.group(1).split("."))) >= (14, 16, 31)
    assert f"var CACHE = 'eiti-v{m.group(1)}'" in SW


def test_vulnerable_pdfjs_removed():
    assert "pdf.js/3.11.174" not in HTML
    assert "cdnjs.cloudflare.com" not in HTML
    assert not re.search(r"pdfjs-dist@[0-3]\.|pdf\.js/[0-3]\.", HTML)


def test_vendored_pdfjs_with_integrity():
    m = re.search(r'<script type="importmap">(\{.*?\})</script>', HTML)
    assert m
    integ = json.loads(m.group(1))["integrity"]
    assert integ["./" + PDF] == sri(PDF)
    assert integ["./" + WORKER] == sri(WORKER)
    assert f'<link rel="modulepreload" href="./{PDF}" integrity="{sri(PDF)}">' in HTML
    assert f"import * as pdfjs from './{PDF}';" in HTML
    assert f"new URL('./{WORKER}', document.baseURI)" in HTML
    assert HTML.index('<script type="importmap">') < HTML.index('<script type="module">')
    assert (ROOT / f"vendor/pdfjs/{V}/LICENSE").is_file()


def test_get_document_always_safe_options():
    calls = re.findall(r"getDocument\(([^)]*)\)", HTML)
    assert calls and all(c.startswith("eitiPdfOpenOptions(") for c in calls), calls
    m = re.search(r"function eitiPdfOpenOptions\(data\) \{\s*return (\{[^}]*\});", HTML)
    assert m and "isEvalSupported: false" in m.group(1) and "enableXfa: false" in m.group(1)


def test_published_and_cached():
    for rel in (PDF, WORKER, f"vendor/pdfjs/{V}/LICENSE"):
        assert f"'{rel}'" in PAGES, rel
    for rel in (PDF, WORKER):
        assert f"BASE + '{rel}'" in SW, rel
