#!/usr/bin/env python3
"""build_store_db.py — R-C: Store→Sector DB build + join coverage matrix.

Goal 2 foundation: accumulate a store→section frequency DB from ground-truth
receipts, keyed by the DETERMINISTIC card merchant id (사업자번호) where a
(date,amount) card match exists, else by a normalized OCR store name (fallback).

Requirement ① (codex/§5 dialectic) — JOIN COVERAGE MATRIX: quantify, per week,
how many dinner/staff/travel receipts are card-matched (사업자번호 obtainable)
vs fallback (cash / card-miss) vs excluded (TOLLS/TELEPHONE = separate card).
This empirically tests stress-point #1 (사업자번호 leverage depends on match rate).

SOT reuse (절대 기준 2): card parsing via extract_card_data.extract_xlsx/xls —
never reimplemented. Receipts + section labels come from the per-week OCR
backups research/wk{nn}_ocr-results.json (section = array membership, reflecting
the human placement encoded at OCR time via input-manifest). NOTE: the
completed-Excel independent ground-truth cross-check belongs to the HEAVY
holdout step (req②, separate GO) — this low-load build uses OCR backups.

Low-load: reads small JSON backups + small card files only (no T&E workbook load).

Usage:
    python3 scripts/build_store_db.py --coverage          # all available weeks
    python3 scripts/build_store_db.py --coverage WK21_2026 WK22_2026
"""

import sys
import json
import re
import glob
import unicodedata
import collections
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"
RESEARCH_DIR = PROJECT_DIR / "research"
PLANNING_DIR = PROJECT_DIR / "planning"
INPUT_DIR = PROJECT_DIR / "raw-data" / "input"

sys.path.insert(0, str(SCRIPTS_DIR))
from extract_card_data import extract_xlsx, extract_xls, parse_date  # noqa: E402  (SOT reuse)

# dinner/staff/travel are the card-matchable meal sections (have store + card).
MEAL_SECTIONS = {"dinner": "DINNER", "staff_meetings": "STAFF", "travel": "TRAVEL"}


def _wk_num(week):
    m = re.match(r"WK?(\d{2})", week)
    return m.group(1) if m else week[2:4]


def available_weeks():
    """Weeks with an OCR backup (research/wk{nn}_ocr-results.json)."""
    out = []
    for p in sorted(RESEARCH_DIR.glob("wk*_ocr-results.json")):
        m = re.match(r"wk(\d{2})_ocr-results\.json", p.name)
        if m:
            out.append(f"WK{m.group(1)}_2026")
    return out


def load_ocr_backup(week):
    p = RESEARCH_DIR / f"wk{_wk_num(week)}_ocr-results.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def find_card_file(week):
    """Per-week card file, excluding _FAIL variants. Prefer .xls then .xlsx.

    NOTE: macOS stores Korean filenames in NFD (decomposed); a glob pattern
    written in NFC fails to match. So we iterdir() and NFC-normalize each name
    before substring-matching — robust to both NFD- and NFC-stored names."""
    folder = INPUT_DIR / week
    if not folder.exists():
        return None
    cands = [p for p in folder.iterdir()
             if p.suffix.lower() in (".xls", ".xlsx")
             and "승인내역" in unicodedata.normalize("NFC", p.name)
             and "FAIL" not in p.name]
    if not cands:
        return None
    cands.sort(key=lambda p: (p.suffix.lower() != ".xls", len(p.name)))
    return cands[0]


def extract_card(path):
    if path is None:
        return []
    try:
        if path.suffix.lower() == ".xlsx":
            return extract_xlsx(path)
        return extract_xls(path)
    except Exception as e:
        print(f"  WARN: card extract failed {path.name}: {e}", file=sys.stderr)
        return []


def norm_store(s):
    """Fallback key — normalize OCR store name (NFC, lower, collapse spaces).
    NOTE: does NOT resolve OCR char-confusion (DSR↔D5R) — brand rollup is a
    future option (R-C design W3). Card 사업자번호 is the deterministic primary."""
    if not s:
        return "(unknown)"
    s = unicodedata.normalize("NFC", str(s)).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _biz_no(raw):
    for k in ("사업자번호", "사업자등록번호"):
        v = raw.get(k)
        if v:
            return unicodedata.normalize("NFC", str(v)).strip()
    return None


def _category(raw):
    return unicodedata.normalize("NFC", str(raw.get("가맹점업종", ""))).strip() or None


def _merchant_name(raw):
    return unicodedata.normalize("NFC", str(raw.get("가맹점명", ""))).strip() or None


def match_card(receipt, card_pool):
    """Consume-based (date, amount) match. Returns the card record or None.
    Mirrors verify_card_matching's consume semantics (each card matched once).
    Normalizes the receipt date via parse_date (OCR backups use mixed
    YYYY-MM-DD / YYYY/MM/DD; card dates are already parse_date-normalized)."""
    rd = parse_date(receipt["date"]) if receipt.get("date") else None
    ra = receipt.get("amount")
    for rec in card_pool:
        if rec.get("_consumed"):
            continue
        if rec.get("date") == rd and rec.get("amount") == ra:
            rec["_consumed"] = True
            return rec
    return None


