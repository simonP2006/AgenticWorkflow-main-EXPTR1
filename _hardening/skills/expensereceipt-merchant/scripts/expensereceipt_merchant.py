#!/usr/bin/env python3
"""expensereceipt_merchant.py — M3: NTS checksum + merchant key + store normalization.

Adds the one accuracy-upgrade the existing EXPTR1 pipeline lacks: deterministic validation of the
10-digit Korean business-registration number (사업자등록번호) via the National Tax Service check-digit
algorithm. Everything else is REUSED (no re-implementation, SOT single-source):

  IMPORT from build_store_db:    _biz_no (G3 best-effort + NFC probe of 사업자번호↔사업자등록번호),
                                 match_card (consume-based (date,amount) join), norm_store,
                                 _merchant_name, _category
  IMPORT from classify_section:  receipt_key (the canonical shared merchant key)

The producer rule validate_biz_no() is exposed for expensereceipt-verify (M7) to IMPORT — the verifier
imports producer rules, never re-implements them (SPEC ANCHOR #2a / verify-imports-producer pattern).

NTS check-digit algorithm (standard 국세청 사업자등록번호 — empirically validated: 15/15 of the real
business numbers in planning/store-db.json PASS):
    digits d1..d10 (d10 = check digit); weights w = [1,3,7,1,3,7,1,3,5] over d1..d9
    s = Σ di*wi  +  (d9 * 5) // 10        # plus the TENS digit of (d9 × 5)
    check = (10 - (s % 10)) % 10
    valid ⟺ check == d10
NOTE (reported to master): the M3 brief's literal weight array [1,3,7,1,3,7,5,1,3] validates only 1/15
real numbers; the master's PROSE ("9th digit ×5, take tens digit") + the real-number oracle both confirm
the STANDARD array above (weight at position 9 = 5). The literal array was a transcription transposition.

SOT discipline (절대 기준 2): deterministic, read-only over card/receipt data; RETURNs the merchant
record to the master. Writes NO SOT and NO files (pure computation + optional stdout report).

Usage:
    python3 expensereceipt_merchant.py --validate 220-81-15770    # one number → JSON {valid: bool}
    python3 expensereceipt_merchant.py --audit-storedb [path]     # validate all biz-keys in a store-db
    python3 expensereceipt_merchant.py --selftest                 # 실측 self-test
"""

import os
import re
import sys
import json
import unicodedata
from pathlib import Path


def _fallback_parse_date(v):
    """MERCHANT-1: parse_date-EQUIVALENT date normalize for the DEGRADED (import-fail) fallback —
    NFC + strip + '/'→'-' + '.'→'-'. Byte-equivalent to the imported producer's parse_date for the
    YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD forms the cards use, so a slash-vs-dash variant still matches."""
    if v is None:
        return v
    return unicodedata.normalize("NFC", str(v)).strip().replace("/", "-").replace(".", "-")


def _fallback_match_card(receipt, card_pool):
    """MERCHANT-1: degraded fallback consume-based (date,amount) join — NOW date-normalizes BOTH sides
    (parse_date-equiv) so it is byte-equivalent to the imported producer (a slash-vs-dash date matches),
    and consumes each card row at most once."""
    rd = _fallback_parse_date(receipt.get("date"))
    ra = receipt.get("amount")
    for rec in card_pool:
        if rec.get("_consumed"):
            continue
        if _fallback_parse_date(rec.get("date")) == rd and rec.get("amount") == ra:
            rec["_consumed"] = True
            return rec
    return None


def _find_project_dir():
    p = Path(__file__).resolve()
    for anc in p.parents:
        if (anc / "CLAUDE.md").exists() and (anc / "scripts").is_dir():
            return anc
    return p.parents[4] if len(p.parents) >= 5 else p.parent


PROJECT_DIR = _find_project_dir()
SCRIPTS_DIR = PROJECT_DIR / "scripts"

# --- REUSE (no re-implementation) — the matching/extraction/normalization primitives ---
try:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from build_store_db import _biz_no, match_card, norm_store, _merchant_name, _category  # noqa: E402
    from classify_section import receipt_key                                                # noqa: E402
    _REUSED = True
