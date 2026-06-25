# MASTER MERGE DIRECTIVE — expensereceipt hardened suite → .claude/skills (OWNER-APPROVED)

> Issued by: master (surface:1). To: CSO (ops executor, surface:3).
> ★Owner go/no-go = **GO** ("머지 승인 + 실 WK23 정산", 2026-06-21). This is the denylist④⑤ irreversible promotion the owner authorized. Execute precisely; master independently verifies.
> All paths relative to `/Users/tajun/spJavis/AgenticWorkflow-main-EXPTR1` (PROJECT).

## Scope — 7 skill dirs to promote (COPY → ORIGINAL)
expensereceipt (master: orchestrator + SKILL.md), expensereceipt-classify, expensereceipt-verify, expensereceipt-place, expensereceipt-db, expensereceipt-extract, expensereceipt-merchant. Source = `_hardening/skills/<dir>`; target = `.claude/skills/<dir>`.

## STEP 1 — pre-merge baseline + BULLETPROOF backup (do FIRST; do NOT proceed if backup unverified)
1. Record pre-merge md5 of EVERY file under `.claude/skills/expensereceipt*` (expect the 8 originals: orch 5dad9088, classify 1946695d, verify 9305ab1f, place 527b96aa, db 40e16d1f, autodetect d51ae8a7, vote 0f5e5055, merchant f662e580). Save the listing to `/tmp/expr_premerge_md5.txt`.
2. Create a DURABLE backup tar of the 7 dirs: `tar czf /Users/tajun/spJavis/expr_premerge_backup_20260621.tgz -C /Users/tajun/spJavis/AgenticWorkflow-main-EXPTR1 .claude/skills/expensereceipt .claude/skills/expensereceipt-classify .claude/skills/expensereceipt-verify .claude/skills/expensereceipt-place .claude/skills/expensereceipt-db .claude/skills/expensereceipt-extract .claude/skills/expensereceipt-merchant` (outside the project tree = survives any in-tree op).
3. ★VERIFY the backup: `tar tzf` lists all expected files; extract to a temp dir and md5-compare a sample (e.g. each orchestrator/sub script) against the live originals — must match. If the backup is incomplete/unverifiable, STOP and report (do NOT merge).

## STEP 2 — merge (cp COPY over ORIGINAL)
For EACH of the 7 dirs: `cp -R _hardening/skills/<dir>/. .claude/skills/<dir>/` (the `/.` copies contents, overwriting). The `_hardening` dirs are full copies of the originals + the hardening changes, so this makes `.claude/skills/<dir>` byte-identical to `_hardening/skills/<dir>`. Do NOT use `--delete`. Do NOT touch raw-data/input.

## STEP 3 — post-merge verification (CSO; master will independently re-verify)
1. ★md5-compare: for every file, `.claude/skills/<dir>/...` md5 == `_hardening/skills/<dir>/...` md5 (the merge made them identical). Report any mismatch.
2. ★AS-SHIPPED selftest on the MERGED .claude orchestrator (the decisive test): `cd /tmp && python3 /Users/tajun/spJavis/AgenticWorkflow-main-EXPTR1/.claude/skills/expensereceipt/scripts/expensereceipt_orchestrator.py --selftest` → expect exit 0, 37/0, and `_REUSED {place:True,db:True,verify:True}` now resolving the `.claude` siblings (which are now hardened). Clear __pycache__ first.
3. Run each merged sub-skill's AS-SHIPPED selftest (classify/verify/place/db/extract/merchant) → all exit 0.
4. Confirm raw-data/input is UNCHANGED (input 158 PRISTINE manifest 7b70b33745f4 — the merge must not have touched input).
5. place.py convergence: `.claude/skills/expensereceipt-place` now == `_hardening` version (the 2-copy LOW item resolved).

## STEP 4 — re-baseline integrity watchdog (IMPORTANT)
The pre-merge origin-integrity baseline (8 originals byte-unchanged) is now INTENTIONALLY changed (that was the merge's purpose). RE-BASELINE the origin watchdog to the NEW post-merge .claude state (the hardened md5s), so it no longer flags the merge as a violation but DOES catch any future unauthorized change. Input watchdog (158 PRISTINE) stays as-is. Note the backup tar path in CSO_TODO for reversibility.

## STEP 5 — report to surface:1
Report: backup verified (path + tar listing count), per-file md5 .claude==_hardening (0 mismatch), AS-SHIPPED merged-orchestrator selftest exit0 37/0, all sub selftests exit0, input 158 PRISTINE, watchdog re-baselined. → master independent verification (AS-SHIPPED merged selftest + md5 spot-check + backup-restorability) → then node context-restart → real WK23 settlement.

## Reversibility
If anything is wrong post-merge: restore from `/Users/tajun/spJavis/expr_premerge_backup_20260621.tgz` (`tar xzf` into the project, overwriting `.claude/skills/expensereceipt*`). The pre-merge md5 listing `/tmp/expr_premerge_md5.txt` confirms a clean restore.
