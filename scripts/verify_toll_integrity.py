#!/usr/bin/env python3
"""P1-1: Deterministic toll-history integrity verification.

Tolls are EXCLUDED from card reconciliation (verify_card_matching.py:8-10,
separate Hi-pass card), so the most important reference receipt
("기간별 사용내역") currently has ZERO deterministic verification. This
script closes that blind spot by checking the internal arithmetic/logical
integrity of ocr-results.json `parking_tolls.toll_history` — surfacing
silent OCR misreads (e.g., 960→900) that no other stage can catch.

Severity:
  violation → exit 1 + research/toll-integrity-report.json (FAIL)
  warning   → exit 0, console only (review)

Read-only. Never opens/saves the output Excel (Phase 4 constraint).

Usage:
    python3 scripts/verify_toll_integrity.py WK09_2026
"""

import io
import json
import sys
from contextlib import redirect_stderr
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
RESEARCH_DIR = PROJECT_DIR / "research"

# SOT reuse (절대 기준 2): distance rules and the date scaffold each live in
# exactly one place inside write_excel — never reimplement here.
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from write_excel import (  # noqa: E402
    get_distance,
    derive_date_scaffold,
    _normalize_dates_in_place,
)


def load_ocr():
    with open(RESEARCH_DIR / "ocr-results.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    # Same normalization write_excel.load_data() applies before
    # derive_date_scaffold: OCR dates may be slash-format (2026/04/13).
    _normalize_dates_in_place(data)
    return derive_date_scaffold(data)  # P0-2 (ADR-043)


def _parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d").date()


def check_toll_integrity(ocr):
    """Run T-1..T-6. Returns (violations, warnings) — lists of str."""
    violations, warnings = [], []
    tolls = ocr.get("parking_tolls", {}).get("toll_history", []) or []
    if not tolls:
        warnings.append("toll_history is empty — nothing to verify")
        return violations, warnings

    # ── T-1: same (entry,exit) route → consistent amount across the week ──
    by_route = {}
    for t in tolls:
        e, x = (t.get("entry") or "").strip(), (t.get("exit") or "").strip()
        if e in ("", "-") or x in ("", "-"):
            continue
        by_route.setdefault((e, x), []).append(t)
    for (e, x), recs in by_route.items():
        amts = {}
        for r in recs:
            amts.setdefault(r.get("amount"), []).append(f"{r.get('date')} {r.get('time')}")
        if len(amts) > 1:
            majority = max(amts, key=lambda a: len(amts[a]))
            for amt, occ in amts.items():
                if amt != majority:
                    warnings.append(
                        f"T-1 {e}→{x}: amount {amt} at {occ} differs from "
                        f"majority {majority} — possible OCR misread")

    # ── T-3: amount 0 on a real gate pair is impossible ──────────────────
    for t in tolls:
        e, x = (t.get("entry") or "").strip(), (t.get("exit") or "").strip()
        if e not in ("", "-") and x not in ("", "-") and t.get("amount") == 0:
            violations.append(
                f"T-3 {t.get('date')} {t.get('time')} {e}→{x}: amount=0 on a "
                f"real route — impossible (suspected misread)")

    # ── T-4: route must resolve via PRD §16 distance rules ───────────────
    for t in tolls:
        e, x = (t.get("entry") or "").strip(), (t.get("exit") or "").strip()
        if e in ("", "-") or x in ("", "-"):
            continue
        with redirect_stderr(io.StringIO()):  # suppress get_distance stderr
            dist = get_distance(e, x)
        if dist is None:
            warnings.append(
                f"T-4 {t.get('date')} {e}→{x}: unresolved route (unknown gate "
                f"name?) — possible place-name OCR misread")

    # ── T-5: every toll date must fall within the derived week ──────────
    # Post-P0-2 (ADR-043) the scaffold is Python-derived from the earliest
    # toll, so checking sunday_date is tautological. The real residual risk
    # is a toll date misread into a different week — derivation's min-anchor
    # would silently absorb it. This catches that class deterministically.
    wm = ocr.get("weekday_mapping", {})
    try:
        monday = _parse_date(wm["monday"])
        sunday = _parse_date(wm["sunday"])
        for t in tolls:
            if not t.get("date"):
                continue
            td = _parse_date(t["date"])
            if not (monday <= td <= sunday):
                violations.append(
                    f"T-5 toll {t['date']} {t.get('time','')} outside derived "
                    f"week [{monday}..{sunday}] (PRD §2-§4) — date misread "
                    f"or split week")
    except (ValueError, KeyError) as ex:
        warnings.append(f"T-5 could not verify week bounds: {ex}")

    # ── T-2: each toll day should pair a go with a back ──────────────────
    # ── T-6: per-date time order / exact-duplicate detection ─────────────
    by_date = {}
    for t in tolls:
        by_date.setdefault(t.get("date"), []).append(t)
    for date, recs in by_date.items():
        seen = set()
        for r in recs:
            key = (r.get("time"), r.get("entry"), r.get("exit"), r.get("amount"))
            if key in seen:
                warnings.append(
                    f"T-6 {date}: exact-duplicate toll {key} — possible "
                    f"double-read")
            seen.add(key)
        has_go = any((r.get("exit") or "").strip() == "기흥동탄" for r in recs)
        has_back = any((r.get("entry") or "").strip() == "기흥동탄" for r in recs)
        if has_go and not has_back:
            warnings.append(
                f"T-2 {date}: go toll present but no return toll "
                f"(early leave / vacation?) — review")

    return violations, warnings


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/verify_toll_integrity.py WK09_2026")
        sys.exit(1)
    week = sys.argv[1]

    ocr = load_ocr()
    violations, warnings = check_toll_integrity(ocr)

    print(f"--- Toll Integrity: {week} ---")
    for w in warnings:
        print(f"  WARNING: {w}")
    if violations:
        print(f"\n⚠ {len(violations)} VIOLATION(S):")
        for v in violations:
            print(f"  ✗ {v}")
        report = {
            "week": week,
            "result": "FAIL",
            "violations": violations,
            "warnings": warnings,
        }
        out = RESEARCH_DIR / "toll-integrity-report.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nFAIL report: {out}")
        print(f"RESULT: FAIL — {len(violations)} toll integrity violation(s).")
        sys.exit(1)

    print(f"\nRESULT: PASS — toll integrity OK "
          f"({len(warnings)} warning(s), non-blocking).")
    sys.exit(0)


if __name__ == "__main__":
    main()
