#!/usr/bin/env python3
"""Read-only reproducible RU/EN coverage audit over shipped KB packs.

An English field is not necessarily a translation. Cyrillic script and
different years are review signals, never automatic verdicts of mistranslation.
The script checks the exact 150,000-record total and never edits KB data.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EN_UNAVAILABLE = re.compile(r"\bWikidata entry;\s*English description is unavailable\b", re.I)
CYRILLIC = re.compile(r"[\u0400-\u052f]")
YEARS = re.compile(r"(?<![A-Za-z\d])\d{4}(?![A-Za-z\d])")
RICH = frozenset({
    "countries", "cities", "admin_regions", "states", "films", "books",
    "people", "elements", "rivers", "languages", "companies", "airports",
    "species", "dinosaurs", "mountains", "lakes",
})


def en_status(record):
    en = record.get("en")
    if not isinstance(en, str) or not en.strip():
        return "en_missing"
    if EN_UNAVAILABLE.search(en):
        return "en_placeholder"
    return "en_content"


def run_audit(kb_root):
    index = json.loads((kb_root / "index.json").read_text(encoding="utf-8"))
    total = Counter()
    domains = []
    for domain, meta in index["domains"].items():
        row = Counter()
        row["packs"] = len(meta["packs"])
        for name in meta["packs"]:
            pack = json.loads((kb_root / name).read_text(encoding="utf-8"))
            if pack.get("domain") != domain:
                raise ValueError(f"Wrong domain in pack {name}")
            for record in pack["entries"].values():
                row["total"] += 1
                state = en_status(record)
                row[state] += 1
                if state == "en_content":
                    en = record["en"]
                    if CYRILLIC.search(en):
                        row["en_mixed_script"] += 1
                    ru_years = set(YEARS.findall(record.get("a") or ""))
                    en_years = set(YEARS.findall(en))
                    if ru_years and en_years and ru_years != en_years:
                        row["year_review"] += 1
                fields = record.get("f") or {}
                if fields.get("origin"):
                    row["f_origin"] += 1
                if fields.get("verify"):
                    row["f_verify"] += 1
                links = record.get("r") or []
                snapshots = record.get("rd") or []
                if links:
                    row["has_links"] += 1
                if snapshots:
                    row["has_snapshots"] += 1
                if len(snapshots) != min(len(links), 5 if domain in RICH else 3):
                    row["snapshot_mismatch"] += 1
        if row["total"] != meta["count"]:
            raise ValueError(f"Domain {domain}: pack count {row['total']} != index {meta['count']}")
        total.update(row)
        domains.append({"domain": domain, "generated": bool(meta.get("gen")), **row})
    if total["total"] != index["count"] or total["total"] != 150000:
        raise ValueError(f"Expected 150000 records, read {total['total']}")
    if total["en_missing"] + total["en_placeholder"] + total["en_content"] != total["total"]:
        raise ValueError("EN categories do not sum to the total")
    return dict(total), domains


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    total, domains = run_audit(ROOT / "kb")
    if args.json:
        print(json.dumps({"total": total, "domains": domains}, ensure_ascii=False))
        return
    cols = ("domain", "total", "en_content", "en_missing", "en_placeholder",
            "en_mixed_script", "f_origin", "f_verify", "has_links",
            "has_snapshots", "snapshot_mismatch", "year_review")
    print("EITI_EN_AUDIT: en_content != verified translation; mixed_script/year_review are review signals")
    print("EITI_EN_AUDIT: " + ",".join(cols))
    for row in domains:
        print("EITI_EN_AUDIT: " + ",".join(str(row.get(k, 0)) for k in cols))
    print("EITI_EN_AUDIT_TOTAL: " + json.dumps(total, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
