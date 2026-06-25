#!/usr/bin/env python3
"""classify_section.py — R-C 3-tier section classifier (store → sector).

Predicts a receipt's section from its MERCHANT IDENTITY (사업자번호 via card
(date,amount) join, else normalized OCR store name) using the store_db section
frequency distribution:
  T1 (auto, high confidence): single dominant section, confidence ≥ θ_high.
  T2 (auto, clear margin):    top section margin ≥ θ_mid (no clear dominance).
  T3 (escalation):            ambiguous (no margin) | unseen (cold-start).

The classifier uses store/date/amount/사업자번호 — it does NOT use the receipt's
positional section as a feature, so the OCR-array section is a valid independent
ground-truth for holdout (master-approved A+B GT). Feature (headcount/hour/amount)
refinement of T2 is deferred to R-D.

SOT reuse (절대 기준 2): build_store_db for key derivation + card join.
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
import build_store_db as bdb  # noqa: E402

DEFAULT_THETA_HIGH = 0.85   # confidence (dominant section share) for T1 auto
DEFAULT_THETA_MID = 0.20    # margin (top1-top2)/total for T2 auto (margin policy)
HC_TRAVEL = 3               # headcount ≥ this at an ambiguous store ⇒ TRAVEL
                            # (data-grounded: STAFF@ambiguous never exceeds hc=2)


def receipt_key(receipt, card_pool):
    """Deterministic merchant key: 사업자번호 (card-matched) else norm store name."""
    cm = bdb.match_card(receipt, card_pool)
    if cm:
        bn = bdb._biz_no(cm.get("raw", {}))
        if bn:
            return bn, cm
    return f"name:{bdb.norm_store(receipt.get('store'))}", None


def classify(receipt, db, card_pool,
             theta_high=DEFAULT_THETA_HIGH, theta_mid=DEFAULT_THETA_MID,
             policy="headcount", hc_travel=HC_TRAVEL):
    """Return {section, tier, confidence, key}. section is None for T3 (escalation).

    policy:
      "margin"   — baseline (R-C): conf≥θ_high→T1, margin≥θ_mid→T2, else T3.
      "headcount"— R-D (§5): conf≥θ_high→T1 (unambiguous). For AMBIGUOUS stores,
                   drop low-confidence margin-T2 (where wrong-auto concentrated);
                   instead allow ONLY the high-precision rule hc≥hc_travel→TRAVEL
                   (STAFF@ambiguous never exceeds hc=2), else T3 escalation. This
                   minimizes wrong-auto-rate (the primary T&E KPI, §5 codex).
    """
    key, _cm = receipt_key(receipt, card_pool)
    e = db.get(key)
    if not e:
        return {"section": None, "tier": "T3-unseen", "confidence": 0.0, "key": key}
    dist = e.get("section_dist") or {}
    total = sum(dist.values())
    if total == 0:
        return {"section": None, "tier": "T3-unseen", "confidence": 0.0, "key": key}
    ranked = sorted(dist.items(), key=lambda kv: -kv[1])
    top_sec, top_n = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    conf = top_n / total
    margin = (top_n - second) / total
    if conf >= theta_high:
        return {"section": top_sec, "tier": "T1", "confidence": round(conf, 3), "key": key}
    # ambiguous zone (conf < θ_high)
    if policy == "headcount":
        hc = receipt.get("headcount")
        if hc is not None and hc >= hc_travel and "TRAVEL" in dist:
            return {"section": "TRAVEL", "tier": "T2-hc", "confidence": round(conf, 3), "key": key}
        return {"section": None, "tier": "T3-ambiguous", "confidence": round(conf, 3), "key": key}
    # baseline margin policy
    if margin >= theta_mid:
        return {"section": top_sec, "tier": "T2", "confidence": round(conf, 3), "key": key}
    return {"section": None, "tier": "T3-ambiguous", "confidence": round(conf, 3), "key": key}
