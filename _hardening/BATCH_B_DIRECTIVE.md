# BATCH B — WORKER DIRECTIVE (db SOT integrity) — CSO (surface:3) → worker s2

> Master Batch C §5 RATIFY-GO → Batch B AUTHORIZED on the COPY. You are a WORKER (not master); report to CSO (surface:3). Read also: `_hardening/MASTER_GO_BATCH_B.md` + `ROUND1_FIX_PLAN.md §4 BATCH B` (full per-item detail). Constraints below are master-binding, WIN on conflict.

## 0. BOUNDARIES (inviolable)
- Edit **ONLY** `_hardening/skills/expensereceipt-db/scripts/` (db-internal: `expensereceipt_db.py` + its SKILL.md). **★Do NOT touch `expensereceipt/scripts/expensereceipt_orchestrator.py`** — DB-1 orchestrator CALL = **Batch F** (deferred). orchestrator must stay byte-identical (md5 `5dad9088c0bc61c3b2ac421a171580ce`).
- **★FIRST capture db ORIGINAL md5**: `.claude/skills/expensereceipt-db/scripts/expensereceipt_db.py` = `40e16d1fd5d113326e919c7b0a9e95ba` (CSO-captured) — re-assert UNCHANGED after the batch (promotion gap provable).
- Original `.claude/skills` byte-untouched · live stays PRE-FIX (no promotion) · input `raw-data/input/` read-only, **manifest `7b70b33745f4` (158 files)** assert before+after · db code must have NO write-path to raw-data/input · no git/merge/other-batch.
- Det-reduction: each fix = new Python fn in the db copy + SKILL.md(copy) references/calls it.

## 1. THE FIXES (`expensereceipt_db.py` + SKILL.md)
- **DB-1 [arg HALF ONLY] (crit):** `promote_week` gains a verify-verdict arg + week-match → **refuse unless verdict==PASS AND week matches**. ★The orchestrator CALL that passes the verdict = **Batch F (DEFER — do NOT touch orchestrator.py)**. Selftest: promote without PASS → refuse; promote wrong-week arg → refuse.
- **DB-4 (crit):** reject `EXPR_DB_BASE == PROJECT_DIR/planning` (enforce strict subdir; basename must be 'expensereceipt' or STORE_DB != legacy path). Selftest: collision base → reject.
- **DB-2 (crit, NOT det) — crash-safety / §6-b:** the multi-file promote (snapshot→STORE_DB→PROMOTED→classifydb→unlink) is non-transactional. Write **PROMOTED (provenance) BEFORE STORE_DB**, OR stage all + atomic swap; add a startup consistency check (store-db == rollup_from_ledger(promoted)) that **self-heals or fail-closes** — never silently half-committed. Selftest: inject crash between PROMOTED/STORE_DB writes → state consistent (self-heal), no silent desync.
- **DB-3 (crit, NOT det) — idempotency:** snapshot **once per logical promote** (key by week, skip if a snapshot for the in-progress week exists) + make promote idempotent on retry (detect week already in PROMOTED → short-circuit). Selftest: retry/crash of a logical promote → clean rollback (no double snapshot of polluted state).
- **DB-5 (high):** rollup sector lookup — NFC + canonical-case normalize before the 4-key learning map + **warn/counter on unknown sector (NO silent drop)**. Selftest: 'Staff Meeting'/'DINNER' variant + unknown → warned/counted, not dropped.
- **DB-6 (high):** gallery_add id = `max(existing G-####)+1` (regex parse), not `len(g)+1` — collision-free under deletion. Selftest: delete-then-add → no duplicate id.
- **DB-7 (med):** canonicalize amount in `_content_sig` (int(round(float)) / normalized) like date. Selftest: int 5000 vs str '5000' same receipt → one ledger row (same sig).
- **DB-8 (med):** `name_index_add` stops snapshotting live STORE_DB into classify-db; store_sector refresh only via `classifydb_rebuild` (post-verify). Selftest: name_index_add on unpromoted store-db → does NOT cache store_sector.
- **DB-10 (low):** min-occurrence-aware confidence (shrink toward 0.5 when occ<N) OR G12 require occ≥N. Selftest: single-observation store → not max-confidence/over-confident.
- **DB-9 (low):** validate date/time at ingest in name_index_add → surface unparseable (not silent '?' bucket). Selftest: bad date → surfaced.

## 2. REQUIRED non-vacuous hardcoded selftests (minimum — each FAIL pre-fix / PASS post-fix)
promote_week without verdict==PASS → refuse · promote_week wrong-week → refuse · EXPR_DB_BASE == PROJECT_DIR/planning → reject · crash between PROMOTED/STORE_DB → consistent (self-heal) · idempotent retry of a logical promote → clean (no double snapshot) · unknown sector → warned/counted (not silently dropped). Plus a case per other fix (DB-6 id, DB-7 sig, DB-8 no-snapshot, DB-10 occ, DB-9 bad-date).
★Namespace isolation: db selftests MUST use their own tempdir/EXPR_DB_BASE (NOT planning/store-db.json) — never perturb the real WK store-db.

## 3. VERIFY + REPORT
- Run `python3 /tmp/cso_sandbox_baseline.py` → db selftest green (21 base + new) + 0 FAIL + cross-importers (orchestrator/verify) still green + classify/others unchanged. Input PRISTINE (manifest 7b70b33745f4, 158). db-original md5 `40e16d1f…` unchanged. orchestrator.py md5 `5dad9088…` unchanged (Batch-F defer).
- Report to **CSO surface:3** (plain text, no backticks/$/modal): [1] db-original md5 before==after + orchestrator md5 unchanged · [2] functions touched · [3] each fix + selftest FAIL-pre/PASS-post DATA · [4] **DB-2/DB-3 crash-safety: show the injected-crash case yields consistent/self-healed state (not silent desync)** · [5] DB-4 collision reject · [6] final counts + no-regression + boundaries + promotion gap + namespace isolation (real store-db untouched). Then HOLD (no Batch D until master §5 + CSO GO). I (CSO) re-verify (crash-safety + DB-4 + namespace) before reporting up. If ambiguous → STOP + ask surface:3.
ACK on surface:3, then begin.