except Exception:                                   # pragma: no cover (isolation fallback)
    _REUSED = False
    # MERCHANT-1: honest degraded-mode log — the producer primitives are unavailable; the fallback below is
    # parse_date-equivalent for dates but local for biz/store. Surfaced (not silently degraded).
    print("  WARN (MERCHANT-1): producer imports unavailable — DEGRADED fallback active (_REUSED=False; "
          "match_card uses the parse_date-equiv normalizer, biz/store primitives are local).", file=sys.stderr)

    def norm_store(s):
        if not s:
            return "(unknown)"
        s = unicodedata.normalize("NFC", str(s)).strip().lower()
        return re.sub(r"\s+", " ", s)

    def _biz_no(raw):
        for k in ("사업자번호", "사업자등록번호"):
            v = raw.get(k)
            if v:
                return unicodedata.normalize("NFC", str(v)).strip()
        return None

    def _merchant_name(raw):
        return unicodedata.normalize("NFC", str(raw.get("가맹점명", ""))).strip() or None

    def _category(raw):
        return unicodedata.normalize("NFC", str(raw.get("가맹점업종", ""))).strip() or None

    match_card = _fallback_match_card               # MERCHANT-1: the date-normalizing fallback join

    def receipt_key(receipt, card_pool):
        cm = match_card(receipt, card_pool)
        if cm:
            bn = _biz_no(cm.get("raw", {}))
            if bn:
                return bn, cm
        return f"name:{norm_store(receipt.get('store'))}", None


# ============================================================================ NEW: NTS CHECKSUM (producer rule)
_NTS_WEIGHTS = (1, 3, 7, 1, 3, 7, 1, 3, 5)          # standard 국세청 사업자등록번호 weights for d1..d9


def validate_biz_no(value):
    """★Producer rule (IMPORTed by expensereceipt-verify). NTS 10-digit business-number check-digit
    validation. Accepts hyphenated or raw input; strips ALL non-digits first. Returns True iff the
    number is exactly 10 digits and its check digit (d10) is consistent. None/empty/wrong-length → False.
    Deterministic — code, not AI judgment (코드는 거짓말하지 않는다)."""
    if value is None:
        return False
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 10:
        return False
    d = [int(c) for c in digits]
    s = sum(x * w for x, w in zip(d[:9], _NTS_WEIGHTS))
    s += (d[8] * 5) // 10                            # tens digit of (d9 × 5)
    return (10 - s % 10) % 10 == d[9]


