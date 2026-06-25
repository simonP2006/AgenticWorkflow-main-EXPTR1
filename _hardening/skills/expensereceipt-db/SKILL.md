---
name: expensereceipt-db
description: >
  [TLDR] Per-receipt ledger + handwriting self-learning gallery + classification-learning DB. The
  memory gene of the suite: the suite gets smarter as receipts accumulate.
  [TRIGGERS] Invoked ONLY by the expensereceipt master at the db stage; NOT user-invocable
  (disable-model-invocation: true).
  [METHODOLOGY] Per-receipt ledger {store,date,amount,people,handwriting}; roll-up to a store→sector
  aggregate (PORT build_store_db.build()); handwriting gallery = (crop ↔ owner-confirmed-text) pairs,
  few-shot samples selected by store/weekday/time METADATA key (not pixels, no CV2/numpy); growth via
  quarantine→snapshot→promote→rollback safe-append (no pollution until verify PASS); classification DB
  (store→Dinner, store+weekday+time→name candidates). Body has detail.
disable-model-invocation: true
---

# expensereceipt-db — Per-Receipt Ledger · Handwriting Gallery · Classification DB

> **Invoked only by** the `expensereceipt` master at the db stage (`disable-model-invocation: true`).
> **Status (M2 BUILT ✅ — Batch-B SOT-integrity hardened)**: implemented + 실측 PASS (43/43 — 21 base + 22 Batch-B cases). Module: [`scripts/expensereceipt_db.py`](scripts/expensereceipt_db.py). Self-test: `python3 scripts/expensereceipt_db.py --selftest`. Genuine reuse of `norm_store`/`parse_date` from the project `scripts/` (SOT single-source); `build()`/transaction-layer PORTed + adapted to ledger input.
>
> **Batch-B db hardening** (SOT integrity + crash-safety; db-internal only — DB-1 orchestrator CALL is Batch F):
> - **DB-1** `promote_week(week, verdict, verdict_week)` — FAIL-CLOSED gate: refuses unless `verdict=='PASS'` AND `verdict_week==week`. The orchestrator threads the real verify verdict in Batch F.
> - **DB-2** `startup_consistency_check`/`store_db_consistent` — invariant `store-db == rollup_from_ledger(PROMOTED)`; PROMOTED (provenance) is written BEFORE STORE_DB (derived), and a half-committed promote is detected + SELF-HEALED (rebuild from provenance) or fail-closed — never a silent half-commit.
> - **DB-3** — snapshot ONCE per logical promote (`store-db.pre-<week>.json`); a retry of an already-promoted week SHORT-CIRCUITS (no double snapshot of a polluted state).
> - **DB-4** — `configure` rejects `EXPR_DB_BASE == PROJECT_DIR/planning` (path-collision guard — never clobber the WK `planning/store-db.json`).
> - **DB-5** `_canon_sector` + `LAST_ROLLUP_UNKNOWN` — NFC + canonical-case sector normalize before the learning map; an unknown sector is warned/counted (NO silent drop).
> - **DB-6** `gallery_add` id = `max(G-####)+1` (collision-free after deletion). **DB-7** `_canon_amount` in `_content_sig` (int≡str dedup). **DB-8** `name_index_add` no longer snapshots the unpromoted store-db (store_sector only via `classifydb_rebuild`). **DB-9** unparseable date/time at ingest surfaced (`ingest_warnings`, not silent '?'). **DB-10** occurrence-aware confidence (shrink toward 0.5 when occ < `_MIN_CONF_OCC`; `raw_confidence` retained).

## Overview (WHY)

Memory is intelligence (기억은 지능의 일부다). This skill is the suite's long-term memory: it records every receipt, grows a handwriting gallery from owner-confirmed readings (honest in-context learning, not model retraining), and accumulates a classification DB so sector/name inference improves over time. It is the Context-Preservation gene and the data backbone the other sub-skills read.

## When to Use / Invocation

