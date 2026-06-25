# Round 1 — Fix Plan v2 (REVISED per MASTER_GO_R1 — APPROVE-WITH-REQUIRED-CHANGES)

> Campaign: expensereceipt Option-A hardening. Author: CSO. Status: **REVISED per master GO; executes batch-by-batch under per-batch master judgment + §5.**
> SOT: `HARDENING_CAMPAIGN.md` + audit `w2jtr2z9i` (48 items) + `MASTER_GO_R1.md` (decisions + 7 must-change).
> Inviolable: original `.claude/skills/` BYTE-UNTOUCHED · input `raw-data/input/` read-only (PRISTINE 2631d118/157) · all work on COPY `_hardening/skills/` · det-reduction = **new Python fn + SKILL.md(copy) calls it** (simultaneous) · worker executes / CSO supervises + selftests / master judges + §5 · **MERGE only past the HARD gate (§3).**

## 0. Precondition DONE — sandbox closed & proven (SANDBOX_CLOSURE_OK: True)
sys.modules copy-binding harness `/tmp/cso_sandbox_run.py` (copy byte-identical) → isolated baseline **177/177, 0 FAIL** (orch27·verify56·classify22·merchant13·db21·place10·autodetect14·vote14); mutation test (break copy-merchant → verify 56→53+3FAIL) proves non-vacuous binding; copy manifest unchanged `aa3e58b3`. Per-batch runner: `python3 /tmp/cso_sandbox_baseline.py` (Python PASS count, ugrep avoided).

## 1. FINAL DECISIONS (master, locked)
- **D1 = HYBRID.** WIRE only 3 LOCAL safety gates — **V6-WIRING** (verify loads ocr-vote-audit.json itself), **DB-1** (promote_week gated on verify verdict==PASS + week-match arg), **DH-3** (thread `run.get('sales_slips')` into verify_logical). **DOC** the narrative overclaims (DH-1 6-subskill, DH-2 stage-table). **Do NOT wire classify/merchant in-process** (V7 calls classify with card_pool=[] → wiring before C1 lands would propagate silent-OTHERS into the gate). **All orchestrator-contract changes = Batch F (LAST)**, each w/ a non-vacuous selftest.
- **D2 = BOTH arms, constrained.** Reverse index = **EXACT-normalized (NFC+casefold+ws-collapse) ONLY, never substring/contains**; on multi-candidate (same norm name, diff biz_no) OR bare-name miss → **ESCALATE** to owner, never auto-pick. `--card` fail-loud co-lands w/ D1 wiring (Batch F), ELSE default **escalate-not-crash**. KICC/세외수입 absent from store-db = C2's escalation, not D2.
- **D3 = APPROVE.** `build_placements(receipts_for_sector, band)` keyed by stable physical-receipt id (1 placement/physical receipt) + PLACE-2 content-md5 media dedup. **expected_pics for run_physical MUST derive from the SAME deduped list (single source)** (orchestrator.py:164 `len(run['placements'])`). `source_image` = COLOR original, never the grayscale OCR copy (PLACE-3).
- **D4 = APPROVE as scoped.** Deterministic `page_count` + per-page emit (stable page-ordinal id) + flag/HALT when `page_count>1`; visual within-page segmentation OUT (Option-A OUT). Fix SKILL.md "split multi-receipt PDFs" overclaim. Co-sequence with VOTE-1.
- **D5 = REUSE pdftoppm/sips/pdfinfo** (de-facto deps, place.py:158-179). **NO new pypdf/PyMuPDF.** page_count via `pdfinfo "Pages:"`. **Fail-closed (ERROR/HALT) if probe binary absent** — never silently assume 1 page.

