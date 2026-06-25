#!/usr/bin/env python3
"""holdout_eval.py — R-C req② Leave-One-Week-Out (LOWO) holdout evaluation.

For each week W: build store_db from ALL OTHER weeks, classify W's receipts,
compare prediction to ground-truth. This empirically converts the 96.6% coverage
+ 6 ambiguous stores into hold-out section-classification accuracy + escalation
rate + θ sensitivity → the McKinsey 90+ judgment basis.

GROUND TRUTH (master-approved A+B cross-check):
  A = OCR-array per-receipt section (feature-independent: classifier predicts
      from store/date/amount, never from array membership).
  B = completed-Excel per-image section count (wk{nn}.json) — count-level
      cross-check. Where A_count != B_count for a (week, section), those receipts
      are flagged GT-UNCERTAIN and EXCLUDED from accuracy (②-3 conservative);
      the divergence rate is reported as a GT-reliability indicator.

②-3: results are reported honestly even if they refute the 76%/88 premise. No
exaggeration. Pausable (short, all-JSON; no bulk openpyxl). Per-week reads only.

Usage:
    python3 scripts/holdout_eval.py            # dry-run (plan only)
    python3 scripts/holdout_eval.py --run      # execute LOWO + θ sweep
"""

import sys
import json
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
import build_store_db as bdb  # noqa: E402
from classify_section import classify  # noqa: E402

ANNOT = PROJECT_DIR / "research" / "annotations"
PLANNING = PROJECT_DIR / "planning"
SECMAP = {"dinner": "DINNER", "staff_meetings": "STAFF", "travel": "TRAVEL"}
# θ_mid (T2/T3 escalation boundary) is the meaningful axis: it governs how much
# ambiguous volume auto-places (T2) vs escalates (T3). θ_high only moves the
# T1/T2 line (both auto) so it leaves auto coverage/accuracy unchanged.
THETA_MID_SWEEP = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
THETA_HIGH_FIXED = 0.85


def b_image_counts(week):
    """B ground-truth: per-image section counts from completed-Excel-derived wk{nn}.json."""
    p = ANNOT / f"wk{bdb._wk_num(week)}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    imgs = d.get("images", {})
    vals = imgs.values() if isinstance(imgs, dict) else imgs
    return Counter(v.get("section") for v in vals if isinstance(v, dict))


def a_receipt_counts(ocr):
    return Counter({sn: len(ocr.get(sk) or []) for sk, sn in SECMAP.items()})


def lowo(weeks, theta_high, theta_mid, policy="headcount"):
    """One LOWO pass at given θ + classifier policy. card extraction cached."""
    card_cache = {w: [dict(r) for r in bdb.extract_card(bdb.find_card_file(w))] for w in weeks}
    confusion = defaultdict(Counter)
    tier = Counter()
    gt_certain = gt_uncertain = correct = auto = esc = unseen = 0
    gt_sec_total, gt_sec_correct = Counter(), Counter()
    uncertain_detail = []
    for W in weeks:
        train = [w for w in weeks if w != W]
        db = bdb.build(train)[0]                      # LOWO DB (W excluded)
        ocr = bdb.load_ocr_backup(W)
        if ocr is None:
            continue
        A, B = a_receipt_counts(ocr), b_image_counts(W)
        certain = set()
        for sn in SECMAP.values():
            if B is None:
                continue
            if A.get(sn, 0) == B.get(sn, 0):
                certain.add(sn)
            else:
                uncertain_detail.append({"week": W, "section": sn,
                                         "A_receipts": A.get(sn, 0), "B_images": B.get(sn, 0)})
        cards = [dict(r) for r in card_cache[W]]       # fresh copy (consume semantics)
        for sk, sn in SECMAP.items():
            for r in (ocr.get(sk) or []):
                if sn not in certain:
                    gt_uncertain += 1
                    continue
                gt_certain += 1
                gt_sec_total[sn] += 1
                p = classify(r, db, cards, theta_high, theta_mid, policy=policy)
                tier[p["tier"]] += 1
                if not p["tier"].startswith("T3"):     # T1 / T2 / T2-hc = auto
                    auto += 1
                    confusion[sn][p["section"]] += 1
                    if p["section"] == sn:
                        correct += 1
                        gt_sec_correct[sn] += 1
                else:
                    esc += 1
                    if p["tier"] == "T3-unseen":
                        unseen += 1
    total_gt = gt_certain + gt_uncertain
    return {
        "policy": policy, "theta_high": theta_high, "theta_mid": theta_mid,
        "section_recall_pct": {s: (round(100 * gt_sec_correct[s] / gt_sec_total[s], 1)
                                   if gt_sec_total[s] else None) for s in ("DINNER", "STAFF", "TRAVEL")},
        "gt_certain": gt_certain, "gt_uncertain": gt_uncertain,
        "gt_divergence_rate_pct": round(100 * gt_uncertain / total_gt, 1) if total_gt else None,
        "auto_coverage_pct": round(100 * auto / gt_certain, 1) if gt_certain else None,
        "auto_accuracy_pct": round(100 * correct / auto, 1) if auto else None,
        # ★ PRIMARY KPI (§5 codex): wrong auto-placements / GT-certain. In T&E a
        # wrong auto-placement silently corrupts the report (worse than escalation).
        "wrong_auto_rate_pct": round(100 * (auto - correct) / gt_certain, 1) if gt_certain else None,
        "escalation_rate_pct": round(100 * esc / gt_certain, 1) if gt_certain else None,
        "unseen_coldstart_pct": round(100 * unseen / gt_certain, 1) if gt_certain else None,
        "tier_counts": dict(tier),
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "uncertain_detail": uncertain_detail,
    }


