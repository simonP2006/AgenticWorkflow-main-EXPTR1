# MASTER GO — Batch C (verify) — expensereceipt Option-A hardening

> Issued by: master (surface:1). To: CSO (ops executor, surface:3) → worker s2 (implementer).
> Status: **Batch A finalization §5 RATIFIED → Batch C AUTHORIZED on the COPY.**
> SOT: `HARDENING_CAMPAIGN.md` (round log) + `ROUND1_FIX_PLAN.md` §4 BATCH C (full item detail — CSO read it verbatim).

## 0. §5 ratification of Batch A finalization (basis for this GO)
5-way convergence: independent adversarial Agent PASS + CSO bidirectional re-verify PASS + worker selftest 41/0 + gemini-flash §5 PASS + **master fresh independent §5 Workflow `w31rkr8v9` = RATIFY-GO** (strongest — re-verified load-bearing facts directly):
- Promotion gap intact: LIVE original classify md5 == `1946695dbed3f5d06cfb82a0fb1dec42` EXACTLY (byte-untouched); copy md5 == `13b58150f667695721a90c051b7fb195`. Hardening lives ONLY in `_hardening/skills/`.
- Copy selftest read-only: EXIT=0, 41 PASS / 0 FAIL.
- Fail-loud confirmed by actual stderr: garbage confirmed values (`GARBAGE-SECTOR`, `12345`) → 2 LOUD section-confirmed re-escalation lines (no silent pass).
- Non-vacuous confirmed structurally: 4 hardening symbols 0-count in original / present in copy; original `_SHORT_TO_SPEC` lacks PARKING/TELEPHONE; 442→887 lines → FIN-1/2/3 NameError-FAIL pre-fix.
- C2 bidirectional sound; named false-negative regression genuinely closed.

**2 info-level polish items LOGGED for merge-time / Batch-F (NOT Batch-C blockers — both still escalate downstream = safe):**
- POLISH-1: fullwidth `ＫＩＣＣ` not NFKC-folded in `_is_parking_slip`/`_exact_norm` (real KICC POS slips emit ASCII; still escalates via store-db-miss net).
- POLISH-2: legacy `{confirmed:true}`-no-sector fall-through (C7 legacy shim already warns; still escalates).

