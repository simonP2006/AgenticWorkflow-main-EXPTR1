# MASTER GO — Batch D (place) — expensereceipt Option-A hardening

> Issued by: master (surface:1). To: CSO (ops executor, surface:3) → worker s2 (implementer).
> Status: **Batch B (db) §5 RATIFIED → Batch D AUTHORIZED on the COPY.**
> SOT: `HARDENING_CAMPAIGN.md` (round log) + `ROUND1_FIX_PLAN.md` §4 BATCH D (full item detail — read verbatim).

## 0. §5 ratification of Batch B (basis for this GO)
master fresh independent §5 Workflow `wq0r17ygb` = **RATIFY-GO** (mustFix 0). 4-way convergence (worker 43/0 + CSO bidirectional + master-WF + Batch-A/C precedent). Master-WF confirmed READ-ONLY: DB-1 gate fail-closed (live probe: no-verdict promote → RuntimeError, no store-db written, exit1); DB-4 planning-collision reject (resolve()-canonical, all bypasses blocked); DB-2/3 crash-safety detect-surfaces + deterministic self-heal + snapshot-once; real planning/store-db.json md5 `dd4e8453` unchanged (namespace isolation); db orig md5 `40e16d1f` untouched (copy `91e431b9`); orchestrator `expensereceipt_orchestrator.py` byte-identical `5dad9088` (Batch-F defer, zero promote_week/db refs); selftest 43/0 exit0.

## 1. INVIOLABLE PROTOCOL (unchanged — binding)
1. **Work on COPY only**: `_hardening/skills/expensereceipt-place/scripts/`. Original `.claude/skills/expensereceipt-place/` BYTE-UNTOUCHED. **Worker captures place ORIGINAL md5 baseline BEFORE any edit**, re-asserts unchanged after.
2. **Input PRISTINE**: `raw-data/input/` read-only, manifest `7b70b33745f4` (158 files) assert before+after. place must NOT write to raw-data/input.
3. **★Preserve M6-verified placement integrity (place.py does delicate xlsx byte-surgery):** the existing place pipeline was adversarially SAFE-verified (verbatim zip, [Content_Types] png Default preserved byte-identical, drawing rels↔blip r:embed correct, no media/cNvPr/rId collision, twoCellAnchor in-bounds, atomic os.replace AFTER physical_verify PASS, input xlsx MD5 immutable). PLACE-1..5 must NOT regress any of these. Re-assert at checkpoint.
4. **Det-reduction**: each fix = new Python fn in the place copy + SKILL.md(copy) calls it.
5. **Non-vacuous selftest per fix**: HARDCODE the real failure case, FAIL pre-fix / PASS post-fix.
6. **Full green gate**: `/tmp/cso_sandbox_baseline.py` (isolated baseline + new place selftests) all green; input PRISTINE assert; place-original md5 unchanged; **orchestrator.py `5dad9088` unchanged (Batch-F defer)** → CSO recheck → **report to surface:1 → master §5.** No advance on a red gate.
7. **Worker resumes each batch ONLY on explicit CSO GO after master §5.** Sequence: A,C,B(done) → **D** → E → F.

## 2. BATCH D SCOPE — place `expensereceipt_place.py` (place-internal; orchestrator UNTOUCHED)
Per ROUND1_FIX_PLAN.md §4 BATCH D. **Master emphasis / binding constraints:**

- **PLACE-1 (crit, det) [dup-paste]:** `build_placements(receipts_for_sector, band)` → exactly 1 placement per stable physical-receipt id (D3). Fixes the re-paste of the same multi-receipt PDF page 3×. selftest: multi-line-item receipt → 1 placement.
- **PLACE-2 (crit, det) [dup-paste]:** content-md5 media dedup — embed each unique image ONCE, reuse rId; coupled to PLACE-1. selftest: duplicate source image → 1 embedded media (reused rId), no media/rId collision.
- **expected_pics SINGLE-SOURCE (must-change 5) — achieve WITHOUT touching orchestrator:** `build_placements()` returns the DEDUPED list, which IS `run['placements']`; orchestrator.py:164 already computes `len(run['placements'])`, so the physical-gate count auto-reflects the deduped count. **Do NOT edit orchestrator.py** — the single-source property comes from place.py dedup. selftest: deduped placement count == embedded media count == physical-gate expected.
- **PLACE-3 (high, det) [grayscale leak]:** placement `source_image` = COLOR original, NEVER the grayscale OCR-preprocessed copy. `_to_png_bytes` guard: mode ∈ ('L','LA','1') → raise/escalate (fail-closed). selftest: grayscale source path → reject/escalate.
- **PLACE-4 (high, det) [uniform-grid]:** per-sector geometry — 3-per-row grid for photo sectors; full-width per_row=1 for TELEPHONE / PARKING (from the WK21 filled-week reference, row_gap=16 ground-truth). layout reads per_row from the band. selftest: full-width band sizing vs WK21 reference; non-uniform item placed correctly.
- **PLACE-5 (high, det):** `resolve_receipt_drawing(xlsx)` dynamic via rels-graph → correct write target; constant fallback for the WK23 template. selftest: variant template resolves correctly (no hardcoded drawing2.xml assumption breaking).

## 3. DEFERRED to Batch F (do NOT touch in Batch D)
orchestrator.py stays byte-identical `5dad9088` (master re-verifies at checkpoint). No orchestrator-contract change. expected_pics single-source is achieved purely in place.py (see §2).

## 4. Required non-vacuous hardcoded cases for Batch D (minimum)
- multi-line-item / multi-receipt page → 1 placement per physical receipt (not 3×)
- duplicate source image → 1 embedded media (reused rId), no collision
- grayscale source → reject/escalate (color original required)
- deduped placement count == embedded media == physical-gate expected (no false-FAIL)
- variant/template drawing target resolved dynamically (PLACE-5)
- M6 integrity preserved: input xlsx MD5 immutable, atomic os.replace only after physical_verify PASS

## 5. Checkpoint
Worker implements on copy → non-vacuous selftests FAIL pre-fix / PASS post-fix → full sandbox baseline green → input PRISTINE assert (158/`7b70b33745f4`) + place-original md5 unchanged + orchestrator.py `5dad9088` unchanged + M6 placement-integrity re-asserted → CSO recheck → **report to surface:1.** Master judges + §5. On convergence → Batch E GO. No merge to live until the HARD MERGE GATE (all batches green + final §5 + 10-fresh-prompt gate + **owner approval — denylist**).
