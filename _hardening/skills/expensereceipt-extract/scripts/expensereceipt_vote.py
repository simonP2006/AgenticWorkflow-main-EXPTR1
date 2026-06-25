#!/usr/bin/env python3
"""expensereceipt_vote.py — M4: adaptive N-read OCR majority voting for the expensereceipt suite.

VERBATIM-CORE PORT of scripts/aggregate_ocr_votes.py (ADR-045): the confidence gate `_vote`, the
two-stage existence-then-field vote, the strong-majority threshold (ceil(0.8·k)), MIN_READS=3 /
MAX_READS=7, the closest-read `synthesize` scaffold, and the exit-code contract (0/2/1) are kept
faithful. The ONLY adaptation: the WK 5-section schema is replaced by a FLAT `receipts` list, because
sector classification is a SEPARATE skill (expensereceipt-classify, M5) — extract just reads raw fields.

Identity key = (date, amount) with TIME EXCLUDED — verbatim from aggregate_ocr_votes._meal_units:
thermal-receipt times are OCR-unstable and would scatter one receipt across many keys; amount is
crisply printed and card-cross-validated. (D-7: this key is mirrored in synthesize() — keep in sync.)

Voted (placement/classification-critical) fields: amount, people, handwriting(normalized). Ancillary
fields (store, biz_no) are NOT voted — they are validated downstream (biz_no by -merchant checksum +
-verify; store by fuzzy match) — mirroring aggregate_ocr_votes excluding store/names/card_number.

Because amount is PART of the identity key, a misread amount produces a DIFFERENT identity (a phantom
receipt seen by a minority) which the existence vote flags as 'missed or hallucinated' → escalation —
NOT a silently "corrected" value. Field-vote correction therefore applies to the non-identity voted
fields (people, handwriting); amount integrity is additionally enforced by the card cross-match in
expensereceipt-verify. This is the intended anti-hallucination behavior (ANCHOR #2b).

★ANCHOR #2b (no silent winner-pick): `_vote` always returns a `chosen` candidate, but an 'unresolved'
level is ESCALATION ONLY — the caller MUST NOT accept `chosen`. Voting is NOT a correctness oracle;
consensus still passes through expensereceipt-verify (the deterministic anti-hallucination gate).

OCR read schema (the extended contract the vision HALT in SKILL.md emits, per read ocr-results-{i}.json):
    {"receipts": [ {"date","time","amount","store","people","biz_no","handwriting","hw_confidence"} ]}

Exit codes (verbatim contract — the master's harness routes these via gate_codes {0:OK,2:VISION-MORE,1:LOGIC}):
    0  consensus reached  → ocr-results.json (+ ocr-vote-audit.json) written
    2  inconclusive, k<MAX_READS → caller adds 2 more independent reads and re-runs (exit 10 to LLM)
    1  k<MIN_READS, OR exhausted at MAX_READS with no consensus → FAIL/escalate

Usage:
    python3 expensereceipt_vote.py --dir <run_dir> [WEEK]      # vote the reads in <run_dir>
    python3 expensereceipt_vote.py --selftest
"""

import sys
import json
import math
import unicodedata
from collections import Counter
from pathlib import Path

MAX_READS = 7
MIN_READS = 3
STRONG_FRACTION = 0.8


# ─────────────────────────────────────────────────────────── VERBATIM CORE (from aggregate_ocr_votes)
def _vote(values, k):
    """Return (level, chosen, distribution). level ∈ {'unanimous','strong','unresolved'}.
    VERBATIM from aggregate_ocr_votes._vote — the anti-hallucination confidence gate."""
    cnt = Counter(values)
    chosen, support = cnt.most_common(1)[0]
    tie = sum(1 for v, c in cnt.items() if c == support) > 1
    strong_need = math.ceil(STRONG_FRACTION * k)
    if support == k and len(cnt) == 1:
        return "unanimous", chosen, dict(cnt)
    if support >= strong_need and not tie and k >= MIN_READS:
        return "strong", chosen, dict(cnt)
    return "unresolved", chosen, dict(cnt)


# ─────────────────────────────────────────────────────────── FLAT-SCHEMA ADAPTATION
def _hw_norm(h):
    if h is None:
        return None
    s = unicodedata.normalize("NFC", str(h)).strip().lower()
    return s or None