## 1. INVIOLABLE PROTOCOL (unchanged from Batch A — re-stated, binding)
1. **Work on COPY only**: `_hardening/skills/expensereceipt-verify/`. Original `.claude/skills/expensereceipt-verify/` BYTE-UNTOUCHED.
   - **Worker first captures the verify ORIGINAL md5 baseline** (like classify's `1946695…`) BEFORE any edit, and re-asserts it unchanged after the batch — promotion gap must be provable.
2. **Input PRISTINE**: `raw-data/input/` read-only, manifest `2631d118` asserted before+after. Verify code must have NO write path to raw-data/input.
3. **Det-reduction**: each fix = new Python fn in the verify copy + the SKILL.md(copy) calls it (simultaneous), not LLM re-reasoning.
4. **Non-vacuous selftest per fix**: HARDCODE the real failure case, FAILing pre-fix / PASSing post-fix — prove with DATA, not "no change".
5. **Full green gate**: `/tmp/cso_sandbox_baseline.py` (177/177 isolated baseline + new verify selftests) all green; input PRISTINE assert; CSO recheck → **report to surface:1 → master judges + §5 at the checkpoint.** No advance on a red gate.
6. **Worker resumes each batch ONLY on explicit CSO GO after master §5.** Sequence: A(done) → **C** → B → D → E → F.

## 2. BATCH C SCOPE — verify `expensereceipt_verify.py` (verify-internal ONLY)
Per ROUND1_FIX_PLAN.md §4 BATCH C. **Master emphasis / binding constraints:**

- **★ANCHOR#2a — this is the suite's most safety-critical gate (the return-angle verify gate). FAIL-CLOSED discipline is mandatory (§6-b · M7 FAILCLOSED lesson):** ERROR / CANNOT-RUN / unrun-mandatory check ⇒ verdict ≠ PASS (exit ≠ 0). Distinguish a deliberate N/A-SKIP (e.g. V3 has no items this round) from an ERROR (producer absent / check raised / required input missing). **A vacuous SKIP must NEVER be counted as a passed check.** Surface per-check status in the JSON report.

- **V6-WIRING [verify-internal HALF ONLY] (crit):** check_consensus LOADS `ocr-vote-audit.json` itself + week-assert + reads ≥ MIN_READS + derive multiread from disk count. **Orchestrator passing run_dir → Batch F (DEFER — do NOT touch orchestrator.py in Batch C).** selftest: disk-load + wrong-week → ERROR (fail-closed).
- **V6-SCHEMA (high):** additive dual-file read (audit + report); report-presence / non-CONSENSUS → FAIL; freshness assert. NO change to the producer contract (protect the 14 vote selftests). selftest: INCONCLUSIVE report present → FAIL; stale week → FAIL.
- **V2-NOCARD (high):** **MUST NOT false-FAIL legit cash/toll/telephone.** Downgrade to escalation/VIOLATION, NOT hard FAIL. Allow-list sectors {PARKING/TOLLS, TELEPHONE-LOCAL} stay allowed; everything else no-card → SURFACED, not silently passed. Try a deterministic cash signal upstream first; if unavailable this round → escalation/VIOLATION. selftest: no-card meal → VIOLATION/escalate (not silent pass, not false-FAIL of cash).
- **V3-INERT (high) doc-honesty:** items not produced upstream this round (D1 = don't-wire-classify). **DROP V3 from the "7-check" claim OR derive explicit applicability from disk — do NOT count a vacuous SKIP as a check.** selftest: assert V3 applicability derived from data.
- **V2-AMOUNT (med):** canonical to-int normalizer in pool + match + negative/refund flag. selftest: str/float/refund.
- **V1-AGREEMENT (med):** matched receipt biz_no == consumed card biz_no (NFC). selftest: valid-but-mismatched biz.
- **V6-V3-CALLER-N/A (med):** derive applicability from disk, not caller booleans (folds into V6-WIRING + V3).
- **V7 (med, NOT det):** replay classify with SAME ordered dinner_dates + confirmed map; escalated-then-confirmed → assert assigned == confirmed.
- **V5 (med, NOT det):** key off cross-read handwriting disagreement (deterministic) + keep None → FAIL floor.
- **VERIFY-FALLBACK-PARSEDATE (low):** extract_card import-fail → ERROR (fail-closed), no naive re-impl.
- **PHYSICAL-CHECKS (low):** independently recompute pic-count delta + assert keys present.

## 3. DEFERRED to Batch F (do NOT touch in Batch C)
All orchestrator-contract / WIRE changes: V6-WIRING orchestrator-passing-run_dir half, DB-1 orchestrator call, DH-3 sales_slips threading, C1 --card fail-loud co-land. Reason (D1): wiring before C1 lands propagates silent-OTHERS into the gate; all orchestrator-contract changes are Batch F (LAST).

## 4. Required non-vacuous hardcoded cases for Batch C (minimum)
- wrong-week vote-audit on disk → ERROR (fail-closed)
- INCONCLUSIVE / non-CONSENSUS report present → FAIL
- stale week → FAIL
- no-card meal → VIOLATION/escalate (NOT false-FAIL of legit cash/toll/telephone)
- V3 applicability derived from data (not a vacuous SKIP counted as a check)
- extract_card import-fail → ERROR (fail-closed)

## 5. Checkpoint
Worker implements on copy → non-vacuous selftests FAIL pre-fix / PASS post-fix → full sandbox baseline green → input PRISTINE assert (2631d118) + verify-original md5 unchanged → CSO bidirectional recheck → **report to surface:1.** Master judges + §5 (Workflow-adversarial + gemini supplementary). On convergence → Batch B GO. No merge to live until the HARD MERGE GATE (all batches green + final §5 + 10-fresh-prompt gate + **owner approval — denylist**).
