---
name: expensereceipt-extract
description: >
  [TLDR] Folder autodetect + receipt vision-OCR (store / date / amount / people / business-number) +
  bottom-handwriting read + adaptive 3→7 multi-read majority voting. Produces the raw per-receipt
  fields the rest of the expensereceipt suite consumes.
  [TRIGGERS] Invoked ONLY by the expensereceipt master at the extract stage; NOT user-invocable
  (disable-model-invocation: true).
  [METHODOLOGY] Default input raw-data/input/WKnn_2026/ (NFC-normalized autodetect: receipt vs
  카드승인내역 vs template); minimal preprocess (rotate + grayscale only — trust Vision); OCR schema
  extends wk-receipt-ocr with 사업자번호 / dinner-people / 맨밑필기; handwriting gallery few-shot chosen
  by store+weekday+time metadata key (not pixels); PORT aggregate_ocr_votes.py voting (identity key
  (date,amount), STRONG=ceil(0.8k), exit 0/2/1); N-read independence; no silent winner-pick. Body has detail.
disable-model-invocation: true
---

# expensereceipt-extract — Folder Autodetect · Vision OCR · Handwriting · 3→7 Voting

> **Invoked only by** the `expensereceipt` master at the extract stage (`disable-model-invocation: true`).
> **Status (M4 BUILT ✅ — deterministic parts; Batch-E ingest hardened)**: `scripts/autodetect.py` (folder/file-kind + G11 preprocess, 실측 23/23 — 14 base + 9 Batch-E) + `scripts/expensereceipt_vote.py` (verbatim-core PORT of `aggregate_ocr_votes`, 실측 17/17 — 14 base + 3 Batch-E, exit 0/2/1). **Vision OCR + bottom-handwriting reads are LLM HALTs specified below** (not code — `vision은 당신만`).
>
> **Batch-E extract hardening:**
> - **AUTODETECT-1** new `telephone_bill` file-kind (`_is_telephone_bill`: NFC tokens 청구내역/통신비/청구서/T world/SKT/KT/LG U+, Latin tokens boundary-safe) → routed to a `telephone_bills` bucket (TELEPHONE sector), NOT `receipts` — a carrier bill never enters the card consume-once match. Handles the owner `청구내역 … T world.pdf` now in input.
> - **AUTODETECT-2** `pdf_page_count`/`pdf_receipt_pages` via **`pdfinfo`** (D5 reuse — no new pypdf): one candidate per page (stable `<stem>#pN` id) + multipage flag/HALT. **★FAIL-CLOSED `PdfInfoUnavailable`: pdfinfo absent/error → ERROR/HALT, NEVER a 1-page assumption.** Runs on a /tmp copy (input immutable).
> - **AUTODETECT-3** `classify_file` branch order documented as load-bearing precedence (card_statement → template → card_slip → telephone_bill → receipt → other).
> - **VOTE-1** `_receipt_units` multiset key `(date, amount, occurrence_ordinal)` + ordinal-aware `synthesize` — two DISTINCT receipts sharing (date,amount) on one day are BOTH voted (not collapsed); the 14 vote-base selftests stay schema-additive-safe.

## Overview (WHY)