## 2. 7 MUST-CHANGE — resolution (incorporated; ground-truth re-verified by CSO)
1. **[BLOCKER] C1 reverse-index → EXACT-match + ESCALATE.** Verified: 까치화방 stored `'까치화방 삼성전자 화성V1라인점'` (341-81-00540), no bare alias → exact-norm '까치화방' MISS → **escalate**; 폴바셋 = 2 rows (220-81-15770 + 211-88-95935) → substring would auto-pick wrong → **exact-norm only**, multi-candidate → escalate. New Python `resolve_store_sector(name)`: build `{exact_norm(merchant_name)→[biz_no...]}` at store-db load; 1 hit→sector; 0 or ≥2→escalate(candidates). NO substring/contains. SKILL.md(copy) calls it.
2. **[MAJOR] C1 --card.** fail-loud co-lands with D1 card-wiring in **Batch F**; until then classify default = **escalate-not-crash** (orchestrator currently never passes card; V7 calls classify card_pool=[]). So Batch A C1 = reverse-index escalate path only; the --card-mandatory enforcement is Batch F.
3. **[MAJOR] V2-NOCARD.** No cash/payment field exists in verify/vote/extract schema. **First** try to source a deterministic cash signal upstream (extract/sector); if unavailable this round, **downgrade to escalation/VIOLATION (NOT hard FAIL)** so legit cash/toll/telephone receipts don't false-FAIL. (Sector-scope {PARKING/TOLLS,TELEPHONE-LOCAL} stays the allow-list; everything else no-card → surfaced, not silently passed.)
4. **[MAJOR] V6 schema reconcile.** Verified live `planning/ocr-vote-audit.json` exists (stale WK22 sections-keyed {week,reads,result,sections}); producer writes {week,reads,result,receipts:int}. **Additive dual-file read (option b):** verify reads BOTH ocr-vote-audit.json + ocr-vote-report.json, treats report-presence/non-CONSENSUS as FAIL, asserts week==expected + reads≥MIN_READS — **no change to the producer contract** (protects 14 vote selftests). Declare the canonical schema in a docstring.
5. **[MAJOR] PLACE pic-count single-source.** expected_pics = `len(deduped build_placements() output)`, which IS `run['placements']` (orchestrator.py:164). The deduped list is the single source for both embedding and the physical-gate count → no false-FAIL.
6. **[MAJOR] C4.** **STRIP item-sum logic from classify entirely** (item-sum==card is verify-V3's domain — authoring-spec.md:20, verify.py:275-298). classify's ONLY change = people∈(None,0) → **escalate, NO coercion** (ANCHOR #2b). DH-4 doc: classify SKILL.md states it CONSUMES people (OCR field), attributes item-sum to verify-V3.
7. **[MAJOR] C7 section-confirmed.** Enumerate ALL writers: orchestrator `{id:sector}` (orch:124,188) vs classify_stage `{batch,confirmed:true}` vs reader `{rid:sector}` (classify:260-262). **Pick ONE schema** = `{rid: sector}` (document it; back-compat: migrate/accept the legacy existence-flag with a shim + warning). **Membership-check** sector ∈ 6 labels (reject else loud). **rid = deterministic fn of immutable receipt fields** (date+amount+store +seconds/file-hash for uniqueness) so a confirmed rid survives HALT→owner-edit→re-run (no silent no-op re-HALT).

**MINOR polish folded in:** H8 use `re.search` + meridiem-strip so '오후 6:30' parses (re.match anchors→None). C6 validate owner-HALT blast radius on WK21/WK23 (confirm escalation rate sane). V6 = additive dual-file read.

## 3. Execution protocol + sequencing + HARD merge gate
**Sequencing: A → C → B → D → E → F** (orchestrator-contract / WIRE changes LAST).
**Each batch on COPY `_hardening/skills`:** worker implements (det-reduction = new Python fn + SKILL.md-copy calls it) → **non-vacuous selftest that HARDCODES the real failure case, FAILing pre-fix / PASSing post-fix** (prove with DATA, not "no change") → full green via `/tmp/cso_sandbox_baseline.py` → **input pristine assert (manifest 2631d118)** → CSO recheck → **report to surface:1 → master judges + §5 at the checkpoint.** No batch advances on a red gate. Required hardcoded cases (gemini M10): KICC→escalate, 까치화방 no-card→escalate, single-spaced toll→PARKING, multi-line-item→1 placement, dup-source→1 media, '오후 6:30'→dinner-time.
**★HARD MERGE GATE (nothing copies to original `.claude/skills` until ALL):** (a) all batches green, (b) master final §5, (c) **10 FRESH-prompt gate** PASSES 100% (zero hallucination · SKILL.md-consistent w/ cited evidence · no new defects · prompts DIFFERENT from every prior round), (d) **master + owner approval (denylist)**. Original byte-untouched + input read-only/copy-first throughout.

## 4. Backlog by batch (revised; orchestrator-contract → Batch F)

### BATCH A — classify `expensereceipt_classify.py` (self-contained; first)
- **C1 (BLOCKER, det)** reverse-index EXACT-norm + escalate-on-miss/ambiguity (§2.1); --card fail-loud → Batch F (§2.2). EV: classify.py:233,230-232,302-304. Regression: more escalations on bare-name merchants (intended); selftest: 까치화방 no-card→escalate, 폴바셋 exact→biz, ambiguous→escalate.
- **C6 (crit, det)[이종희/까치화방386]** no-time STAFF/TRAVEL → ESCALATE+db_bias+names (only DINNER auto-commits). EV: classify.py:230-232; SPEC:34-36. Regression: validate WK21/WK23 escalation rate (§2 polish). selftest: no-time STAFF/TRAVEL→escalate.
- **C2 (crit, det)[KICC]** parking-slip detector (tokens 세외수입·현장·주차·KICC) → ESCALATE (PARKING/TOLLS vs OTHERS). EV: classify.py:90. selftest: KICC slip→escalate.
- **C3 (crit, det)** whitespace-insensitive toll match (`re.sub(r'\s+','',title)` vs '기간별사용내' prefix) + body/line-item scan. EV: classify.py:90,186. selftest: single-spaced '기간별 사용내역'→PARKING.
- **C4 (crit, det)** people∈(None,0)→escalate NO coercion; **STRIP item-sum from classify** (§2.6). EV: classify.py:207,181. selftest: people None/0→escalate; assert no item-sum compute in classify.
- **C5 (high, det)** safe int-coercion (non-numeric→None→escalate per C4)+range. EV: classify.py:207. selftest: people='2'.
- **C7 (high, det)** one schema {rid:sector} + membership-check + rid=det-fn-of-immutable-fields + legacy shim (§2.7). EV: classify.py:259-262. selftest: invalid sector→reject; rid stable across re-run.
- **H8 (high, det)** `re.search`+meridiem 오전/오후/AM/PM→24h + hour0-23/min0-59. EV: classify.py:107,92. selftest: '오후 6:30'→dinner-time; '24:00'→invalid.
- **H9 (high, det)** normalize dates via build_store_db.parse_date before dinner_dates key + sort. EV: classify.py:214,272,255. selftest: mixed-format same-date link.
- **M10** update classify SKILL.md to actual behavior (honesty) + all above non-vacuous cases.

### BATCH C — verify `expensereceipt_verify.py` (verify-internal; orchestrator threading → F)
- **V6-WIRING [verify-internal half] (crit, det)** check_consensus LOADs ocr-vote-audit.json itself + week-assert + reads≥MIN_READS + derive multiread from disk count. **Orchestrator passing run_dir → Batch F.** EV: verify.py:317-331; orch:146-148. selftest: disk-load + wrong-week→ERROR.
- **V6-SCHEMA (high, det)** additive dual-file read (audit+report); report-presence/non-CONSENSUS→FAIL; freshness assert (§2.4). EV: vote.py:163-184; verify.py:330-331. selftest: INCONCLUSIVE report present→FAIL; stale week→FAIL.
- **V2-NOCARD (high, det)** escalation/VIOLATION not hard FAIL; cash-signal-upstream if available (§2.3). EV: verify.py:243-252,267-272. selftest: no-card meal→VIOLATION/escalate (not silent pass, not false-FAIL of cash).
- **V3-INERT (high, det)** D1=don't-wire-classify; items not produced upstream this round → **drop V3 from the 7-check claim (doc-honesty) OR mark explicit applicability from disk**, not a vacuous SKIP counted as a check. EV: verify.py:281-298. selftest: assert V3 applicability derived from data.
- **V2-AMOUNT (med, det)** canonical to-int normalizer in pool+match + negative/refund flag. EV: verify.py:246-247,258-259. selftest: str/float/refund.
- **V1-AGREEMENT (med, det)** matched receipt biz_no==consumed card biz_no (NFC). EV: verify.py:204-209. selftest: valid-but-mismatched biz.
- **V6-V3-CALLER-N/A (med, det)** derive applicability from disk not caller booleans (folds into V6-WIRING+V3). EV: verify.py:359-360,296-297.
- **V7 (med, NOT det)** replay classify w/ SAME ordered dinner_dates+confirmed map; escalated-then-confirmed→assert assigned==confirmed. EV: verify.py:348-354. selftest: escalated-confirmed agreement.
- **V5 (med, NOT det)** key off cross-read handwriting disagreement (deterministic)+keep None→FAIL floor. EV: verify.py:306-314.
- **VERIFY-FALLBACK-PARSEDATE (low, det)** extract_card import-fail → ERROR (fail-closed), no naive re-impl. EV: verify.py:99-101.
- **PHYSICAL-CHECKS (low, det)** independently recompute pic-count delta + assert keys present. EV: verify.py:398-405.

### BATCH B — db `expensereceipt_db.py` (DB-1 wiring → F; verdict-gating ARG here)
- **DB-1 [arg half] (crit, det)** promote_week gains verify-verdict arg + week-match (refuse unless PASS). **Orchestrator CALL → Batch F.** EV: db.py:399-403. selftest: promote w/o PASS→refuse.
- **DB-4 (crit, det)** reject EXPR_DB_BASE == PROJECT_DIR/planning (strict subdir). EV: db.py:112-113. selftest: collision base→reject.
- **DB-2 (crit, NOT det)** write PROMOTED before STORE_DB (or staged atomic swap) + startup consistency self-heal. EV: db.py:399-415. selftest: crash-between→consistent.
- **DB-3 (crit, NOT det)** snapshot once per logical promote (key by week) + idempotent retry. EV: db.py:404-406,418-431. selftest: retry/crash→clean rollback.
- **DB-5 (high, det)** NFC+canonical-case sector map + warn/counter unknown (no silent drop). EV: db.py:94-99,270-272.
- **DB-6 (high, det)** gallery id = max G-####+1. EV: db.py:307-323.
- **DB-7 (med, det)** canonicalize amount in _content_sig. EV: db.py:196-199.
- **DB-8 (med, det)** name_index_add stops snapshotting store-db; store_sector only via post-verify rebuild. EV: db.py:353-363.
- **DB-10 (low, det)** min-occurrence-aware confidence OR G12 require occ≥N. EV: db.py:283-284.
- **DB-9 (low, det)** validate date/time at ingest, surface unparseable. EV: db.py:357.

### BATCH D — place `expensereceipt_place.py`
- **PLACE-1 (crit, det)[dup-paste]** `build_placements(receipts_for_sector,band)` 1/physical-receipt id (D3). EV: place.py:368-383,215-232. selftest: multi-line-item→1 placement.
- **PLACE-2 (crit, det)[dup-paste]** content-md5 media dedup (embed unique once, reuse rId); coupled PLACE-1. EV: place.py:209-232. selftest: dup-source→1 media.
- **expected_pics single-source (must-change 5)** run_physical count from deduped list (§2.5). EV: orch:164. selftest: deduped count == placed.
- **PLACE-3 (high, det)[grayscale]** placement requires `source_image`=COLOR original; _to_png_bytes guard mode∈('L','LA','1')→raise/escalate. EV: autodetect.py:131-142; place.py:142-155,216. selftest: grayscale path→reject.
- **PLACE-4 (high, det)[uniform-grid]** per-sector geometry (3-grid photo sectors; full-width per_row=1 for TELEPHONE/PARKING from reference); layout reads per_row from band. EV: place.py:263,331,338-347. selftest: full-width band sizing vs WK21 ref.
- **PLACE-5 (high, det)** `resolve_receipt_drawing(xlsx)` dynamic (rels-graph) → write target; constant fallback. EV: place.py:68,185,466,266-296. selftest: variant template.

### BATCH E — extract/merchant `autodetect.py`,`expensereceipt_vote.py`,`expensereceipt_merchant.py`
- **AUTODETECT-1 (high, det)** new file-kind 'telephone_bill' (NFC tokens 청구내역/통신비/청구서/T world/SKT/KT/LG U+) → telephone sector, NOT receipts. EV: autodetect.py:50-65. selftest: T-world→telephone.
- **AUTODETECT-2 (high, det)** page_count via `pdfinfo` + per-page emit (page-ordinal id) + flag/HALT page_count>1; fail-closed if pdfinfo absent (D4/D5). EV: SKILL.md:32; autodetect no split. selftest: multi-page→count+flag.
- **VOTE-1 (high, det)** multiset key (date,amount,occurrence_ordinal) stable order; vote per occurrence. EV: vote.py:76-82. selftest: dup-amount day→both voted.
- **MERCHANT-1 (med, det)** fallback match_card normalize dates (parse_date-equiv) + log _REUSED=False. EV: merchant.py:82-90.
- **MERCHANT-2 (med, det)** one owner of consume-once join (verify imports merchant join OR align to verify's canceled-row+None-guard). EV: verify.py:243-262.
- **AUTODETECT-3 (low, det)** precedence comment + dual-token selftest. EV: autodetect.py:54-65.
- **MERCHANT-3 (low, det)** additive structural biz guard (reject all-zero) as separate flag, producer back-compat. EV: merchant.py:105-118.

### BATCH F — orchestrator-contract + doc-honesty (LAST; each w/ non-vacuous selftest)
- **D1-WIRE V6-WIRING [orch half]** orchestrator threads run_dir/week into run_logical so verify binds vote-audit from disk. selftest: orchestrate→V6 from disk.
- **D1-WIRE DB-1 [orch call]** orchestrator calls verify→quarantine→promote as one code-enforced txn after run_physical PASS (promote gated on verdict). selftest: FAIL verdict→no promote.
- **D1-WIRE DH-3** thread `run.get('sales_slips')` into verify_logical (KICC 매출전표 path reachable). EV: orch:146-148. selftest: sales_slip→consumed not V2-FAIL.
- **C1 --card fail-loud co-land** orchestrator always passes card_pool; classify --card-mandatory enforced now (§2.2). selftest: missing card→fail-loud (not crash).
- **DR-5 (low, det)** orchestrator _dinner_confidence uses shared norm_store/_mkey key. EV: orch:98. selftest: double-space store→G12 match.
- **DH-7 (low)** call stage_inputs() at head of orchestrate (code-enforce copy-first) OR soften docstring. EV: orch:74-89.
- **DH-1 / DH-2 (DOC)** rewrite master SKILL.md to actual behavior (verify→place→verify gate + emit-once trace; drop stage-table/exit-code/6-subskill overclaims). DH-6 drop stale _get_name_db_row_range clause.
- **NOT wired (D1):** classify/merchant in-process — deferred (post-C1, future round if desired).

## 5. Mandated-critical coverage (re-confirmed)
C1✅(A,BLOCKER-fixed) · C2✅(A) · 중복붙임✅(PLACE-1+2,D) · 흑백누수✅(PLACE-3,D) · 이종희/까치화방386✅(C6,A) · 균일그리드✅(PLACE-4,D).
