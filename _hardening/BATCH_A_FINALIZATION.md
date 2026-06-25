# BATCH A — INTEGRATED FINALIZATION (master addendum §5 FAIL → C7 refinement + 2 MAJOR + 1 note, ONE assignment)

> Authority: master addendum §5 (Workflow w3gkspypg) = FAIL — adversarial-edge found defects gemini/CSO/worker missed. Fix ALL below in ONE pass on the COPY (still classify, still Batch A, NOT Batch C). Same inviolable boundaries: copy `_hardening/skills/expensereceipt-classify/` only · original `.claude/skills` byte-untouched (live stays PRE-FIX, no promotion) · input read-only · no git/merge/other-batch.
> CSO independently CONFIRMED both MAJORs (pre-fix baseline): 주차장/공영주차장/노상주차장 → escalate=False (regression); `_SHORT_TO_SPEC` only {DINNER,STAFF,TRAVEL,OTHERS}; PARKING/TELEPHONE short → ValueError abort.

## [MAJOR-1] C2 주차장 REGRESSION (token-boundary over-correction broke real parking slips)
**Problem:** real parking-lot slips 주차장 / 공영주차장 / 노상주차장 / 시영주차장 now do NOT escalate (they contain 주차 but aren't the standalone segment), so a genuine parking receipt silently → OTHERS-LOCAL; worse, a dinner-time 주차장 that store-db learned as DINNER would silent-auto-commit to DINNER = **ANCHOR #2b violation**. The current selftest only checks 주차장갈비 (must-NOT), so the regression is invisible.
**Fix (worker discretion):** restore real parking slips → ESCALATE (suggested PARKING/TOLLS) while keeping food/business-suffix compounds blocked. Either: (a) 주차 substring + exclude when a food/business suffix follows (식당·갈비·카페·뷔페·주점·치킨·국밥·… ) , OR (b) add 주차장/공영주차장/노상주차장/시영주차장 as STRONG tokens. Ensure the parking detection fires BEFORE any store-db DINNER auto-commit (a parking slip must never silently become DINNER).
**★Required selftest (BOTH directions):** 주차장→escalate · 공영주차장→escalate · 노상주차장→escalate · 주차장갈비→NOT escalate · 현장식당→NOT escalate · 세외수입_KICC→escalate. (Pre-fix: the parking-lot ones FAIL [escalate=False]; post-fix PASS.)

## [MAJOR-2] C7 half-fix — _SHORT_TO_SPEC missing PARKING/TELEPHONE
**Problem:** `_SHORT_TO_SPEC` has only 4 of 6 sectors → owner short label `PARKING` or `TELEPHONE` → `_confirmed_sector` ValueError → run abort.
**Fix:** add `PARKING`→`PARKING/TOLLS`, `TELEPHONE`→`TELEPHONE` (all 6 canonical sectors covered; inert to store-learning so safe).
**Selftest:** `_confirmed_sector('PARKING',rid)`→PARKING/TOLLS, `('TELEPHONE',rid)`→TELEPHONE; no abort (pre-fix: ValueError).

## [C7 REFINEMENT — master judgment] run()-level resilience (the C7 residual I flagged)
**Fix in `run()` (around L476):**
1. **case/whitespace-normalize the canonical passthrough too** — accept `travel`/`Travel`/`OTHERS-LOCAL`/whitespace-variants → canonical (not just the 6 exact short forms). Owner case/spacing typos are recoverable input.
2. **catch the ValueError** for a still-genuinely-invalid label (garbage/unknown sector) → **re-escalate THAT receipt only + log the bad value (per-receipt LOUD) + run CONTINUES** (NO whole-run abort). One owner typo in a multi-receipt week must not crash the whole run.
**Selftest:** case-variant (travel/Travel)→accept/resolve · garbage label in a multi-receipt run → that receipt re-escalates AND the run completes (other receipts processed) · loud-log assertion preserved (rewrite the old case-9 from "abort expected" → "per-receipt-loud + run-completes expected").

## [NOTE → fold] _normalize_confirmed_label isinstance(str) guard
Add `isinstance(cval, str)` guard in `_normalize_confirmed_label` (non-string confirmed value → handle gracefully via the same re-escalate path, don't crash).

## [C5] no mandatory change
C5 is robust (1e308 etc. is cosmetic). No action required; do not regress it.

## VERIFY + REPORT (to CSO surface:3, plain text, no backticks/$/modal)
- Each fix: non-vacuous selftest FAIL-pre / PASS-post (hardcode the real inputs). `python3 /tmp/cso_sandbox_baseline.py` → classify FAIL=0, cross-importers (orch 27 / verify 56) green, others unchanged. Input pristine (manifest 2631d118). Original byte-untouched. Copy only. Live NOT promoted.
- Report: [1] functions touched · [2] each fix + selftest FAIL-pre/PASS-post DATA — **for C2 show BOTH directions (parking-lot escalate restored AND food-suffix still suppressed AND standalone 주차/현장 still escalate)** · [3] final selftest counts + no-regression · [4] original untouched + input pristine + promotion gap.
Then HOLD (no Batch C until master §5 re-confirm of this finalization + CSO GO). I (CSO) will re-verify adversarially — both directions on C2 — before reporting up.