def _receipt_units(ocr):
    """VOTE-1 multiset key `{(date, amount, occurrence_ordinal): (amount, people, handwriting_norm)}` —
    identity (date,amount) with TIME excluded, PLUS a stable within-read occurrence ordinal so two DISTINCT
    receipts sharing the same (date,amount) on one day are BOTH voted independently (not collapsed/overwritten,
    as a plain (date,amount) dict key would). Restores the legacy section-separated guarantee.
    (D-7: the (date,amount)+ordinal key is mirrored in synthesize() — keep in sync.)"""
    out, seen = {}, {}
    for r in ocr.get("receipts", []) or []:
        base = (r.get("date"), r.get("amount"))
        ordn = seen.get(base, 0)
        seen[base] = ordn + 1
        out[(r.get("date"), r.get("amount"), ordn)] = (r.get("amount"), r.get("people"), _hw_norm(r.get("handwriting")))
    return out


def aggregate(reads):
    """Returns (resolved: bool, consensus: {ident: voted_tuple}, unresolved: list[str]).
    Two-stage vote (existence then field), mirroring aggregate_ocr_votes.aggregate."""
    k = len(reads)
    per_read = [_receipt_units(r) for r in reads]
    all_idents = set()
    for u in per_read:
        all_idents.update(u.keys())
    consensus, unresolved = {}, []
    for ident in sorted(all_idents, key=lambda x: tuple(map(str, x))):
        present = [ident in u for u in per_read]
        ex_level, ex_choice, _ = _vote(present, k)
        if ex_level == "unresolved" or ex_choice is False:
            unresolved.append(f"receipt {ident}: existence not agreed "
                              f"(seen {sum(present)}/{k}) — missed or hallucinated")
            continue
        vals = [u[ident] for u in per_read if ident in u]
        lvl, choice, dist = _vote(vals, len(vals))
        if lvl == "unresolved":
            unresolved.append(f"receipt {ident} (amount,people,handwriting): "
                              f"no consensus — candidates {dist}")
        else:
            consensus[ident] = choice
    return (len(unresolved) == 0), consensus, unresolved


def _best_base_read(reads, consensus):
    def disagreement(r):
        u = _receipt_units(r)
        return sum(1 for ident, val in consensus.items() if u.get(ident) != val)
    return min(range(len(reads)), key=lambda i: disagreement(reads[i]))


def synthesize(reads, consensus):
    """Closest-read scaffold; overwrite voted placement-critical fields (amount, people) with the
    majority value. handwriting is kept from the (agreed) base read to preserve original text — if a
    receipt reached consensus, the base read already agreed on its normalized handwriting.
    (D-7: identity key (date,amount) mirrors _receipt_units — keep in sync.)"""
    base = json.loads(json.dumps(reads[_best_base_read(reads, consensus)]))
    seen = {}
    for r in base.get("receipts", []) or []:
        b = (r.get("date"), r.get("amount"))
        ordn = seen.get(b, 0); seen[b] = ordn + 1       # VOTE-1: ordinal-aware (mirror _receipt_units)
        ident = (r.get("date"), r.get("amount"), ordn)
        if ident in consensus:
            amount, people, _hw = consensus[ident]
            r["amount"] = amount
            r["people"] = people
    return base


# ─────────────────────────────────────────────────────────── IO
def load_reads(run_dir):
    reads, i = [], 1
    while True:
        p = Path(run_dir) / f"ocr-results-{i}.json"
        if not p.exists():
            break
        reads.append(json.loads(p.read_text(encoding="utf-8")))
        i += 1
    return reads


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    import os
    os.replace(tmp, path)


def run(run_dir, week="WK"):
    """Vote the reads in run_dir. Returns exit code (0/2/1). Writes consensus / report into run_dir."""
    run_dir = Path(run_dir)
    reads = load_reads(run_dir)
    k = len(reads)
    print(f"--- expensereceipt OCR Vote: {week} (reads={k}) ---")
    if k < MIN_READS:
        print(f"ERROR: only {k} read(s); need ≥ {MIN_READS}.")
        return 1
    resolved, consensus, unresolved = aggregate(reads)
    if resolved:
        _write(run_dir / "ocr-results.json", synthesize(reads, consensus))
        try:
            _write(run_dir / "ocr-vote-audit.json",
                   {"week": week, "reads": k, "result": "CONSENSUS", "receipts": len(consensus)})
        except Exception:
            pass
        print(f"RESULT: CONSENSUS over {k} reads → ocr-results.json ({len(consensus)} receipts). "
              f"NOTE: still passes through expensereceipt-verify (voting augments, not replaces).")
        return 0
    _write(run_dir / "ocr-vote-report.json",
           {"week": week, "reads": k, "result": "INCONCLUSIVE", "unresolved": unresolved})
    print(f"\n⚠ {len(unresolved)} unresolved field(s):")
    for u in unresolved:
        print(f"  {u}")
    if k < MAX_READS:
        print(f"RESULT: INCONCLUSIVE — add 2 more independent reads "
              f"(ocr-results-{k+1}.json, ocr-results-{k+2}.json) and re-run (max {MAX_READS}).")
        return 2
    print(f"RESULT: FAIL — {MAX_READS} reads exhausted, no consensus. Re-read flagged receipts "
          f"(max 2) then escalate to the owner via master (ANCHOR #2b — no silent winner-pick).")
    return 1


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if "--selftest" in args:
        return _selftest()
    if "--dir" in args:
        run_dir = args[args.index("--dir") + 1]
        weeks = [a for a in args if not a.startswith("--") and a != run_dir]
        return run(run_dir, weeks[0] if weeks else "WK")
    print(__doc__)
    return 0