Garbage-in is the enemy (ANCHOR #2b): if the raw store/date/amount/people/business-number/handwriting are wrong, every downstream skill polishes a lie. This skill is the **accurate pixel→text reader + multi-read consensus gate** that makes the foundation trustworthy. It is the Research-phase gene of the suite.

## When to Use / Invocation

Invoked only by the `expensereceipt` master at the extract stage (two vision HALTs: OCR read, bottom-handwriting read). Not user-invocable.

## Methodology — *deterministic: `autodetect.py` + `expensereceipt_vote.py` (M4 BUILT); vision = LLM HALT spec below*

- **Folder autodetect** (NEW): scan `raw-data/input/WKnn_2026/` (Q1 default; `~/WKww_YYYY` optional alias), **NFC-normalize** every name (macOS NFD trap), classify file-kind: receipt image/PDF vs `카드승인내역*.xls(x)` (card statement, **spreadsheet not PDF**) vs `*T&E*.xlsx` template vs `매출전표` card-company slip. Split multi-receipt PDFs.
- **★KICC 매출전표 (replacement receipt)**: `sales_slip_candidates(manifest)` surfaces `매출전표` slips as replacement-receipt candidates (machine-broke → card-company slip = valid receipt). Each is OCR'd (`승인번호`, amount, card_last) and accepted only if its 승인번호+amount matches a card-statement row — the deterministic guard is in `-verify.check_card_match`.
- **Preprocess** (**G11**, minimal): simple rotation + grayscale only — **no Hough deskew / thermal pipeline**; trust Claude Vision skew/low-light reading.
- **Vision OCR**: PORT `wk-receipt-ocr` schema BASE + **extend** with `사업자번호`, dinner-level `people` (main-item count, options excluded), `맨밑필기` (bottom handwriting). N-read **independence contract** (each read from scratch).
- **Handwriting gallery few-shot** (**G10**): select similar samples by **store/weekday/time metadata key** (no CV2/numpy), inject into the vision prompt; never dump the full gallery.
- **Multi-read voting**: PORT `aggregate_ocr_votes.py` verbatim core — identity key `(date,amount)` (time excluded), `_vote` levels {unanimous/strong/unresolved}, STRONG=`ceil(0.8·k)`, MIN=3/MAX=7, exit `0`=consensus / `2`=need-more-reads (→VISION-MORE) / `1`=fail. **G3** card-`raw` keys probed best-effort+NFC. Voting is **not** a correctness oracle → `-verify` is the downstream defense; `unresolved` ⇒ escalation, never accept `chosen`.

### OCR read schema (the contract each independent vision read emits → `ocr-results-{i}.json`)

```json
{ "receipts": [
  { "date": "YYYY-MM-DD", "time": "HH:MM:SS", "amount": 0, "store": "<name>",
    "people": 1, "biz_no": "<10-digit, hyphenated as printed>",
    "handwriting": "<bottom-of-receipt text: 'dinner alone' | Korean name | null>",
    "hw_confidence": 0.0 } ] }
```
- **Voted** (placement/classification-critical): `amount`, `people`, `handwriting`. **Ancillary** (downstream-validated, not voted): `store` (fuzzy), `biz_no` (-merchant checksum + -verify). Identity key = `(date, amount)`, **time excluded** (verbatim PORT decision).
- A misread `amount` becomes a **phantom receipt** (existence-flagged → escalation), not a silent "correction" — amount integrity is additionally enforced by the card cross-match in `-verify`.

### Vision HALT contract (two re-entrant HALTs, exit-10 — `vision은 당신만`)

1. **OCR HALT**: the master runs the harness; on `exit 10 + "VISION-REQUIRED: OCR"`, the LLM reads each receipt (PDF/image) **independently** N times (no referencing prior reads — the N-read independence contract), emitting `ocr-results-{i}.json`. Re-invoke `expensereceipt_vote.py --dir <run> WKnn` → `0` consensus / `2` add 2 more reads (3→5→7) / `1` exhausted-escalate.
2. **Handwriting HALT**: for the bottom-handwriting field, the master injects gallery few-shot examples (from `-db` `gallery_query` by store/weekday/time metadata key, **G10**) into the prompt; the LLM reads the handwriting; low confidence or vote-disagreement → **escalation to the owner via master** (★ANCHOR #2b — no silent fill, no winner-pick).

> Sections are **not** assigned here — classification is `-classify` (M5). Extract produces only the flat raw `receipts` list.

## AI-Agent Automation

Vision OCR + handwriting = LLM (HALT to master). Folder autodetect, preprocess (G11 minimal), and voting = deterministic Python (`autodetect.py`, `expensereceipt_vote.py`). Unresolved consensus or low confidence → escalation → master → owner. The master trusts the vote script's **exit code**, not an LLM claim of success (anti-hallucination).

## Inputs / Outputs

- **Inputs**: `raw-data/input/WKnn_2026/` (read-only); handwriting gallery (from `-db`).
- **Outputs**: `research/.../ocr-results-{i}.json` (per read) → consensus `ocr-results.json` + `ocr-vote-audit.json` (consumed by `-verify` req#6). RETURNs raw fields to master; **does not write SOT**.

## Inherited DNA (Parent Genome)

> Inherits the complete AgenticWorkflow genome; purpose varies, genome identical. See `soul.md §0`.

**Constitutional Principles**:
1. **Quality Absolutism** — boundary-legibility digits get 3→7 reads; thermal Hangul read by semantic context; never trade accuracy for speed/token.
2. **Single-File SOT** — writes only its `ocr-results-*.json`; RETURNs to master; never writes `state.yaml`.
3. **Code Change Protocol** — PORT `aggregate_ocr_votes.py` (don't reinvent); new autodetect/preprocess minimized.

**Inherited Patterns**:
| DNA Component | Inherited Form (extract) |
|---|---|
| 3-Phase Structure | Research-phase gene (signal acquisition) |
| SOT Pattern | RETURNs raw fields; master writes the ledger |
| 4-Layer QA | L1 = consensus reached; feeds L1/P1 of `-verify` |
| P1 Hallucination Prevention | multi-read voting + `unresolved`→escalation, no silent winner-pick |
| P2 Expert Delegation | the OCR/voting specialist |
| Safety Hooks | input dir immutable; outputs fully reversible |
| Adversarial Review | consensus cross-checked by `-verify` (card match) |
| Decision Log | vote-audit JSON records consensus/dispersion |
| Context Preservation | handwriting self-learning gallery grows across runs |

**Domain-Specific Gene Expression**: P1 (anti-hallucination via voting) + Context Preservation (gallery) express strongest.

## References

- **Implementation**: `scripts/autodetect.py` (folder/file-kind + G11 preprocess + Batch-E telephone_bill/pdf_page_count; CLI `WKnn` / `--dir` / `--selftest`) + `scripts/expensereceipt_vote.py` (voting + VOTE-1 multiset key; CLI `--dir <run> WKnn` / `--selftest`). M4 BUILT + Batch-E — autodetect 실측 23/23, vote 실측 17/17.
- SPEC §1/§4 · plan §3.3 (**G11, G10, G3, Q1**) · reuse: `scripts/aggregate_ocr_votes.py` (verbatim-core PORT — `_vote`/existence-then-field/STRONG=ceil(0.8k)/exit 0-2-1), `.claude/skills/wk-receipt-ocr` (OCR schema base, independence contract), `scripts/build_store_db.py` `find_card_file` NFC rule (mirrored in autodetect). Gallery few-shot consumed from `-db` `gallery_query` (G10).
