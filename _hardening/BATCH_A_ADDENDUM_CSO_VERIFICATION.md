# Batch A ADDENDUM — CSO Independent Verification → master addendum §5

> Worker fixed the 3 master-§5 defects on the COPY. CSO independently re-verified. **2 of 3 fully PASS; C7 has a residual design-call I flag for your judgment.** Original untouched, input pristine, no regression. Worker HELD (no Batch C).

## Defect-flip verification (my independent probe `/tmp/cso_addendum_probe.py`)
1. **C5-NaN — FIXED ✓.** `people=float('nan')` → `escalate=True`, **NO crash** (was uncaught `int(nan)` ValueError pre-fix).
2. **C2 over-escalation — FIXED ✓.** 현장식당 / 주차장갈비 / KICC카페 → all `OTHERS-LOCAL, escalate=False` (route normally); **genuine 세외수입_KICC → escalate=True**. The bare-substring false-positives are gone; the real parking slip still escalates.
3. **C7 short-label — FIXED for the flagged case ✓, but with a RESIDUAL ⚠.**
   - `_SHORT_TO_SPEC` = {DINNER→'Dinner', STAFF→'STAFF MEETING', TRAVEL→'TRAVEL BUSINESS/ENTERTAINMENT', OTHERS→'OTHERS-LOCAL'} → short labels normalize cleanly (the exact case you flagged: owner writes `TRAVEL` → no longer aborts). Verified.
   - **RESIDUAL:** `run()` line 476 `sector = _confirmed_sector(confirmed[rid], rid)` has **no try/except**. A truly-invalid or case-variant label (e.g. `GARBAGE-SECTOR`, lowercase `travel`, `Travel`) still raises an **uncaught ValueError that aborts the entire run()** — a single typo'd owner label kills the whole week's classify.
   - **Tension:** your Batch-A C7 spec said "reject LOUD" (raise = loud), but your addendum principle said "복구가능 owner입력에 절대 크래시 금지 … run서 ValueError 잡아 재escalate." The worker took the `_SHORT_TO_SPEC` arm (normalize) but did NOT add the run()-level catch. So common abbreviations are accepted, but any other bad owner label aborts the run.
   - **CSO recommendation (your call):** add a run()-level `try/except ValueError` around line 476 → on invalid label, **re-escalate that one receipt** (don't abort the run) + record the bad value. This satisfies "never crash on recoverable owner input" while keeping the loud signal per-receipt. If you prefer abort-as-loud-reject, the current behavior is acceptable as-is. **Flagging for your addendum §5 judgment, not unilaterally directing the worker.**

## No regression / boundaries
- Selftests: classify **38 / 0 FAIL / exit 0** (35 + 3 addendum); orchestrator 27/27 + verify 56/56 green vs the fixed copy; merchant/db/place/autodetect/vote unchanged.
- Doc corrections present: SKILL.md `_TOLL_PREFIX` (was `_TOLL_TRIGGERS`), count 38/38; §6-b escalation disclosures (headcount→people remap, card-join 19=19 irrelevant, C6 0-count structural-not-empirical).
- **Original `.claude/skills` 16 source files byte-UNTOUCHED** (changed 0 / missing 0) · input **PRISTINE `2631d118`** · only 2 copy files touched · promotion gap respected (live stays pre-fix).

## Ask
Master: run addendum §5 + judge the C7 residual (accept loud-reject-abort, OR require the run()-level catch+re-escalate). On PASS → Batch C GO and I resume (worker held). No merge until the HARD gate.
