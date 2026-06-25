#!/usr/bin/env python3
"""expensereceipt_verify.py — M7: the MANDATORY anti-hallucination gate (★ANCHOR #2a return-angle gate).

Multi-read voting reduces stochastic OCR error, but a *systematic* misread (every read wrong the same
way) yields a confident-WRONG consensus. The final defense is independent DETERMINISTIC cross-check —
checksum, card matching, arithmetic. This gate is that defense. Code is deterministic; it does not
hallucinate (코드는 거짓말하지 않는다). It is the suite's dominant gene (L1/P1).

Discipline (PORT of verify_week.py, Caveat — re-wired as IN-PROCESS IMPORT, layout deps stripped):
  • read-only · deterministic · writes ONLY a JSON report (no workbook, no *_FAIL.xlsx — dropped).
  • IMPORTs producer rules, never re-implements: validate_biz_no (-merchant, req#1), classify rules
    (-classify, req#7), zip_drawing_counts/row_cell_consistency/physical_verify (-place, PHYSICAL),
    parse_date (extract_card_data, date-normalize).
  • Result PASS/FAIL/SKIP; a check that raises → SKIP (an honest partial report, never a false green).
    verdict: exit 0 iff no FAIL among violations (SKIP/warning allowed); exit 1 if any violation FAIL.

★G6 two entry points (the master enforces order):
  • LOGICAL (run_logical) — checks 1–6 + rule consistency on RAW data (no placed file). Run BEFORE place.
  • PHYSICAL (run_physical) — drawing count / anchor preservation / no-repair open / row-cell consistency
    on the PLACED xlsx. Run AFTER place. Place mutates the output ONLY after LOGICAL passes.

7 checks (SPEC ANCHOR #2a):
  V1 business-number checksum   — IMPORT validate_biz_no
  V2 card (date,amount) match   — consume-based reconcile (PORT verify_card_matching); ★G1 canceled rows
                                  defensively excluded; ★G3 card-raw keys best-effort + NFC
  V3 item-sum == card amount    — NEW (conditional: receipts carrying line items)
  V4 amount != 0                — generalize verify_toll_integrity T-3 to all sectors
  V5 handwriting confidence     — NEW (handwriting present ⇒ confidence ≥ threshold, else escalate)
  V6 multi-read consensus       — ★G4: consume ocr-vote-audit.json (result == 'CONSENSUS'); NOT compare()
  V7 rule consistency           — IMPORT classify; sector ∈ 6 valid + no store-confident contradiction

SOT discipline (절대 기준 2): read-only; RETURNs the verdict to the master (who records it in state.yaml);
writes NO SOT. On FAIL → re-read flagged receipts only (max 2) → escalate to the owner via master.

Usage:
    python3 expensereceipt_verify.py --selftest
    (master invokes run_logical()/run_physical() in-process or via a thin CLI wired at M8)
"""

