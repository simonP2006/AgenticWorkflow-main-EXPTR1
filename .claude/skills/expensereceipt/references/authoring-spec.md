# expensereceipt — Suite Authoring Spec (build contract)

> The contract every skill in this suite obeys. Read together with `EXPENSERECEIPT-SKILL-DESIGN-SPEC.md` (LOCKED SOT) and `EXPR-MILESTONE0-BUILD-PLAN.md` (build plan + §11 binding guardrails).
> Applies to the master (`expensereceipt`) and all 6 sub-skills.
> Language: framework docs = Korean OK; **runtime execution + script code = English** (절대 기준 1 — AI performance). Final deliverables = English + Korean pair where applicable.

---

## A. The skill suite (locked)

**Representative (master) skill — the ONLY skill the user talks to:**
- `expensereceipt` — model-invocable; orchestration + orchestration-trace + master-owned SOT single-writer + owner interaction (name-selection / handwriting-confirm / escalation).

**Sub-skills (6) — invoked only by the master, never by the user directly:**
| # | Name | Responsibility (SPEC §1) | Engine |
|---|------|--------------------------|--------|
| 1 | `expensereceipt-extract`  | folder autodetect / split / preprocess + vision OCR (store/date/amount/**people**/**business-number**) + **bottom-handwriting** read (gallery few-shot) + multi-read 3→7 voting | LLM+det |
| 2 | `expensereceipt-merchant` | NTS 10-digit business-number checksum (**NEW**) + merchant key + store-name normalization | det |
| 3 | `expensereceipt-classify` | 6-sector rule engine + Dinner LLM-probability + STAFF/TRAVEL name selection | det+LLM+human |
| 4 | `expensereceipt-verify`   | ★MANDATORY anti-hallucination gate (ANCHOR #2a): checksum · card cross-match · item-sum==card · amount≠0 · handwriting-confidence · multi-read consensus · rule consistency. read-only · deterministic · IMPORT producer rules | det |
| 5 | `expensereceipt-place`    | Receipt Sheet placement: 3-per-row per sector within the template pre-sized sector bands; true overflow ESCALATE (insert-row = formula-aware shift NOT implemented / fail-loud, G7). **Surgical direct-zip, openpyxl FORBIDDEN, twoCellAnchor** | det |
| 6 | `expensereceipt-db`       | per-receipt ledger + handwriting self-learning gallery + classification-learning DB | det |

---

## B. Absolute criteria (inherited from AgenticWorkflow — contextualize, never drop)

1. **절대 기준 1 — Final-output quality is supreme.** Ignore speed, token cost, workload, length limits. The only criterion is the **accuracy of the expense settlement**. Add verification rounds (e.g. 3→7 multi-read voting) to raise quality.
2. **절대 기준 2 — Single-file SOT + hierarchical memory.** All shared run state lives in ONE SOT file written **only by the master**. The 6 sub-skills RETURN results to the master; they never concurrently write the SOT. `expensereceipt-verify` is strictly **read-only**. (Independent per-receipt output files are fine; the SOT is the single write point.)
3. **절대 기준 3 — Code Change Protocol.** Before writing/modifying any script: Step 1 intent → Step 2 ripple-effect analysis → Step 3 change design, proportional to change size. Reused EXPTR1 scripts are IMPORT/PORT(copy) — **originals are not modified** without `.bak` + master approval.
4. Priority on conflict: **절대 기준 1 > (절대 기준 2, 절대 기준 3).** If 할루시네이션 방지 (ANCHOR #2) is threatened, halt 1/3 execution and report to master.

These are restated, domain-contextualized, inside every skill's `## Inherited DNA (Parent Genome)` section (§H).

---

## C. Design criteria (this suite MUST satisfy all)

1. Multiple skills → one **representative** + 6 **sub-skills**. ✔ (1 + 6)
2. The user talks **only to the representative** (`expensereceipt`).
3. On an expense-settlement command, the representative **autonomously** drives the sub-skills.
4. **No silent guessing (ANCHOR #2b)**: store/date/amount/people/biz-number/handwriting are never filled by assumption. Low confidence ⇒ HALT/escalation to the master (who relays to the owner), never silent winner-pick.
5. Every **sub-skill** sets `disable-model-invocation: true` in frontmatter (project-scope stability + lower LLM load). The **master must NOT** set this (it must be model-invocable so the user's request triggers it).
6. **3-Layer Description Template** (§D), **reconciled to ≤ 1024 characters** (Claude's hard cap).
7. **Sub-skill naming**: each sub-skill name begins with the full master name `expensereceipt-` as prefix; `name:` == folder name exactly.
8. **Orchestration Trace** is mandatory in the master's output (§E).
9. Skill bodies live in `.claude/skills/<name>/` (project-scope, EXPTR1-only). User-scope symlink + discovery re-validated at M10 (rename-8단계).

---

## D. 3-Layer Description Template (frontmatter `description:`) — **≤ 1024 chars**

Every `SKILL.md` `description` follows three labelled inline layers in ONE string:

```
[TLDR] <1–2 sentences: what this skill is and does, plain terms>
[TRIGGERS] <MASTER: the Korean/English user phrases that invoke it, e.g. "경비 정산 해줘",
  "영수증 정산", "process receipts" | SUB-SKILL: "invoked ONLY by the expensereceipt master at
  stage X; NOT user-invocable" (paired with disable-model-invocation: true)>
[METHODOLOGY] <ONE-LINE pointer: the concrete techniques/fields it covers + "full detail in body
  / references". Compressed to honor the 1024-char cap — the full methodology lives in the BODY.>
```

**Reconcile rule (critical, directive §1)**: the foresight ~500-token target exceeds Claude's **1024-character** hard cap. Keep `[TLDR]` + `[TRIGGERS]` full; compress `[METHODOLOGY]` to a one-line pointer; move full methodology into the SKILL.md `## Methodology` body. Proven in-repo: `wk-receipt-ocr` description ≈ 420 chars. Target ≤ ~950 chars to leave margin.

- Master description **must list user trigger phrases** (model-invocable).
- Sub-skill descriptions **must state "invoked only by the expensereceipt master; not user-invocable"** + `disable-model-invocation: true`.
- Block scalar `description: >-` (master) or `>` (subs) is fine, but the flattened length still counts toward 1024.

---

## E. Orchestration Trace (master output — mandatory, SPEC §1)

When the master responds to an expense-settlement command, its output MUST contain these clearly separated sections (so the orchestration is **user-verifiable**; inline simulation alone is forbidden):

1. **`## 🧭 Orchestration Trace`** — (a) the master's activation + auto-classification cycle (how it parsed the command, which stage applies); (b) an ordered table of every sub-skill invoked: order #, stage, sub-skill, exit-code/HALT, what it produced, why. Mechanically generated from the harness `emit()`/`_flush()` event stream (PORT of `run_week.py`).
2. **`## 📦 Sub-skill Outputs`** — each sub-skill's product in its OWN labelled subsection (`### Output — expensereceipt-<x>`). Never merge them.
3. **`## 🧩 Master Synthesis`** — the master's integrated synthesis (final placed workbook, verify verdict, ledger/gallery updates, decisions).

The trace proves the sub-skills were actually invoked (visibility), not simulated.

---

## F. Required SKILL.md structure (all 7 skills)

```
---
name: <exact folder name>
description: <3-Layer, ≤1024 chars — §D>
disable-model-invocation: true      # SUB-SKILLS ONLY; OMIT for the master
---

# <Human Title>

## Overview            (WHY — purpose, where it sits in the pipeline)
## When to Use / Invocation
   - master: user trigger phrases + the classification it performs
   - sub-skill: "Invoked only by the expensereceipt master at stage X. disable-model-invocation."
## Methodology         (WHAT/HOW — the concrete techniques; cite SPEC §, plan §, reuse asset)
## AI-Agent Automation (which steps are det vs LLM vs human-via-master; how invoked)
## Inputs / Outputs    (data contract with the master + SOT fields it reads / writes-via-master)
## Inherited DNA (Parent Genome)   (§H — the genome, contextualized to this skill)
## References          (cross-links: SPEC, build plan, reuse assets)
```

- `name:` MUST equal the folder name exactly (frontmatter ↔ folder).
- Keep methodology faithful to the LOCKED SPEC + build plan; do not invent.
- `-verify` body adds the "read-only / deterministic / IMPORT producer rules" note; `-place` body adds the "openpyxl FORBIDDEN / twoCellAnchor / surgical direct-zip" note.

---

## G. SOT schema (master-owned — `planning/expensereceipt/state.yaml`)

```yaml
suite: expensereceipt
parent_genome:
  source: "AgenticWorkflow"
  version: "<build date YYYY-MM-DD>"
  inherited_dna: [absolute-criteria, sot-pattern, 3-phase-structure, 4-layer-qa,
                  p1-hallucination-prevention, safety-hooks, adversarial-review,
                  decision-log, context-preservation]
run:
  week: "WKnn_2026"                 # input folder under raw-data/input/ (Q1 decision)
  input_dir: "raw-data/input/WKnn_2026/"
  output_xlsx: "raw-data/output/simon_park_T&E_WKnn_2026.xlsx"
  current_stage: "<extract|merchant|classify|verify-logical|place|verify-physical|db>"
receipts:                            # per-receipt ledger (written only by master, from sub-skill output)
  - id: R-001
    store: "<name>"; date: "YYYY-MM-DD"; amount: 0; people: 0
    biz_no: "<10-digit>"; biz_no_valid: true
    handwriting: "<dinner alone | name | null>"; hw_confidence: 0-1
    merchant_key: "<biz_no | name:...>"
    sector: "<PARKING/TOLLS|TELEPHONE-LOCAL|Dinner|STAFF MEETING|TRAVEL|OTHERS-LOCAL>"
    card_match: "<MATCHED|NO_CARD>"
verify:
  logical: { verdict: "<PASS|FAIL>", checks: {} }   # pre-placement (G6)
  physical: { verdict: "<PASS|FAIL>", checks: {} }  # post-placement (G6)
orchestration_trace: []              # SPEC §1 audit trail
```

The handwriting gallery + classification-learning DB are separate persistent files (`gallery/`, `classify-db.json`) grown via the `quarantine→snapshot→promote→rollback` safe-append pattern (PORT of `build_store_db.py`); they are not the run SOT.

---

## H. `## Inherited DNA (Parent Genome)` section template (port EXPTR1 form, 9 genome items)

Every skill embeds this section (contextualize each row to the skill's role):

```
## Inherited DNA (Parent Genome)
> This skill inherits the complete genome of AgenticWorkflow. Purpose varies by skill; the genome is
> identical. See soul.md §0.

**Constitutional Principles** (contextualized):
1. Quality Absolutism — <what quality means for this skill; ignore speed/token>
2. Single-File SOT — master-owned state; this skill <RETURNS results | is read-only>
3. Code Change Protocol — intent→impact→design before touching any script

**Inherited Patterns**:
| DNA Component | Inherited Form (this skill) |
|---|---|
| 3-Phase Structure | extract/classify → verify/place → db |
| SOT Pattern | per-receipt ledger, single writer = master |
| 4-Layer QA | L0 Anti-Skip / L1 Verification / L1.5 pACS / L2 Adversarial Review |
| P1 Hallucination Prevention | deterministic checks (esp. expensereceipt-verify gate) |
| P2 Expert Delegation | 6 specialized sub-skills |
| Safety Hooks | block_destructive_commands.py; openpyxl-FORBIDDEN protects xlsx zip |
| Adversarial Review | @reviewer / @fact-checker cross-check (OCR vs card) |
| Decision Log | autopilot-logs/ + classification-learning DB |
| Context Preservation | handwriting self-learning gallery + per-receipt ledger across runs |

**Domain-Specific Gene Expression**: <which genes express strongest for THIS skill>
```

The 9 inherited genome items (canonical): (1) 절대 기준 3개, (2) SOT 패턴, (3) 3단계 구조, (4) 4계층 검증, (5) P1 봉쇄, (6) Safety Hook, (7) Adversarial Review, (8) Decision Log, (9) Context Preservation.

---

## I. Binding Guardrails (M0 approval — apply at named milestone)

Full text + traceability table in `EXPR-MILESTONE0-BUILD-PLAN.md §11`. Summary:
G1 canceled-row defensive detection [-verify] · G2 dynamic name-DB only, no 1007-ceiling [-classify/-place] · G3 card-raw keys best-effort+NFC [-extract/-merchant/-verify] · G4 consensus = `ocr-vote-audit.json` not `compare()` [-verify] · G5 `section-confirmed.json` written by master/human, not sub-skill [-classify/master] · G6 verify 2-split pre/post-place [-verify/master] · G7 insert-row = formula-aware shift NOT implemented (fail-loud, raises; partial shift would silently desync `<c r>`/`<f>` vs `<row r>`); primary = template pre-sized sector bands, true overflow → ESCALATE to master [-place] · G8 candidate-output + atomic os.replace rollback [-place] · G9 STAFF "already 1 Dinner" = SAME-DATE scope [-classify] · G10 gallery few-shot = metadata key, not pixels [-db/-extract] · G11 preprocess minimal = rotate+grayscale [-extract] · Caveat verify leaf = in-process IMPORT, strip layout deps [-verify].

---

## J. Build order + reuse map

Dependency-ordered milestones (build plan §2): **M1 scaffold (this) → M2 -db → M3 -merchant → M4 -extract → M5 -classify → M6 -place → M7 -verify → M8 master → M9 integration dry-run → M10 rename-8단계.** Per-asset reuse strategy (IMPORT/PORT/REFERENCE/NEW) in build plan §1. Net-NEW code is minimized (build plan §1 "Net-NEW inventory"): NTS checksum, folder-autodetect+preprocess, OCR schema-extension fields, item-sum check, handwriting confidence+gallery, `<pic>`+rels+media injection, 3-per-row coordinate engine, OTHERS-LOCAL cell-group.