def main():
    weeks = bdb.available_weeks()
    if "--run" not in sys.argv:
        print("=== holdout_eval DRY-RUN (no execution) ===")
        print(f"  weeks (LOWO folds): {[bdb._wk_num(w) for w in weeks]} (n={len(weeks)})")
        print(f"  GT: A=OCR per-receipt section, B=Excel per-image count cross-check")
        print(f"  GT-UNCERTAIN: A_count != B_count per (week,section) → excluded + divergence reported")
        print(f"  θ_mid sweep (escalation boundary): {THETA_MID_SWEEP}")
        print(f"  metrics: confusion / auto coverage+accuracy / escalation / unseen / θ-sensitivity")
        print("  → run with --run (GN-gated heavy step)")
        return

    print(f"=== holdout_eval A/B ablation — {len(weeks)} weeks (LOWO) ===")
    baseline = lowo(weeks, THETA_HIGH_FIXED, 0.20, policy="margin")     # R-C baseline
    hc = lowo(weeks, THETA_HIGH_FIXED, 0.20, policy="headcount")        # R-D +headcount
    print(f"\nGT reliability: certain={baseline['gt_certain']} uncertain={baseline['gt_uncertain']} "
          f"divergence={baseline['gt_divergence_rate_pct']}% (A vs B). NOTE: metrics below are the "
          f"CURRENT feature/frequency design's holdout numbers (14wk, STAFF n small) — NOT an absolute ceiling.")

    def rowfmt(label, k):
        return f"  {label:26} baseline={str(baseline.get(k)):>7}   +headcount={str(hc.get(k)):>7}"
    print("\n=== A/B ablation (baseline margin-T2  vs  +headcount rule) @θ_high=0.85 ===")
    print(rowfmt("wrong-auto-rate% ★KPI", "wrong_auto_rate_pct"))
    print(rowfmt("auto-coverage%", "auto_coverage_pct"))
    print(rowfmt("auto-accuracy%", "auto_accuracy_pct"))
    print(rowfmt("escalation%", "escalation_rate_pct"))
    print(f"  {'STAFF recall%':26} baseline={baseline['section_recall_pct']['STAFF']:>7}   "
          f"+headcount={hc['section_recall_pct']['STAFF']:>7}")
    print(f"  section recall  baseline={baseline['section_recall_pct']}  +hc={hc['section_recall_pct']}")
    print(f"\n  tier baseline:   {baseline['tier_counts']}")
    print(f"  tier +headcount: {hc['tier_counts']}")
    secs = ["DINNER", "STAFF", "TRAVEL"]
    print(f"\n=== confusion @ +headcount (GT-certain, auto-placed) ===")
    print(f"{'actual/pred':>12} " + " ".join(f"{s:>8}" for s in secs))
    for a in secs:
        rr = hc["confusion"].get(a, {})
        print(f"{a:>12} " + " ".join(f"{rr.get(p, 0):>8}" for p in secs))

    report = {"weeks": weeks, "theta_high": THETA_HIGH_FIXED,
              "framing_note": ("Holdout numbers are the CURRENT design's metrics over 14 weeks "
                               "(store-frequency + optional headcount; STAFF n small; this IS the "
                               "feature ablation). NOT an absolute ceiling — richer context "
                               "(project/companion) could improve further; conversely some "
                               "STAFF↔TRAVEL ambiguity may be irreducible without it. "
                               "PRIMARY KPI = wrong_auto_rate_pct (§5 codex)."),
              "baseline_margin": baseline, "plus_headcount": hc}
    PLANNING.mkdir(parents=True, exist_ok=True)
    (PLANNING / "store-db-holdout.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote planning/store-db-holdout.json")
    dwr = (hc['wrong_auto_rate_pct'] or 0) - (baseline['wrong_auto_rate_pct'] or 0)
    print(f"\n②-3 HONEST DELTA (+headcount vs baseline): "
          f"wrong-auto-rate {baseline['wrong_auto_rate_pct']}%→{hc['wrong_auto_rate_pct']}% (Δ{dwr:+.1f}), "
          f"STAFF-recall {baseline['section_recall_pct']['STAFF']}%→{hc['section_recall_pct']['STAFF']}%, "
          f"auto-coverage {baseline['auto_coverage_pct']}%→{hc['auto_coverage_pct']}%, "
          f"escalation {baseline['escalation_rate_pct']}%→{hc['escalation_rate_pct']}%.")


if __name__ == "__main__":
    main()
