#!/usr/bin/env python3
"""P1-2+ : Adaptive N-read OCR majority voting (ADR-045, supersedes ADR-044).

Crumpled thermal-paper Korean receipts produce silent misreads. A single
read cannot detect them; 2-read (ADR-044) only flags disagreement. This
aggregates N independent reads and takes the per-field majority, which
strongly corrects the *stochastic* error class (read varies run to run).

CRITICAL — not a correctness oracle: the *systematic* error class (the
crumple genuinely makes 6 look like 0) makes every read agree on the WRONG
value. Majority voting then yields a confident wrong answer. Therefore:
  • agreement is an ESCALATION signal, never a correctness guarantee;
  • low agreement → FAIL/re-read, never silent acceptance;
  • the consensus is still fed THROUGH the deterministic layers
    (verify_toll_integrity P1-1, verify_card_matching, derive_date_scaffold
    P0-2) — voting augments, never replaces them. (ADR-045 §결합)

Compares RAW LLM judgment only — never applies derive_date_scaffold (the
Python scaffold is identical by construction and would mask divergence).

Adaptive depth: caller runs base 3 reads → this script. Exit codes:
  0  consensus reached → consensus written to research/ocr-results.json
  2  inconclusive but more reads allowed (k < MAX_READS) → caller adds 2
     more reads (ocr-results-{k+1,k+2}.json) and re-runs
  1  exhausted (k >= MAX_READS) still no consensus → FAIL, escalate

Usage:
    python3 scripts/aggregate_ocr_votes.py WK09_2026
"""

import json
import math
import sys
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
RESEARCH_DIR = PROJECT_DIR / "research"
PLANNING_DIR = PROJECT_DIR / "planning"

MAX_READS = 7          # adaptive ceiling (절대 기준 1: cost ignored for quality)
MIN_READS = 3          # base batch
STRONG_FRACTION = 0.8  # strong-majority threshold = ceil(0.8 * k)


def _load_reads():
    """Load ocr-results-1.json .. ocr-results-N.json (contiguous from 1)."""
    reads = []
    i = 1
    while True:
        p = RESEARCH_DIR / f"ocr-results-{i}.json"
        if not p.exists():
            break
        with open(p, "r", encoding="utf-8") as f:
            reads.append(json.load(f))
        i += 1
    return reads


# ─── Identity keys & voted (placement-critical) fields per section ────
# Excluded by design (noise / Python-owned / audit): names, store,
# meal_type, toll direction, card_number, approval, items, note.

def _toll_units(ocr):
    pt = ocr.get("parking_tolls", {}) or {}
    return {(t.get("date"), t.get("time"), t.get("entry"), t.get("exit")):
            (t.get("amount"),) for t in pt.get("toll_history", []) or []}


def _parking_units(ocr):
    pt = ocr.get("parking_tolls", {}) or {}
    return {(p.get("date"),): (p.get("amount"),)
            for p in pt.get("parking_receipts", []) or []}


def _meal_units(ocr, key, with_hc):
    # Identity key = (date, amount). `time` was deliberately dropped:
    # thermal-receipt times are OCR-unstable (faded print) so the same
    # receipt scattered across many time-keys and never reached consensus,
    # while `amount` is crisply printed and cross-validated by the card
    # reconciliation layer (secretary2). See ADR / wk19 escalation.
    # D-7 INTENTIONAL DUPLICATION: this identity tuple is mirrored in
    # synthesize() — keep both in sync if changed.
    out = {}
    for r in ocr.get(key, []) or []:
        ident = (r.get("date"), r.get("amount"))
        out[ident] = (r.get("amount"),) + (
            (r.get("headcount"),) if with_hc else ())
    return out


_SECTIONS = [
    ("toll_history", _toll_units, ("amount",)),
    ("parking_receipts", _parking_units, ("amount",)),
    ("dinner", lambda o: _meal_units(o, "dinner", False), ("amount",)),
    ("staff_meetings", lambda o: _meal_units(o, "staff_meetings", True),
     ("amount", "headcount")),
    ("travel", lambda o: _meal_units(o, "travel", True),
     ("amount", "headcount")),
]


def _vote(values, k):
    """Return (level, chosen, distribution).
    level ∈ {'unanimous','strong','unresolved'}."""
    cnt = Counter(values)
    chosen, support = cnt.most_common(1)[0]
    tie = sum(1 for v, c in cnt.items() if c == support) > 1
    strong_need = math.ceil(STRONG_FRACTION * k)
    if support == k and len(cnt) == 1:
        return "unanimous", chosen, dict(cnt)
    if support >= strong_need and not tie and k >= MIN_READS:
        return "strong", chosen, dict(cnt)
    return "unresolved", chosen, dict(cnt)