# ─────────────────────────────────────────────────────────── 실측 SELF-TEST
def _R(receipts):
    return {"receipts": receipts}


def _selftest():
    import tempfile, shutil
    ok = True

    def check(label, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    base = [
        {"date": "2026-06-02", "time": "18:20:00", "amount": 5000, "store": "스팟마트",
         "people": 1, "biz_no": "119-81-00851", "handwriting": "dinner alone"},
        {"date": "2026-06-03", "time": "12:30:00", "amount": 24000, "store": "폴바셋",
         "people": 3, "biz_no": "220-81-15770", "handwriting": "홍길동"},
    ]

    # --- T1: 3 unanimous reads → CONSENSUS exit 0 ---
    d = Path(tempfile.mkdtemp(prefix="vote_t1_"))
    for i in (1, 2, 3):
        _write(d / f"ocr-results-{i}.json", _R([dict(r) for r in base]))
    rc = run(d, "WK_T1")
    out = json.loads((d / "ocr-results.json").read_text(encoding="utf-8"))
    check("3 unanimous reads → exit 0 (CONSENSUS)", rc == 0)
    check("consensus ocr-results.json written, 2 receipts", len(out["receipts"]) == 2)
    shutil.rmtree(d, ignore_errors=True)

    # --- T2: identity key excludes TIME (same date+amount, different time → still consensus) ---
    d = Path(tempfile.mkdtemp(prefix="vote_t2_"))
    for i, t in enumerate(("18:20:00", "18:21:00", "18:19:00"), 1):
        recs = [dict(base[0], time=t), dict(base[1])]
        _write(d / f"ocr-results-{i}.json", _R(recs))
    check("identity key (date,amount) time-excluded → consensus despite time variance", run(d, "WK_T2") == 0)
    shutil.rmtree(d, ignore_errors=True)

    # --- T3: amount disagreement at k=3 (2 vs 1, strong_need=3) → INCONCLUSIVE exit 2 ---
    d = Path(tempfile.mkdtemp(prefix="vote_t3_"))
    _write(d / "ocr-results-1.json", _R([dict(base[0], amount=5000), dict(base[1])]))
    _write(d / "ocr-results-2.json", _R([dict(base[0], amount=5000), dict(base[1])]))
    _write(d / "ocr-results-3.json", _R([dict(base[0], amount=9999), dict(base[1])]))
    rc = run(d, "WK_T3")
    check("amount split 2/1 at k=3 (support 2 < ceil(0.8·3)=3) → exit 2", rc == 2)
    check("inconclusive report written", (d / "ocr-vote-report.json").exists())
    shutil.rmtree(d, ignore_errors=True)

    # --- T4: existence disagreement (receipt in 1/3 reads) → exit 2 (missed/hallucinated) ---
    d = Path(tempfile.mkdtemp(prefix="vote_t4_"))
    _write(d / "ocr-results-1.json", _R([dict(base[0]), dict(base[1]),
                                         {"date": "2026-06-04", "amount": 7000, "people": 1, "handwriting": None}]))
    _write(d / "ocr-results-2.json", _R([dict(base[0]), dict(base[1])]))
    _write(d / "ocr-results-3.json", _R([dict(base[0]), dict(base[1])]))
    check("existence seen 1/3 → unresolved → exit 2 (not silently dropped/included)", run(d, "WK_T4") == 2)
    shutil.rmtree(d, ignore_errors=True)

    # --- T5: handwriting disagreement → unresolved (ANCHOR#2b escalation) ---
    d = Path(tempfile.mkdtemp(prefix="vote_t5_"))
    _write(d / "ocr-results-1.json", _R([dict(base[0], handwriting="dinner alone"), dict(base[1])]))
    _write(d / "ocr-results-2.json", _R([dict(base[0], handwriting="dinner alone"), dict(base[1])]))
    _write(d / "ocr-results-3.json", _R([dict(base[0], handwriting="김철수"), dict(base[1])]))
    check("handwriting split 2/1 at k=3 → unresolved → exit 2 (escalation, no silent fill)", run(d, "WK_T5") == 2)
    shutil.rmtree(d, ignore_errors=True)

    # --- T6: k<MIN_READS → exit 1 ---
    d = Path(tempfile.mkdtemp(prefix="vote_t6_"))
    _write(d / "ocr-results-1.json", _R([dict(base[0])]))
    _write(d / "ocr-results-2.json", _R([dict(base[0])]))
    check("k=2 < MIN_READS=3 → exit 1", run(d, "WK_T6") == 1)
    shutil.rmtree(d, ignore_errors=True)

    # --- T7: exhausted at MAX_READS=7 with persistent 4/3 split → exit 1 ---
    d = Path(tempfile.mkdtemp(prefix="vote_t7_"))
    for i in range(1, 8):
        amt = 5000 if i <= 4 else 6000     # 4 vs 3, support 4 < ceil(0.8·7)=6 → unresolved
        _write(d / f"ocr-results-{i}.json", _R([dict(base[0], amount=amt), dict(base[1])]))
    rc = run(d, "WK_T7")
    check("k=7 persistent 4/3 split (support 4 < ceil(0.8·7)=6) → exit 1 (exhausted/escalate)", rc == 1)
    shutil.rmtree(d, ignore_errors=True)

    # --- T8: strong-majority FIELD correction at k=5 on a NON-identity field. amount(=identity) is
    #         held stable at 10200; people is misread once (9) vs 2 four times. support 4 >= ceil(0.8·5)=4
    #         → strong → consensus corrects people=2. (A misread of amount itself would instead become a
    #         phantom receipt flagged by the existence vote — see T3 — which is the intended escalation.)
    d = Path(tempfile.mkdtemp(prefix="vote_t8_"))
    for i in range(1, 6):
        ppl = 2 if i != 3 else 9
        _write(d / f"ocr-results-{i}.json", _R([dict(base[0], amount=10200, people=ppl), dict(base[1])]))
    rc = run(d, "WK_T8")
    out = json.loads((d / "ocr-results.json").read_text(encoding="utf-8"))
    voted = [r for r in out["receipts"] if r.get("amount") == 10200][0]["people"]
    check("strong majority 4/5 → exit 0, consensus people=2 (corrects the 9 outlier; amount=identity stable)",
          rc == 0 and voted == 2)
    shutil.rmtree(d, ignore_errors=True)

    # --- T9: _vote thresholds (verbatim core) direct ---
    check("_vote unanimous (3/3 same)", _vote([1, 1, 1], 3)[0] == "unanimous")
    check("_vote strong (4/5, no tie, k≥3)", _vote([1, 1, 1, 1, 2], 5)[0] == "strong")
    check("_vote unresolved (tie 2-2)", _vote([1, 1, 2, 2], 4)[0] == "unresolved")
    check("_vote unresolved (3/5 < ceil(0.8·5)=4)", _vote([1, 1, 1, 2, 3], 5)[0] == "unresolved")

    # --- ★VOTE-1: two DISTINCT receipts sharing (date,amount) on one day → BOTH voted (multiset, not collapsed) ---
    d = Path(tempfile.mkdtemp(prefix="vote_v1_"))
    def _twins():
        return [{"date": "2026-06-05", "amount": 8000, "people": 1, "handwriting": "dinner alone", "store": "A"},
                {"date": "2026-06-05", "amount": 8000, "people": 2, "handwriting": "홍길동", "store": "B"}]
    for i in (1, 2, 3):
        _write(d / f"ocr-results-{i}.json", _R(_twins()))
    rc = run(d, "WK_V1")
    out = json.loads((d / "ocr-results.json").read_text(encoding="utf-8"))
    same = [r for r in out["receipts"] if r.get("date") == "2026-06-05" and r.get("amount") == 8000]
    check("★VOTE-1: dup (date,amount) same day → CONSENSUS, BOTH occurrences present (count 2)", rc == 0 and len(same) == 2)
    check("★VOTE-1: each occurrence INDEPENDENTLY voted (people 1 AND 2 both survive; not collapsed to one)",
          sorted(r["people"] for r in same) == [1, 2])
    check("★VOTE-1: _receipt_units assigns occurrence ordinals (2 distinct keys for the twin (date,amount))",
          len(_receipt_units(_R(_twins()))) == 2)
    shutil.rmtree(d, ignore_errors=True)

    print("RESULT:", "PASS — all 실측 checks green" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
