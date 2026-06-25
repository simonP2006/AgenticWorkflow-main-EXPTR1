# MASTER GO — Batch F (orchestrator-contract + doc-honesty) — expensereceipt Option-A hardening — ★LAST BATCH

> Issued by: master (surface:1). To: **fresh-CSO** (post E→F restart, surface:3 or new) → worker s2.
> Status: pending Batch E §5 ratify (Workflow `wuqwv49zz`). On ratify → CSO careful restart → this GO.
> SOT: `HARDENING_CAMPAIGN.md` + `ROUND1_FIX_PLAN.md` §4 BATCH F (full detail — read verbatim).
> ★This is the INTEGRATION-CRITICAL final batch: the FIRST and ONLY edit to `expensereceipt_orchestrator.py`. It wires the 6 hardened sub-skills into one fail-closed end-to-end pipeline.

## 0. Scope note — what Batch F MAY touch on the COPY
- **orchestrator copy** `_hardening/skills/expensereceipt/scripts/expensereceipt_orchestrator.py` — the wiring (its md5 WILL change from `5dad9088`; that is EXPECTED for Batch F).
- **classify copy** `_hardening/skills/expensereceipt-classify/scripts/expensereceipt_classify.py` — ONLY for C1 `--card` fail-loud co-land (enforce --card-mandatory). Capture its current copy md5 first; the change must be surgical + non-vacuous-tested.
- **master SKILL.md** (the expensereceipt master skill doc) — DH-1/DH-2/DH-6 doc-honesty rewrite.
- ★ALL `.claude/skills/**` ORIGINALS (orchestrator + all 6 subs) stay BYTE-UNTOUCHED (promotion gap — nothing merges until the HARD MERGE GATE). The other 5 sub COPIES (verify, place, db, extract, merchant) stay as ratified in A–E — do NOT re-edit them.

## 1. INVIOLABLE PROTOCOL (binding)
1. Work on COPY only. ALL originals byte-untouched. Worker captures orchestrator-copy + classify-copy md5 baselines before editing; the 5 other sub copies' md5 must be UNCHANGED after Batch F.
2. Input PRISTINE: `raw-data/input/` read-only, manifest `7b70b33745f4` (158) before+after. No write to raw-data/input.
3. Det-reduction + non-vacuous selftest per fix (FAIL pre-fix / PASS post-fix) — ORCHESTRATE-LEVEL where applicable.
4. Full green gate: `/tmp/cso_sandbox_baseline.py` + new orchestrate selftests; input PRISTINE; originals untouched → CSO recheck → report to surface:1 → master §5 (the biggest §5).
5. Worker resumes only on explicit fresh-CSO GO. This is the LAST batch → then 10-fresh-prompt gate → merge (owner approval, denylist).

## 2. BATCH F SCOPE — orchestrator-contract wiring (per ROUND1_FIX_PLAN §4 BATCH F). Master emphasis:
- **D1-WIRE V6-WIRING [orch half] (crit):** orchestrator threads run_dir/week into run_logical so verify binds the vote-audit from disk (verify's disk-load half was done in Batch C). selftest: orchestrate → V6 reads vote-audit from disk; wrong-week on disk → ERROR.
- **D1-WIRE DB-1 [orch call] (crit):** orchestrator calls verify → quarantine → promote as ONE code-enforced transaction AFTER run_physical PASS, with promote GATED on verdict==PASS (the db-side gate was done in Batch B). selftest: FAIL/ERROR verdict → NO promote (fail-closed); PASS → promote.
- **D1-WIRE DH-3 (crit):** thread `run.get('sales_slips')` into verify_logical so the KICC 매출전표 (card sales-slip alternate-receipt) path is reachable. ★This is what lets the owner's KICC/롯데 매출전표 settle instead of false-V2-FAIL. selftest: sales_slip present → consumed, NOT V2-FAIL.
- **C1 --card fail-loud co-land (crit):** orchestrator ALWAYS passes card_pool into classify; classify enforces --card-mandatory now (fail-LOUD if card_pool missing, NOT silent-OTHERS, NOT crash). selftest: missing card → fail-loud ESCALATE (not crash, not silent route).
- **DR-5 (low):** orchestrator _dinner_confidence uses the shared norm_store/_mkey key. selftest: double-space store → G12 match.
- **DH-7 (low):** call stage_inputs() at head of orchestrate (code-enforce copy-first) OR soften the docstring to match reality.
- **DH-1 / DH-2 / DH-6 (DOC honesty):** rewrite master SKILL.md to ACTUAL behavior — verify→place→verify gate + emit-once orchestration trace; DROP the stage-table / exit-code / "6-subskill" overclaims; drop the stale `_get_name_db_row_range` clause. §6-b: zero overclaim residue (master grep the doc after).
- **NOT wired (deferred, document as such):** classify/merchant in-process reuse — leave deferred (future round). Do not over-reach.

## 3. ★Carry-forward cautions (from prior batches)
- **Batch-D LOW-2 (DORMANT over-dedup):** when wiring build_placements into the runtime orchestration, ENSURE the runtime supplies stable physical-receipt ids + images so dedup keys on the ID — NEVER on store|amount. Do NOT activate the dormant over-dedup path (would collapse two distinct receipts). Add a non-vacuous selftest that two distinct same-day same-amount receipts both get placed.
- **Batch-D LOW-1 (png-Default):** safe for WK00/WK23 template (registers png); no action unless a no-pic template is introduced.
- **fail-closed everywhere:** the wired txn must preserve every fail-closed property from C/B/D — ERROR/unrun-mandatory → verdict≠PASS → no promote/place; degradation never silently green.

## 4. Required non-vacuous hardcoded cases for Batch F (minimum)
- orchestrate → V6 binds vote-audit from disk; wrong-week on disk → ERROR
- verify FAIL/ERROR verdict → orchestrator does NOT promote (fail-closed)
- KICC sales_slip present → consumed (not V2-FAIL) → settles
- missing card_pool → classify fail-loud ESCALATE (not crash, not silent-OTHERS)
- two distinct same-day same-amount receipts → both placed (dormant over-dedup NOT activated)
- master SKILL.md doc-honesty: zero overclaim residue (grep after)

## 5. Checkpoint (the biggest — integration-critical)
Worker implements on copy (orchestrator + classify-for-C1 + master SKILL.md) → non-vacuous orchestrate-level selftests → full sandbox baseline green → input PRISTINE (158/`7b70b33745f4`) + ALL originals byte-untouched + the 5 non-classify sub COPIES md5 unchanged → CSO recheck → **report to surface:1.** Master judges + §5 (the deepest: verify orchestrator wiring is correct AND fail-closed end-to-end AND doc-honest). On convergence → ★**10 FRESH-PROMPT GATE** (100%·zero-hallucination·prompts differ from every prior round) → **merge proposal to owner (denylist — owner approval required).** Then (a) real WK23 settlement on the merged, hardened suite.