Invoked only by the `expensereceipt` master at the db stage (after a run's data is verified). Not user-invocable.

## Methodology — *implemented in `scripts/expensereceipt_db.py` (M2)*

> Function map: `ledger_add`/`ledger_read`/`ledger_week` (ledger; `_content_sig` w/ **DB-7** canonical amount) · `rollup`/`rollup_from_ledger` (PORT of `build()`/`finalize()`; **DB-5** `_canon_sector`+unknown-count, **DB-10** occ-aware confidence) · `gallery_add` (**DB-6** max+1 id)/`gallery_query` (G10 metadata-key few-shot) · `name_index_add` (**DB-8** no store-db snapshot, **DB-9** date validate)/`name_candidates`/`classifydb_rebuild` (classify-DB) · `quarantine_week`/`promote_week` (**DB-1** verdict gate, **DB-2** PROMOTED-first, **DB-3** snapshot-once)/`rollback` · `store_db_consistent`/`startup_consistency_check` (**DB-2** self-heal) · `configure(base)` (**DB-4** planning-collision reject) · CLI `--rollup/--quarantine/--promote[ --verdict PASS --verdict-week WK]/--rollback/--selftest`. All writes atomic (temp→`os.replace`). Namespaced under `planning/expensereceipt/` — never the WK `planning/store-db.json`.


- **Per-receipt ledger** (NEW finer schema): `{store, date, amount, people, handwriting}` per receipt — the upstream source the aggregate rolls up from. Written via the master (SOT discipline).
- **Roll-up to store aggregate** (PORT `build_store_db.build()`): `section_dist` Counter, `confidence = max/sum`, `dominant_section`, `typical = [min, median, max]` for headcount/amount/hour, `occurrences`, `source_weeks`.
- **Handwriting self-learning gallery** (**G10**): accumulate (handwriting-crop ↔ owner-confirmed-text) pairs; on a new read, select similar samples by **store/weekday/time metadata key** (no pixel similarity — no CV2/numpy) and inject as few-shot into `-extract`'s vision prompt; **never dump the full gallery** (context explosion). Grows by owner confirmation (human-in-loop, one loop).
- **Classification-learning DB**: store→Dinner probability; store+weekday+time→name candidates (STAFF/TRAVEL).
- **Safe-append (no pollution)**: PORT the `quarantine→snapshot→promote→rollback` transaction layer — a run's observations are quarantined until `-verify` PASSes, then promoted (snapshot first); rollback restores the last snapshot. Reused for both the ledger roll-up and the gallery.

## AI-Agent Automation

Fully deterministic Python. The gallery's "learning" is in-context few-shot accumulation (not AI retraining — explicitly a skill limitation, stated honestly). Growth gated by `-verify` PASS + owner confirmation.

## Inputs / Outputs

- **Inputs**: verified per-receipt data (from master, post-`-verify`), owner-confirmed handwriting text.
- **Outputs**: `planning/expensereceipt/ledger.json`, store-db aggregate, `gallery/` (handwriting pairs), `classify-db.json`. The master persists these; this skill prepares/returns them (SOT single-writer = master).

## Inherited DNA (Parent Genome)

> Inherits the complete AgenticWorkflow genome; purpose varies, genome identical. See `soul.md §0`.

**Constitutional Principles**:
1. **Quality Absolutism** — accumulate honestly; never claim AI retraining; few-shot grows real read accuracy.
2. **Single-File SOT** — prepares/returns DB updates; the master is the single writer; growth gated by verify PASS.
3. **Code Change Protocol** — PORT `build_store_db` aggregator + transaction layer; minimal NEW (per-receipt schema, gallery).

**Inherited Patterns**:
| DNA Component | Inherited Form (db) |
|---|---|
| 3-Phase Structure | spans all phases (the memory substrate) |
| SOT Pattern | per-receipt ledger; master single-writer |
| 4-Layer QA | growth gated by `-verify` PASS (no-pollution) |
| P1 Hallucination Prevention | quarantine until verified; confidence != evidence (check occurrences) |
| P2 Expert Delegation | the memory/learning specialist |
| Safety Hooks | quarantine→snapshot→rollback (no irreversible pollution) |
| Adversarial Review | promotion gated by the verify gate |
| Decision Log | classification-learning DB records observed sectors |
| Context Preservation | **this skill IS the Context-Preservation gene** (gallery + ledger across runs) |

**Domain-Specific Gene Expression**: Context Preservation + Memory express **strongest** — the suite's RLM/self-learning substrate.

## References

- **Implementation**: `scripts/expensereceipt_db.py` (M2 BUILT + Batch-B SOT-integrity hardened, 실측 43/43 — 21 base + 22 Batch-B cases).
- SPEC §3/§4 · plan §3.1 (**G10**) · reuse: `scripts/build_store_db.py` (PORT `build()`/`finalize` + `quarantine`/`promote`/`snapshot`/`rollback`; IMPORT `norm_store`), `scripts/extract_card_data.py` (IMPORT `parse_date`), `planning/store-db.json` (schema reference — NOT written; this suite uses `planning/expensereceipt/store-db.json`).
- **Outputs (namespaced)**: `planning/expensereceipt/{ledger.json, store-db.json, classify-db.json, gallery/gallery.json, store-db-quarantine/, store-db-snapshots/, store-db-promoted.json}`.
