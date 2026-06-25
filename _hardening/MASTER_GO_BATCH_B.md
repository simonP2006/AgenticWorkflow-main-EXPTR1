# MASTER GO — Batch B (db) — expensereceipt Option-A hardening

> Issued by: master (surface:1). To: CSO (ops executor, surface:3) → worker s2 (implementer).
> Status: **Batch C (verify) §5 RATIFIED → Batch B AUTHORIZED on the COPY.**
> SOT: `HARDENING_CAMPAIGN.md` (round log) + `ROUND1_FIX_PLAN.md` §4 BATCH B (full item detail — read verbatim).

## 0. §5 ratification of Batch C (basis for this GO)
master fresh independent §5 Workflow `wslt6vsex` = **RATIFY-GO** (mustFix 0). 4-way convergence: worker 88/0 + CSO bidirectional re-verify PASS + master-WF (re-verified load-bearing facts directly) + the prior Batch A precedent. Master-WF confirmed READ-ONLY:
- Batch-F DEFER honored: `expensereceipt_orchestrator.py` orig == copy md5 `5dad9088c0bc61c3b2ac421a171580ce`, diff empty (NO orchestrator-contract drift).
- Promotion gap: LIVE verify md5 `9305ab1f11966a3ddbf9d20b666d2138` byte-untouched; copy `ca3ab103…`; selftest read-only (copy md5 unchanged before+after).
- Selftest EXIT0, 88/0 (89 green).
- ANCHOR#2a fail-closed: every degradation → ERROR → verdict ≠ PASS; vacuous SKIP never inflates gate; multiread_expected from on-disk count.
- V2-NOCARD bidirectional: no silent no-card pass; no false-FAIL of legit cash/toll/telephone.

## 1. INVIOLABLE PROTOCOL (unchanged — binding)
1. **Work on COPY only**: `_hardening/skills/expensereceipt-db/scripts/`. Original `.claude/skills/expensereceipt-db/` BYTE-UNTOUCHED. **Worker captures db ORIGINAL md5 baseline BEFORE any edit**, re-asserts unchanged after.
2. **Input PRISTINE**: `raw-data/input/` read-only. ★Baseline RE-BASELINED 157→**158** (the owner-added `WK22_2026/매출전표 - 롯데카드.pdf` is confirmed legit owner prep; the 157 campaign-baseline files remain byte-unchanged). Assert against CSO's updated 158-file manifest before+after. db code must have NO write-path to raw-data/input.
3. **Det-reduction**: each fix = new Python fn in the db copy + SKILL.md(copy) calls it (simultaneous).
4. **Non-vacuous selftest per fix**: HARDCODE the real failure case, FAILing pre-fix / PASSing post-fix.
5. **Full green gate**: `/tmp/cso_sandbox_baseline.py` (isolated baseline + new db selftests) all green; input PRISTINE assert (158 manifest); CSO recheck → **report to surface:1 → master judges + §5 at the checkpoint.** No advance on a red gate.
6. **Worker resumes each batch ONLY on explicit CSO GO after master §5.** Sequence: A,C(done) → **B** → D → E → F.

## 2. BATCH B SCOPE — db `expensereceipt_db.py` (db-internal; DB-1 orchestrator CALL → Batch F)
Per ROUND1_FIX_PLAN.md §4 BATCH B. **Master emphasis / binding constraints:**

- **DB-1 [arg HALF ONLY] (crit):** promote_week gains a verify-verdict arg + week-match (refuse unless verdict==PASS + week matches). **Orchestrator CALL that passes the verdict → Batch F (DEFER — do NOT touch `expensereceipt_orchestrator.py` in Batch B).** selftest: promote without PASS → refuse.
- **DB-4 (crit):** reject `EXPR_DB_BASE == PROJECT_DIR/planning` (enforce strict subdir; path-collision safety). selftest: collision base → reject.
- **DB-2 (crit, NOT det) — crash-safety:** write PROMOTED before STORE_DB (or staged atomic swap) + startup consistency self-heal. §6-b: inconsistency must be detected + fail-closed/self-heal, never silently half-committed. selftest: crash-between → consistent.
- **DB-3 (crit, NOT det) — idempotency:** snapshot once per logical promote (key by week) + idempotent retry. selftest: retry/crash → clean rollback.
- **DB-5 (high):** NFC + canonical-case sector map + warn/counter on unknown (NO silent drop). selftest: unknown sector → warned/counted, not dropped.
- **DB-6 (high):** gallery id = max(G-####)+1 (no collision/overwrite). selftest: id allocation.
- **DB-7 (med):** canonicalize amount in `_content_sig`. selftest: amount-format variants → same sig.
- **DB-8 (med):** `name_index_add` stops snapshotting store-db; store_sector only via post-verify rebuild. selftest: name_index_add does not mutate store-db snapshot.
- **DB-10 (low):** min-occurrence-aware confidence OR G12 require occ ≥ N. selftest: low-occurrence → not over-confident.
- **DB-9 (low):** validate date/time at ingest, surface unparseable. selftest: bad date → surfaced.

## 3. DEFERRED to Batch F (do NOT touch in Batch B)
DB-1 orchestrator CALL (the orchestrator threading promote→verdict-gated txn). All orchestrator-contract changes are Batch F (LAST). `expensereceipt_orchestrator.py` stays byte-identical through Batch B (master will re-verify md5 `5dad9088…` unchanged at the checkpoint).

## 4. Required non-vacuous hardcoded cases for Batch B (minimum)
- promote_week without verdict==PASS → refuse
- promote_week wrong-week arg → refuse
- EXPR_DB_BASE == PROJECT_DIR/planning collision → reject
- crash between PROMOTED/STORE_DB writes → consistent (self-heal)
- idempotent retry of a logical promote → clean (no double snapshot)
- unknown sector → warned/counted (not silently dropped)

## 5. Checkpoint
Worker implements on copy → non-vacuous selftests FAIL pre-fix / PASS post-fix → full sandbox baseline green → input PRISTINE assert (158 manifest) + db-original md5 unchanged + `expensereceipt_orchestrator.py` md5 `5dad9088…` unchanged (Batch-F defer) → CSO recheck → **report to surface:1.** Master judges + §5. On convergence → Batch D GO. No merge to live until the HARD MERGE GATE (all batches green + final §5 + 10-fresh-prompt gate + **owner approval — denylist**).
