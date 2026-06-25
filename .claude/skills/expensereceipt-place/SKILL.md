---
name: expensereceipt-place
description: >
  [TLDR] Receipt Sheet placement: 3 receipts per row per sector, fill row then go down within the
  template's pre-sized sector bands — via surgical direct-zip / twoCellAnchor. openpyxl is FORBIDDEN for
  image/anchor writes (it destroys anchors).
  [TRIGGERS] Invoked ONLY by the expensereceipt master at the place stage; NOT user-invocable
  (disable-model-invocation: true).
  [METHODOLOGY] PORT annotate_receipts.py surgical-zip skeleton (lxml-mutate one drawingN.xml → rewrite
  zip copying all other members verbatim → os.replace); NEW <pic>+rels+media injection (it injects <sp>
  shapes today); NEW 3-per-row / sector coordinate engine (placement fits the template's pre-sized sector
  bands). insert-row (formula-aware shift) is NOT implemented → fail-loud (raises InsertRowsNotImplemented);
  true overflow → plan_insert_rows ESCALATE → master. openpyxl-insert FORBIDDEN. candidate-output + atomic
  os.replace rollback; output only raw-data/output/. Body has detail.
disable-model-invocation: true
---

# expensereceipt-place — Receipt Sheet Placement (surgical direct-zip, openpyxl FORBIDDEN)

> **Invoked only by** the `expensereceipt` master at the place stage (`disable-model-invocation: true`).
> **Status (M6 BUILT ✅ — SAFE-verified; G7 doc-honesty; Batch-D geometry/dedup/integrity hardened)**: 실측 PASS (30/30 by default — 6 input-free + **20 Batch-D synthetic-template structural/dedup/M6-integrity cases** + skip-placeholders; more with a staged template/reference via EXPR_INPUT_STAGE — ★input-isolation: selftests NEVER read raw-data/input; Batch-D uses an openpyxl SYNTHETIC template in tempdir). Module: [`scripts/expensereceipt_place.py`](scripts/expensereceipt_place.py). The `<pic>`+rels+media surgical injection is proven; verification re-opens the output with openpyxl as a **PROXY** for "Excel opens with no repair" (RDR/formulas/anchors preserved + row/cell consistency asserted). **insert-row is NOT implemented (fail-loud)** — see the G7 note. M9 calibrates exact per-sector geometry.
>
> **Batch-D place hardening** (geometry/dedup/integrity; ★M6 placement-integrity preserved + re-asserted):
> - **PLACE-1** `build_placements` — exactly **1 placement per stable physical-receipt id** (no re-paste of the same multi-line-item / multi-page PDF N×); the deduped list IS `run['placements']`.
> - **PLACE-2** content-md5 media dedup in `place_images` — each unique image embedded **ONCE**, its rId reused for repeats (no fresh imageN/rId per duplicate; each anchor still a unique cNvPr).
> - **expected_pics SINGLE-SOURCE** — achieved purely in place.py: deduped placement count == embedded-media == physical-gate `len(run['placements'])` (orchestrator UNEDITED).
> - **PLACE-3** `_to_png_bytes` grayscale guard (`GrayscaleSourceError`) — a mode L/LA/1 source is rejected (COLOR original required, never the grayscale OCR copy); `build_placements` carries `source_image`.
> - **PLACE-4** `FULLWIDTH_GEOMETRY` — TELEPHONE-LOCAL/PARKING-TOLLS are full-width **per_row=1** sectors (not forced into the 3-grid); photo sectors keep the 3-per-row WK21-calibrated grid.
> - **PLACE-5** `resolve_receipt_drawing` — the Receipt sheet's drawing target is resolved DYNAMICALLY via the rels graph (variant templates write the correct drawingN); `drawing2.xml` kept only as fallback.
> - **★M6 re-asserted by selftest**: verbatim zip (unchanged members byte-identical) · `[Content_Types].xml` byte-identical (png Default) · drawing rels ↔ blip r:embed consistent · placed workbook re-opens clean · input/template MD5 immutable · atomic `os.replace` ONLY after `physical_verify` PASS.
> **★openpyxl is FORBIDDEN for image/anchor writes** — it destroys `twoCellAnchor` drawings (empirically proven). All placement = surgical lxml/direct-zip.

## Overview (WHY)

