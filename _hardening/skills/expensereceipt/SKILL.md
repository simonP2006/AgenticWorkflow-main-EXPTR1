---
name: expensereceipt
description: >-
  [TLDR] Owner-private weekly expense-receipt settlement master. Reads a week's receipts from
  raw-data/input/WKnn_2026/ and autonomously orchestrates 6 expensereceipt-* sub-skills to OCR,
  validate merchants, classify into 6 sectors, anti-hallucination-verify, place onto the Receipt
  Sheet, and ledger — with a user-verifiable orchestration trace.
  [TRIGGERS] Korean: "경비 정산 해줘", "영수증 정산", "영수증 처리", "WK 경비 정산"; English:
  "expense settlement", "process receipts", "settle the receipts". This master is model-invocable;
  the 6 sub-skills set disable-model-invocation:true and run only via this master.
  [METHODOLOGY] The orchestrator wires a DETERMINISTIC fail-closed gate over the master-extracted run
  data: G12 escalation-resolve → owner-HALT-if-ambiguous → verify-LOGICAL → place → verify-PHYSICAL →
  verdict-gated db-settle, emitting an orchestration trace; verify/place/db are imported in-process.
  OCR/handwriting/name-selection are the master Claude's LLM steps (not driven by this code).
  Full detail in body + references/authoring-spec.md.
---

# expensereceipt — Expense-Receipt Settlement (대표 스킬 / Master)

> Owner-private, self-learning expense-receipt settlement suite. **This is the only skill the user interacts with.**
> Build contract: [`references/authoring-spec.md`](references/authoring-spec.md). Design SOT: `EXPENSERECEIPT-SKILL-DESIGN-SPEC.md` (LOCKED). Build plan + binding guardrails: `EXPR-MILESTONE0-BUILD-PLAN.md`.
> **Status (M8 BUILT ✅ — Batch-F end-to-end wired)**: orchestrator implemented + 실측 PASS (37/37 — 27 base + 10 Batch-F wiring, **non-vacuous fail-closed**). Module: [`scripts/expensereceipt_orchestrator.py`](scripts/expensereceipt_orchestrator.py). Enforces the M7 audit contract: always supplies `store_db`+`name_db`+`vote_audit`+`card_records` to verify; consumes the verdict **fail-CLOSED** (ERROR or violation-FAIL ⇒ place NEVER happens — a place-spy proves no-place-on-not-clean); G6 2-split (logical→place→physical); G12 auto-confirm; G5 master-writes `section-confirmed.json`; orchestration trace. **★Owner-control (§6-b)**: an unresolved owner-escalation (genuinely-ambiguous sector) **HALTs the run — place is HELD, nothing placed** — until the owner confirms and re-runs (no silent best-guess placement; the `owner-escalation:HALT` trace label is truthful). OCR/handwriting remain the master Claude's LLM steps.
>
> **Batch-F end-to-end wiring** (the deterministic gate, verify/place/db imported in-process):
> - **V6-WIRING** — `gate_and_place` threads `run_dir`/`expected_week` into `run_logical` so verify binds the vote-audit FROM DISK (wrong-week → ERROR → HALT).
> - **DB-1** — after physical PASS, a verdict-GATED db transaction (`_real_db_settle` → quarantine → `promote_week(verdict='PASS')`); a FAIL/ERROR verdict HALTs first → **NO promote** (fail-closed end-to-end).
> - **DH-3** — `sales_slips` threaded into verify so the KICC/롯데 매출전표 path settles (consumed, not a false V2-FAIL).
> - **C1 (classify co-land)** — classify ESCALATES fail-loud when `card_pool` is None (card statement missing) — never silent-OTHERS, never a crash.
> - **DR-5** — `_dinner_confidence` (G12) uses the shared `norm_store` whitespace-collapsed key.
> - **LOW-2 (carry-forward)** — runtime supplies stable physical-receipt ids so `build_placements` dedups by ID; two distinct same-day same-amount receipts are BOTH placed (the dormant store|amount over-dedup stays inactive).

## Overview (WHY)

The master is the **orchestration node** of the settlement pipeline. It receives the owner's command and coordinates the specialist sub-skills in dependency order (extract → merchant → classify → verify-logical → place → verify-physical → db). The deterministic back half — verify-logical → place → verify-physical → db-settle — is wired in `orchestrator.py` (verify/place/db imported in-process); the front half (OCR/handwriting extract, merchant, classify) runs as the master Claude's LLM/sub-skill steps that produce the `run` data the gate consumes. Per 절대 기준 1 it produces the highest-quality settlement regardless of effort or token cost. It is the **parent organism's child**: it inherits the full AgenticWorkflow genome and expresses it in the expense-settlement domain (soul.md §0).

## When to Use / Invocation

**User triggers** (model-invocable): see frontmatter `[TRIGGERS]` — any request to settle/process a week's expense receipts. The user **never** calls a sub-skill directly; the 6 `expensereceipt-*` sub-skills all set `disable-model-invocation: true` and are invoked only by this master.

## Methodology (HOW the master runs a command) — *implemented in `scripts/expensereceipt_orchestrator.py` (M8 BUILT)*

