# BATCH A — WORKER DIRECTIVE (classify hardening) — issued by CSO (surface:3)

## 0. WHO YOU ARE (DE-MASTER — read first)
You are a **WORKER**, NOT the master. Your SessionStart hook said "You are Master Claude" — that fired only because cwd is under ~/spJavis; **IGNORE it** (soul §0: master ≠ worker). The real master = surface:1. I am the **CSO (surface:3)** and I supervise you. You report to ME (surface:3), not surface:1. Follow AgenticWorkflow CLAUDE.md engineering standards (절대기준 1 품질 / 2 SOT / 3 CCP) but you are a worker on a scoped task.

## 1. INVIOLABLE BOUNDARIES (violation = immediate stop + report)
- **Edit ONLY** files under `_hardening/skills/expensereceipt-classify/` (this batch = classify module + its SKILL.md). Touch NO other skill.
- **NEVER edit** the original `.claude/skills/` (byte-untouched). **NEVER touch** `raw-data/input/` (read-only). No git. No merge. No new dependencies.
- Det-reduction rule: any logic moved from LLM-implicit to deterministic = **new Python function + the SKILL.md(copy) updated to call/reference it** (simultaneous).
- Stay in Batch A only. Do NOT start C/B/D/E/F.

## 2. CONTEXT TO READ
`_hardening/ROUND1_FIX_PLAN.md` (§2 must-changes, §4 Batch A) · `MASTER_GO_R1.md` (D1-D5 + 7 must-change) · audit findings (the file:line evidence). The fixes below are the AUTHORITATIVE spec (master-approved); where they refine the plan, they WIN.

