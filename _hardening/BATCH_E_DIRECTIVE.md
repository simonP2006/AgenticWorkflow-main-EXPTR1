# BATCH E — WORKER DIRECTIVE (extract/merchant ingest) — CSO (surface:3) → worker s2

> Master Batch D §5 RATIFY-GO → Batch E AUTHORIZED on the COPY. You are a WORKER (not master); report to CSO (surface:3). Read also: `_hardening/MASTER_GO_BATCH_E.md` + `ROUND1_FIX_PLAN.md §4 BATCH E`. Constraints below are master-binding, WIN on conflict.

## 0. BOUNDARIES (inviolable)
- Edit **ONLY** these COPY files: `_hardening/skills/expensereceipt-extract/scripts/autodetect.py` + `expensereceipt_vote.py`, and `_hardening/skills/expensereceipt-merchant/scripts/expensereceipt_merchant.py` (+ the two skills' SKILL.md). **★Do NOT touch `expensereceipt/scripts/expensereceipt_orchestrator.py`** (stays byte-identical md5 `5dad9088c0bc61c3b2ac421a171580ce`).
- **★FIRST capture each touched-file ORIGINAL md5** (CSO-captured baselines): autodetect.py `d51ae8a79e9eb609b4c0bc53c6f3f108` · expensereceipt_vote.py `0f5e505562c3dd810a52cab027c4cfce` · expensereceipt_merchant.py `f662e5802f1175355d7cd9a136d6ac54` — re-assert ALL unchanged after the batch.
- Original `.claude/skills` byte-untouched · live PRE-FIX (no promotion) · input `raw-data/input/` read-only, manifest `7b70b33745f4` (158) assert before+after · NO write-path to raw-data/input · selftests use synthetic/tempdir inputs (the real input incl. the owner T-world bill is READ-ONLY) · no git/merge/other-batch.
- Det-reduction: each fix = new Python fn in the copy + SKILL.md(copy) references/calls it.

## 1. THE FIXES
**autodetect.py:**
- **AUTODETECT-1 (high, det):** new file-kind `telephone_bill` — NFC tokens (청구내역 / 통신비 / 청구서 / T world / SKT / KT / LG U+) → TELEPHONE sector bucket, NOT the receipts list (so it does NOT enter the card consume-once match). Handles the owner `청구내역 인쇄하기 _ T world.pdf` now in input. selftest: T-world bill filename → telephone_bill (not receipt).
- **AUTODETECT-2 (high, det):** page_count via **`pdfinfo`** (D5 — REUSE pdftoppm/sips/pdfinfo, **NO new pypdf/PyMuPDF**) + emit one candidate per page (stable page-ordinal id) + flag/HALT when page_count>1. **★FAIL-CLOSED: if the `pdfinfo` binary is absent / errors → ERROR/HALT, NEVER silently assume 1 page.** selftest: multi-page PDF → page_count + flag; pdfinfo-absent (simulate) → ERROR (fail-closed, not 1-page).
- **AUTODETECT-3 (low, det):** precedence comment (the existing classify_file branch order is load-bearing) + dual-token selftest (a filename matching 2 patterns → deterministic precedence).

**expensereceipt_vote.py:**
- **VOTE-1 (high, det):** multiset key `(date, amount, occurrence_ordinal)` with stable within-read order — vote PER OCCURRENCE so two DISTINCT receipts sharing the same (date,amount) on one day are BOTH voted (not collapsed/overwritten). Restores the legacy section-separated guarantee. selftest: duplicate date+amount same day → both occurrences voted (count stays 2, each independently validated). ★Do NOT break the 14 vote base selftests (producer schema additive).

**expensereceipt_merchant.py:**
- **MERCHANT-1 (med, det):** the fallback (import-fail) match_card normalizes dates (parse_date-equiv: NFC+strip+replace('/','-').replace('.','-')) so it's byte-equivalent to the imported producer; log `_REUSED=False` honestly when degraded. selftest: slash-vs-dash date variant → fallback still matches (== imported path).
- **MERCHANT-2 (med, det):** ONE owner of the consume-once (date,amount) join — pick: either -verify IMPORTs merchant's join (producer-rule) OR merchant aligns its match_card to verify's (canceled-row exclusion + None-amount guard). **Document the chosen single source.** selftest: consume-once not double-counted. (NOTE: this is merchant-side only; do NOT edit verify in Batch E — if you choose "verify imports", just make merchant's join the canonical importable one; the verify-side wiring stays as Batch C left it.)
- **MERCHANT-3 (low, det):** additive structural biz guard — reject all-zero `0000000000` (and optionally reserved-range) as a **SEPARATE flag/function**, keeping `validate_biz_no` (the producer -verify imports) BACK-COMPAT unchanged. selftest: all-zero biz → rejected by the new structural check; validate_biz_no checksum behavior unchanged.

## 2. REQUIRED non-vacuous hardcoded selftests (minimum — each FAIL pre-fix / PASS post-fix)
T-world/통신비/청구내역 file → telephone_bill → TELEPHONE (not receipts) · multi-page PDF → page_count + flag/HALT · **pdfinfo-absent → ERROR/HALT (fail-closed, never 1-page)** · duplicate date+amount same day → both voted (not collapsed) · date-format variant → merchant match works · consume-once → no double-count · all-zero biz → rejected (structural) · dual-token filename → deterministic precedence.

## 3. VERIFY + REPORT
- Run `python3 /tmp/cso_sandbox_baseline.py` → autodetect + vote + merchant selftests green (14+14+13 base + new) + 0 FAIL + cross-importers (orchestrator/verify) still green + others unchanged. Input PRISTINE (158, `7b70b33745f4`). All 3 touched-originals md5 unchanged. orchestrator.py `5dad9088` unchanged.
- Report to **CSO surface:3** (plain text, no backticks/$/modal): [1] each touched-original md5 before==after + orchestrator md5 unchanged · [2] functions touched (per file) · [3] each fix + selftest FAIL-pre/PASS-post DATA · [4] **★AUTODETECT-2 pdfinfo fail-closed: show pdfinfo-absent → ERROR (not 1-page)** · [5] AUTODETECT-1: T-world bill → telephone (not card-matched) · [6] VOTE-1: dup date+amount → both voted · [7] final counts + no-regression + boundaries + promotion gap. Then HOLD (no Batch F until master §5 + CSO GO + the planned E→F restart). I (CSO) re-verify (pdfinfo fail-closed + telephone-routing + VOTE-1 both-voted + all-zero-reject + 3 originals + orch untouched) before reporting up. If ambiguous → STOP + ask surface:3.
ACK on surface:3, then begin.
