# MASTER GO — Batch E (extract/merchant) — expensereceipt Option-A hardening

> Issued by: master (surface:1). To: CSO (ops executor, surface:3) → worker s2 (implementer).
> Status: **Batch D (place) §5 RATIFIED → Batch E AUTHORIZED on the COPY.**
> SOT: `HARDENING_CAMPAIGN.md` (round log) + `ROUND1_FIX_PLAN.md` §4 BATCH E (full item detail — read verbatim).

## 0. §5 ratification of Batch D (basis for this GO)
master fresh independent §5 Workflow `wc5r13qhq` = **RATIFY-GO** (mustFix 0). 4-way convergence (worker 30/0 incl M6 6 cases + CSO bidirectional + master-WF deep M6 + precedent). Master-WF confirmed READ-ONLY: M6 byte-integrity intact (template MD5 immutable across real placement, verbatim zip, [Content_Types] png preserved, rels↔blip, clean re-open, os.replace STRICTLY gated on physical_verify PASS — forced-fail→ESCALATE no output); dedup bidirectional (same-id×3→1, distinct→N, content-md5 media→1 rId, fresh cNvPr per anchor); orchestrator `5dad9088` byte-identical (Batch-F defer); place orig `527b96aa` untouched (copy `ddc6d1a4`); input immutable.

**Batch-D LOW residuals LOGGED (fail-CLOSED, NON-blocking — for merge-time / Batch-F):**
- LOW-1 (safe): place embeds PNG without adding a [Content_Types] png Default — safe because the real WK00 template already registers png; a no-pic template fails closed (ESCALATE before write). No action needed for WK23.
- ★LOW-2 (Batch-F caution): `build_placements` has a DORMANT over-dedup risk — for id-less / image-less receipts its dedup could key on store|amount and collapse two DISTINCT receipts. DORMANT because build_placements is invoked ONLY by selftest + planning docs, NOT any runtime path. **★When Batch F wires orchestration, ensure the runtime supplies stable physical-receipt ids + images so dedup keys on the id (never store|amount) — do NOT activate this dormant over-dedup path.**

## 1. INVIOLABLE PROTOCOL (unchanged — binding)
1. **Work on COPY only**: `_hardening/skills/expensereceipt-extract/scripts/` (autodetect.py, expensereceipt_vote.py) + `_hardening/skills/expensereceipt-merchant/scripts/` (expensereceipt_merchant.py). Originals `.claude/skills/expensereceipt-extract/` and `.claude/skills/expensereceipt-merchant/` BYTE-UNTOUCHED. **Worker captures the ORIGINAL md5 baseline of EACH touched file BEFORE editing**, re-asserts unchanged after.
2. **Input PRISTINE**: `raw-data/input/` read-only, manifest `7b70b33745f4` (158 files) assert before+after. extract/merchant must NOT write to raw-data/input. (NOTE: the owner T-world telecom bill `청구내역 인쇄하기 _ T world.pdf` is now in the input — AUTODETECT-1 must classify it correctly; it is READ-ONLY.)
3. **Det-reduction**: each fix = new Python fn in the copy + SKILL.md(copy) calls it.
4. **Non-vacuous selftest per fix**: HARDCODE the real failure case, FAIL pre-fix / PASS post-fix.
5. **Full green gate**: `/tmp/cso_sandbox_baseline.py` (isolated baseline + new selftests) all green; input PRISTINE assert; each touched-original md5 unchanged; **orchestrator.py `5dad9088` unchanged (Batch-F defer)** → CSO recheck → **report to surface:1 → master §5.** No advance on a red gate.
6. **Worker resumes each batch ONLY on explicit CSO GO after master §5.** Sequence: A,C,B,D(done) → **E** → F.

## 2. BATCH E SCOPE — autodetect.py / expensereceipt_vote.py / expensereceipt_merchant.py (orchestrator UNTOUCHED)
Per ROUND1_FIX_PLAN.md §4 BATCH E. **Master emphasis / binding constraints:**

- **AUTODETECT-1 (high, det):** new file-kind `telephone_bill` — NFC tokens (청구내역 / 통신비 / 청구서 / T world / SKT / KT / LG U+) → TELEPHONE sector, NOT a receipt. (Directly handles the owner T-world bill in input.) selftest: T-world bill → telephone (not receipts).
- **AUTODETECT-2 (high, det):** page_count via `pdfinfo` (D5 reuse pdftoppm/sips/pdfinfo, NO new pypdf/PyMuPDF) + per-page emit (stable page-ordinal id) + flag/HALT when page_count>1. **★Fail-closed: if pdfinfo absent → ERROR/HALT, NEVER silently assume 1 page.** selftest: multi-page PDF → count + flag; pdfinfo-absent → ERROR (fail-closed).
- **VOTE-1 (high, det):** multiset key (date, amount, occurrence_ordinal) stable order; vote PER OCCURRENCE (so two receipts with the same date+amount on one day are both voted, not collapsed). selftest: duplicate-amount same-day → both voted.
- **MERCHANT-1 (med, det):** fallback match_card normalizes dates (parse_date-equiv) + logs `_REUSED=False` honestly. selftest: date-format variant still matches.
- **MERCHANT-2 (med, det):** ONE owner of the consume-once join (verify imports merchant's join OR merchant aligns to verify's canceled-row + None-guard — pick one, document it). selftest: consume-once not double-counted.
- **AUTODETECT-3 (low, det):** precedence comment + dual-token selftest (ambiguous file → deterministic precedence).
- **MERCHANT-3 (low, det):** additive structural biz guard (reject all-zero biz_no) as a SEPARATE flag, producer back-compat (do not break the 14 vote / existing selftests).

## 3. DEFERRED to Batch F (do NOT touch in Batch E)
orchestrator.py stays byte-identical `5dad9088`. No orchestrator-contract change. (Batch F will wire: V6-WIRING orch-half, DB-1 orch call, DH-3 sales_slips threading, C1 --card fail-loud, plus the Batch-D LOW-2 dormant-over-dedup caution above.)

## 4. Required non-vacuous hardcoded cases for Batch E (minimum)
- T-world / 통신비 / 청구내역 file → telephone_bill kind → TELEPHONE sector (NOT receipts)
- multi-page PDF → page_count + flag/HALT
- pdfinfo binary absent → ERROR/HALT (fail-closed, never assume 1 page)
- duplicate date+amount same day → both occurrences voted (not collapsed)
- date-format variant → merchant match still works
- consume-once join → no double-count

## 5. Checkpoint
Worker implements on copy → non-vacuous selftests FAIL pre-fix / PASS post-fix → full sandbox baseline green → input PRISTINE assert (158/`7b70b33745f4`) + each touched-original md5 unchanged + orchestrator.py `5dad9088` unchanged → CSO recheck → **report to surface:1.** Master judges + §5. On convergence → **Batch F** (LAST; orchestrator-contract — and at the E→F boundary, the planned careful CSO new-pane restart). No merge to live until the HARD MERGE GATE (all batches green + final §5 + 10-fresh-prompt gate + **owner approval — denylist**).
