# BATCH A — ADDENDUM (master §5 PASS-with-notes: 3 latent defects to fix NOW on copy)

> Authority: master §5 (3-lens Workflow + gemini-flash) PASSED Batch A but adversarial edge-testing found 3 real defects (latent/quarantined now; go LIVE at Batch-F wiring/promotion). Fix on the COPY now (still classify, still Batch A — **NOT Batch C**). Same inviolable boundaries: copy `_hardening/skills/expensereceipt-classify/` only · original `.claude/skills` byte-untouched · input read-only · no git/merge · no other batch.

## 3 DEFECTS (each: fix + a NON-VACUOUS selftest, FAIL pre-fix / PASS post-fix)
1. **C5-NaN crash.** `_safe_people(float('nan'))` → `int(nan)` raises uncaught `ValueError` → crash. Fix: guard NaN (e.g. `math.isnan`) → return None → routes to C4 escalate (unread headcount). Selftest: `people=float('nan')` → escalate, NO crash.
2. **C2 substring over-escalation.** `_PARKING_SLIP_TOKENS` bare-substring match wrongly escalates real merchants that merely CONTAIN a token — 현장식당 (contains 현장), 주차장갈비 (contains 주차), KICC카페 (contains KICC). Fix: token-boundary / anchored match (e.g. exact token segmentation, or require 세외수입+KICC co-occurrence, or word-boundary) so a genuine parking slip (세외수입/현장 standalone, KICC parking category) still escalates but those 3 do NOT. Selftest: 현장식당·주차장갈비·KICC카페 → **NOT escalate** (route normally); genuine KICC 세외수입 slip → still escalate.
3. **C7 short-label re-run crash.** If the owner writes a non-canonical / short sector label into section-confirmed (e.g. `rid→TRAVEL` short form), `_confirmed_sector`'s membership-check raises uncaught `ValueError` → `run()` ABORTS (crash on recoverable owner input). Fix: normalize via `_SHORT_TO_SPEC` (short→canonical) OR catch the ValueError in `run()` and re-escalate that receipt (never crash on recoverable owner input). Selftest: short-label confirmed value → re-run SUCCEEDS (receipt resolved or re-escalated), no abort.

Target: classify selftest 35 → ~38 (one non-vacuous case per defect). Run `/tmp/cso_sandbox_baseline.py` → classify FAIL=0, cross-importers (orch 27 / verify 56) still green, others unchanged.

## DOC / DISCLOSURE corrections (§6-b honesty)
- SKILL.md:93 — `22/22` → the actual current selftest numbers.
- SKILL.md:46 — `_TOLL_TRIGGERS` → `_TOLL_PREFIX` (renamed constant; stale reference).
- Escalation-rate disclosure (in your report / any doc that cites it): state explicitly (a) the headcount→people fixture remap that was applied, (b) the real card-join was causally irrelevant to the rate (19=19 identical with/without), (c) the C6 "0 added escalations" is a **structural certainty** (the measured data all carries a time, so the no-time branch is never entered) — NOT an empirical validation that C6 never over-escalates in the wild.

## ★PROMOTION GAP (critical — do not violate)
The hardened classify lives in `_hardening/` ONLY. The LIVE `.claude/skills/expensereceipt-classify` stays **pre-fix**. Do NOT copy/promote to live. Batch C (later) must NOT assume the live classify is hardened. Promotion happens only at the final gate-merge.

## REPORT (to CSO surface:3, plain text, no backticks/$/modal)
[1] WHAT changed (functions touched) · [2] each defect: the fix + the selftest FAIL-pre/PASS-post data · [3] the 3 over-escalation merchants now route normally + genuine KICC still escalates · [4] doc corrections applied · [5] final selftest counts + no-regression + original untouched + input pristine. Then HOLD (still no Batch C until master §5 of the addendum + CSO GO).