def _hour(t):
    t = str(t or "")
    return int(t[:2]) if t[:2].isdigit() else None


def build(weeks):
    store_db = {}
    coverage = []

    def agg(key, section, receipt, category, merchant, week):
        e = store_db.setdefault(key, {
            "merchant_name": merchant, "category": category,
            "section_dist": collections.Counter(),
            "headcounts": [], "amounts": [], "hours": [],
            "occurrences": 0, "source_weeks": set(),
        })
        if merchant and not e["merchant_name"]:
            e["merchant_name"] = merchant
        if category and not e["category"]:
            e["category"] = category
        e["section_dist"][section] += 1
        if receipt.get("headcount") is not None:
            e["headcounts"].append(receipt["headcount"])
        if receipt.get("amount") is not None:
            e["amounts"].append(receipt["amount"])
        h = _hour(receipt.get("time"))
        if h is not None:
            e["hours"].append(h)
        e["occurrences"] += 1
        e["source_weeks"].add(week)

    for week in weeks:
        ocr = load_ocr_backup(week)
        if ocr is None:
            continue
        card_pool = [dict(r) for r in extract_card(find_card_file(week))]
        matched = fallback = excluded = 0

        for sec_key, sec_name in MEAL_SECTIONS.items():
            for r in (ocr.get(sec_key) or []):
                cm = match_card(r, card_pool)
                if cm:
                    key = _biz_no(cm.get("raw", {})) or f"name:{norm_store(_merchant_name(cm.get('raw', {})) or r.get('store'))}"
                    agg(key, sec_name, r, _category(cm.get("raw", {})),
                        _merchant_name(cm.get("raw", {})) or r.get("store"), week)
                    matched += 1
                else:
                    agg(f"name:{norm_store(r.get('store'))}", sec_name, r, None,
                        r.get("store"), week)
                    fallback += 1

        # excluded = separate-card sections (TOLLS/PARKING tolls + TELEPHONE)
        pt = ocr.get("parking_tolls", {}) or {}
        excluded += len(pt.get("toll_history", []) or []) + len(pt.get("parking_receipts", []) or [])
        tel = ocr.get("telephone") or {}
        if isinstance(tel, dict) and tel.get("payment_amount"):
            excluded += 1

        meal_total = matched + fallback
        coverage.append({
            "week": week,
            "card_matched": matched,
            "fallback": fallback,
            "excluded_tolls_tel": excluded,
            "meal_total": meal_total,
            "match_rate_pct": round(100 * matched / meal_total, 1) if meal_total else None,
        })

    # finalize store_db (Counter/set -> serializable + confidence)
    final = {}
    for key, e in store_db.items():
        dist = dict(e["section_dist"])
        total = sum(dist.values())
        hc = sorted(e["headcounts"]); am = sorted(e["amounts"]); hr = sorted(e["hours"])
        final[key] = {
            "merchant_name": e["merchant_name"], "category": e["category"],
            "section_dist": dist,
            "confidence": round(max(dist.values()) / total, 3) if total else 0,
            "dominant_section": max(dist, key=dist.get) if dist else None,
            "typical": {
                "headcount": [hc[0], hc[len(hc)//2], hc[-1]] if hc else None,
                "amount": [am[0], am[len(am)//2], am[-1]] if am else None,
                "hour": [hr[0], hr[len(hr)//2], hr[-1]] if hr else None,
            },
            "occurrences": e["occurrences"],
            "source_weeks": sorted(e["source_weeks"]),
        }
    return final, coverage


def print_coverage(coverage):
    print("\n=== JOIN COVERAGE MATRIX (req① — 사업자번호 deterministic-key reach) ===")
    print(f"{'week':>10} {'card-matched':>13} {'fallback':>9} {'excl(toll/tel)':>15} {'meal_tot':>9} {'match%':>7}")
    tm = tf = te = tt = 0
    for c in coverage:
        print(f"{c['week']:>10} {c['card_matched']:>13} {c['fallback']:>9} "
              f"{c['excluded_tolls_tel']:>15} {c['meal_total']:>9} "
              f"{(str(c['match_rate_pct']) if c['match_rate_pct'] is not None else '-'):>7}")
        tm += c['card_matched']; tf += c['fallback']; te += c['excluded_tolls_tel']; tt += c['meal_total']
    rate = round(100*tm/tt, 1) if tt else None
    print(f"{'TOTAL':>10} {tm:>13} {tf:>9} {te:>15} {tt:>9} {str(rate):>7}")
    print(f"\nInterpretation (②-3): {rate}% of meal receipts get a deterministic 사업자번호 "
          f"key via card join; the rest fall back to OCR store name. "
          f"{'High' if (rate or 0) >= 70 else 'Moderate/low'} card-key leverage.")


# ============================ req④ — quarantine / promote / snapshot / rollback ==
# Self-learning safety (stress-point #5): a new week's observations are STAGED in
# quarantine and merged into store-db.json ONLY after the week's verify_week PASSES
# (caller's responsibility to check). Each promotion snapshots the prior DB so a
# bad append is fully reversible. Unverified data NEVER pollutes the live DB.
QUAR_DIR = PLANNING_DIR / "store-db-quarantine"
SNAP_DIR = PLANNING_DIR / "store-db-snapshots"
PROMOTED = PLANNING_DIR / "store-db-promoted.json"
STORE_DB = PLANNING_DIR / "store-db.json"


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def quarantine_week(week):
    """Stage a week's observations (NOT merged into the live DB)."""
    db, cov = build([week])
    _write(QUAR_DIR / f"{week}.json", {"week": week, "store_db": db, "coverage": cov})
    print(f"QUARANTINED {week} → {QUAR_DIR.relative_to(PROJECT_DIR)}/{week}.json "
          f"({len(db)} keys). NOT merged — awaiting verify_week PASS → --promote.")


def promote_week(week):
    """After verify_week PASS: snapshot live DB, then rebuild DB from all promoted
    weeks (+ this one). Reversible via --rollback."""
    if not (QUAR_DIR / f"{week}.json").exists():
        print(f"ERROR: {week} not quarantined (run --quarantine {week} first)", file=sys.stderr)
        sys.exit(1)
    # snapshot current live DB before mutating
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    n = len(list(SNAP_DIR.glob("store-db.v*.json")))
    if STORE_DB.exists():
        _write(SNAP_DIR / f"store-db.v{n}.json", _read(STORE_DB, {}))
    promoted = _read(PROMOTED, [])
    if week not in promoted:
        promoted.append(week)
    db, _cov = build(promoted)          # rebuild from promoted provenance (idempotent)
    _write(STORE_DB, db)
    _write(PROMOTED, promoted)
    (QUAR_DIR / f"{week}.json").unlink()
    print(f"PROMOTED {week}. snapshot=store-db.v{n}.json | promoted weeks={promoted} | "
          f"store-db.json rebuilt ({len(db)} keys). Rollback: --rollback")


def rollback():
    """Restore store-db.json from the latest snapshot (undo last promote)."""
    snaps = sorted(SNAP_DIR.glob("store-db.v*.json"), key=lambda p: int(re.search(r"v(\d+)", p.name).group(1)))
    if not snaps:
        print("ERROR: no snapshot to roll back to", file=sys.stderr)
        sys.exit(1)
    latest = snaps[-1]
    _write(STORE_DB, _read(latest, {}))
    promoted = _read(PROMOTED, [])
    popped = promoted.pop() if promoted else None
    _write(PROMOTED, promoted)
    latest.unlink()
    print(f"ROLLED BACK to {latest.name} (undid promote of {popped}). "
          f"store-db.json restored | promoted weeks={promoted}")


def main():
    args = sys.argv[1:]
    # req④ transactional modes
    if "--quarantine" in args:
        quarantine_week(args[args.index("--quarantine") + 1]); return
    if "--promote" in args:
        promote_week(args[args.index("--promote") + 1]); return
    if "--rollback" in args:
        rollback(); return

    coverage_only = "--coverage" in args
    weeks = [a for a in args if not a.startswith("--")] or available_weeks()
    if not weeks:
        print("No OCR backups found (research/wk*_ocr-results.json)", file=sys.stderr)
        sys.exit(1)

    print(f"Building store DB from {len(weeks)} weeks: {[_wk_num(w) for w in weeks]}")
    store_db, coverage = build(weeks)

    PLANNING_DIR.mkdir(parents=True, exist_ok=True)
    (PLANNING_DIR / "store-db.json").write_text(
        json.dumps(store_db, indent=2, ensure_ascii=False), encoding="utf-8")
    (PLANNING_DIR / "store-db-coverage.json").write_text(
        json.dumps({"weeks": weeks, "coverage": coverage}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    _write(PROMOTED, weeks)   # transactional baseline: bulk build = promote-all (req④ consistency)

    print(f"\nstore_db: {len(store_db)} distinct keys "
          f"({sum(1 for v in store_db.values() if not v['source_weeks'][0].startswith('name'))} ...)")
    n_biz = sum(1 for k in store_db if not k.startswith("name:"))
    n_name = sum(1 for k in store_db if k.startswith("name:"))
    print(f"  keyed by 사업자번호: {n_biz}  |  keyed by store-name fallback: {n_name}")
    amb = sum(1 for v in store_db.values() if len(v["section_dist"]) > 1)
    print(f"  ambiguous (multi-section) keys: {amb}/{len(store_db)} "
          f"(confidence<1.0 — escalation candidates)")
    print_coverage(coverage)
    print(f"\nWrote planning/store-db.json + planning/store-db-coverage.json")


if __name__ == "__main__":
    main()
