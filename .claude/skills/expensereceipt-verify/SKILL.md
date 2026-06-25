---
name: expensereceipt-verify
description: >
  [TLDR] MANDATORY anti-hallucination gate (read-only, deterministic) — the ANCHOR #2a return-angle
  gate. Blocks bad data before placement and verifies physical integrity after.
  [TRIGGERS] Invoked ONLY by the expensereceipt master at the verify stage(s); NOT user-invocable
  (disable-model-invocation: true).
  [METHODOLOGY] 7 checks: biz-checksum · card (date,amount) cross-match · item-sum==card · amount≠0 ·
  handwriting-confidence · multi-read consensus (ocr-vote-audit.json) · rule consistency. Two entry
  points (G6): pre-placement LOGICAL + post-placement PHYSICAL (zip drawing count, twoCellAnchor
  preserved, no-repair open). PORT verify_week skeleton; IMPORT leaf checks + producer rules; canceled
  rows (취소여부) defensively excluded. Read-only enforced by CODE (JSON only). Body has detail.
disable-model-invocation: true
---

# expensereceipt-verify — Anti-Hallucination Gate (★ANCHOR #2a, read-only)

> **Invoked only by** the `expensereceipt` master at the verify stage(s) (`disable-model-invocation: true`).
> **Status (M7 BUILT ✅ — fail-closed hardened + Batch-C)**: implemented + 실측 PASS (88/88 — 7 checks each PASS+FAIL + 9 fail-closed injection cases (a)–(h) + N/A regression + **32 Batch-C verify-hardening cases**). Module: [`scripts/expensereceipt_verify.py`](scripts/expensereceipt_verify.py). read-only · deterministic · JSON-only (no workbook, no FAIL.xlsx). Producers IMPORTed in-process (`_REUSED` surfaced in the report). **★Fail-CLOSED**: an **ERROR** (a mandatory check that could not run — producer absent / check raised / required input absent) ⇒ verdict ≠ PASS, exit ≠ 0; only a deliberate **N/A-SKIP** (no line items, single-read by design) is clean — a gate that gates an irreversible place-mutation must STOP on an unrun check.
>
> **Batch-C verify hardening** (ANCHOR#2a fail-closed strengthened; verify-internal only — orchestrator wiring is Batch F):
> - **V6-WIRING/SCHEMA** `check_consensus_disk`+`load_vote_files` — derives consensus FROM DISK: dual-file read of `ocr-vote-audit.json`+`ocr-vote-report.json`, week-assert, reads≥`MIN_READS`, **multiread derived from the on-disk `ocr-results-*.json` count** (not a caller boolean). wrong-week/stale/reads<MIN/audit-absent-when-multiread ⇒ ERROR; INCONCLUSIVE report present ⇒ FAIL. Producer (vote) contract UNCHANGED — additive read.
> - **V2-NOCARD** `check_no_card` — a no-card receipt outside {PARKING/TOLLS, TELEPHONE-LOCAL} is SURFACED as escalation (warning severity), **never a silent pass and never a hard FAIL of legit cash/toll/telephone**.
> - **V2-AMOUNT** `_norm_amount`/`_is_refund` — canonical amount → int via producer `parse_amount` (str/float/refund), in pool + match.
> - **V1-AGREEMENT** `check_biz_agreement` — a card-MATCHED receipt's `biz_no` must equal the consumed card 사업자번호 (NFC) — catches checksum-valid-but-mismatched identity V1 cannot.
> - **V3-INERT** `v3_applicable` — V3 (item-sum) applicability **derived from data**; a vacuous SKIP is N/A, **NOT counted as a passed check**.
> - **V7** — replays `classify_receipt` with the SAME ordered `dinner_dates` + the confirmed map; escalated-then-confirmed ⇒ `assigned == confirmed`.
> - **V5** `check_handwriting_consensus` — keys off cross-read DISAGREEMENT (deterministic) + None→FAIL floor; does not trust a model `hw_confidence` scalar.
> - **VERIFY-FALLBACK-PARSEDATE** — `extract_card` import-fail ⇒ `parse_date`/`parse_amount`=None ⇒ date/amount checks ERROR (no naive re-impl).
> - **PHYSICAL-CHECKS** — `run_physical` asserts every expected `physical_verify` key present (missing ⇒ ERROR) + independently recomputes the pic-count delta.
> **★This skill is the mandatory anti-hallucination gate — never skippable (ANCHOR #2a). It is strictly read-only and deterministic, and IMPORTs producer rules (no re-implementation).**

## Overview (WHY)

Multi-read voting reduces *stochastic* error but a *systematic* misread (every read wrong the same way) yields a confident-wrong consensus. The final defense is **independent deterministic cross-check** — card matching, checksum, arithmetic. This gate is that defense. Code is deterministic; it does not hallucinate (코드는 거짓말하지 않는다). It is the dominant gene of the suite (L1/P1).

## When to Use / Invocation

Invoked only by the `expensereceipt` master, at **two** points (G6): **logical** (before place) and **physical** (after place). Not user-invocable.

## Methodology — *implemented in `scripts/expensereceipt_verify.py` (M7 BUILT)*

> Function map: `check_biz_checksum`(V1, IMPORT `validate_biz_no`; **producer-absent⇒ERROR**) · `check_biz_presence`(V1b, **warning** — escalate if biz_no absent on a card-matched non-toll/tel receipt) · `check_card_match`+`build_card_pool`+`is_canceled`(V2, consume-based reconcile · ★G1 canceled-defensive [cancel-named column OR explicit cancel-status value; key-absent⇒not-canceled] · ★G3 NFC raw keys) · `check_item_sum`(V3, NEW; None item⇒ERROR not 0-coerce; no items⇒N/A-SKIP) · `check_amount_nonzero`(V4) · `check_handwriting_confidence`(V5, NEW) · `check_consensus`(V6, ★G4 `ocr-vote-audit.json` not `compare()`; multiread-expected+absent/malformed⇒ERROR, genuine single-read⇒N/A-SKIP) · `check_rule_consistency`(V7, IMPORT `classify_receipt`; **classify-absent or store_db-None⇒ERROR**) · `run_logical`/`run_physical`(★G6 2-split; -place-absent⇒PHYSICAL ERROR) · `Result`/`_run`/`_verdict` (PORT verify_week — **★raise→ERROR (fail-closed)**; verdict PASS/exit 0 ONLY if no ERROR and no violation-FAIL). Report surfaces `_REUSED` + per-check kind (ran / n/a-skip / error). All producers IMPORTed in-process (Caveat — layout deps stripped); writes ONLY a JSON report.


**7 checks** (SPEC ANCHOR #2a) → existing coverage:
1. business-number checksum — IMPORT `validate_biz_no()` from `-merchant` (NEW producer).
2. card `(date,amount)` cross-match — PORT `verify_card_matching.reconcile` (consume-once; leftover card rows = FAIL). **★KICC 매출전표 replacement-receipt** (machine-broke → card-company slip = valid receipt, owner-confirmed): `check_card_match(receipts, pool, sales_slips)` — a 매출전표 consumes a still-unconsumed card row ONLY when its `승인번호` **and** amount match a statement row (② statement-승인번호 = source-of-truth; ① no double-consume). A slip with no matching 승인번호, or matching 승인번호 but different amount, is **REJECTED** (stray/tampered — fail-closed; the unique approval number blocks generalization).
3. item-sum == card amount — NEW. **★V3-INERT honesty: line items are NOT produced upstream this round** (classify is not wired to emit items = D1), so V3 is genuinely N/A and `v3_applicable(receipts)` derives this **from the data** — a vacuous SKIP is reported as N/A and is **NOT counted as a passed check** (the gate's effective coverage this round is the 6 applicable checks + V3-when-items-appear, not a hardcoded 7/7).
4. amount ≠ 0 — PORT `verify_toll_integrity` T-3, generalized to all sectors.
5. handwriting confidence — NEW.
6. multi-read consensus — **G4**: consume `ocr-vote-audit.json` (from `aggregate_ocr_votes`); **NOT** `verify_ocr_consistency.compare` (that is dual-read pairwise diff only).
7. rule consistency — IMPORT producer rules (mirrors `verify_week` C38 importing `build_store_db`).

**Two entry points (G6)**: (a) **LOGICAL** = checks 1–6 + rule consistency on raw data (no placed file) → run **before** place; (b) **PHYSICAL** = `_zip_drawing_counts` (`<pic>` count == receipt count, twoCellAnchor preserved, Excel no-repair open) → run **after** place. Master forces place only after LOGICAL PASS.

- **G1**: canceled rows — robustly detect the cancel column/value (`취소여부`='Y'/'취소', NFC); **key-absent ⇒ not-canceled**; exclude canceled from card cross-match (Q2).
- **G3**: card-`raw` keys best-effort + NFC.
- **Caveat**: re-wire `verify_week` leaf checks as **in-process IMPORT** (pure module-level fns), satisfy each leaf signature, strip hardcoded `OUTPUT_DIR`/`research`/`planning` layout deps.
- **Read-only (Q5)**: enforced by **code** — 0 file writes except a JSON report; **drop** `verify_card_matching`'s openpyxl `*_FAIL.xlsx` writer. Two-tier severity: violation=exit 1, warning=exit 0.

## AI-Agent Automation

Fully deterministic Python; no LLM. On FAIL → re-read flagged receipts only (max 2) → escalate to master/owner. Never silent-pass.

## Inputs / Outputs

- **Inputs (read-only)**: consensus OCR + `ocr-vote-audit.json` (from `-extract`), card pool, merchant checksum rule (from `-merchant`), classify rules (from `-classify`), placed xlsx (physical pass, from `-place`).
- **Outputs**: JSON verify report (logical + physical), exit 0/1. **Writes NO workbook, NO SOT** (read-only). Master records verdict in SOT.

## Inherited DNA (Parent Genome)

> Inherits the complete AgenticWorkflow genome; purpose varies, genome identical. See `soul.md §0`.

**Constitutional Principles**:
1. **Quality Absolutism** — the gate is mandatory and never skipped; a failing check stops the pipeline.
2. **Single-File SOT** — **read-only**; never writes SOT or workbook; master records the verdict.
3. **Code Change Protocol** — IMPORT producer rules (no re-implementation); PORT the gate-runner skeleton.

**Inherited Patterns**:
| DNA Component | Inherited Form (verify) |
|---|---|
| 3-Phase Structure | gate between Planning and Implementation (logical), and after (physical) |
| SOT Pattern | read-only; emits JSON report; master records verdict |
| 4-Layer QA | **this skill IS L1/P1** (semantic + deterministic gate) |
| P1 Hallucination Prevention | 7 deterministic checks — the dominant gene |
| P2 Expert Delegation | the verification specialist |
| Safety Hooks | read-only by code; protects the deliverable |
| Adversarial Review | independent cross-check of OCR consensus vs card truth |
| Decision Log | per-check PASS/FAIL ledger (JSON) |
| Context Preservation | verify verdict persisted in SOT by master |

**Domain-Specific Gene Expression**: P1 (anti-hallucination) + 4-Layer QA express **strongest** — this is the suite's dominant gene (the verify gate).

## References

- **Implementation**: `scripts/expensereceipt_verify.py` (M7 BUILT + fail-closed hardened + Batch-C, 실측 88/88 — 7 checks PASS+FAIL + 9 fail-closed injection cases + N/A regression + 32 Batch-C verify-hardening cases). `run_logical()` / `run_physical()` are the master entry points (G6 order: logical before place, physical after). **★The master MUST pass `store_db` (even `{}` at cold-start) and the real vote-audit, and producers must be importable — else the gate returns ERROR / exit≠0 and the master must NOT proceed.** CLI `--selftest`.
- SPEC ANCHOR #2a, §1 · plan §3.6 (**G6, G1, G4, G3, Q2, Q5, Caveat**) · reuse: PORT `verify_week.py` Result/verdict skeleton + `verify_card_matching.reconcile` consume pattern (re-wired in-process, layout deps stripped); IMPORT producers `expensereceipt_merchant.validate_biz_no`, `expensereceipt_classify.classify_receipt`, `expensereceipt_place.{zip_drawing_counts,physical_verify,row_cell_consistency}`, `extract_card_data.parse_date`.