def normalize_biz_no(value):
    """Return the 10-digit string (non-digits stripped) or None if not 10 digits."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 10 else None


def is_structurally_valid_biz_no(value):
    """MERCHANT-3: ADDITIVE structural biz-number guard, SEPARATE from validate_biz_no's NTS checksum.
    Rejects degenerate patterns a checksum CANNOT catch — notably all-zero `0000000000` (which actually
    PASSES the NTS check digit) and the all-same-digit family. ★validate_biz_no (the producer that
    -verify IMPORTs) is UNCHANGED/back-compat — this is a stricter OPT-IN check the caller layers on top.
    Returns True only when the number is 10 digits, NTS-valid, AND not a degenerate/reserved pattern."""
    digits = normalize_biz_no(value)
    if digits is None:
        return False
    if digits == "0000000000" or len(set(digits)) == 1:      # all-zero / all-same-digit → structurally invalid
        return False
    return validate_biz_no(digits)


# ============================================================================ MERCHANT-2: canonical join
def consume_match_card(receipt, card_pool):
    """★MERCHANT-2 — the SINGLE canonical owner of the consume-once (date,amount) card join for the suite.
    -verify IMPORTs THIS as the producer rule (wired at Batch F; until then verify keeps its Batch-C
    consume logic and the single-ownership is finalized at the F wiring — verify is NOT edited in Batch E).
    Mirrors verify's None-amount guard (a None amount NEVER matches — None==None would falsely consume a
    row, fail-closed) and delegates the actual (date,amount) compare to the imported producer match_card
    (or the date-normalizing fallback), which consumes each card row at most once (no double-count)."""
    if receipt.get("amount") is None:               # verify-aligned None-amount guard (fail-closed)
        return None
    return match_card(receipt, card_pool)


# ============================================================================ MERCHANT RECORD
def merchant_for_receipt(receipt, card_pool):
    """Derive the merchant record for one receipt against the card pool. Single consume-based match;
    keeps the card record (so merchant_name/category survive even when biz_no is absent — receipt_key
    drops the card ref in that case). merchant_key is IDENTICAL in format to classify_section.receipt_key
    (hyphenated card biz_no, else 'name:<norm store>') so -db / -classify / -merchant agree (절대 기준 2).

    Returns: {merchant_key, biz_no, biz_no_valid, merchant_name, category, store_norm, card_match}.
    biz_no_valid is None when there is no biz_no (cash/no-card)."""
    cm = consume_match_card(receipt, card_pool)     # MERCHANT-2: canonical consume-once join (None-amount guarded)
    raw = (cm or {}).get("raw", {}) or {}
    biz_no = _biz_no(raw)                            # G3: best-effort + NFC probe (both key spellings)
    merchant_key = biz_no if biz_no else f"name:{norm_store(receipt.get('store'))}"
    return {
        "merchant_key": merchant_key,
        "biz_no": biz_no,
        "biz_no_valid": (validate_biz_no(biz_no) if biz_no else None),
        "merchant_name": _merchant_name(raw) or receipt.get("store"),
        "category": _category(raw),
        "store_norm": norm_store(receipt.get("store")),
        "card_match": "MATCHED" if cm else "NO_CARD",
    }


# ============================================================================ CLI
def _audit_storedb(path):
    db = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for k in db:
        if k.startswith("name:"):
            continue
        rows.append({"key": k, "valid": validate_biz_no(k),
                     "merchant": db[k].get("merchant_name")})
    n_valid = sum(1 for r in rows if r["valid"])
    print(json.dumps({"store_db": str(path), "biz_keys": len(rows),
                      "valid": n_valid, "invalid": len(rows) - n_valid,
                      "rows": rows}, ensure_ascii=False, indent=2))
    return 0 if n_valid == len(rows) else 1


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if "--selftest" in args:
        return _selftest()
    if "--validate" in args:
        v = args[args.index("--validate") + 1]
        print(json.dumps({"value": v, "normalized": normalize_biz_no(v),
                          "valid": validate_biz_no(v)}, ensure_ascii=False))
        return 0 if validate_biz_no(v) else 1
    if "--audit-storedb" in args:
        i = args.index("--audit-storedb")
        path = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("--") \
            else str(PROJECT_DIR / "planning" / "store-db.json")
        return _audit_storedb(path)
    print(__doc__)
    return 0


# ============================================================================ 실측 SELF-TEST
# 15 REAL 10-digit business numbers from planning/store-db.json (card-derived, KNOWN-VALID).
_KNOWN_VALID = [
    "320-11-00856", "119-81-00851", "220-81-15770", "395-01-02543", "201-81-21515",
    "341-81-00540", "220-87-92541", "527-22-01942", "544-47-01125", "241-36-00411",
    "211-88-95935", "142-85-21553", "135-31-35624", "158-85-00403", "823-15-02706",
]


def _selftest():
    ok = True

    def check(label, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    # --- T1: every KNOWN-VALID real business number PASSES (master cross-checks the same set) ---
    allv = all(validate_biz_no(n) for n in _KNOWN_VALID)
    check(f"NTS checksum: all {len(_KNOWN_VALID)} real biz-numbers VALID", allv)
    for n in _KNOWN_VALID:
        if not validate_biz_no(n):
            print(f"      ! UNEXPECTED FAIL on real number {n}")

    # --- T2: corrupted check digit FAILS (flip d10 to a guaranteed-different value) ---
    def corrupt(num):
        d = re.sub(r"\D", "", num)
        return d[:9] + str((int(d[9]) + 1) % 10)
    allc = all(not validate_biz_no(corrupt(n)) for n in _KNOWN_VALID)
    check(f"NTS checksum: all {len(_KNOWN_VALID)} corrupted (d10+1) numbers INVALID", allc)

    # --- T3: input form tolerance (hyphen strip) + length/None guards ---
    check("hyphenated == digit-only validity ('220-81-15770' & '2208115770')",
          validate_biz_no("220-81-15770") and validate_biz_no("2208115770"))
    check("non-10-digit → False", not validate_biz_no("123") and not validate_biz_no("12345678901"))
    check("None / empty / non-numeric → False",
          (not validate_biz_no(None)) and (not validate_biz_no("")) and (not validate_biz_no("abc")))
    check("normalize_biz_no strips non-digits", normalize_biz_no("220-81-15770") == "2208115770")

    # --- T4: G3 best-effort + NFC card-raw probe (사업자번호 OR 사업자등록번호) ---
    rcpt = {"store": "폴바셋", "date": "2026-06-03", "amount": 24000}
    pool_a = [{"date": "2026-06-03", "amount": 24000,
               "raw": {"사업자번호": "220-81-15770", "가맹점명": "폴바셋", "가맹점업종": "커피전문점"}}]
    pool_b = [{"date": "2026-06-03", "amount": 24000,
               "raw": {"사업자등록번호": "220-81-15770", "가맹점명": "폴바셋"}}]   # alternate key spelling
    ma = merchant_for_receipt(rcpt, [dict(r) for r in pool_a])
    mb = merchant_for_receipt(dict(rcpt), [dict(r) for r in pool_b])
    check("G3: biz_no found via 사업자번호 key", ma["biz_no"] == "220-81-15770" and ma["biz_no_valid"] is True)
    check("G3: biz_no found via 사업자등록번호 key (best-effort probe)", mb["biz_no"] == "220-81-15770")
    check("merchant record: category from card raw", ma["category"] == "커피전문점")
    check("merchant record: merchant_name from card raw", ma["merchant_name"] == "폴바셋")

    # --- T5: NO-CARD fallback (cash / no match) ---
    mc = merchant_for_receipt({"store": "스팟마트", "date": "2026-06-02", "amount": 5000}, [])
    check("NO_CARD fallback: name: key + biz_no None + valid None",
          mc["merchant_key"] == f"name:{norm_store('스팟마트')}" and mc["biz_no"] is None and mc["biz_no_valid"] is None)
    check("NO_CARD fallback: card_match == 'NO_CARD'", mc["card_match"] == "NO_CARD")

    # --- T6: merchant_key IDENTICAL to classify_section.receipt_key (cross-skill consistency, 절대 기준 2) ---
    rk_key, _ = receipt_key(dict(rcpt), [dict(r) for r in pool_a])
    check("merchant_key == receipt_key (consistency with -classify / -db)", ma["merchant_key"] == rk_key)

    # ═══════════ ★BATCH E — merchant ingest hardening (non-vacuous: each FAIL pre-fix / PASS post-fix) ═══════════
    # MERCHANT-1: the degraded fallback match_card date-normalizes (slash/dash variant matches == imported)
    check("MERCHANT-1: _fallback_parse_date '/'→'-' and '.'→'-' (parse_date-equiv)",
          _fallback_parse_date("2026/06/03") == "2026-06-03" and _fallback_parse_date("2026.06.03") == "2026-06-03")
    _fb_hit = _fallback_match_card({"date": "2026/06/03", "amount": 24000},
                                   [{"date": "2026-06-03", "amount": 24000, "raw": {}}])
    check("MERCHANT-1: fallback match_card normalizes slash-vs-dash date → MATCHES (== imported path)", _fb_hit is not None)

    # MERCHANT-2: canonical consume-once join — None-amount guard (verify-aligned) + consume-once (no double-count)
    check("MERCHANT-2: consume_match_card None-amount → no match (verify-aligned fail-closed guard)",
          consume_match_card({"date": "2026-06-03", "amount": None}, [{"date": "2026-06-03", "amount": None, "raw": {}}]) is None)
    _sh = [{"date": "2026-06-03", "amount": 24000, "raw": {"사업자번호": "220-81-15770"}}]
    _h1 = consume_match_card({"date": "2026-06-03", "amount": 24000}, _sh)
    _h2 = consume_match_card({"date": "2026-06-03", "amount": 24000}, _sh)
    check("MERCHANT-2: consume-once — same card consumed only ONCE (2nd receipt → no match, no double-count)",
          _h1 is not None and _h2 is None)

    # MERCHANT-3: all-zero biz passes the NTS checksum but is structurally REJECTED (separate guard; validate_biz_no unchanged)
    check("MERCHANT-3: validate_biz_no('0000000000') still True (NTS checksum back-compat UNCHANGED)",
          validate_biz_no("0000000000") is True)
    check("MERCHANT-3: is_structurally_valid_biz_no REJECTS all-zero 0000000000 (degenerate)",
          is_structurally_valid_biz_no("0000000000") is False)
    check("MERCHANT-3: is_structurally_valid_biz_no REJECTS all-same-digit 1111111111",
          is_structurally_valid_biz_no("1111111111") is False)
    check("MERCHANT-3: is_structurally_valid_biz_no ACCEPTS a real valid number (220-81-15770)",
          is_structurally_valid_biz_no("220-81-15770") is True)
    check("MERCHANT-3: validate_biz_no checksum behavior UNCHANGED (all 15 real numbers still valid)",
          all(validate_biz_no(n) for n in _KNOWN_VALID))

    print(f"\nreused project primitives (_biz_no/match_card/norm_store/receipt_key): {_REUSED}")
    print("RESULT:", "PASS — all 실측 checks green" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
