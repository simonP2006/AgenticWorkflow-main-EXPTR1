---
name: expensereceipt-classify
description: >
  [TLDR] 6-sector classification engine: deterministic triggers + Dinner store-name LLM-probability +
  STAFF/TRAVEL attendee-name selection. Routes each receipt to its Receipt-Sheet sector.
  [TRIGGERS] Invoked ONLY by the expensereceipt master at the classify stage; NOT user-invocable
  (disable-model-invocation: true).
  [METHODOLOGY] SPEC §2 priority rules: PARKING/TOLLS ("기간별 사용 내용") & TELEPHONE-LOCAL ("T world")
  deterministic; bottom-handwriting triggers Dinner / STAFF / TRAVEL; STAFF↔TRAVEL split by A999
  company-column (TERADYNE=STAFF / SAMSUNG EDS·HBM-PE=TRAVEL); STAFF "already 1 Dinner" = SAME-DATE;
  IMPORT classify_section.classify + dynamic read_name_database (no 1007 ceiling); OTHERS-LOCAL fallback;
  ambiguous ≥2-no-handwriting → escalation (master/human writes section-confirmed.json). Body has detail.
disable-model-invocation: true
---

# expensereceipt-classify — 6-Sector Rule Engine · Name Selection

> **Invoked only by** the `expensereceipt` master at the classify stage (`disable-model-invocation: true`).
> **Status (M5 BUILT ✅ · Batch-A HARDENED)**: implemented + 실측 PASS (35/35 — 22 base + 13 Batch-A hardening cases). Module: [`scripts/expensereceipt_classify.py`](scripts/expensereceipt_classify.py). Covers det triggers, handwriting→A999-company routing, G9 same-date STAFF, G5 escalation HALT, G2 dynamic name-DB (reads past row 1007). `_REUSED=True`. **★Awaiting master independent verify + the first `gemini §5` adversarial review.**
>
> **Batch-A hardening (C1–C7, H8–H9)** — deterministic reductions + escalation-over-guessing tightened (ANCHOR #2b):
> - **C1** `resolve_store_sector` — when the card-join misses, an EXACT-norm (NFC+casefold+collapse-whitespace) reverse index `{merchant_name → 사업자번호…}` resolves the store; a unique 사업자번호 yields its store-db sector, while a **miss or ambiguity (≥2) escalates** (never substring/contains, never a silent OTHERS-LOCAL).
> - **C2** `_is_parking_slip` — KICC/세외수입/현장/주차 municipal parking slips **escalate** (PARKING/TOLLS vs OTHERS-LOCAL), not a silent fallback.
> - **C3** `_is_toll` — Hi-pass toll trigger is **whitespace-insensitive** (strips all `\s`, tests prefix `기간별사용내`) and scans body/line-item fields, not just the title.
> - **C4** unread/zero headcount **escalates** — classify never silently assumes ≤1, never coerces (item-sum is **verify-V3's** job, not classify's).
> - **C5** `_safe_people` — headcount is safely coerced (`'2'`→2; non-numeric→None→escalate) before any numeric compare (no `str >= int` crash).
> - **C6** in the no-time branch only **DINNER auto-commits**; a no-time STAFF/TRAVEL store **escalates** for owner name selection.
> - **C7** `compute_rid` — stable, collision-resistant receipt id from immutable fields; `section-confirmed.json` is `{rid: SECTOR}`, a non-canonical sector is **rejected LOUD**, and a legacy `{confirmed:true}` flag is accepted via a documented shim+warning.
> - **H8** `_hhmm` — `re.search` + 오전/오후·AM/PM → 24h with range validation (`오후 6:30`→18:30; invalid→no-time, never a fabricated dinner).
> - **H9** `_norm_date` — every date is normalized via `build_store_db.parse_date` before the G9 same-date link and the run sort (`2026-06-01` ≡ `2026/06/01`).

## Overview (WHY)

Classification decides which sector each receipt lands in — and the STAFF↔TRAVEL distinction is intrinsically ambiguous for multi-attendee meals. This skill resolves what is **deterministically resolvable** and **escalates** what is not (no silent winner-pick, ANCHOR #2b). It is a Planning-phase gene.

## When to Use / Invocation

Invoked only by the `expensereceipt` master at the classify stage. Not user-invocable.

## Methodology — *implemented in `scripts/expensereceipt_classify.py` (M5 BUILT)*

> Function map: `classify_receipt` (the SPEC §2 decision tree below) · `company_sector` (TERADYNE→STAFF / SAMSUNG→TRAVEL) · `_lookup_names` + `name_candidates` (A999 name match + escalation candidates) · `_store_t1_sector` (IMPORT `classify_section.classify`, T1-only signal, label-robust) · `resolve_store_sector` (**C1** exact-norm 사업자번호 reverse index + escalate-on-miss) · `_is_parking_slip` (**C2** KICC/세외수입 slip) · `_is_toll` (**C3** whitespace-insensitive toll) · `_safe_people` (**C5** safe headcount coerce) · `_norm_date` (**H9** date canonicalize) · `compute_rid` + `_confirmed_sector` (**C7** stable id + canonical-sector validation/legacy shim) · `load_name_db` (G2 dynamic `read_name_database`) · `run` (date/time-ordered for G9; writes `section-predictions.json`; reads `section-confirmed.json`; exit 0/2). **Escalation is never silent** (ANCHOR #2b); the store-name Dinner probability (LLM) and STAFF/TRAVEL name selection (owner) are surfaced as escalations the master/owner resolve.


Priority order (SPEC §2):
1. **PARKING/TOLLS** ← receipt name "기간별 사용 내**역**" or "내**용**" [deterministic; M9 calibration: real Hi-pass statements print 내역, C3 `_TOLL_PREFIX` (whitespace-insensitive prefix `기간별사용내`) matches both 내역/내용 and any spacing variant].
2. **TELEPHONE-LOCAL** ← receipt name "T world" [deterministic].
3. **Bottom-handwriting trigger** (highest): "dinner alone"→Dinner · Teradyne Korean name→STAFF · SAMSUNG EDS/HBM-PE name→TRAVEL.
4. **No-handwriting rules**: Dinner (17:50+ & 1-person & solo-meal venue → store-name LLM-probability); **STAFF** ((a) **same-date** an existing Dinner + Dinner-condition receipt [**G9**] OR (b) ≥2-person → Teradyne name select) ; **TRAVEL** (≥2 → SAMSUNG EDS/HBM-PE name; ≥3 → + Teradyne name).
5. **OTHERS-LOCAL** ← fallback (NEW sector; cell-group inspected at M6).

- **STAFF↔TRAVEL key insight (G2)**: encoded by which **A999 company-column** the name sits in (TERADYNE=STAFF / SAMSUNG EDS·HBM-PE=TRAVEL). Use **dynamic** `read_name_database` only — **never** the hardcoded `range(999,1008)` 1007-ceiling.
- **IMPORT** `classify_section.classify` (3-tier T1 conf≥0.85 / headcount≥3→TRAVEL / T3 escalate).
- **People-count (DH-4 honesty)**: classify **CONSUMES** the per-receipt people/headcount field produced upstream (extract/vote); it does **NOT** itself count main-items or compute an item-sum. The `item-sum == card amount` cross-check belongs to **`-verify` (V3)**, not classify. A people/headcount that is **unread or zero escalates** (C4, ANCHOR #2b) — classify never silently assumes ≤1 and never coerces.
- **Escalation (G5)**: ambiguous ≥2-no-handwriting → predict to `section-predictions.json` + HALT; the **master/human writes `section-confirmed.json`** between runs; this skill never self-writes it.
- **Solo-lunch flag**: no-handwriting / 1-person / lunch stays **OTHERS-LOCAL** per SPEC; TRAVEL-rescue = SPEC extension (owner decides) — re-confirm at M5.

## AI-Agent Automation

Deterministic triggers + rule engine = Python. Dinner store-name probability = LLM. STAFF/TRAVEL name selection = human-via-master (DB candidate ranking → owner confirm). Escalation HALT on ambiguity.

## Inputs / Outputs

- **Inputs**: per-receipt fields + handwriting (from `-extract`), merchant key (from `-merchant`), store-learning DB + name-DB (from `-db` / `Receipt!A999:H1007`).
- **Outputs**: `section-predictions.json` + sector per receipt (RETURNed to master). **Does not write SOT or `section-confirmed.json`.**

## Inherited DNA (Parent Genome)

> Inherits the complete AgenticWorkflow genome; purpose varies, genome identical. See `soul.md §0`.

**Constitutional Principles**:
1. **Quality Absolutism** — resolve deterministically where possible; escalate where not; never guess a sector.
2. **Single-File SOT** — RETURNs predictions; master/human owns `section-confirmed.json`; master writes ledger.
3. **Code Change Protocol** — IMPORT `classify_section.classify`; rules re-parameterized to 6 sectors.

**Inherited Patterns**:
| DNA Component | Inherited Form (classify) |
|---|---|
| 3-Phase Structure | Planning-phase gene (routing) |
| SOT Pattern | predictions only; master writes confirmed sector |
| 4-Layer QA | feeds `-verify` req#7 (rule consistency) |
| P1 Hallucination Prevention | ambiguous → escalation, no silent winner-pick |
| P2 Expert Delegation | the classification specialist |
| Safety Hooks | read-only over DB/name-DB |
| Adversarial Review | section assignment cross-checked by `-verify` (store-observed sections) |
| Decision Log | name-selection decisions logged via master |
| Context Preservation | classification-learning DB grows (store→Dinner, store+weekday+time→names) |

**Domain-Specific Gene Expression**: P1 (escalation over guessing) + Human-AI boundary (owner decides ambiguous attendees) express strongest.

## References

- **Implementation**: `scripts/expensereceipt_classify.py` (M5 BUILT + Batch-A hardened + addendum + finalization, 실측 41/41 — 22 base + 13 hardening + 3 addendum + 3 finalization cases). CLI `--dir <run> --store-db <p> --template <p> --card <p>` / `--selftest`.
- SPEC §2 · plan §3.4 (**G9, G2, G5**, solo-lunch flag) · reuse: `scripts/classify_section.py` (IMPORT `classify` — T1 store signal), `scripts/classify_stage.py` (G5 escalation-HALT pattern PORTed), `scripts/write_excel.py` (IMPORT `read_name_database` — G2 dynamic), `scripts/build_store_db.py` (card join). Store-learning labels (short) ↔ SPEC sectors mapped via `-db` `_SECTOR_TO_LEARNING` + `_SHORT_TO_SPEC`.