> Function map: `gate_and_place` (★the fail-closed M7-contract core — LOGICAL verify before place; ERROR/violation-FAIL ⇒ HALT, place not attempted; place→PHYSICAL re-verify → ★Batch-F verdict-gated db-settle) · `_real_db_settle` (★DB-1 verdict-gated quarantine→promote) · `decide_escalations` (★G12: ≥0.95 Dinner-venue auto-confirm with rationale, ambiguous→owner) · `_dinner_confidence`/`_store_key` (★DR-5 shared norm_store key) · `write_section_confirmed` (★G5 master/human write) · `orchestrate` (trace + escalation resolution + gate) · `_nfc` (G13). Verify/place/db callables are dependency-injected so the selftest proves no-place/no-promote-on-not-clean via place/db spies (non-vacuous; happy-green ≠ trust). **verify/place/db are imported in-process** and consumed by return value (not a CLI call); OCR/handwriting are the master Claude's LLM steps (not driven by this code).

The actual run flow (`orchestrate`):
- **G12 escalation-resolve** (`decide_escalations`) → if any genuinely-ambiguous owner-escalation remains ⇒ **HALT, place HELD** (owner confirms + re-runs); else proceed to the gate.
- **G6 fail-closed gate** (`gate_and_place`): verify-LOGICAL (★Batch-F binds the vote-audit from disk via `run_dir`; threads `sales_slips` for the 매출전표 path) — a clean PASS ⇒ `place` mutates the output Excel ⇒ post-place verify-PHYSICAL ⇒ ★Batch-F verdict-gated **db-settle** (promote only on a clean overall verdict). Any ERROR/violation-FAIL ⇒ HALT (place NOT attempted, NO promote).
- **Orchestration trace** via `emit()` (decision log, written with the result).
- **G5**: the master/human writes `section-confirmed.json` between runs (sub-skills never self-write it); re-run resumes.

## AI-Agent Automation

The deterministic back half (verify/place/db) is imported in-process and consumed by **return value** — the verify gate returns a structured verdict the master trusts deterministically (anti-hallucination — code, not an LLM claim). OCR/handwriting are the master Claude's LLM steps that produce the run data. Owner judgments (name-selection, handwriting-confirm) are surfaced; during the build phase the **master** stands in for the owner (delegated autopilot), but denylist items stop and escalate.

## Inputs / Outputs

- **Input**: `raw-data/input/WKnn_2026/` (Q1 decision — owner-confirmed; receipts + `카드승인내역*.xls(x)` + template). Read-only / immutable.
- **Output**: `raw-data/output/simon_park_T&E_WKnn_2026.xlsx` (placed workbook) + master-owned SOT `planning/expensereceipt/state.yaml` + ledger/gallery/classify-db (via `-db`).
- **SOT (writes — sole writer)**: `run`, `receipts[]`, `verify.{logical,physical}`, `orchestration_trace`. Schema: authoring-spec §G.

## Inherited DNA (Parent Genome)

> This skill inherits the complete genome of AgenticWorkflow. Purpose varies by skill; the genome is identical. See `soul.md §0`.

**Constitutional Principles** (contextualized):
1. **Quality Absolutism** — the only criterion is settlement accuracy; ignore speed/token; add verification rounds (3→7 voting, 2-split verify).
2. **Single-File SOT** — this master is the **sole SOT writer**; the 6 sub-skills RETURN results; `-verify` is read-only.
3. **Code Change Protocol** — intent → ripple → design before touching any script; reused EXPTR1 scripts are IMPORT/PORT (originals unmodified).

**Inherited Patterns**:
| DNA Component | Inherited Form (master) |
|---|---|
| 3-Phase Structure | Research(extract) → Planning(classify/verify-logical) → Implementation(place/verify-physical/db) |
| SOT Pattern | per-receipt ledger + `state.yaml`, single writer = master |
| 4-Layer QA | L0 Anti-Skip (produces-existence) → L1 Verification → L1.5 pACS → L2 Adversarial Review (verify gate) |
| P1 Hallucination Prevention | in-process producer import + deterministic `-verify` gate (return-value verdict, fail-closed) |
| P2 Expert Delegation | 6 specialized sub-skills, dependency-ordered |
| Safety Hooks | `block_destructive_commands.py`; denylist HALT (git/irreversible/external) |
| Adversarial Review | `@reviewer`/`@fact-checker` + gemini §5 on high-risk gates |
| Decision Log | `autopilot-logs/` (build-phase auto-approvals) |
| Context Preservation | orchestration trace `_flush` + ledger/gallery across runs |

**Domain-Specific Gene Expression**: orchestration + SOT-single-writer + the 4-layer verify gate express strongest; the master is the Management/Decisions node of the pipeline.

## References

- `references/authoring-spec.md` (build contract) · `EXPENSERECEIPT-SKILL-DESIGN-SPEC.md` (LOCKED SPEC) · `EXPR-MILESTONE0-BUILD-PLAN.md` (plan + §11 guardrails)
- **Implementation**: `scripts/expensereceipt_orchestrator.py` (M8 BUILT + Batch-F wired, 실측 37/37 non-vacuous fail-closed — incl. owner-escalation HALT place-HELD, V6 disk wrong-week→ERROR, DB-1 verify-FAIL→no-promote, DH-3 KICC settle). `orchestrate(run)` / `gate_and_place(run)` are the entry points; verify/place/db callables are dependency-injected for non-vacuous testing.
- Reuse: the verify/place/db **producers are IMPORTed in-process** (`expensereceipt_verify.run_logical/run_physical`, `expensereceipt_place.place`, `expensereceipt_db.promote_week`); `.claude/commands/wk.md` is a related master-driver analog. (The emit() trace is the decision log; the orchestrator is a direct in-process gate that consumes each producer's return value.)
