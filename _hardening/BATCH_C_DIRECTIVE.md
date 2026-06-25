# BATCH C — WORKER DIRECTIVE (verify gate hardening) — CSO (surface:3) → worker s2

> Master RATIFY-GO (Batch A finalization §5, 5-way convergence). Batch C AUTHORIZED on the COPY. You are a WORKER (not master). Report to CSO (surface:3). Read also: `_hardening/MASTER_GO_BATCH_C.md` + `ROUND1_FIX_PLAN.md §4 BATCH C` (full per-item detail) + audit findings. The constraints below are master-binding and WIN on conflict.

## 0. BOUNDARIES (inviolable)
- Edit **ONLY** `_hardening/skills/expensereceipt-verify/` (verify-internal: `expensereceipt_verify.py` + its SKILL.md). **★Do NOT touch `expensereceipt/scripts/expensereceipt_orchestrator.py`** — all orchestrator-contract/threading is **Batch F** (deferred).
- **★FIRST capture the verify ORIGINAL md5 baseline**: `md5 .claude/skills/expensereceipt-verify/scripts/expensereceipt_verify.py` (record it) BEFORE any edit; re-assert it UNCHANGED after the batch (promotion gap must be provable, like classify's `1946695…`).
- Original `.claude/skills` byte-untouched · live stays PRE-FIX (no promotion) · `raw-data/input/` read-only, manifest `2631d118` assert before+after · verify must have NO write path to raw-data/input · no git/merge/other-batch.
- Det-reduction: each fix = new Python fn in the verify copy + SKILL.md(copy) references/calls it.

## 1. ★ANCHOR#2a — FAIL-CLOSED is the whole point of this gate (§6-b · M7 lesson)
This is the suite's most safety-critical gate. **ERROR / CANNOT-RUN / unrun-mandatory check ⇒ verdict ≠ PASS (exit ≠ 0).** Distinguish a deliberate N/A-SKIP (V3 genuinely has no items this round) from an ERROR (producer absent / check raised / required input missing). **A vacuous SKIP must NEVER be counted as a passed check.** Surface per-check status in the JSON report. Every fix below must preserve/strengthen this — never weaken a mandatory check into a clean SKIP.

## 2. THE FIXES (`expensereceipt_verify.py` + SKILL.md)
- **V6-WIRING [verify-HALF ONLY] (crit):** `check_consensus` LOADS `ocr-vote-audit.json` itself + assert `audit['week']==expected` + `reads>=MIN_READS` + derive `multiread_expected` from the on-disk count of `ocr-results-*.json` (NOT a caller boolean). **Orchestrator passing run_dir = Batch F — do NOT touch orchestrator.py.** Selftest: disk-load OK; wrong-week on disk → ERROR (fail-closed).
- **V6-SCHEMA (high):** additive **dual-file read** — verify reads BOTH `ocr-vote-audit.json` + `ocr-vote-report.json`; report-presence / non-CONSENSUS result → FAIL; freshness/week assert so a stale CONSENSUS can't satisfy. **NO change to the producer (vote) contract** (protect the 14 vote selftests). Selftest: INCONCLUSIVE report present → FAIL; stale week → FAIL.
- **V2-NOCARD (high):** ★MUST NOT false-FAIL legit cash/toll/telephone. A receipt that consumes no card row: if sector ∈ {PARKING/TOLLS, TELEPHONE-LOCAL} (or a deterministic cash signal if you can source one upstream) → allowed; everything else no-card → **escalation / VIOLATION (NOT hard FAIL), SURFACED not silently passed.** Selftest: no-card meal → VIOLATION/escalate; no-card toll/telephone → NOT false-FAIL.
- **V3-INERT (high, doc-honesty):** items aren't produced upstream this round (classify not wired = D1). **DROP V3 from the "7-check" claim OR derive explicit applicability from disk** — do NOT count a vacuous SKIP as a passed check. Update SKILL.md honestly. Selftest: V3 applicability derived from data, not a clean SKIP.
- **V2-AMOUNT (med):** canonical to-int (or Decimal) amount normalizer in build_card_pool + check_card_match (mirror parse_amount) + explicit negative/refund flag. Selftest: str/float/refund amounts.
- **V1-AGREEMENT (med):** for every card-MATCHED receipt assert `receipt.biz_no == _biz_no(matched_card.raw)` (NFC). Selftest: checksum-valid-but-mismatched biz → flagged.
- **V6-V3-CALLER-N/A (med):** remove caller ability to declare a mandatory check N/A — derive applicability from disk (folds into V6-WIRING + V3).
- **V7 (med):** replay `classify_receipt` with the SAME ordered `dinner_dates` + confirmed map the real run used (not empty); for escalated-then-confirmed receipts assert `assigned == confirmed` (section-confirmed). Keep the valid-sector membership arm. (Note: classify is now hardened in the copy — the sandbox harness binds the copy classify; verify against it.)
- **V5 (med):** key off cross-read handwriting DISAGREEMENT (deterministic, from reads on disk) + keep the None→FAIL floor. Don't trust a model-supplied hw_confidence scalar.
- **VERIFY-FALLBACK-PARSEDATE (low):** extract_card import-fail → set parse_date=None and make date-normalizing checks return ERROR (fail-closed), NOT a naive inline re-impl.
- **PHYSICAL-CHECKS (low):** run_physical independently recomputes the pic-count delta (zip_drawing_counts(placed) − baseline) + asserts every expected pv key present (missing → ERROR not silent FAIL).

## 3. REQUIRED non-vacuous hardcoded selftests (minimum — each FAIL pre-fix / PASS post-fix)
wrong-week vote-audit on disk → ERROR · INCONCLUSIVE/non-CONSENSUS report present → FAIL · stale week → FAIL · no-card meal → VIOLATION/escalate (AND no-card toll/telephone → NOT false-FAIL) · V3 applicability derived from data · extract_card import-fail → ERROR. Plus a case per other fix (V2-AMOUNT, V1-AGREEMENT, V7, V5, PHYSICAL).

## 4. VERIFY + REPORT
- Run `python3 /tmp/cso_sandbox_baseline.py` → verify selftest green (56 base + your new cases) + 0 FAIL + cross-importers (orchestrator) still green + classify/others unchanged. Input PRISTINE (2631d118). Verify-original md5 unchanged (capture before, assert after).
- Report to **CSO surface:3** (plain text, no backticks/$/modal): [1] verify-original md5 before==after · [2] functions touched · [3] each fix + selftest FAIL-pre/PASS-post DATA · [4] **per-check ERROR vs SKIP discipline preserved (ANCHOR#2a): show a forced-ERROR case yields verdict≠PASS** · [5] V2-NOCARD: cash/toll/telephone NOT false-FAILed · [6] final counts + no-regression + boundaries + promotion gap. Then HOLD (no Batch B until master §5 + CSO GO). I (CSO) re-verify (incl. the fail-closed ERROR cases + V2-NOCARD both ways) before reporting up. If ambiguous → STOP + ask surface:3.
ACK on surface:3, then begin.
