#!/usr/bin/env python3
"""classify_stage.py — R-D pipeline stage S3c (run_week, post-OCR / pre-write_excel).

Replaces the human section pre-sort's RELIABILITY: predicts each meal receipt's
section from the store→sector DB (conservative headcount policy, the wrong-auto-
minimizing default), writes predictions, and ESCALATES ambiguous (T3) receipts —
silent placement is forbidden (§5). Re-entrant escalation HALT (mirrors the
vision-HALT contract): exit 2 if unconfirmed escalations exist; the reviewer
confirms by writing planning/section-confirmed.json, then re-run proceeds.

NON-DISRUPTIVE (safe integration): does NOT modify research/ocr-results.json, so
write_excel (S4) still consumes the existing sections and the deterministic tail
(S4–S8 + verify_week C38) is byte-unchanged on already-sectioned weeks (WK21
regression). Full pre-sort *replacement* (predicted sections feeding write_excel)
is a separately-gated next step.

If store-db.json is absent (R-C DB not built), the stage SKIPS (exit 0) for
backward compatibility.

Usage: python3 scripts/classify_stage.py WK21_2026 [--no-escalate]
"""

import sys
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
import build_store_db as bdb  # noqa: E402
from classify_section import classify  # noqa: E402

PLANNING = PROJECT_DIR / "planning"
RESEARCH = PROJECT_DIR / "research"
SECMAP = {"dinner": "DINNER", "staff_meetings": "STAFF", "travel": "TRAVEL"}

EXIT_OK = 0
EXIT_ESCALATE = 2   # run_week maps gate exit 2 → VISION/escalation HALT (re-entrant)


def main():
    args = sys.argv[1:]
    week = [a for a in args if not a.startswith("--")][0]
    no_escalate = "--no-escalate" in args

    db_path = PLANNING / "store-db.json"
    ocr_path = RESEARCH / "ocr-results.json"
    if not db_path.exists():
        print("classify_stage: SKIP — planning/store-db.json absent (R-C DB not built)")
        sys.exit(EXIT_OK)
    if not ocr_path.exists():
        print("classify_stage: SKIP — research/ocr-results.json absent")
        sys.exit(EXIT_OK)

    db = json.loads(db_path.read_text(encoding="utf-8"))
    ocr = json.loads(ocr_path.read_text(encoding="utf-8"))
    cards = [dict(r) for r in bdb.extract_card(bdb.find_card_file(week))]

    preds, escalations = [], []
    for sk, sn in SECMAP.items():
        for r in (ocr.get(sk) or []):
            p = classify(r, db, cards)   # conservative headcount policy (default)
            rec = {"store": r.get("store"), "date": r.get("date"),
                   "amount": r.get("amount"), "headcount": r.get("headcount"),
                   "ocr_section": sn, "predicted": p["section"],
                   "tier": p["tier"], "confidence": p["confidence"], "key": p["key"]}
            preds.append(rec)
            if p["tier"].startswith("T3"):
                escalations.append(rec)

    PLANNING.mkdir(parents=True, exist_ok=True)
    (PLANNING / "section-predictions.json").write_text(
        json.dumps({"week": week, "policy": "headcount(conservative)",
                    "predictions": preds, "escalations": escalations},
                   indent=2, ensure_ascii=False), encoding="utf-8")

    n_auto = len(preds) - len(escalations)
    print(f"classify_stage {week}: {len(preds)} meal receipts → {n_auto} auto-classified, "
          f"{len(escalations)} escalation(s). predictions→planning/section-predictions.json")

    confirmed = (PLANNING / "section-confirmed.json").exists()
    if escalations and not confirmed and not no_escalate:
        print(f"SECTION-ESCALATION: {len(escalations)} ambiguous receipt(s) need confirmation "
              f"(purpose-ambiguity, e.g. coffee-chain STAFF vs TRAVEL). Review "
              f"planning/section-predictions.json → confirm sections → write "
              f"planning/section-confirmed.json → re-run. (silent placement forbidden, §5)")
        for e in escalations[:8]:
            print(f"  ESCALATE: {e['store']} {e['date']} hc={e['headcount']} "
                  f"ocr_section={e['ocr_section']} pred={e['predicted']}({e['tier']})")
        sys.exit(EXIT_ESCALATE)

    print(f"classify_stage: OK ({'escalations confirmed' if confirmed else 'no escalations'})")
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
