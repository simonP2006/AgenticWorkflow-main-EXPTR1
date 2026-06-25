# Batch A (classify) — CSO Independent Verification Report → master judgment + §5

> Status: **Batch A executed on COPY by worker s2; CSO independently re-verified = CLEAN PASS.** Awaiting master judgment + §5 (adversarial cross-verify of Batch A output) → then Batch C GO. Worker is HELD (no Batch C, no merge).

## Worker output (9 fixes + M10, copy `_hardening/skills/expensereceipt-classify/`)
C1 exact-norm (NFC+casefold+ws-collapse) 사업자번호 reverse-index + escalate-on-miss/ambiguity (substring forbidden) · C2 KICC/세외수입 parking-slip → escalate · C3 whitespace-insensitive toll + body scan · C4 unread/zero headcount → escalate (no coercion; **no item-sum in classify** — verify-V3's job) · C5 safe people coerce · C6 no-time STAFF/TRAVEL → escalate (only DINNER auto-commits) · C7 stable `compute_rid` + canonical-sector LOUD reject + legacy shim · H8 re.search+meridiem 24h · H9 parse_date normalization (G9 same-date link) · M10 SKILL.md doc-honesty.

## CSO independent re-verification (6 axes — all PASS)
1. **Selftests** (`/tmp/cso_sandbox_baseline.py`): classify **35 PASS / 0 FAIL / exit 0** (22 original + 13 new TDD); **orchestrator 27/27 + verify 56/56 green while bound to the FIXED copy classify** (sandbox isolation real); merchant 13 / db 21 / place 10 / autodetect 14 / vote 14 all unchanged. **Regression = 0.** (Runner shows classify "MISMATCH" only because its BASE=22 predates the +13 tests; FAIL=0 is the truth.)
2. **Non-vacuous flip** (my independent probe `/tmp/cso_prefix_probe.py`, pre-fix capture vs post-fix): C1 까치화방 no-card `OTHERS/false`→`escalate` · C2 KICC `OTHERS/false`→`escalate` · C3 single-space toll `OTHERS`→`PARKING/TOLLS` (double-space still works) · C5 people='2' `TypeError crash`→`escalate, no crash` · C6 까치화방 card no-time `silent TRAVEL`→`escalate`. **All buggy→fixed, proven with data.** (Worker's 13 embedded TDD cases independently corroborate, captured FAIL-pre/PASS-post.)
3. **M10 doc-honesty**: classify SKILL.md now states item-sum belongs to **verify-V3**, classify **CONSUMES** the OCR people field (does not compute it) — matches GO must-change #6 + DH-4. New deterministic fns present: `resolve_store_sector`, `_PARKING_SLIP_TOKENS`, `_exact_norm`, `_safe_people`, `compute_rid`.
4. **C6 escalation rate** (worker-measured, real WK20-22, real card-join): 56%→76%. The **+20pp is 100% C4** (unread-headcount escalate, SPEC-correct). **C1/C2/C6 added 0 escalations on real data** (every real meal receipt carries a time → no-time branch never fires) ⇒ **no over-escalation**. Honest caveat: research backups lack handwriting → 76% is an upper bound.
5. **Inviolable boundaries**: original `.claude/skills` **16 source files byte-UNTOUCHED** (changed 0 / missing 0, vs audit `/tmp/exptr_original_before.md5`) · input **PRISTINE `2631d118`** (0 mismatch) · only copy classify edited · CSO `/tmp` harness untouched.
6. **Open question resolved**: WK23 has no parsed OCR (PDF only); worker measured adjacent real weeks (WK20-22) instead of fabricating WK23 numbers. **CSO approved option (i)** — close on WK20-22 figures; WK23 PDF parsing = OCR/vision = Batch-A-out-of-scope + scope-expansion, and the C6 over-escalation concern is already answered.

## Regression risk
Primary driver of higher escalation = **C4 unread-headcount → escalate** (by design, ANCHOR #2b). Cross-importers (orchestrator, verify) unaffected (27/56 green). No code in other modules touched.

## Artifacts
Plan: `_hardening/ROUND1_FIX_PLAN.md` (Batch A) · Directive: `_hardening/BATCH_A_DIRECTIVE.md` · Worker copy: `_hardening/skills/expensereceipt-classify/`.

## Ask
Master: judge Batch A + run §5 (adversarial cross-verify of the classify diff). On PASS → give Batch C GO and I resume (worker held). No merge until the HARD gate (all batches + final §5 + 10-fresh-prompt + master/owner approval).
