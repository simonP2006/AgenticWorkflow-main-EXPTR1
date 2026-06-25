# MASTER GO — Round 1 fix (APPROVE-WITH-REQUIRED-CHANGES)

§5 cross-model verdict (Workflow 4-lens `wluv48s5m` + gemini-flash s4) = **approve-with-changes**, tightly converged. Plan shape + batch coverage SOUND (all 6 mandated criticals + 12 crit + 14 high mapped to batches w/ file:line, NO gaps). 1 BLOCKER + 6 MAJORS must be fixed; D1-D5 decided. The plan honestly tagged DB-2/DB-3/V5/V7/DH-1/DH-2 as NOT deterministically-reducible (no over-claim).

## DECISIONS (final — master)
- **D1 = HYBRID.** WIRE only 3 LOCAL safety gates: V6-WIRING (verify loads ocr-vote-audit.json itself), DB-1 (promote_week gated on verify verdict==PASS + week-match arg), DH-3 (thread run.get('sales_slips') into verify_logical). DOC the narrative overclaims (DH-1 6-subskill, DH-2 stage-table/exit-code). **Do NOT wire classify/merchant in-process until C1/D2 lands** (V7 already calls classify with card_pool=[] → wiring first propagates silent-OTHERS into the gate). All orchestrator-contract changes = Batch F (LAST), each w/ a non-vacuous selftest.
- **D2 = BOTH arms, constrained.** (1) reverse index = EXACT-normalized (NFC+casefold+ws-collapse) ONLY, never substring/contains; on multi-candidate hit (same norm name, diff biz_no) OR bare-name true miss → **ESCALATE** to owner-control, NEVER auto-pick. (2) --card fail-loud co-lands w/ D1 card-wiring, ELSE default escalate-not-crash. KICC/세외수입 absent from store-db → that is C2's escalation, not D2.
- **D3 = APPROVE** (strongest fix). build_placements(receipts_for_sector, band) keyed by stable physical-receipt id (1 placement / physical receipt) + PLACE-2 content-md5 media dedup. **expected_pics for run_physical MUST derive from the SAME deduped list (single source)** else physical gate false-FAILs. source_image = COLOR original, NOT the grayscale OCR copy (PLACE-3).
- **D4 = APPROVE as scoped.** deterministic page_count + per-page emit (stable page-ordinal id) + flag/HALT when page_count>1; visual within-page segmentation OUT (= hand image-editing, Option-A OUT). Fix SKILL.md "split multi-receipt PDFs" overclaim. Co-sequence with VOTE-1 (dup (date,amount) identity).
- **D5 = REUSE pdftoppm/sips/pdfinfo** (already de-facto deps, place.py:158-179). NO new pypdf/PyMuPDF. page_count via pdfinfo "Pages:". Fail-closed (ERROR/HALT) if probe binary absent — never silently assume 1 page.

## MUST-CHANGE BEFORE GO (7 — REVISE plan first)
1. **[BLOCKER] C1 reverse-index:** exact-match + ESCALATE-on-miss/ambiguity. Ground truth: 까치화방 stored '까치화방 삼성전자 화성V1라인점' (341-81-00540) → exact bare-OCR '까치화방' MISS; 폴바셋 has 2 biz_no rows. Substring/contains auto-pick FORBIDDEN (violates escalation half of owner mandate).
2. **[MAJOR] C1 --card fail-loud** co-land w/ D1 wiring OR default escalate-not-crash (orchestrator never passes card; V7 calls classify card_pool=[]).
3. **[MAJOR] V2-NOCARD:** NO cash/payment field in verify/vote/extract schema → source a deterministic cash signal upstream FIRST, OR downgrade to escalation/VIOLATION (NOT hard FAIL — else every legit cash receipt false-FAILs).
4. **[MAJOR] V6 schema:** live ocr-vote-audit.json = stale WK22 sections-keyed {week,reads,result,sections}; producer writes {week,reads,result,receipts:int}. Reconcile + declare canonical; prefer additive dual-file read (verify reads BOTH audit+report, option b) over changing producer contract (touches 14 vote selftests).
5. **[MAJOR] PLACE pic-count single-source:** expected_pics from the deduped build_placements() list (orchestrator.py:164 passes len(run['placements'])).
6. **[MAJOR] C4:** STRIP item-sum-in-classify (belongs to verify V3, authoring-spec.md:20; verify.py:275-298 owns it). Only classify fix = people in (None,0) → escalate, NO coercion (ANCHOR #2b).
7. **[MAJOR] C7 section-confirmed:** enumerate ALL writers (orchestrator {id:sector} @120-125 vs classify_stage {batch,confirmed:true} vs reader {rid:sector} @classify.py:260-262), pick+document ONE schema + back-compat/migration, membership-check (sector ∈ 6 labels), **pin rid = deterministic fn of immutable receipt fields** (+seconds/file-hash for uniqueness, gemini) so a confirmed rid survives HALT→owner-edit→re-run (else silent no-op re-HALT).

## MINOR POLISH (fold in, not GO-blocking)
- H8: re.search / meridiem-strip so '오후 6:30' parses (re.match anchors → None).
- C6: validate owner-HALT whole-run blast radius on WK21/WK23 (escalation is SPEC-correct; confirm rate sane).
- V6-SCHEMA: prefer the additive dual-file read (option b).

## EXECUTION PROTOCOL
1. **REVISE** ROUND1_FIX_PLAN.md to incorporate ALL above → post revised-diff summary to surface:1.
2. **Sequencing:** A → C → B → … → F (orchestrator-contract/WIRE changes LAST).
3. **Each batch on the COPY** `_hardening/skills`: implement → **non-vacuous selftest that HARDCODES the real failure cases** (KICC→escalate, 까치화방 no-card→escalate, single-spaced toll→PARKING, multi-line-item→1 placement, dup-source→1 media, '오후 6:30'→dinner-time) FAILing pre-fix / PASSing post-fix (gemini M10: prove "fixed" with DATA, not just "no change") → full green selftest → input pristine check (manifest 2631d118).
4. **Per-batch report** to surface:1 → master judges + §5 at checkpoints.
5. **★MERGE GATE (HARD):** nothing copies to original `.claude/skills` until (a) all batches green, (b) master final §5, (c) the **10 FRESH-prompt gate** PASSES (100%: zero hallucination, SKILL.md-consistent w/ cited evidence, no new defects, prompts DIFFERENT from every prior round) — (d) master + owner approval (denylist).
6. Original `.claude/skills` byte-untouched throughout; input read-only/copy-first.

Worker executes under CSO; CSO manages lifecycle + selftests; master judges + §5. Credit: gemini-flash independently endorsed D1=WIRE/D3=Python/D4=page-only + surfaced the C7-rid + M10-prove-with-data points.
