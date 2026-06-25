---
name: expensereceipt-merchant
description: >
  [TLDR] NTS 10-digit business-registration-number checksum validation + merchant-key derivation +
  store-name normalization. The accuracy-upgrade gene the existing EXPTR1 pipeline lacks.
  [TRIGGERS] Invoked ONLY by the expensereceipt master at the merchant stage; NOT user-invocable
  (disable-model-invocation: true).
  [METHODOLOGY] NEW NTS checksum (weights [1,3,7,1,3,7,5,1,3]; 9th digit ×5 then take its tens digit;
  (10 − sum%10) % 10 == 10th digit; strip non-digits first); IMPORT _biz_no / norm_store / match_card /
  receipt_key from build_store_db (extraction + consume-based (date,amount) join + name fallback);
  card-raw keys probed best-effort + NFC (사업자번호 ↔ 사업자등록번호). Exposes validate_biz_no() for
  expensereceipt-verify to IMPORT (producer-rule pattern). Body has detail.
disable-model-invocation: true
---

# expensereceipt-merchant — NTS Checksum · Merchant Key · Store Normalization

> **Invoked only by** the `expensereceipt` master at the merchant stage (`disable-model-invocation: true`).
> **Status (M3 BUILT ✅ — Batch-E ingest hardened)**: implemented + 실측 PASS (22/22 — 13 base + 9 Batch-E). Module: [`scripts/expensereceipt_merchant.py`](scripts/expensereceipt_merchant.py). `validate_biz_no()` = standard NTS checksum, **empirically 15/15** real business numbers VALID / 15/15 corrupted INVALID (`--audit-storedb` mirrors master's cross-check). Genuine reuse (`_REUSED=True`).
>
> **Batch-E merchant hardening:**
> - **MERCHANT-1** `_fallback_match_card` + `_fallback_parse_date` — the DEGRADED (import-fail) join now date-normalizes (NFC+strip+'/'→'-'+'.'→'-'), byte-equivalent to the imported producer (slash-vs-dash dates match); a `_REUSED=False` warning is logged honestly when degraded.
> - **MERCHANT-2** `consume_match_card` — the SINGLE canonical consume-once (date,amount) join (None-amount guard mirrors verify, fail-closed); `merchant_for_receipt` uses it; `-verify` IMPORTs it at Batch F (verify NOT edited in Batch E — single-ownership finalized at F wiring).
> - **MERCHANT-3** `is_structurally_valid_biz_no` — ADDITIVE structural guard rejecting all-zero `0000000000` (which actually PASSES the NTS checksum) and all-same-digit; `validate_biz_no` (the producer `-verify` imports) stays back-compat UNCHANGED.

## Overview (WHY)

The existing EXPTR1 pipeline only **extracts** the business number; it never validates it. This skill adds the **NTS 10-digit checksum** — the SPEC-flagged "최대 정확도 업그레이드" — and derives the canonical merchant key that `-classify`, `-db`, and `-verify` all agree on. It is a pure deterministic gene: code, not LLM (코드는 거짓말하지 않는다).

## When to Use / Invocation

Invoked only by the `expensereceipt` master at the merchant stage. Not user-invocable.

## Methodology — *implemented in `scripts/expensereceipt_merchant.py` (M3)*

- **NEW NTS checksum** `validate_biz_no()` (the one major net-new algorithm; the ★producer rule `-verify` IMPORTs): for a 10-digit number `d1…d10` (d10 = check digit), weights **`[1,3,7,1,3,7,1,3,5]`** over `d1…d9`; add the **tens digit of `d9×5`** (i.e. `(d9*5)//10`); `check = (10 − (sum % 10)) % 10`; valid iff `check == d10`. **Strip all non-digits first** (card data is hyphenated, e.g. `220-81-15770`).
  - **★Correction (reported to master)**: the M3 brief's literal weight array `[1,3,7,1,3,7,5,1,3]` validates only **1/15** real numbers; the master's own PROSE ("9th digit ×5, take tens digit") + the real-number oracle confirm the **standard** array above (weight at position 9 = 5) — **15/15** real numbers PASS. The literal array was a transcription transposition.
- **Merchant key** (IMPORT `receipt_key` from `build_store_db`): biz-number primary (when the consume-based `(date,amount)` card join succeeds and a biz-no exists), else `name:<norm_store>` fallback.
- **Store-name normalization** (IMPORT `norm_store`): NFC + lower + whitespace-collapse.
- **G3**: probe card-`raw` keys best-effort + NFC (`사업자번호` ↔ `사업자등록번호`); no hardcoded key access.
- **Producer rule**: expose `validate_biz_no()` so `-verify` IMPORTs it (no re-implementation — the verify gate imports producer rules).

## AI-Agent Automation

Fully deterministic Python; no LLM. Returns `{merchant_key, biz_no, biz_no_valid}` per receipt to the master.

## Inputs / Outputs

- **Inputs**: per-receipt raw fields (from `-extract`); card pool (`extract_card_data` records, biz-no at `raw['사업자번호']`).
- **Outputs**: merchant key + checksum verdict per receipt (RETURNed to master); `validate_biz_no()` importable by `-verify`. **Does not write SOT.**

## Inherited DNA (Parent Genome)

> Inherits the complete AgenticWorkflow genome; purpose varies, genome identical. See `soul.md §0`.

**Constitutional Principles**:
1. **Quality Absolutism** — validate, don't just extract; the checksum is an accuracy upgrade with no speed excuse.
2. **Single-File SOT** — RETURNs the key/verdict; master writes the ledger.
3. **Code Change Protocol** — IMPORT existing extractors; the only NEW code is the checksum (intent→impact→design done).

**Inherited Patterns**:
| DNA Component | Inherited Form (merchant) |
|---|---|
| 3-Phase Structure | Planning-phase gene (identity resolution) |
| SOT Pattern | RETURNs merchant key; master writes ledger |
| 4-Layer QA | feeds `-verify` req#1 (checksum) |
| P1 Hallucination Prevention | deterministic checksum — code, not AI judgment |
| P2 Expert Delegation | the merchant-identity specialist |
| Safety Hooks | read-only over card/raw data |
| Adversarial Review | checksum verdict re-checked by `-verify` (imports validate_biz_no) |
| Decision Log | invalid-checksum events surfaced to master |
| Context Preservation | merchant key feeds the store-learning DB |

**Domain-Specific Gene Expression**: P1 (deterministic validation) + CCP (minimal NEW code) express strongest.

## References

- **Implementation**: `scripts/expensereceipt_merchant.py` (M3 BUILT + Batch-E, 실측 22/22). Exposes `validate_biz_no()` (producer rule for M7 `-verify`), `is_structurally_valid_biz_no()` (MERCHANT-3 structural guard), `consume_match_card()` (MERCHANT-2 canonical join), `merchant_for_receipt()`, `normalize_biz_no()`. CLI `--validate / --audit-storedb / --selftest`.
- SPEC §1 (merchant) · plan §3.2 (**G3**) · reuse: `scripts/build_store_db.py` (IMPORT `_biz_no`/`norm_store`/`match_card`/`_merchant_name`/`_category`), `scripts/classify_section.py` (IMPORT `receipt_key` — note: it lives here, not in build_store_db), `scripts/extract_card_data.py` (card raw schema). Optional external: `k-skill:nts-business-registration` (lookup, not checksum).