def aggregate(reads):
    """Returns (resolved: bool, consensus_units, unresolved: list[str])."""
    k = len(reads)
    consensus = {}      # section -> {ident: voted_tuple}
    unresolved = []

    for name, extract, fields in _SECTIONS:
        per_read = [extract(r) for r in reads]
        all_idents = set()
        for u in per_read:
            all_idents.update(u.keys())
        consensus[name] = {}
        for ident in sorted(all_idents, key=lambda x: tuple(map(str, x))):
            # Existence vote: a receipt must be seen by a (strong) majority.
            present = [ident in u for u in per_read]
            ex_level, ex_choice, ex_dist = _vote(present, k)
            if ex_level == "unresolved" or ex_choice is False:
                unresolved.append(
                    f"[{name}] {ident}: existence not agreed "
                    f"(seen {sum(present)}/{k}) — missed or hallucinated")
                continue
            # Field value vote among reads that contain this receipt.
            vals = [u[ident] for u in per_read if ident in u]
            lvl, choice, dist = _vote(vals, len(vals))
            if lvl == "unresolved":
                unresolved.append(
                    f"[{name}] {ident} {fields}: no consensus — "
                    f"candidates {dist}")
            else:
                consensus[name][ident] = choice

    # telephone (single object)
    for fld in ("month_matches", "payment_amount"):
        vals = [(r.get("telephone", {}) or {}).get(fld) for r in reads]
        lvl, choice, dist = _vote(vals, k)
        if lvl == "unresolved":
            unresolved.append(
                f"[telephone] {fld}: no consensus — candidates {dist}")
        else:
            consensus.setdefault("telephone", {})[fld] = choice

    return (len(unresolved) == 0), consensus, unresolved


def _best_base_read(reads, consensus):
    """Pick the read whose voted fields least disagree with consensus —
    used as the scaffold for the synthesized consensus json so ancillary
    fields (store/names) stay self-consistent."""
    def disagreement(r):
        d = 0
        for name, extract, _ in _SECTIONS:
            u = extract(r)
            for ident, val in consensus.get(name, {}).items():
                if u.get(ident) != val:
                    d += 1
        return d
    return min(range(len(reads)), key=lambda i: disagreement(reads[i]))


def synthesize(reads, consensus):
    """Build the consensus ocr-results.json: start from the closest read,
    then overwrite every voted field with the majority value so the
    placement-critical fields are exactly the consensus."""
    base = json.loads(json.dumps(reads[_best_base_read(reads, consensus)]))

    pt = base.setdefault("parking_tolls", {})
    for t in pt.get("toll_history", []) or []:
        key = (t.get("date"), t.get("time"), t.get("entry"), t.get("exit"))
        if key in consensus.get("toll_history", {}):
            t["amount"] = consensus["toll_history"][key][0]
    for p in pt.get("parking_receipts", []) or []:
        key = (p.get("date"),)
        if key in consensus.get("parking_receipts", {}):
            p["amount"] = consensus["parking_receipts"][key][0]
    for sec, with_hc in (("dinner", False), ("staff_meetings", True),
                         ("travel", True)):
        for r in base.get(sec, []) or []:
            # D-7 INTENTIONAL DUPLICATION: mirrors _meal_units() identity
            # key (date, amount) — keep both in sync if changed.
            key = (r.get("date"), r.get("amount"))
            if key in consensus.get(sec, {}):
                vals = consensus[sec][key]
                r["amount"] = vals[0]
                if with_hc and len(vals) > 1:
                    r["headcount"] = vals[1]
    tel = consensus.get("telephone", {})
    if tel:
        base.setdefault("telephone", {}).update(tel)
    return base


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/aggregate_ocr_votes.py WK09_2026")
        sys.exit(1)
    week = sys.argv[1]

    reads = _load_reads()
    k = len(reads)
    print(f"--- OCR Vote Aggregation: {week} (reads={k}) ---")
    if k < MIN_READS:
        print(f"ERROR: only {k} read(s); need ≥ {MIN_READS} "
              f"(ocr-results-1.json .. ocr-results-{MIN_READS}.json)")
        sys.exit(1)

    resolved, consensus, unresolved = aggregate(reads)

    if resolved:
        out = synthesize(reads, consensus)
        with open(RESEARCH_DIR / "ocr-results.json", "w",
                  encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        try:
            PLANNING_DIR.mkdir(parents=True, exist_ok=True)
            audit = {"week": week, "reads": k, "result": "CONSENSUS",
                     "sections": {s: len(v) for s, v in consensus.items()}}
            with open(PLANNING_DIR / "ocr-vote-audit.json", "w",
                      encoding="utf-8") as f:
                json.dump(audit, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        print(f"RESULT: CONSENSUS over {k} reads → research/ocr-results.json")
        print("NOTE: consensus still passes through P1-1 / card / P0-2 "
              "deterministic layers (voting augments, not replaces).")
        sys.exit(0)

    report = {"week": week, "reads": k, "result": "INCONCLUSIVE",
              "unresolved": unresolved}
    with open(RESEARCH_DIR / "ocr-vote-report.json", "w",
              encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n⚠ {len(unresolved)} unresolved field(s):")
    for u in unresolved:
        print(f"  {u}")
    print(f"\nReport: research/ocr-vote-report.json")

    if k < MAX_READS:
        print(f"RESULT: INCONCLUSIVE — add 2 more independent reads "
              f"(ocr-results-{k+1}.json, ocr-results-{k+2}.json) and re-run "
              f"(adaptive depth, max {MAX_READS}).")
        sys.exit(2)

    print(f"RESULT: FAIL — {MAX_READS} reads exhausted, still no consensus. "
          f"Re-read the listed receipts manually; max retries then "
          f"escalate to user (systematic-misread suspected).")
    sys.exit(1)


if __name__ == "__main__":
    main()