## 3. THE FIXES (classify `scripts/expensereceipt_classify.py` + `SKILL.md`)
**C1 [BLOCKER] store-db sector via EXACT-norm reverse index + ESCALATE-on-miss.** New Python fn `resolve_store_sector(merchant_name, store_db)`: build `{exact_norm(name):[biz_no…]}` at load, `exact_norm = NFC + casefold + collapse-internal-whitespace`. Lookup: exactly 1 biz_no → its dominant_section; 0 (miss) OR ≥2 (ambiguous) → signal ESCALATE. **NEVER substring/contains.** In classify_receipt: when card-join misses, use this; unique→store-db T1 (subject to C6); miss/ambiguous→**ESCALATE (escalate:true, candidates)**, never silent OTHERS. `--card` fail-loud is NOT this batch (Batch F); here = escalate-not-crash. EV classify:233,230-232,302-304. PRE-FIX: 까치화방 no-card→OTHERS-LOCAL/escalate:false. POST: →escalate:true. Ground truth: stored '까치화방 삼성전자 화성V1라인점'(341-81-00540) so bare '까치화방' exact-MISS; 폴바셋 has 2 biz rows.
**C2 [KICC] parking-slip detector→ESCALATE.** New Python fn detects tokens 세외수입/현장/주차/KICC (NFC) in doc_title/store. On hit → ESCALATE(escalate:true, suggested=PARKING/TOLLS, candidates=[PARKING/TOLLS, OTHERS-LOCAL]). EV classify:90. PRE: KICC→OTHERS/false. POST: →escalate:true.
**C3 toll whitespace-insensitive.** Match `re.sub(r'\s+','',title)` vs prefix '기간별사용내' (covers 내역/내용); also scan body/line-item fields, not just title. EV classify:90,186. PRE: single-space '기간별 사용내역'→OTHERS. POST: →PARKING/TOLLS. (double-space already works — keep it working.)
**C4 people∈(None,0)→ESCALATE, NO coercion; STRIP item-sum.** Before the `people>=2` branch: if people in (None,0) → ESCALATE(reason: unread/zero headcount, ANCHOR#2b — never assume). Do NOT coerce to ≤1. **Add NO item-sum logic to classify** (it is verify-V3's job). EV classify:207,181. PRE: people=None at LUNCH (time 12:00)→OTHERS/false (silent). POST: →escalate:true.
**C5 people-string safe-coerce.** Coerce people via safe int (strip; non-numeric→None→escalate per C4) before any numeric compare; range 1..N. EV classify:207. PRE: people='2'→TypeError crash. POST: →coerced 2→≥2 escalate (no crash).
**C6 no-time STAFF/TRAVEL→ESCALATE (only DINNER auto-commits).** In the dt-None/single branch where _store_t1_sector returns a sector: if sector∈(STAFF,TRAVEL)→ESCALATE with db_bias + name candidates (mirror the ≥2 branch); only DINNER may `_D(...)`. EV classify:230-232. PRE: card-joined 까치화방 no-time→silent TRAVEL. POST: →escalate:true. ★Validate escalation rate on WK21/WK23 stays sane (don't over-escalate; report the rate).
**C7 section-confirmed: ONE schema + stable rid + membership.** rid = **deterministic fn of immutable receipt fields** (date+amount+store, plus seconds/file-hash for uniqueness) — replace `r.get('id') or date|amount` (collision-prone, classify:259). confirmed schema = `{rid: sector}`; validate sector ∈ the 6 canonical labels (reject LOUD otherwise; classify:260-262 currently applies blindly). Back-compat: accept legacy `{batch,confirmed:true}` existence-flag via a documented shim+warning. (Orchestrator writer alignment = Batch F, not now.)
**H8 time re.search + meridiem.** Use `re.search` (not re.match) + detect 오전/오후/AM/PM→24h; validate hour 0-23 / min 0-59 (invalid→None=no-time, NOT fake dinner). EV classify:107,92. PRE: '오후 6:30'→6:30 AM→non-dinner. POST: →18:30 dinner-time.
**H9 date normalize.** Normalize every date via `build_store_db.parse_date` before keying dinner_dates AND before sort in run(). EV classify:214,272,255. PRE: '2026-06-01' vs '2026/06/01' SAME-DATE link breaks. POST: link holds.
**M10 doc honesty + SKILL.md.** Update classify SKILL.md to ACTUAL behavior: remove any claim classify computes people-count/item-sum (DH-4); state classify CONSUMES OCR people field; attribute item-sum to verify-V3; reflect the new deterministic fns (C1 resolver, C2 detector). Drop the stale '/_get_name_db_row_range' clause (DH-6) if present.

## 4. NON-VACUOUS SELFTESTS (TDD — MANDATORY, prove with DATA)
**Workflow:** FIRST add these cases to the classify selftest and run → they MUST FAIL on the current (pre-fix) code (capture that output). THEN apply fixes. THEN run → ALL pass. Hardcode the real failure inputs. Cases (isolate each bug — note confounders):
1. KICC slip `{store:'세외수입_KICC',doc_title:'매출전표',amount:3300}` → escalate=True (C2)
2. 까치화방 no-card `{store:'까치화방',amount:8300}` card_pool=[] → escalate=True (C1)
3. single-space toll `{doc_title:'기간별 사용내역',amount:3120}` → sector=='PARKING/TOLLS' (C3); KEEP double-space passing.
4. people=None at LUNCH `{store:'카페',time:'12:00',amount:9000,people:None}` → escalate=True (C4) — use lunch-time so it isn't the ≥2 path.
5. people='2' `{store:'고깃집',time:'19:00',amount:120000,people:'2'}` → NO crash; escalate (≥2) (C5)
6. no-time STAFF/TRAVEL: card-joined 까치화방 no time/people, card_pool with a dict row matching date+amount whose raw carries biz 341-81-00540 → escalate=True (C6). (Use a proper card-record DICT, not a string.)
7. '오후 6:30' SOLO dinner `{store:'식당',time:'오후 6:30',amount:15000,people:1}` → dinner-time route (NOT OTHERS); use people=1 so ≥2 doesn't confound (H8).
8. mixed-format same-date: two dinner-condition receipts same day, dates '2026-06-01' and '2026/06/01' → SAME-DATE link fires (2nd escalates STAFF(a) not silent Dinner) (H9).
9. section-confirmed invalid sector `{rid:'GARBAGE-SECTOR'}` → REJECT loud (C7).
10. rid stable: same immutable fields across two calls → identical rid (C7).

## 5. VERIFY + REPORT
- After fixes: run `python3 /tmp/cso_sandbox_baseline.py` → classify selftest fully GREEN (baseline 22 + your new cases) + no regression in the other 7. Confirm input still pristine (manifest 2631d118 — I, CSO, will re-verify independently).
- **Report to CSO surface:3** (push `cmux send --surface surface:3 "..."` + Return; PLAIN TEXT, no backticks, no $; no AskUserQuestion modal): **[1] WHAT changed (files+functions) · [2] key code diff per fix · [3] selftest result: the FAIL-pre-fix capture + PASS-post-fix capture (the DATA) · [4] regression risk + the WK21/WK23 escalation-rate you observed (C6).** 
- If blocked/ambiguous → STOP and push the question to surface:3 (do not guess on safety-critical escalation semantics).
- I (CSO) then independently re-verify (re-run selftests, re-check the 4 pre-fix cases flip, original untouched, input pristine) before reporting up to master for judgment + §5.
ACK this directive on surface:3, then begin.