import os
import re
import sys
import json
import math
import unicodedata
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Status vocabulary. ★Fail-closed distinction (M7 hardening): ERROR (a MANDATORY check could not run —
# producer absent / check raised / required input absent) is NEVER clean; only a deliberate N/A-SKIP
# (genuinely not-applicable: no line items, single-read by design) is clean. A gate that gates an
# irreversible place-mutation must STOP when a check could not actually run (ANCHOR #2a / §6-b).
PASS, FAIL, SKIP, ERROR = "PASS", "FAIL", "SKIP", "ERROR"
_BIZ_OPTIONAL_SECTORS = {"PARKING/TOLLS", "TELEPHONE-LOCAL"}   # biz_no legitimately absent (separate card)
HANDWRITING_CONF_MIN = 0.70
VALID_SECTORS = {"PARKING/TOLLS", "TELEPHONE-LOCAL", "Dinner", "STAFF MEETING",
                 "TRAVEL BUSINESS/ENTERTAINMENT", "OTHERS-LOCAL"}


def _find_project_dir():
    p = Path(__file__).resolve()
    for anc in p.parents:
        if (anc / "CLAUDE.md").exists() and (anc / "scripts").is_dir():
            return anc
    return p.parents[4] if len(p.parents) >= 5 else p.parent


PROJECT_DIR = _find_project_dir()
SKILLS = PROJECT_DIR / ".claude" / "skills"

# --- IMPORT producer rules in-process (no subprocess; layout deps stripped). Fallbacks keep verify
#     runnable in isolation, but the real run uses the producers (SOT single-source). ---
_REUSED = {"merchant": False, "classify": False, "place": False, "extract_card": False}
try:
    sys.path.insert(0, str(SKILLS / "expensereceipt-merchant" / "scripts"))
    from expensereceipt_merchant import validate_biz_no            # noqa: E402  (req#1 producer rule)
    _REUSED["merchant"] = True
except Exception:
    validate_biz_no = None      # ★CRIT#1: producer absent → V1 ERROR (no divergent re-implementation;
    #                              the gate must NOT certify with a weak fallback — fail-closed).
try:
    sys.path.insert(0, str(SKILLS / "expensereceipt-classify" / "scripts"))
    from expensereceipt_classify import classify_receipt           # noqa: E402  (req#7 producer rule)
    _REUSED["classify"] = True
except Exception:
    classify_receipt = None
try:
    sys.path.insert(0, str(SKILLS / "expensereceipt-place" / "scripts"))
    from expensereceipt_place import zip_drawing_counts, row_cell_consistency, physical_verify  # noqa: E402
    _REUSED["place"] = True
except Exception:
    zip_drawing_counts = row_cell_consistency = physical_verify = None
try:
    sys.path.insert(0, str(PROJECT_DIR / "scripts"))
    from extract_card_data import parse_date, parse_amount         # noqa: E402  (date/amount-normalize reuse)
    _REUSED["extract_card"] = True
except Exception:
    # VERIFY-FALLBACK-PARSEDATE (fail-closed): NO naive inline re-impl. A missing producer means the
    # date/amount normalizer is UNAVAILABLE — date/amount-normalizing checks must ERROR (never certify
    # with a divergent local parser). parse_date/parse_amount = None → those checks fail-closed to ERROR.
    parse_date = None
    parse_amount = None

MIN_READS = 3            # V6-WIRING: the suite votes 3→7 (mirror expensereceipt_vote.MIN_READS); < this ⇒ ERROR


# ============================================================ helpers
def _norm_date(d):
    # parse_date None (producer import failed) → return raw; the date-using checks guard on
    # `parse_date is None` and ERROR (fail-closed) instead of normalizing with a divergent local parser.
    return parse_date(d) if (parse_date is not None and d) else d


def _norm_amount(v):
    """V2-AMOUNT: canonical amount → int via the producer parse_amount (mirror; SOT single-source).
    None when unparseable OR when the producer is unavailable (fail-closed — an amount check that needs a
    normalized value must ERROR, never certify on a divergent local parse). Negative (refund) preserved."""
    if v is None or parse_amount is None:
        return None
    return parse_amount(v)


def _is_refund(v):
    """V2-AMOUNT: explicit negative/refund flag (a refund row must be surfaced, never silently matched)."""
    a = _norm_amount(v)
    return a is not None and a < 0


def _card_biz_no(raw):
    """V1-AGREEMENT: the card row's 사업자번호 (NFC), mirroring build_store_db._biz_no — the source of
    truth that a card-MATCHED receipt's biz_no must agree with."""
    for k in ("사업자번호", "사업자등록번호"):
        v = (raw or {}).get(k)
        if v:
            return unicodedata.normalize("NFC", str(v)).strip()
    return None


_CANCEL_VALUE_HINTS = {"y", "취소", "cancel", "취소승인", "승인취소", "true", "1"}
# explicit cancel-STATUS tokens that signal a canceled row even under a generically-named column
# (e.g. 거래구분=취소). Exact-match on the (stripped) value → avoids false positives (a store name is
# never exactly "취소"). NFC-normalized.
_CANCEL_STATUS_TOKENS = {"취소", "취소승인", "매출취소", "승인취소", "취소거래", "거래취소",
                         "cancel", "canceled", "cancelled"}


def is_canceled(card_raw):
    """★G1 defensive canceled-row detection. NO hardcoded key assumption (ANCHOR #2b — never silently
    drop/keep on a guess). Two robust signals: (a) a cancellation-NAMED column (key contains '취소' or
    'cancel', NFC) whose value indicates a cancel; (b) ANY field whose VALUE is an explicit cancel-status
    token (exact-match, e.g. 거래구분=취소). A key-absent record is treated as NOT canceled."""
    for k, v in (card_raw or {}).items():
        kn = unicodedata.normalize("NFC", str(k))
        vs = unicodedata.normalize("NFC", str(v)).strip()
        vsl = vs.lower()
        if "취소" in kn or "cancel" in kn.lower():                # (a) cancellation-named column
            if vsl in _CANCEL_VALUE_HINTS or "취소" in vs:
                return True
        if vs in _CANCEL_STATUS_TOKENS or vsl in _CANCEL_STATUS_TOKENS:  # (b) explicit cancel-status value
            return True
    return False


def _approval_no(raw):
    """★KICC: 승인번호 (the UNIQUE per-transaction approval id, the slip-match source-of-truth) —
    best-effort + NFC (G3), digits only."""
    for k in ("승인번호", "승인 번호", "approval"):
        v = raw.get(k)
        if v:
            return re.sub(r"\D", "", unicodedata.normalize("NFC", str(v)))
    return None


def _card_last(raw):
    """Trailing visible digits of the (masked) card number — a confirmation key for slip matching."""
    cn = unicodedata.normalize("NFC", str(raw.get("카드번호", "")))
    digits = re.findall(r"\d", cn)
    return "".join(digits[-3:]) if len(digits) >= 3 else None


def build_card_pool(card_records, exclude_canceled=True):
    """Consume-based card pool (PORT verify_card_matching). ★G1: canceled rows excluded (Q2). ★G3: biz/store
    read from raw best-effort + NFC. Surfaces 승인번호 + card_last for KICC 매출전표 (replacement-receipt) matching."""
    pool = []
    for i, rec in enumerate(card_records or []):
        raw = rec.get("raw", {}) or {}
        if exclude_canceled and is_canceled(raw):
            continue
        pool.append({"index": i, "date": _norm_date(rec.get("date")),
                     "amount": _norm_amount(rec.get("amount")),          # V2-AMOUNT: canonical int
                     "refund": _is_refund(rec.get("amount")),            # V2-AMOUNT: negative/refund flag
                     "biz_no": _card_biz_no(raw),                        # V1-AGREEMENT: card source-of-truth biz
                     "approval": _approval_no(raw), "card_last": _card_last(raw),
                     "raw": raw, "consumed": False, "consumed_by": None})
    return pool


class Result:
    __slots__ = ("cid", "name", "status", "evidence", "severity")

    def __init__(self, cid, name, status, evidence, severity="violation"):
        self.cid, self.name, self.status, self.evidence, self.severity = cid, name, status, evidence, severity

    def to_dict(self):
        kind = {PASS: "ran", FAIL: "ran", SKIP: "n/a-skip", ERROR: "error"}.get(self.status, "ran")
        return {"id": self.cid, "name": self.name, "status": self.status, "kind": kind,
                "evidence": self.evidence, "severity": self.severity}


def _run(checks):
    """Run (cid, name, fn, severity) tuples. ★A raising check → ERROR (a MANDATORY check that could not
    run), NOT a clean SKIP — this is the fail-closed core (my self-caught ⒜). Honest partial, never green."""
    results = []
    for cid, name, fn, severity in checks:
        try:
            status, evidence = fn()
        except Exception as e:                                     # ★ exception ⇒ ERROR (fail-closed), not SKIP
            status, evidence = ERROR, f"check could not run (raised): {type(e).__name__}: {e}"
        results.append(Result(cid, name, status, evidence, severity))
    return results


def _verdict(results):
    """★Fail-CLOSED: verdict PASS / exit 0 ONLY if no ERROR and no violation-FAIL. An ERROR (unrun
    mandatory check) blocks just like a FAIL — the gate must STOP on a check it could not actually run.
    Deliberate N/A-SKIP and warnings do not block."""
    errors = [r for r in results if r.status == ERROR]
    fails = [r for r in results if r.status == FAIL and r.severity == "violation"]
    if errors:
        return ERROR, 1
    if fails:
        return FAIL, 1
    return PASS, 0


# ============================================================ the 7 LOGICAL checks
def check_biz_checksum(receipts):
    if validate_biz_no is None:                                    # ★CRIT#1 fail-closed
        return ERROR, "producer validate_biz_no unavailable (-merchant not importable) — cannot certify checksums"
    bad = [r.get("id") or r.get("store") for r in receipts
           if r.get("biz_no") and not validate_biz_no(r.get("biz_no"))]
    return (FAIL, f"invalid NTS checksum: {bad}") if bad else (PASS, "all present business numbers pass NTS checksum")


def check_biz_presence(receipts):
    """★MED#7 (severity=warning): a card-MATCHED meal/others receipt should carry a biz_no (it comes from
    the card). Absence on a non-toll/tel, card-matched receipt is an extraction gap → escalate (surfaced,
    not exit-blocking — cash receipts legitimately lack a biz_no, handled by the NO_CARD / optional-sector
    paths)."""
    missing = [r.get("id") for r in receipts
               if not r.get("biz_no")
               and r.get("sector") not in _BIZ_OPTIONAL_SECTORS
               and r.get("card_match", "MATCHED") == "MATCHED"]
    return (FAIL, f"biz_no absent on card-matched non-toll/tel receipts — escalate: {missing}") if missing \
        else (PASS, "biz_no presence OK (or legitimately absent)")


def check_card_match(receipts, card_pool, sales_slips=None):
    """Consume-based cross-match.
    Phase 1: normal receipts consume card rows by (date, amount).
    Phase 2 (★KICC 매출전표 replacement-receipt, master-approved): a card-company sales slip consumes a
      STILL-UNCONSUMED card row ONLY when its 승인번호 AND amount both match that row. ② source-of-truth =
      the card statement's 승인번호 (the slip must exist in the statement). ① no-double-consume — a row
      already matched by a normal receipt is not re-consumed. A slip whose 승인번호+amount is NOT in the
      statement is REJECTED (stray / tampered — fail-closed; it validates nothing).
    Unconsumed card rows (no receipt AND no matched 매출전표) = FAIL (reimbursement loss). NO_CARD receipts
    (cash / toll / telephone — separate or no card) are allowed."""
    if parse_date is None:                                         # PARSEDATE-fallback: normalizer absent ⇒ fail-closed
        return ERROR, "date normalizer unavailable (extract_card import failed) — cannot card-match (fail-closed)"
    # ★None-amount guard (fail-closed): a None/unparseable amount must NEVER match (None == None is True in
    # Python and would silently consume the wrong row). Amounts are normalized (V2-AMOUNT) before the guard.
    none_amt = [("card", c["index"]) for c in card_pool if c["amount"] is None]
    none_amt += [("receipt", r.get("id")) for r in receipts if _norm_amount(r.get("amount")) is None]
    none_amt += [("매출전표", s.get("approval")) for s in (sales_slips or []) if _norm_amount(s.get("amount")) is None]
    if none_amt:
        return ERROR, f"None/unparseable amount(s) — cannot reliably card-match (data-integrity, fail-closed): {none_amt}"

    no_card = []
    for r in receipts:
        rd, ra = _norm_date(r.get("date")), _norm_amount(r.get("amount"))   # V2-AMOUNT canonical compare
        hit = next((c for c in card_pool
                    if not c["consumed"] and c["amount"] is not None and c["date"] == rd and c["amount"] == ra), None)
        if hit:
            hit["consumed"] = True
            hit["consumed_by"] = ("receipt", r.get("id"))
        else:
            no_card.append(r.get("id") or f"{rd}|{ra}")
    slip_ok, slip_rejected = [], []
    for s in (sales_slips or []):
        sapp = re.sub(r"\D", "", str(s.get("approval") or ""))
        samt = _norm_amount(s.get("amount"))
        hit = next((c for c in card_pool
                    if not c["consumed"] and sapp and c["amount"] is not None
                    and c.get("approval") == sapp and c["amount"] == samt), None)
        if hit:
            hit["consumed"] = True
            hit["consumed_by"] = ("매출전표", sapp)
            slip_ok.append(sapp)
        else:
            slip_rejected.append({"approval": sapp, "amount": samt,
                                  "reason": "승인번호+amount not matched in the card statement — stray/tampered, NOT accepted"})
    leftover = [c["index"] for c in card_pool if not c["consumed"]]
    if leftover:
        ev = f"unconsumed card rows (no receipt and no matched 매출전표): {leftover}"
        return FAIL, ev + (f"; rejected stray slips: {slip_rejected}" if slip_rejected else "")
    return PASS, (f"all card rows consumed (normal + {len(slip_ok)} 매출전표 replacement); "
                  f"no-card receipts: {len(no_card)}; rejected stray slips: {len(slip_rejected)}")


def check_item_sum(receipts):
    """NEW: for receipts carrying line items, Σ(item amounts) must equal the card/receipt amount.
    ★MED#9: a None line-item amount is ERROR (a missing item the OCR failed to read) — it is NOT coerced
    to 0 (which would silently hide it). No items at all = deliberate N/A-SKIP."""
    checked = mism = 0
    bad, err = [], []
    for r in receipts:
        items = r.get("items")
        if not items:
            continue
        checked += 1
        amts = [(it.get("amount") if isinstance(it, dict) else it) for it in items]
        if any(a is None for a in amts):
            err.append(r.get("id"))
            continue
        s = sum(amts)
        if s != r.get("amount"):
            mism += 1
            bad.append({"id": r.get("id"), "item_sum": s, "amount": r.get("amount")})
    if err:
        return ERROR, f"None/missing line-item amount (cannot sum — OCR gap) → escalate: {err}"
    if checked == 0:
        return SKIP, "no receipts carry line items (deliberate N/A)"
    return (FAIL, f"item-sum != amount: {bad}") if mism else (PASS, f"item-sum == amount for {checked} itemized receipts")


def check_amount_nonzero(receipts):
    bad = [r.get("id") or r.get("store") for r in receipts if not r.get("amount")]
    return (FAIL, f"amount is 0/missing: {bad}") if bad else (PASS, f"all {len(receipts)} amounts non-zero")


def check_handwriting_confidence(receipts, threshold=HANDWRITING_CONF_MIN):
    low = []
    for r in receipts:
        hw = (r.get("handwriting") or "").strip()
        if hw:
            conf = r.get("hw_confidence")
            if conf is None or conf < threshold:
                low.append({"id": r.get("id"), "handwriting": hw, "hw_confidence": conf})
    return (FAIL, f"low-confidence handwriting → escalate: {low}") if low else (PASS, "handwriting confidence OK / none")


def check_consensus(vote_audit, multiread_expected=True):
    """★G4: multi-read consensus = ocr-vote-audit.json result == 'CONSENSUS' (the aggregate_ocr_votes
    output). NOT verify_ocr_consistency.compare (dual-read pairwise diff only).
    ★MED#8 fail-closed: if multi-read was EXPECTED (the suite does 3→7 voting) but the audit is
    absent/empty/malformed → ERROR (cannot certify consensus). Only a genuine single-read (by design)
    is a deliberate N/A-SKIP."""
    if not vote_audit:
        if multiread_expected:
            return ERROR, "multi-read expected but ocr-vote-audit.json absent/empty — cannot certify consensus"
        return SKIP, "single-read by design (deliberate N/A)"
    res = vote_audit.get("result")
    if res is None:
        return ERROR, f"vote-audit malformed (no 'result' key): {vote_audit}"
    return (PASS, f"vote consensus over {vote_audit.get('reads')} reads") if res == "CONSENSUS" \
        else (FAIL, f"OCR not at consensus (result={res}) — re-read/escalate")


def load_vote_files(run_dir):
    """V6-WIRING/V6-SCHEMA: additive DUAL-FILE read of BOTH vote outputs from disk (producer contract
    unchanged — verify only reads what the vote producer already writes). Returns
    (audit, report, n_reads_on_disk); a present-but-unparseable file → 'MALFORMED'."""
    run_dir = Path(run_dir)

    def _read(name):
        p = run_dir / name
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return "MALFORMED"
    audit = _read("ocr-vote-audit.json")
    report = _read("ocr-vote-report.json")
    n_reads = len(list(run_dir.glob("ocr-results-*.json")))     # derive multiread from the on-disk read count
    return audit, report, n_reads


def check_consensus_disk(run_dir, expected_week):
    """V6-WIRING + V6-SCHEMA (fail-closed): derive multi-read consensus FROM DISK, not a caller boolean.
    - multiread_expected ⇐ on-disk count of ocr-results-*.json (≥2 ⇒ multi-read this run).
    - dual-file: a present ocr-vote-report.json with result != CONSENSUS ⇒ FAIL (vote did NOT reach
      consensus); a present ocr-vote-audit.json must be result==CONSENSUS, week==expected, reads≥MIN_READS.
    - week mismatch (stale audit/report) ⇒ ERROR (a stale CONSENSUS can't satisfy THIS run).
    - multi-read expected but no audit ⇒ ERROR; a genuine single-read (count<2, no files) ⇒ N/A-SKIP."""
    audit, report, n_reads = load_vote_files(run_dir)
    multiread_expected = n_reads >= 2
    if audit == "MALFORMED" or report == "MALFORMED":
        return ERROR, f"vote file malformed JSON in {run_dir} — cannot certify consensus (fail-closed)"
    if report is not None:                                          # an INCONCLUSIVE report present ⇒ not consensus
        if report.get("week") not in (None, expected_week):
            return ERROR, f"stale vote-report week={report.get('week')} != expected {expected_week} (fail-closed)"
        if report.get("result") != "CONSENSUS":
            return FAIL, f"ocr-vote-report.json present result={report.get('result')} — OCR did NOT reach consensus"
    if not audit:
        if multiread_expected:
            return ERROR, (f"multi-read expected ({n_reads} reads on disk) but ocr-vote-audit.json absent/empty "
                           f"— cannot certify consensus")
        return SKIP, f"single-read by design ({n_reads} read(s) on disk; deliberate N/A)"
    if audit.get("week") != expected_week:
        return ERROR, f"stale vote-audit week={audit.get('week')} != expected {expected_week} (a stale CONSENSUS cannot satisfy)"
    if audit.get("result") != "CONSENSUS":
        return FAIL, f"vote-audit result={audit.get('result')} (not CONSENSUS)"
    reads = audit.get("reads")
    if not isinstance(reads, int) or reads < MIN_READS:
        return ERROR, f"vote-audit reads={reads} < MIN_READS={MIN_READS} — insufficient to certify consensus (fail-closed)"
    return PASS, f"disk vote consensus: {reads} reads, week={expected_week}, CONSENSUS"


def check_no_card(receipts, card_records):
    """V2-NOCARD (escalation severity, NOT hard FAIL): a receipt that consumes NO card row is SURFACED
    for owner review UNLESS its sector legitimately has no card (PARKING/TOLLS, TELEPHONE-LOCAL = separate
    card). ★MUST NOT false-FAIL legit cash/toll/telephone — optional sectors are allowed; every other
    no-card receipt is an escalation (possible cash OR a missing card row — owner decides), never a silent
    pass. Read-only: builds its own fresh pool (does not perturb V2's consume state)."""
    if parse_date is None:
        return ERROR, "date normalizer unavailable (extract_card import failed) — cannot determine no-card receipts (fail-closed)"
    pool = build_card_pool(card_records)
    escalate = []
    for r in receipts:
        if r is None:
            continue
        rd, ra = _norm_date(r.get("date")), _norm_amount(r.get("amount"))
        hit = next((c for c in pool if not c["consumed"] and c["amount"] is not None
                    and c["date"] == rd and c["amount"] == ra), None)
        if hit:
            hit["consumed"] = True
        elif r.get("sector") not in _BIZ_OPTIONAL_SECTORS:         # cash/toll/telephone legitimately no-card
            escalate.append({"id": r.get("id"), "sector": r.get("sector"), "amount": r.get("amount")})
    return (FAIL, f"no-card receipt(s) outside {sorted(_BIZ_OPTIONAL_SECTORS)} → escalate (cash? missing card row?): {escalate}") \
        if escalate else (PASS, "no-card receipts all legit (toll/telephone) or all card-matched")


def check_biz_agreement(receipts, card_records):
    """V1-AGREEMENT: for every card-MATCHED receipt, receipt.biz_no must EQUAL the consumed card row's
    사업자번호 (NFC). A checksum-VALID but DIFFERENT biz on the matched card is an identity mismatch (wrong
    store / swapped card) that V1's per-number checksum cannot catch → FAIL. Read-only fresh pool."""
    if parse_date is None:
        return ERROR, "date normalizer unavailable (extract_card import failed) — cannot match for biz agreement (fail-closed)"
    pool = build_card_pool(card_records)
    mism = []
    for r in receipts:
        if r is None:
            continue
        rd, ra = _norm_date(r.get("date")), _norm_amount(r.get("amount"))
        hit = next((c for c in pool if not c["consumed"] and c["amount"] is not None
                    and c["date"] == rd and c["amount"] == ra), None)
        if not hit:
            continue
        hit["consumed"] = True
        rbiz = unicodedata.normalize("NFC", str(r.get("biz_no"))).strip() if r.get("biz_no") else None
        cbiz = hit.get("biz_no")
        if rbiz and cbiz and rbiz != cbiz:
            mism.append({"id": r.get("id"), "receipt_biz": rbiz, "card_biz": cbiz})
    return (FAIL, f"receipt biz_no != matched card 사업자번호 (identity mismatch): {mism}") if mism \
        else (PASS, "card-matched receipts agree with card 사업자번호 (or biz absent)")


def check_handwriting_consensus(receipts, reads=None, threshold=HANDWRITING_CONF_MIN):
    """V5 (hardened): the trustworthy handwriting signal is cross-read DISAGREEMENT (deterministic, from
    the per-read OCR results on disk) — NOT a model-supplied hw_confidence scalar. Per receipt carrying
    handwriting: reads disagree on it ⇒ escalate. With NO cross-read evidence, fall back to the None→FAIL
    floor (handwriting present + hw_confidence None/below-threshold ⇒ FAIL — never silently trust a bare scalar)."""
    by_id = {}
    if reads:
        for read in reads:
            for r in (read or []):
                if r is None:
                    continue
                by_id.setdefault(r.get("id"), []).append((r.get("handwriting") or "").strip())
    low = []
    for r in receipts:
        if r is None:
            continue
        hw = (r.get("handwriting") or "").strip()
        if not hw:
            continue
        rid = r.get("id")
        if reads and rid in by_id:
            if len(set(by_id[rid])) > 1:                          # cross-read DISAGREEMENT (deterministic)
                low.append({"id": rid, "handwriting": hw, "read_variants": sorted(set(by_id[rid]))})
        else:                                                     # no cross-read evidence → None→FAIL floor
            conf = r.get("hw_confidence")
            if conf is None or conf < threshold:
                low.append({"id": rid, "handwriting": hw, "hw_confidence": conf})
    return (FAIL, f"handwriting low-trust (cross-read disagreement / no-confidence floor) → escalate: {low}") if low \
        else (PASS, "handwriting cross-read agreement / high confidence / none")


def v3_applicable(receipts):
    """V3-INERT: V3 (item-sum) applicability DERIVED FROM DATA — True iff some receipt carries line items.
    A vacuous SKIP (no items produced upstream this round) is N/A, NOT a passed check (doc-honesty: V3 is
    not counted toward the gate's passed-check total when inapplicable)."""
    return any(r.get("items") for r in (receipts or []) if r is not None)


def check_rule_consistency(receipts, store_db=None, name_db=None, card_pool=None, confirmed=None):
    """req#7: every assigned sector is a valid SPEC sector (always checkable), and where the store-DB is
    confident the assignment must not contradict the classify rules (IMPORT classify_receipt).
    ★Fail-closed: the contradiction arm is MANDATORY — if the classify producer is absent (CRIT#2) or
    store_db was not provided (HIGH#6, the run_logical default), it CANNOT run → ERROR (never a silent
    PASS that lets a wrong sector through). store_db={} (cold-start, no learned stores) IS runnable:
    classify simply finds no confident store and 0 contradictions."""
    invalid = [r.get("id") for r in receipts if r.get("sector") not in VALID_SECTORS]
    if invalid:
        return FAIL, f"sector not in the 6 valid sectors: {invalid}"
    if classify_receipt is None:
        return ERROR, "classify producer unavailable (-classify not importable) — rule contradiction NOT checked"
    if store_db is None:
        return ERROR, "store_db not provided — store-confident contradiction NOT checked (master must pass store_db)"
    confirmed = confirmed or {}
    # V7: replay classify in the SAME date/time order the real run used, ACCUMULATING dinner_dates (G9) —
    # so a same-date 2nd dinner is judged with the real prior-dinner context, not an empty set per receipt.
    ordered = sorted(receipts, key=lambda r: (str(_norm_date(r.get("date"))), str(r.get("time"))))
    dinner_dates = set()
    contradictions = []
    for r in ordered:
        d = classify_receipt(r, store_db, name_db or {}, [dict(c) for c in (card_pool or [])], dinner_dates)
        assigned, rid = r.get("sector"), r.get("id")
        if d.get("escalate"):
            # V7: an escalated receipt the owner later CONFIRMED — the assigned sector MUST equal the confirm
            if rid in confirmed and assigned and assigned != confirmed[rid]:
                contradictions.append({"id": rid, "assigned": assigned, "confirmed": confirmed[rid],
                                       "kind": "escalated-confirmed-disagreement"})
        elif d.get("sector") and assigned and d["sector"] != assigned:   # concrete-rule contradiction
            contradictions.append({"id": rid, "assigned": assigned, "rule": d["sector"]})
        if d.get("registers_dinner") or assigned == "Dinner":            # mirror run() dinner_dates (G9)
            dinner_dates.add(_norm_date(r.get("date")))
    return (FAIL, f"sector contradicts classify rules: {contradictions}") if contradictions \
        else (PASS, "all sectors valid and rule-consistent")


# ============================================================ G6 entry points
def run_logical(receipts, card_records=None, vote_audit=None, store_db=None, name_db=None,
                multiread_expected=True, sales_slips=None, report_path=None,
                run_dir=None, expected_week=None, confirmed=None, reads=None):
    """★G6 pre-placement LOGICAL gate. Read-only; writes ONLY the JSON report (if report_path given).
    ★Fail-closed: ERROR (unrun mandatory check) ⇒ verdict ERROR / exit 1. The master must pass store_db
    (even {} at cold-start) and the real vote-audit; producers must be importable, or the gate STOPS.
    ★Batch C verify-HALF: when run_dir+expected_week are given, V6 derives consensus FROM DISK (dual-file
    audit+report, multiread from the on-disk read count) and V5 keys off cross-read disagreement — so a
    MANDATORY check's applicability is derived from disk, not a caller boolean (V6-V3-CALLER-N/A). The
    orchestrator passing run_dir is Batch F (DEFERRED). The JSON report surfaces _REUSED, per-check kind
    (ran / n/a-skip / error), and v3_applicable (V3-INERT doc-honesty)."""
    card_pool = build_card_pool(card_records)
    if run_dir is not None:                                         # disk-derived (verify-half) path
        v6 = lambda: check_consensus_disk(run_dir, expected_week)
        v5 = lambda: check_handwriting_consensus(receipts, reads)
    else:                                                          # back-compat caller-passed path
        v6 = lambda: check_consensus(vote_audit, multiread_expected)
        v5 = lambda: check_handwriting_confidence(receipts)
    checks = [
        ("V1", "business-number NTS checksum", lambda: check_biz_checksum(receipts), "violation"),
        ("V1b", "business-number presence (escalate if absent on card-matched)", lambda: check_biz_presence(receipts), "warning"),
        ("V1c", "biz_no == matched card 사업자번호 (V1-AGREEMENT)", lambda: check_biz_agreement(receipts, card_records), "violation"),
        ("V2", "card (date,amount) cross-match", lambda: check_card_match(receipts, card_pool, sales_slips), "violation"),
        ("V2b", "no-card receipt surfacing (V2-NOCARD escalation)", lambda: check_no_card(receipts, card_records), "warning"),
        ("V3", "item-sum == card amount", lambda: check_item_sum(receipts), "violation"),
        ("V4", "amount != 0", lambda: check_amount_nonzero(receipts), "violation"),
        ("V5", "handwriting confidence", v5, "violation"),
        ("V6", "multi-read consensus (vote-audit)", v6, "violation"),
        ("V7", "rule consistency", lambda: check_rule_consistency(receipts, store_db, name_db, card_pool, confirmed), "violation"),
    ]
    results = _run(checks)
    verdict, code = _verdict(results)
    report = {"gate": "LOGICAL", "verdict": verdict, "reused": dict(_REUSED),
              "v3_applicable": v3_applicable(receipts),            # V3-INERT: applicability derived from data
              "checks": [r.to_dict() for r in results]}
    if report_path:
        _write_json(report_path, report)
    return code, report


def run_physical(placed_xlsx, baseline_counts, expected_pics, report_path=None):
    """★G6 post-placement PHYSICAL gate (read-only) on the placed xlsx — IMPORT -place primitives.
    ★HIGH#4 fail-closed: if -place is not importable the physical gate CANNOT run → ERROR / exit 1
    (never a silent (0, SKIP) that lets an unverified placed workbook through)."""
    if zip_drawing_counts is None or physical_verify is None:
        results = [Result("P0", "expensereceipt-place producer", ERROR,
                          "-place not importable — PHYSICAL gate cannot run (fail-closed)")]
        verdict, code = _verdict(results)
        report = {"gate": "PHYSICAL", "verdict": verdict, "reused": dict(_REUSED),
                  "checks": [r.to_dict() for r in results]}
        if report_path:
            _write_json(report_path, report)
        return code, report
    pv = physical_verify(placed_xlsx, expected_pics, baseline_counts)
    # PHYSICAL-CHECKS (fail-closed): a MISSING expected pv key must be an ERROR, NOT a silent FAIL via
    # pv.get(...) defaulting to a falsy → so assert every expected key is present first.
    expected_keys = ("pic_delta_ok", "anchors_not_lost", "rdr_preserved", "row_cell_consistent", "openpyxl_reopen")
    missing = [k for k in expected_keys if k not in pv]
    if missing:
        results = [Result("P0", "physical_verify key completeness", ERROR,
                          f"physical_verify missing expected keys {missing} — cannot certify placement (fail-closed)")]
        verdict, code = _verdict(results)
        report = {"gate": "PHYSICAL", "verdict": verdict, "reused": dict(_REUSED), "checks": [r.to_dict() for r in results]}
        if report_path:
            _write_json(report_path, report)
        return code, report
    # INDEPENDENTLY recompute the pic-count delta (do not solely trust pv's flag).
    try:
        indep_delta = zip_drawing_counts(placed_xlsx).get("pic", 0) - (baseline_counts or {}).get("pic", 0)
        indep_ok = (indep_delta == expected_pics)
    except Exception as e:
        results = [Result("P0", "independent pic-delta recompute", ERROR, f"zip_drawing_counts failed: {e} (fail-closed)")]
        verdict, code = _verdict(results)
        report = {"gate": "PHYSICAL", "verdict": verdict, "reused": dict(_REUSED), "checks": [r.to_dict() for r in results]}
        if report_path:
            _write_json(report_path, report)
        return code, report
    results = [
        Result("P1", "injected <pic> count == receipts (independent recompute)",
               PASS if (pv["pic_delta_ok"] and indep_ok) else FAIL,
               {"pv_pic_delta_ok": pv["pic_delta_ok"], "independent_pic_delta": indep_delta, "expected": expected_pics}),
        Result("P2", "twoCellAnchors preserved", PASS if pv["anchors_not_lost"] else FAIL, ""),
        Result("P3", "RDR <sp> preserved", PASS if pv["rdr_preserved"] else FAIL, ""),
        Result("P4", "row/cell consistency (no desync)", PASS if pv["row_cell_consistent"] else FAIL, ""),
        Result("P5", "openpyxl no-repair re-open (proxy)", PASS if pv["openpyxl_reopen"] else FAIL, ""),
    ]
    verdict, code = _verdict(results)
    report = {"gate": "PHYSICAL", "verdict": verdict, "reused": dict(_REUSED),
              "checks": [r.to_dict() for r in results]}
    if report_path:
        _write_json(report_path, report)
    return code, report


def _write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if "--selftest" in args:
        return _selftest()
    print(__doc__)
    return 0


# ============================================================ 실측 SELF-TEST (each check PASS + FAIL direction)
def _exls_for_test():
    """WK23 KICC reproduction with a ★SYNTHETIC in-memory card list — the selftest NEVER opens the real
    input .xls (input-isolation fix: the real card file is OLE-format and was externally mutated when its
    directory was accessed; selftests must not touch raw-data/input). The 5 WK23-shaped card rows (4 with
    normal receipts + KICC via 매출전표) all consume → V2 PASS. Returns the V2 status (PASS expected)."""
    cards = [
        {"date": "2026-06-04", "amount": 9500, "raw": {"승인번호": "50652117", "카드번호": "3792-******-**321"}},
        {"date": "2026-06-04", "amount": 8300, "raw": {"승인번호": "00200038"}},
        {"date": "2026-06-02", "amount": 8700, "raw": {"승인번호": "00400076"}},
        {"date": "2026-06-01", "amount": 22800, "raw": {"승인번호": "62502113"}},
        {"date": "2026-06-02", "amount": 3300, "raw": {"승인번호": "41777115", "카드번호": "3792-******-**321"}},
    ]
    receipts = [{"id": "r1", "date": "2026-06-04", "amount": 9500}, {"id": "r2", "date": "2026-06-04", "amount": 8300},
                {"id": "r3", "date": "2026-06-02", "amount": 8700}, {"id": "r4", "date": "2026-06-01", "amount": 22800}]
    slip = [{"approval": "41777115", "amount": 3300}]   # the OCR'd KICC 매출전표
    return check_card_match(receipts, build_card_pool(cards), sales_slips=slip)[0]


def _selftest():
    ok = True

    def check(label, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    # real-ish receipts (biz numbers are genuine valid ones from store-db.json)
    good = [
        {"id": "R1", "store": "스팟마트", "date": "2026-06-02", "amount": 5000, "people": 1,
         "biz_no": "119-81-00851", "handwriting": "dinner alone", "hw_confidence": 0.95, "sector": "Dinner"},
        {"id": "R2", "store": "폴바셋", "date": "2026-06-03", "amount": 24000, "people": 3,
         "biz_no": "220-81-15770", "handwriting": "", "hw_confidence": None, "sector": "STAFF MEETING"},
    ]
    cards = [
        {"date": "2026-06-02", "amount": 5000, "raw": {"사업자번호": "119-81-00851", "가맹점명": "스팟마트"}},
        {"date": "2026-06-03", "amount": 24000, "raw": {"사업자번호": "220-81-15770", "가맹점명": "폴바셋"}},
    ]
    vote_ok = {"result": "CONSENSUS", "reads": 3}

    # --- V1 biz checksum: PASS then FAIL ---
    check("V1 PASS: valid biz numbers", check_biz_checksum(good)[0] == PASS)
    check("V1 FAIL: corrupted biz number caught",
          check_biz_checksum([{**good[0], "biz_no": "119-81-00852"}])[0] == FAIL)
    check("V1 reused real producer validate_biz_no", _REUSED["merchant"] is True)

    # --- V2 card match + ★G1 canceled-row defensive ---
    check("V2 PASS: all cards consumed", check_card_match(good, build_card_pool(cards))[0] == PASS)
    check("V2 FAIL: unconsumed card (extra card row) → reimbursement-loss",
          check_card_match([good[0]], build_card_pool(cards))[0] == FAIL)
    cancel_cards = cards + [{"date": "2026-06-04", "amount": 9000,
                             "raw": {"사업자번호": "201-81-21515", "취소여부": "Y"}}]
    pool_excl = build_card_pool(cancel_cards)
    check("★G1: canceled card row (취소여부=Y) excluded from pool", len(pool_excl) == 2)
    check("★G1: canceled row does NOT become an unconsumed FAIL",
          check_card_match(good, build_card_pool(cancel_cards))[0] == PASS)
    check("★G1: key-absent ⇒ not-canceled (no false drop)", is_canceled({"가맹점명": "X"}) is False)
    check("★G1: alternate cancel value '취소' detected", is_canceled({"거래구분": "취소"}) is True)
    check("★G3: biz read via 사업자번호 raw key (NFC)", build_card_pool(cards)[0]["raw"].get("사업자번호") == "119-81-00851")

    # --- ★KICC 매출전표 replacement-receipt (machine broke → card-company slip = valid receipt; master-approved) ---
    kicc_cards = [{"date": "2026-06-02", "amount": 3300,
                   "raw": {"사업자번호": "116-81-19948", "승인번호": "41777115",
                           "카드번호": "3792-******-**321", "가맹점명": "세외수입_KICC(현장)"}}]
    slip = [{"approval": "41777115", "amount": 3300, "card_last": "321", "source": "매출전표"}]
    check("★KICC: 매출전표 (승인번호+amount match) consumes the otherwise-receiptless card row → V2 PASS",
          check_card_match([], build_card_pool(kicc_cards), sales_slips=slip)[0] == PASS)
    check("★KICC NON-VACUOUS: stray slip (승인번호 99999999 not in statement) → REJECTED, card row still FAIL",
          check_card_match([], build_card_pool(kicc_cards), sales_slips=[{"approval": "99999999", "amount": 3300}])[0] == FAIL)
    check("★KICC tamper: 승인번호 matches but amount differs → REJECTED (no consume), card row FAIL",
          check_card_match([], build_card_pool(kicc_cards), sales_slips=[{"approval": "41777115", "amount": 9999}])[0] == FAIL)
    _dcpool = build_card_pool([{"date": "2026-06-02", "amount": 3300, "raw": {"승인번호": "41777115"}}])
    check_card_match([{"id": "RX", "date": "2026-06-02", "amount": 3300}], _dcpool, sales_slips=slip)
    check("★KICC ① no-double-consume: row consumed by the normal receipt, slip does NOT re-consume",
          _dcpool[0]["consumed"] and _dcpool[0]["consumed_by"][0] == "receipt")
    check("★None-amount guard: receipt amount None → V2 ERROR (fail-closed; no None==None false-match)",
          check_card_match([{"id": "rn", "date": "2026-06-02", "amount": None}], build_card_pool(kicc_cards))[0] == ERROR)
    check("★None-amount guard: card amount None → V2 ERROR",
          check_card_match([], build_card_pool([{"date": "2026-06-02", "amount": None, "raw": {}}]))[0] == ERROR)
    check("★None-amount guard: slip amount None → V2 ERROR (not a None==None consume)",
          check_card_match([], build_card_pool(kicc_cards), sales_slips=[{"approval": "41777115", "amount": None}])[0] == ERROR)
    _rc = _exls_for_test()
    check("★real WK23: 4 receipts + KICC 매출전표 → all 5 card rows consumed → V2 PASS (was FAIL in M9)",
          _rc == PASS)

    # --- V3 item-sum ---
    check("V3 SKIP: no line items", check_item_sum(good)[0] == SKIP)
    check("V3 PASS: items sum to amount",
          check_item_sum([{"id": "R", "amount": 9000, "items": [4000, 5000]}])[0] == PASS)
    check("V3 FAIL: items mismatch amount",
          check_item_sum([{"id": "R", "amount": 9000, "items": [4000, 4000]}])[0] == FAIL)

    # --- V4 amount != 0 ---
    check("V4 PASS: non-zero amounts", check_amount_nonzero(good)[0] == PASS)
    check("V4 FAIL: amount 0 caught", check_amount_nonzero([{**good[0], "amount": 0}])[0] == FAIL)
    check("V4 FAIL: amount None caught", check_amount_nonzero([{**good[0], "amount": None}])[0] == FAIL)

    # --- V5 handwriting confidence ---
    check("V5 PASS: high-confidence/empty handwriting", check_handwriting_confidence(good)[0] == PASS)
    check("V5 FAIL: handwriting present but low confidence → escalate",
          check_handwriting_confidence([{**good[0], "handwriting": "홍길동", "hw_confidence": 0.3}])[0] == FAIL)
    check("V5 FAIL: handwriting present, confidence None → escalate",
          check_handwriting_confidence([{**good[0], "handwriting": "홍길동", "hw_confidence": None}])[0] == FAIL)

    # --- V6 ★G4 consensus from vote-audit (NOT compare) ---
    check("V6 PASS: vote-audit CONSENSUS", check_consensus(vote_ok)[0] == PASS)
    check("V6 FAIL: vote-audit INCONCLUSIVE", check_consensus({"result": "INCONCLUSIVE", "reads": 7})[0] == FAIL)
    check("V6 N/A-SKIP: genuine single-read (multiread_expected=False)",
          check_consensus(None, multiread_expected=False)[0] == SKIP)

    # --- V7 rule consistency ---
    check("V7 PASS: valid sectors (store_db provided)", check_rule_consistency(good, store_db={})[0] == PASS)
    check("V7 FAIL: invalid sector caught",
          check_rule_consistency([{**good[0], "sector": "NONSENSE"}])[0] == FAIL)
    check("V7 reused real classify producer", _REUSED["classify"] is True)

    # --- gate runner verdict + read-only (JSON report only) ---
    import tempfile
    work = Path(tempfile.mkdtemp(prefix="verify_self_"))
    code, rep = run_logical(good, cards, vote_ok, store_db={}, report_path=work / "verify-logical.json")
    check("LOGICAL gate: clean data → verdict PASS, exit 0", code == 0 and rep["verdict"] == PASS)
    check("LOGICAL gate: JSON report written (read-only, no workbook)", (work / "verify-logical.json").exists())
    bad_code, bad_rep = run_logical([{**good[0], "amount": 0, "biz_no": "119-81-00852"}], cards, vote_ok, store_db={})
    check("LOGICAL gate: bad data → verdict FAIL, exit 1", bad_code == 1 and bad_rep["verdict"] == FAIL)
    check("LOGICAL gate: only the JSON report exists in workdir (no FAIL.xlsx, read-only)",
          [p.name for p in work.iterdir()] == ["verify-logical.json"])

    # --- ★G6 PHYSICAL gate against a placed xlsx (IMPORT -place) — STAGED template + SYNTHETIC image
    #     (input-isolation: selftests NEVER read raw-data/input; stage via EXPR_INPUT_STAGE post-restore) ---
    if _REUSED["place"]:
        import importlib
        place = importlib.import_module("expensereceipt_place")
        tmpl = place._staged_input("simon_park_T&E_WK00_2026.xlsx")
        if tmpl:
            from PIL import Image as _PImg
            img0 = work / "r.png"
            _PImg.new("RGB", (80, 120), (210, 210, 210)).save(img0)
            out = work / "placed.xlsx"
            baseline = place.zip_drawing_counts(tmpl)
            place.place(tmpl, out, [{"img_path": str(img0), "from": (1, 0, 130, 0), "to": (4, 0, 148, 0)}])
            pcode, prep = run_physical(out, baseline, 1, report_path=work / "verify-physical.json")
            check("★G6 PHYSICAL: placed xlsx (pic+1) → verdict PASS, exit 0", pcode == 0 and prep["verdict"] == PASS)
            check("★G6 PHYSICAL: pic-count + anchor + row/cell + no-repair all PASS",
                  all(c["status"] == PASS for c in prep["checks"]))
        else:
            check("★G6 PHYSICAL (skipped — no staged template; stage via EXPR_INPUT_STAGE post-restore)", True)
    else:
        check("★G6 PHYSICAL (skipped — -place not importable)", True)

    # =============== ★FAIL-CLOSED hardening — each unrun-MANDATORY path now BLOCKS (not greens) ===============
    V = sys.modules[__name__]   # the RUNNING module (so monkeypatches affect the live globals the checks read)

    # (a) injected check-exception → ERROR · exit≠0 (a None receipt makes mandatory checks raise)
    a_code, a_rep = run_logical([None], cards, vote_ok, store_db={})
    check("(a) injected check-exception → verdict ERROR, exit≠0 (not green)", a_code != 0 and a_rep["verdict"] == ERROR)
    check("(a) _run maps a raising check to ERROR (not SKIP)",
          _run([("X", "x", lambda: (_ for _ in ()).throw(ValueError("boom")), "violation")])[0].status == ERROR)

    # (b) validate_biz_no producer absent → ERROR + _REUSED surfaced
    _orig = V.validate_biz_no
    V.validate_biz_no = None
    try:
        check("(b) validate_biz_no absent → V1 ERROR (no weak-fallback certify)", check_biz_checksum(good)[0] == ERROR)
        b_code, b_rep = run_logical(good, cards, vote_ok, store_db={})
        check("(b) producer-absent → gate verdict ERROR, exit≠0", b_code != 0 and b_rep["verdict"] == ERROR)
        check("(b) report surfaces _REUSED (producer provenance)", "reused" in b_rep)
    finally:
        V.validate_biz_no = _orig

    # (c) classify_receipt=None → V7 ERROR (no silent genuine PASS)
    _origc = V.classify_receipt
    V.classify_receipt = None
    try:
        check("(c) classify producer absent → V7 ERROR (not silent PASS)", check_rule_consistency(good, store_db={})[0] == ERROR)
    finally:
        V.classify_receipt = _origc

    # (d) -place not importable → run_physical ERROR · exit≠0 (not (0,SKIP))
    _origz = V.zip_drawing_counts
    V.zip_drawing_counts = None
    try:
        d_code, d_rep = run_physical("anything.xlsx", {}, 1)
        check("(d) -place absent → PHYSICAL verdict ERROR, exit≠0", d_code != 0 and d_rep["verdict"] == ERROR)
    finally:
        V.zip_drawing_counts = _origz

    # (e) store_db=None but contradiction expected → ERROR (loud), not silent PASS
    check("(e) store_db=None → V7 ERROR (contradiction not silently skipped)",
          check_rule_consistency(good, store_db=None)[0] == ERROR)

    # (f) multi-read expected but vote-audit absent/malformed → ERROR
    check("(f) multiread expected + vote-audit absent → V6 ERROR", check_consensus(None, multiread_expected=True)[0] == ERROR)
    check("(f) vote-audit malformed (no 'result') → V6 ERROR", check_consensus({"reads": 3})[0] == ERROR)

    # (g) biz_no absent on a card-matched non-toll/tel receipt → escalate (V1b warning)
    check("(g) biz_no absent on card-matched meal → escalate (V1b FAIL/warning)",
          check_biz_presence([{"id": "G", "sector": "Dinner", "card_match": "MATCHED", "amount": 5000}])[0] == FAIL)
    check("(g) biz_no legitimately absent on TOLLS/cash → not flagged",
          check_biz_presence([{"id": "T", "sector": "PARKING/TOLLS", "card_match": "NO_CARD", "amount": 3300}])[0] == PASS)

    # (h) None line-item amount → ERROR (not coerced to 0)
    check("(h) None line-item amount → V3 ERROR (no 0-coerce hiding)",
          check_item_sum([{"id": "H", "amount": 9000, "items": [None, 5000]}])[0] == ERROR)

    # --- regression: deliberate N/A stays clean (no over-correction) ---
    check("regression: V3 no items → N/A-SKIP (clean)", check_item_sum(good)[0] == SKIP)
    check("regression: V6 single-read → N/A-SKIP (clean)", check_consensus(None, multiread_expected=False)[0] == SKIP)
    reg_code, reg_rep = run_logical(good, cards, vote_ok, store_db={}, multiread_expected=True)
    check("regression: clean data still verdict PASS exit 0 (N/A-skips don't block)",
          reg_code == 0 and reg_rep["verdict"] == PASS)
    check("regression: per-check kind surfaced (ran / n/a-skip / error)", all("kind" in c for c in reg_rep["checks"]))
    check("regression: _REUSED surfaced in report", "reused" in reg_rep)

    # =============== ★BATCH C — verify gate hardening (non-vacuous: each FAIL pre-fix / PASS post-fix) ===============
    def _wk_dir(files):
        d = Path(tempfile.mkdtemp(prefix="verify_bc_"))
        for nm, obj in files.items():
            (d / nm).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        return d
    _reads3 = {"ocr-results-1.json": {}, "ocr-results-2.json": {}, "ocr-results-3.json": {}}

    # --- V6-WIRING: check_consensus LOADs from disk, week-assert, reads≥MIN_READS, multiread from disk count ---
    d_ok = _wk_dir({"ocr-vote-audit.json": {"week": "WK21_2026", "reads": 3, "result": "CONSENSUS", "receipts": 5}, **_reads3})
    check("V6-WIRING: disk vote-audit CONSENSUS (week match, 3 reads) → PASS", check_consensus_disk(d_ok, "WK21_2026")[0] == PASS)
    check("V6-WIRING: wrong-week vote-audit on disk → ERROR (fail-closed)", check_consensus_disk(d_ok, "WK99_2026")[0] == ERROR)
    check("V6-WIRING: multiread expected (3 reads on disk) but audit absent → ERROR",
          check_consensus_disk(_wk_dir(dict(_reads3)), "WK21_2026")[0] == ERROR)
    check("V6-WIRING: reads < MIN_READS (audit reads=2) → ERROR",
          check_consensus_disk(_wk_dir({"ocr-vote-audit.json": {"week": "WK21_2026", "reads": 2, "result": "CONSENSUS"}, **_reads3}), "WK21_2026")[0] == ERROR)
    check("V6-WIRING: genuine single-read (1 read file, no audit) → N/A-SKIP (clean)",
          check_consensus_disk(_wk_dir({"ocr-results-1.json": {}}), "WK21_2026")[0] == SKIP)
    # --- V6-SCHEMA: additive dual-file (audit + report); INCONCLUSIVE report → FAIL; stale week → ERROR ---
    check("V6-SCHEMA: INCONCLUSIVE ocr-vote-report.json present → FAIL",
          check_consensus_disk(_wk_dir({"ocr-vote-report.json": {"week": "WK21_2026", "reads": 7, "result": "INCONCLUSIVE", "unresolved": ["x"]}, **_reads3}), "WK21_2026")[0] == FAIL)
    check("V6-SCHEMA: stale-week CONSENSUS audit (week != expected) → ERROR (a stale CONSENSUS cannot satisfy)",
          check_consensus_disk(_wk_dir({"ocr-vote-audit.json": {"week": "WK20_2026", "reads": 3, "result": "CONSENSUS"}, **_reads3}), "WK21_2026")[0] == ERROR)
    _dmal = Path(tempfile.mkdtemp(prefix="verify_bc_"))
    (_dmal / "ocr-vote-audit.json").write_text("{bad json", encoding="utf-8")
    (_dmal / "ocr-results-1.json").write_text("{}", encoding="utf-8")
    check("V6-SCHEMA: malformed vote file → ERROR", check_consensus_disk(_dmal, "WK21_2026")[0] == ERROR)
    # ★ANCHOR#2a via the disk path: a forced disk ERROR yields gate verdict ≠ PASS (exit ≠ 0)
    wc_code, wc_rep = run_logical(good, cards, store_db={}, run_dir=str(d_ok), expected_week="WK99_2026")
    check("★ANCHOR#2a: disk wrong-week → run_logical verdict ERROR, exit≠0 (fail-closed gate)",
          wc_code != 0 and wc_rep["verdict"] == ERROR)
    ok_code, ok_rep = run_logical(good, cards, store_db={}, run_dir=str(d_ok), expected_week="WK21_2026")
    check("★ANCHOR#2a: disk correct-week consensus → gate PASS exit 0", ok_code == 0 and ok_rep["verdict"] == PASS)

    # --- V2-NOCARD: no-card meal → escalate; cash/toll/telephone NOT false-FAILed ---
    check("V2-NOCARD: no-card MEAL → escalate (surfaced FAIL, not silent pass)",
          check_no_card([{"id": "m1", "date": "2026-06-09", "amount": 12000, "sector": "Dinner"}], cards)[0] == FAIL)
    check("V2-NOCARD: no-card TOLL → NOT false-FAIL (legit separate card)",
          check_no_card([{"id": "t1", "date": "2026-06-09", "amount": 3300, "sector": "PARKING/TOLLS"}], cards)[0] == PASS)
    check("V2-NOCARD: no-card TELEPHONE → NOT false-FAIL",
          check_no_card([{"id": "p1", "date": "2026-06-09", "amount": 55000, "sector": "TELEPHONE-LOCAL"}], cards)[0] == PASS)
    _nc_rep = run_logical([{"id": "m2", "date": "2026-06-09", "amount": 12000, "sector": "Dinner"}], [], vote_ok, store_db={})[1]
    _v2b = next((c for c in _nc_rep["checks"] if c["id"] == "V2b"), None)
    check("V2-NOCARD: no-card meal surfaced as V2b warning severity (escalation, not a hard exit-block)",
          _v2b is not None and _v2b["status"] == FAIL and _v2b["severity"] == "warning")

    # --- V2-AMOUNT: canonical normalizer (str/float/refund) ---
    check("V2-AMOUNT: '5,000' / '5000원' → int 5000", _norm_amount("5,000") == 5000 and _norm_amount("5000원") == 5000)
    check("V2-AMOUNT: float 5000.0 → 5000", _norm_amount(5000.0) == 5000)
    check("V2-AMOUNT: negative/refund flagged", _is_refund("-3300") is True and _is_refund(5000) is False)
    check("V2-AMOUNT: str-amount receipt matches str-amount card after normalization → V2 PASS",
          check_card_match([{"id": "sa", "date": "2026-06-02", "amount": "5,000"}],
                           build_card_pool([{"date": "2026-06-02", "amount": "5000", "raw": {}}]))[0] == PASS)

    # --- V1-AGREEMENT: matched receipt biz_no == card 사업자번호 (NFC) ---
    check("V1-AGREEMENT: checksum-valid but MISMATCHED biz on matched card → FAIL",
          check_biz_agreement([{"id": "ba", "date": "2026-06-02", "amount": 5000, "biz_no": "220-81-15770"}],
                              [{"date": "2026-06-02", "amount": 5000, "raw": {"사업자번호": "119-81-00851"}}])[0] == FAIL)
    check("V1-AGREEMENT: matching biz → PASS",
          check_biz_agreement([{"id": "bok", "date": "2026-06-02", "amount": 5000, "biz_no": "119-81-00851"}],
                              [{"date": "2026-06-02", "amount": 5000, "raw": {"사업자번호": "119-81-00851"}}])[0] == PASS)

    # --- V3-INERT: applicability derived from data (NOT a vacuous SKIP counted as a passed check) ---
    check("V3-INERT: applicability derived from data — no items → not applicable", v3_applicable(good) is False)
    check("V3-INERT: applicability derived from data — items present → applicable",
          v3_applicable([{"id": "i", "amount": 9000, "items": [4000, 5000]}]) is True)
    check("V3-INERT: gate report surfaces v3_applicable (doc-honest)", "v3_applicable" in run_logical(good, cards, vote_ok, store_db={})[1])

    # --- V7: replay classify with ordered dinner_dates + confirmed map; escalated-then-confirmed agreement ---
    _v7 = [{"id": "v7", "store": "고깃집", "date": "2026-06-02", "time": "19:00", "amount": 120000, "people": 3, "sector": "STAFF MEETING"}]
    check("V7: escalated-then-confirmed AGREES (assigned == confirmed) → PASS",
          check_rule_consistency(_v7, store_db={}, confirmed={"v7": "STAFF MEETING"})[0] == PASS)
    check("V7: escalated-then-confirmed DISAGREES (assigned != confirmed) → FAIL",
          check_rule_consistency(_v7, store_db={}, confirmed={"v7": "TRAVEL BUSINESS/ENTERTAINMENT"})[0] == FAIL)

    # --- V5: cross-read handwriting DISAGREEMENT (deterministic) + None-floor ---
    _rd_dis = [[{"id": "h1", "handwriting": "dinner alone"}], [{"id": "h1", "handwriting": "dinner alone"}], [{"id": "h1", "handwriting": "김철수"}]]
    check("V5: cross-read handwriting DISAGREEMENT → escalate (ignores a high scalar)",
          check_handwriting_consensus([{"id": "h1", "handwriting": "dinner alone", "hw_confidence": 0.99}], _rd_dis)[0] == FAIL)
    check("V5: cross-read AGREEMENT → PASS (trusted deterministically)",
          check_handwriting_consensus([{"id": "h1", "handwriting": "dinner alone", "hw_confidence": 0.99}], [[{"id": "h1", "handwriting": "dinner alone"}]] * 3)[0] == PASS)
    check("V5: None-floor preserved (handwriting present, no reads, conf None) → FAIL",
          check_handwriting_consensus([{"id": "h2", "handwriting": "홍길동", "hw_confidence": None}], reads=None)[0] == FAIL)

    # --- VERIFY-FALLBACK-PARSEDATE: extract_card import-fail (parse_date=None) → date checks ERROR (no naive re-impl) ---
    _opd = V.parse_date
    V.parse_date = None
    try:
        check("PARSEDATE-fallback: parse_date=None → V2 card-match ERROR (fail-closed, no naive re-impl)",
              check_card_match(good, build_card_pool(cards))[0] == ERROR)
        check("PARSEDATE-fallback: parse_date=None → V1-AGREEMENT ERROR", check_biz_agreement(good, cards)[0] == ERROR)
        check("PARSEDATE-fallback: parse_date=None → V2-NOCARD ERROR", check_no_card(good, cards)[0] == ERROR)
    finally:
        V.parse_date = _opd

    # --- PHYSICAL-CHECKS: missing pv key → ERROR (not silent FAIL) ---
    if _REUSED["place"]:
        _opv = V.physical_verify
        V.physical_verify = lambda *a, **k: {"pic_delta_ok": True}      # missing the other 4 keys
        try:
            mk_code, mk_rep = run_physical("anything.xlsx", {"pic": 0}, 1)
            check("PHYSICAL-CHECKS: physical_verify missing pv keys → verdict ERROR (not silent FAIL)",
                  mk_code != 0 and mk_rep["verdict"] == ERROR)
        finally:
            V.physical_verify = _opv
    else:
        check("PHYSICAL-CHECKS (skipped — -place not importable)", True)

    import shutil
    shutil.rmtree(work, ignore_errors=True)
    print(f"\nreused producers: {_REUSED}")
    print("RESULT:", "PASS — all 실측 checks green (ANCHOR #2a fail-closed gate)" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