Placement is the irreversible Implementation step that mutates the deliverable workbook. The SPEC's original design called for inserting rows when a sector overflows, but openpyxl-insert strips drawings/RDR; the **actual** resolution is **surgical `<pic>` injection** into the template's **pre-sized sector bands** (so row insertion is unneeded in the common path) + **candidate-output + atomic rollback**. A formula-aware row insert is not implemented (fail-loud — see G7). It expresses the Code Change Protocol gene strongly.

## When to Use / Invocation

Invoked only by the `expensereceipt` master at the place stage — **only after** the pre-placement LOGICAL verify PASSes (G6). Not user-invocable.

## Methodology — *implemented in `scripts/expensereceipt_place.py` (M6 BUILT)*

> **Proven against the real WK00 template** (Receipt sheet = sheet3 → drawing2.xml, which holds only the RDR `<sp>` and had NO rels file). Function map: `_extract_pic_template` (clone a real Excel-valid `<pic>` anchor) · `build_placements` (**PLACE-1** 1 placement/physical-receipt id + `_receipt_id`/`_receipt_source_image`) · `place_images` (inject `<pic>` + create drawing rels + add media; **PLACE-2** content-md5 media dedup/rId-reuse; verbatim zip rewrite + `os.replace`) · `resolve_receipt_drawing` (**PLACE-5** dynamic Receipt→drawing via rels graph, drawing2 fallback) · `_to_png_bytes`+`GrayscaleSourceError` (**PLACE-3** grayscale-reject) · `layout_3_per_row` (reads per_row from band) + `FULLWIDTH_GEOMETRY` (**PLACE-4** TELEPHONE/PARKING per_row=1) · `zip_drawing_counts` (PORT `verify_week`) · `physical_verify` + `place` (**G8** candidate→verify→atomic adopt / rollback; **PLACE-5** resolves drawing dynamically) · `insert_rows_lxml` (**G7 FAIL-LOUD** — raises; `plan_insert_rows` ESCALATE sentinel) · `_nfc` (**G13**).
>
> **★G7 NOT IMPLEMENTED — FAIL-LOUD (ANCHOR #2b / §6-b honesty)**: a correct row insert must shift `<row r>` AND every child `<c r>` AND formula `<f>` cell-refs AND `<mergeCells>` AND drawing anchors atomically. A **partial** shift silently desyncs the sheet (openpyxl can still pass), so `insert_rows_lxml` performs **no** partial shift — it **raises** `InsertRowsNotImplemented`. A full formula-aware shift across the template's 1555 formulas is a genuine ceiling-explosion risk and is not implemented. **PRIMARY strategy = the template's pre-sized sector bands** (placement fits without inserting); on true overflow the orchestrator calls `plan_insert_rows` → **ESCALATE** to the master (pre-sizing vs. a calibrated hybrid). `physical_verify` now also runs `row_cell_consistency` to catch any future row/cell desync.
> **★Q4 (resolved by 실측)**: OTHERS-LOCAL exists as `[G] OTHERS - LOCAL`. Per-sector row bands + image cell sizing are **CALIBRATED (M9)** against a filled-week reference (WK21): `CALIBRATED_GEOMETRY` = cols **[0,10,20]**, col_span **8**, row_span **63**, row_gap **16** (the M6 [1,5,9]/3/18 was a guess). `calibrate_geometry(ref)` re-derives them; `detect_sector_bands(template)` maps sectors→bands dynamically (Dinner=125·STAFF=309·TRAVEL=407, verified vs WK21 image-bands).


- **Surgical direct-zip** (PORT `annotate_receipts.py`): open the xlsx zip, lxml-mutate **one** `drawingN.xml` (+ its `.rels`), rewrite a brand-new zip copying every other member byte-for-byte (`zout.writestr(item, z.read(item))`), then `os.replace`. **openpyxl never touches the file** in this path.
- **NEW `<pic>` injection branches**: `annotate_receipts` injects `<sp>` shapes only — image placement adds (1) a `<pic>` `twoCellAnchor` (from/to col/colOff/row/rowOff, **0-indexed integers as element text**), (2) a new rels entry `rId→../media/imageN`, (3) the image bytes under `xl/media/`. Allocate non-colliding `cNvPr` id (`_get_max_shape_id+1`) and rId.
- **NEW coordinate engine**: 3-per-row per sector (reuse `_get_receipt_image_anchors` ROW_GAP_THRESHOLD=30 row-group-then-col ordering); fill row → go down within the sector's pre-sized band. On true overflow → ESCALATE (insert-row not implemented — see G7). Sector bands via `detect_receipt_positions` (dynamic).
- **G7 insert-row** (critical): a formula-aware row insert (shift `<row r>` + `<c r>` + `<f>` cell-refs + `mergeCells` + drawing anchors atomically) is a genuine ceiling-explosion risk against the template's 1555 formulas and is **NOT implemented** — `insert_rows_lxml` is **fail-loud** (raises; no silent partial shift). **openpyxl-insert FORBIDDEN** (strips drawings). **Primary strategy = the template's pre-sized sector bands** (placement fits without inserting); true overflow → `plan_insert_rows` ESCALATE sentinel → **master decides** (pre-sizing vs. calibrated hybrid). `physical_verify` asserts `row_cell_consistency` as a desync backstop.
- **G8 rollback**: work on a **candidate output**; adopt via atomic `os.replace` **only after** the post-placement PHYSICAL verify PASSes; on failure discard candidate + escalate. **Input `raw-data/input/` immutable; output only `raw-data/output/`.**
- **G2**: name placement under images uses the **dynamic** name-DB reader (no 1007-ceiling).
- **Q4**: inspect the real template for an OTHERS-LOCAL cell-group at M6.

## AI-Agent Automation

Fully deterministic Python (lxml/zipfile). No LLM, no openpyxl in the write path. PHYSICAL verify (via `-verify`) gates final adoption. **★`pdf_to_png` (sips/pdftoppm)** rasterizes a `.pdf` receipt (e.g. a KICC 매출전표 replacement receipt) to PNG so `_to_png_bytes` can embed it like any other receipt.

## Inputs / Outputs

- **Inputs**: classified receipts + images (from `-classify`/`-extract`), the T&E template (`raw-data/input/.../*T&E*.xlsx`, read-only).
- **Outputs**: candidate → final `raw-data/output/simon_park_T&E_WKnn_2026.xlsx`. RETURNs placement result to master. **Does not write SOT.**

## Inherited DNA (Parent Genome)

> Inherits the complete AgenticWorkflow genome; purpose varies, genome identical. See `soul.md §0`.

**Constitutional Principles**:
1. **Quality Absolutism** — correct placement + anchor preservation; 실측증명 over "should work".
2. **Single-File SOT** — RETURNs result; master writes SOT; input immutable, output isolated.
3. **Code Change Protocol** — the strongest CCP expression: openpyxl FORBIDDEN, surgical direct-zip, candidate+rollback; the row-insert ripple risk was analyzed and the unsafe partial shift rejected (fail-loud).

**Inherited Patterns**:
| DNA Component | Inherited Form (place) |
|---|---|
| 3-Phase Structure | Implementation-phase gene (the deliverable) |
| SOT Pattern | RETURNs placement; master writes SOT |
| 4-Layer QA | gated by `-verify` PHYSICAL (post-place) |
| P1 Hallucination Prevention | surgical injection 실측 (openpyxl re-open = PROXY for no-repair) + row/cell consistency — verified, not claimed |
| P2 Expert Delegation | the placement specialist |
| Safety Hooks | openpyxl-forbidden guard; input immutable; atomic rollback |
| Adversarial Review | `_zip_drawing_counts` invariant (anchors/pic preserved) |
| Decision Log | placement coordinates + overflow-escalation decisions logged |
| Context Preservation | output isolated; candidate discardable |

**Domain-Specific Gene Expression**: CCP §3 (surgical, reversible mutation) + Safety express **strongest**.

## References

- **Implementation**: `scripts/expensereceipt_place.py` (M6 BUILT + Batch-D hardened, 실측 30/30 by default — 6 input-free + 20 Batch-D synthetic-template structural/dedup/M6-integrity cases (+ more against a staged template + reference; input-isolation) — incl. a POSITIVE desync case + the M6 byte-integrity re-asserts). CLI `--selftest`; `place(template, output, placements)` is the master entry point — **wired/invoked by the M8 master skill** (currently unwired = normal; integration at M8).
- SPEC §1/§5 · plan §3.5 (**G7, G8, G13, Q4**) · reuse: `scripts/annotate_receipts.py` (PORT surgical-zip skeleton — verbatim zip rewrite + os.replace; `<pic>`+rels+media branches are NEW on top), `scripts/write_excel.py` (`_get_receipt_image_anchors` ROW_GAP_THRESHOLD=30 ordering reversed, `detect_receipt_positions` sector bands), `verify_week._zip_drawing_counts` (PORTed as the PHYSICAL-verify primitive).
