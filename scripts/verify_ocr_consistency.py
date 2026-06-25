#!/usr/bin/env python3
"""P1-2: Dual-read OCR self-consistency verification (ADR-044).

Crumpled thermal-paper Korean receipts produce silent OCR misreads that a
single read cannot detect (e.g., 960→900). Step 3 produces TWO independent
reads of the same images — ocr-results.json and ocr-results-2.json — and
this script deterministically diffs their placement-critical fields. Any
numeric/identity disagreement means at least one read is wrong → block and
re-read the flagged receipts (절대 기준 1: cost ignored for correctness).

Compares RAW LLM judgment only — does NOT apply derive_date_scaffold (the
Python-derived scaffold is identical by construction and would mask the
very disagreement we want to surface).

Excluded by design (not placement-critical / known-noisy / Python-owned):
  names·name_affiliations (FORM names come from Receipt sheet DB, not OCR),
  store, meal_type / toll direction (Python-recomputed/unused — P0-2),
  card_number·approval·items·note (audit metadata, not written to cells).

Severity: any mismatch → exit 1 + research/ocr-consistency-report.json.

Usage:
    python3 scripts/verify_ocr_consistency.py WK09_2026
"""

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
RESEARCH_DIR = PROJECT_DIR / "research"


def _load(name):
    p = RESEARCH_DIR / name
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _tolls(ocr):
    pt = ocr.get("parking_tolls", {}) or {}
    return [(t.get("date"), t.get("time"), t.get("entry"), t.get("exit"),
             t.get("amount")) for t in pt.get("toll_history", []) or []]


def _parking(ocr):
    pt = ocr.get("parking_tolls", {}) or {}
    return [(p.get("date"), p.get("amount"))
            for p in pt.get("parking_receipts", []) or []]


def _meals(ocr, key, with_headcount):
    out = []
    for r in ocr.get(key, []) or []:
        base = (r.get("date"), r.get("time"), r.get("amount"))
        out.append(base + ((r.get("headcount"),) if with_headcount else ()))
    return out


# section name → (extractor, human label)
_SECTIONS = [
    ("toll_history", _tolls, "(date, time, entry, exit, amount)"),
    ("parking_receipts", _parking, "(date, amount)"),
    ("dinner", lambda o: _meals(o, "dinner", False), "(date, time, amount)"),
    ("staff_meetings", lambda o: _meals(o, "staff_meetings", True),
     "(date, time, amount, headcount)"),
    ("travel", lambda o: _meals(o, "travel", True),
     "(date, time, amount, headcount)"),
]


def compare(run1, run2):
    """Return list of mismatch strings (empty = consistent)."""
    mismatches = []

    for name, extract, label in _SECTIONS:
        c1, c2 = Counter(extract(run1)), Counter(extract(run2))
        if c1 == c2:
            continue
        only1 = list((c1 - c2).elements())
        only2 = list((c2 - c1).elements())
        mismatches.append(
            f"[{name}] {label} diverges between the two reads:")
        for t in only1:
            mismatches.append(f"    run1-only: {t}")
        for t in only2:
            mismatches.append(f"    run2-only: {t}")
        if len(extract(run1)) != len(extract(run2)):
            mismatches.append(
                f"    count: run1={len(extract(run1))} "
                f"run2={len(extract(run2))} (receipt-count divergence)")

    t1 = run1.get("telephone", {}) or {}
    t2 = run2.get("telephone", {}) or {}
    for fld in ("month_matches", "payment_amount"):
        if t1.get(fld) != t2.get(fld):
            mismatches.append(
                f"[telephone] {fld}: run1={t1.get(fld)!r} "
                f"run2={t2.get(fld)!r}")

    return mismatches


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/verify_ocr_consistency.py WK09_2026")
        sys.exit(1)
    week = sys.argv[1]

    run1 = _load("ocr-results.json")
    run2 = _load("ocr-results-2.json")
    if run1 is None:
        print("ERROR: research/ocr-results.json missing — Step 3 not run")
        sys.exit(1)
    if run2 is None:
        print("ERROR: research/ocr-results-2.json missing — the second "
              "independent read (P1-2) was not performed. Step 3 must "
              "produce TWO independent OCR passes.")
        sys.exit(1)

    mismatches = compare(run1, run2)

    print(f"--- OCR Dual-Read Consistency: {week} ---")
    if mismatches:
        print(f"\n⚠ {sum(1 for m in mismatches if not m.startswith('    '))} "
              f"section(s) inconsistent between the two independent reads:")
        for m in mismatches:
            print(f"  {m}")
        report = {
            "week": week,
            "result": "FAIL",
            "mismatches": mismatches,
            "guidance": "Re-read ONLY the receipts behind the listed "
                        "tuples; do not blindly trust either run. Max 2 "
                        "retries then escalate to user.",
        }
        out = RESEARCH_DIR / "ocr-consistency-report.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nFAIL report: {out}")
        print("RESULT: FAIL — dual-read disagreement (silent misread risk).")
        sys.exit(1)

    print("\nRESULT: PASS — two independent reads agree on all "
          "placement-critical fields.")
    sys.exit(0)


if __name__ == "__main__":
    main()
