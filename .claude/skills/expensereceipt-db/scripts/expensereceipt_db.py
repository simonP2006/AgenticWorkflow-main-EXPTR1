#!/usr/bin/env python3
"""expensereceipt_db.py — M2: the data backbone of the expensereceipt suite.

Owns four namespaced persistence assets under planning/expensereceipt/ (NEVER the
WK pipeline's planning/store-db.json — this suite is self-contained):

  1. ledger.json            per-receipt ledger (SPEC §3: {store,date,amount,people,handwriting}
                            + enrichment: merchant_key, sector, category, time, week, id, ...).
                            The fine-grained UPSTREAM source the store-db rolls up from.
  2. store-db.json          store(merchant_key)→sector aggregate (PORT of build_store_db.build()/
                            finalize(): section_dist, confidence, dominant_section, typical, occurrences).
  3. gallery/gallery.json   handwriting self-learning gallery (crop ↔ owner-confirmed-text pairs).
                            Few-shot retrieval by store/weekday/time-band METADATA KEY (G10 — NOT pixel
                            similarity; no CV2/numpy). Grows by owner confirmation (human-in-loop).
  4. classify-db.json       classification-learning DB: store→sector view (from store-db) + a
                            name_index {merchant_key → weekday → time_band → [attendee names]} for
                            STAFF/TRAVEL name candidates (SPEC §4: 가게+요일+시간→이름후보).

Safe-append (no pollution): a week's observations are STAGED in quarantine and merged into the live
store-db ONLY after the master confirms that week's verify PASS (--promote). Each promotion snapshots
the prior DB so a bad append is fully reversible (--rollback). PORT of build_store_db.py req④.

SOT discipline (절대 기준 2): this module is the SINGLE WRITER of its own DB files (its "별도 산출물
파일"); it NEVER writes the run SOT (state.yaml) — the master is the sole SOT writer. The 6 sub-skills
RETURN results to the master, which records pointers/summaries in state.yaml.

Reuse (SOT single-source): norm_store + parse_date are IMPORTED from the project scripts/ (same pattern
build_store_db uses), with an inline fallback so the skill stays runnable in isolation.

Usage (master invokes by subprocess):
    python3 expensereceipt_db.py --rollup                 # rebuild store-db from promoted weeks
    python3 expensereceipt_db.py --quarantine WK23_2026   # stage a week (not merged)
    python3 expensereceipt_db.py --promote   WK23_2026    # after verify PASS: snapshot + merge
    python3 expensereceipt_db.py --rollback              # undo last promote
    python3 expensereceipt_db.py --selftest             # 실측 self-test (uses a temp base)
"""

import os
import re
import sys
import json
import shutil
import unicodedata
import collections
from datetime import datetime
from pathlib import Path

def _find_project_dir():
    """Locate the EXPTR1 root robustly (marker = CLAUDE.md + scripts/), not by a fixed parent depth
    (the skill nests deeper than the project scripts/). Relocation-safe."""
    p = Path(__file__).resolve()
    for anc in p.parents:
        if (anc / "CLAUDE.md").exists() and (anc / "scripts").is_dir():
            return anc
    return p.parents[4] if len(p.parents) >= 5 else p.parent   # fallback: EXPTR1 by depth


PROJECT_DIR = _find_project_dir()                    # .../AgenticWorkflow-main-EXPTR1
SCRIPTS_DIR = PROJECT_DIR / "scripts"

# --- reuse pure helpers from the project SOT (norm_store, parse_date); inline fallback if absent ---
try:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from build_store_db import norm_store          # noqa: E402
    from extract_card_data import parse_date        # noqa: E402
    _REUSED = True
except Exception:                                   # pragma: no cover (isolation fallback)
    _REUSED = False

    def norm_store(s):
        if not s:
            return "(unknown)"
        s = unicodedata.normalize("NFC", str(s)).strip().lower()
        return re.sub(r"\s+", " ", s)

    def parse_date(val):
        if val is None:
            return ""
        if isinstance(val, datetime):
            return val.strftime("%Y-%m-%d")
        s = str(val).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
        return s

# Map the SPEC Receipt-Sheet sector (stored in ledger.sector, used by -place) → the SHORT store-learning
# label used in store-db section_dist. The short labels match the existing ecosystem (classify_section.py,
# classify_stage.py, the WK store-db.json) so classify_section.classify — which special-cases "TRAVEL" —
# works against this suite's store-db. PARKING/TOLLS and TELEPHONE-LOCAL are DETERMINISTIC-trigger sectors
# (no store-learning) and are intentionally excluded from the rollup (like build_store_db excludes tolls/tel).
_SECTOR_TO_LEARNING = {
    "Dinner": "DINNER",
    "STAFF MEETING": "STAFF",
    "TRAVEL BUSINESS/ENTERTAINMENT": "TRAVEL",
    "OTHERS-LOCAL": "OTHERS",
}

# DB-5: deterministic-trigger sectors are intentionally NOT learned (excluded from rollup, like tolls/tel
# in build_store_db) — they must NOT be flagged as "unknown".
_DETERMINISTIC_SECTORS = {"PARKING/TOLLS", "TELEPHONE-LOCAL"}
# DB-5: NFC + canonical-case map of common owner/OCR variants → the canonical SPEC sector.
_SECTOR_CANON = {
    "dinner": "Dinner",
    "staff meeting": "STAFF MEETING", "staff": "STAFF MEETING", "staff_meeting": "STAFF MEETING",
    "staff meetings": "STAFF MEETING",
    "travel business/entertainment": "TRAVEL BUSINESS/ENTERTAINMENT", "travel": "TRAVEL BUSINESS/ENTERTAINMENT",
    "others-local": "OTHERS-LOCAL", "others": "OTHERS-LOCAL", "other": "OTHERS-LOCAL",
    "parking/tolls": "PARKING/TOLLS", "parking": "PARKING/TOLLS", "tolls": "PARKING/TOLLS",
    "telephone-local": "TELEPHONE-LOCAL", "telephone": "TELEPHONE-LOCAL",
}
_MIN_CONF_OCC = 3                 # DB-10: occurrences needed for full confidence (under this → shrink toward 0.5)
LAST_ROLLUP_UNKNOWN = {}          # DB-5: last rollup's unknown-sector counter (surfaced; selftest-observable)


def _canon_sector(sector):
    """DB-5: NFC + canonical-case normalize a sector to its SPEC label ('Staff Meeting'/'DINNER'/' travel '
    variants → canonical). Returns the canonical SPEC sector, or None if unrecognized (→ warned/counted,
    never silently dropped)."""
    if not sector:
        return None
    s = unicodedata.normalize("NFC", str(sector)).strip()
    if s in _SECTOR_TO_LEARNING or s in _DETERMINISTIC_SECTORS:
        return s
    return _SECTOR_CANON.get(re.sub(r"\s+", " ", s).lower())


def _canon_amount(v):
    """DB-7: canonical amount for the dedup signature — int 5000 and str '5000'/'5,000원' collapse to one
    ledger row (mirror parse_amount). Unparseable → the raw value (so a sig is still computable)."""
    if v is None:
        return None
    try:
        return int(round(float(str(v).replace(",", "").replace("원", "").replace("₩", "").strip())))
    except (ValueError, TypeError):
        return v

# ----------------------------------------------------------------------------- paths (configurable)
_BASE = None
LEDGER = STORE_DB = COVERAGE = CLASSIFY_DB = None
GALLERY_DIR = GALLERY_JSON = QUAR_DIR = SNAP_DIR = PROMOTED = None


def configure(base=None):
    """Point the module at a base dir. Default = planning/expensereceipt/ (env EXPR_DB_BASE overrides).
    Callable by the self-test to run against a temp dir without touching real DB files."""
    global _BASE, LEDGER, STORE_DB, COVERAGE, CLASSIFY_DB
    global GALLERY_DIR, GALLERY_JSON, QUAR_DIR, SNAP_DIR, PROMOTED
    if base is None:
        base = os.environ.get("EXPR_DB_BASE") or (PROJECT_DIR / "planning" / "expensereceipt")
    _BASE = Path(base)
    # DB-4: reject a base that collides with the WK pipeline's planning/ — writing store-db.json there
    # would clobber the real WK store-db (planning/store-db.json). Enforce a strict, dedicated subdir.
    if _BASE.resolve() == (PROJECT_DIR / "planning").resolve():
        raise ValueError(f"EXPR_DB_BASE must NOT be {PROJECT_DIR / 'planning'} (collides with the WK "
                         f"store-db planning/store-db.json) — use a dedicated subdir e.g. "
                         f"planning/expensereceipt (DB-4 path-collision guard)")
    LEDGER = _BASE / "ledger.json"
    STORE_DB = _BASE / "store-db.json"
    COVERAGE = _BASE / "store-db-coverage.json"
    CLASSIFY_DB = _BASE / "classify-db.json"
    GALLERY_DIR = _BASE / "gallery"
    GALLERY_JSON = GALLERY_DIR / "gallery.json"
    QUAR_DIR = _BASE / "store-db-quarantine"
    SNAP_DIR = _BASE / "store-db-snapshots"
    PROMOTED = _BASE / "store-db-promoted.json"
    return _BASE


# ----------------------------------------------------------------------------- atomic IO helpers
def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(path, obj):
    """Crash-safe atomic write (temp → os.replace), per AGENTS.md Context Preservation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


# ----------------------------------------------------------------------------- metadata-key helpers (G10)
def _hour(t):
    t = str(t or "")
    return int(t[:2]) if t[:2].isdigit() else None


def time_band(t):
    """Coarse time bucket for the gallery/name metadata key (NOT pixel data)."""
    h = _hour(t)
    if h is None:
        return None
    if 5 <= h <= 10:
        return "breakfast"
    if 11 <= h <= 13:
        return "lunch"
    if 14 <= h <= 16:
        return "afternoon"
    if 17 <= h <= 21:
        return "dinner"
    return "late"           # 22-23, 0-4


_WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def weekday(date_str):
    d = parse_date(date_str)
    try:
        return _WD[datetime.strptime(d, "%Y-%m-%d").weekday()]
    except (ValueError, TypeError):
        return None


def _mkey(record):
    """Canonical merchant key — IDENTICAL format to classify_section.receipt_key (the shared key every
    expensereceipt skill agrees on): explicit merchant_key, else the card 사업자번호 AS-IS (hyphenated,
    e.g. '220-81-15770'), else 'name:<norm store>'. Do NOT strip hyphens — the existing store-db and
    receipt_key key by the hyphenated form; stripping would desync -db from -classify/-merchant
    (cross-skill consistency, 절대 기준 2). The checksum (validate_biz_no in -merchant) strips internally."""
    mk = record.get("merchant_key")
    if mk:
        return mk
    bn = record.get("biz_no")
    if bn and str(bn).strip():
        return str(bn).strip()
    return f"name:{norm_store(record.get('store'))}"


# ============================================================================= 1. LEDGER (SPEC §3)
_LEDGER_CORE = ("store", "date", "amount", "people", "handwriting")


def ledger_read():
    return _read(LEDGER, [])


def _content_sig(rec):
    """Stable content signature for idempotent dedup when an explicit id is absent. DB-7: amount is
    canonicalized (int 5000 ≡ str '5000') just like the date, so a format-variant re-read of the same
    receipt collapses to ONE ledger row."""
    return (rec.get("week"), _mkey(rec), parse_date(rec.get("date")),
            _canon_amount(rec.get("amount")), str(rec.get("time") or ""), rec.get("handwriting"))


def ledger_add(records):
    """Append per-receipt records, IDEMPOTENT on explicit id OR content signature (re-running a week
    never double-counts). Normalizes date; derives merchant_key + weekday + time_band; auto-assigns a
    stable R-#### id when absent. Each record carries at least the SPEC §3 core fields."""
    if isinstance(records, dict):
        records = [records]
    led = ledger_read()
    existing_ids = {r.get("id") for r in led if r.get("id")}
    existing_sigs = {_content_sig(r) for r in led}
    next_n = max([int(m.group(1)) for r in led
                  for m in [re.match(r"R-(\d+)$", str(r.get("id") or ""))] if m] or [0])
    for r in records:
        rec = dict(r)
        rec["date"] = parse_date(rec.get("date"))
        rec.setdefault("people", None)
        rec.setdefault("handwriting", None)
        rec["merchant_key"] = _mkey(rec)
        rec["weekday"] = weekday(rec.get("date"))
        rec["time_band"] = time_band(rec.get("time"))
        sig = _content_sig(rec)
        if (rec.get("id") and rec["id"] in existing_ids) or sig in existing_sigs:
            continue                                   # idempotent
        if not rec.get("id"):
            next_n += 1
            rec["id"] = f"R-{next_n:04d}"
        existing_ids.add(rec["id"]); existing_sigs.add(sig)
        led.append(rec)
    _write(LEDGER, led)
    return led


def ledger_week(week):
    return [r for r in ledger_read() if r.get("week") == week]


# ============================================================================= 2. STORE-DB ROLLUP
# PORT of build_store_db.build()/finalize(), adapted to take per-receipt LEDGER records as input
# (instead of research/wk*_ocr-results.json). Keying + aggregation + finalize are faithful copies.
def rollup(records):
    """Aggregate ledger records → store-db {merchant_key: {section_dist, confidence, ...}}.
    Only LEARNABLE_SECTORS contribute (Dinner/STAFF/TRAVEL/OTHERS); deterministic sectors excluded."""
    store_db = {}

    def agg(key, section, r):
        e = store_db.setdefault(key, {
            "merchant_name": r.get("merchant_name") or r.get("store"),
            "category": r.get("category"),
            "section_dist": collections.Counter(),
            "headcounts": [], "amounts": [], "hours": [],
            "occurrences": 0, "source_weeks": set(),
        })
        if r.get("merchant_name") and not e["merchant_name"]:
            e["merchant_name"] = r["merchant_name"]
        if r.get("category") and not e["category"]:
            e["category"] = r["category"]
        e["section_dist"][section] += 1
        if r.get("people") is not None:
            e["headcounts"].append(r["people"])
        if r.get("amount") is not None:
            e["amounts"].append(r["amount"])
        h = _hour(r.get("time"))
        if h is not None:
            e["hours"].append(h)
        e["occurrences"] += 1
        if r.get("week"):
            e["source_weeks"].add(r["week"])

    unknown = collections.Counter()
    for r in records:
        canon = _canon_sector(r.get("sector"))             # DB-5: NFC + canonical-case normalize first
        if canon in _DETERMINISTIC_SECTORS:
            continue                                       # deterministic-trigger — intentionally not learned
        learn = _SECTOR_TO_LEARNING.get(canon)
        if learn is None:
            if r.get("sector"):                            # present-but-UNRECOGNIZED → surface, never silent-drop
                unknown[str(r.get("sector"))] += 1
            continue
        agg(_mkey(r), learn, r)
    LAST_ROLLUP_UNKNOWN.clear()
    LAST_ROLLUP_UNKNOWN.update(unknown)
    if unknown:                                            # DB-5: warn + count (no silent drop)
        print(f"  WARN (DB-5): {sum(unknown.values())} record(s) with UNKNOWN sector NOT learned "
              f"(surfaced/counted, not silently dropped): {dict(unknown)}", file=sys.stderr)

    final = {}
    for key, e in store_db.items():
        dist = dict(e["section_dist"])
        total = sum(dist.values())
        occ = e["occurrences"]
        # DB-10: shrink confidence toward 0.5 when under-observed (occ < _MIN_CONF_OCC) — a single
        # observation is NOT max-confidence. weight = min(occ, N)/N (linear); at occ ≥ N → raw confidence.
        raw_conf = (max(dist.values()) / total) if total else 0
        w = (min(occ, _MIN_CONF_OCC) / _MIN_CONF_OCC) if _MIN_CONF_OCC else 1.0
        conf = round(0.5 + (raw_conf - 0.5) * w, 3) if total else 0
        hc = sorted(e["headcounts"]); am = sorted(e["amounts"]); hr = sorted(e["hours"])
        final[key] = {
            "merchant_name": e["merchant_name"], "category": e["category"],
            "section_dist": dist,
            "confidence": conf,
            "raw_confidence": round(raw_conf, 3),          # DB-10: pre-shrink value retained for transparency
            "dominant_section": max(dist, key=dist.get) if dist else None,
            "typical": {
                "headcount": [hc[0], hc[len(hc) // 2], hc[-1]] if hc else None,
                "amount": [am[0], am[len(am) // 2], am[-1]] if am else None,
                "hour": [hr[0], hr[len(hr) // 2], hr[-1]] if hr else None,
            },
            "occurrences": e["occurrences"],
            "source_weeks": sorted(e["source_weeks"]),
        }
    return final


def rollup_from_ledger(weeks):
    """Rebuild store-db from the ledger records of the given weeks (provenance-driven, idempotent)."""
    wset = set(weeks)
    return rollup([r for r in ledger_read() if r.get("week") in wset])


# ============================================================================= 3. HANDWRITING GALLERY (G10)
def gallery_read():
    return _read(GALLERY_JSON, [])


def gallery_add(confirmed_text, store=None, date=None, time=None, crop_ref=None, week=None, merchant_key=None):
    """Record an owner-confirmed (crop ↔ text) pair. Grows by owner confirmation (human-in-loop).
    Stores ONLY metadata keys (store/weekday/time_band) — never pixel features (G10)."""
    g = gallery_read()
    # DB-6: id = max(existing G-####)+1 (regex parse), NOT len(g)+1 — collision-free after a deletion
    # (len-based would re-mint an existing id once any earlier entry is removed).
    nums = [int(m.group(1)) for e in g for m in [re.match(r"G-(\d+)$", str(e.get("id") or ""))] if m]
    nid = (max(nums) + 1) if nums else 1
    entry = {
        "id": f"G-{nid:04d}",
        "confirmed_text": confirmed_text,
        "store": store,
        "merchant_key": merchant_key or (f"name:{norm_store(store)}" if store else None),
        "weekday": weekday(date) if date else None,
        "time_band": time_band(time) if time else None,
        "week": week,
        "crop_ref": crop_ref,            # path/pointer to the crop image (not pixel data)
    }
    g.append(entry)
    _write(GALLERY_JSON, g)
    return entry


def gallery_query(store=None, date=None, time=None, merchant_key=None, k=5):
    """Few-shot retrieval by METADATA KEY (G10), NOT pixel similarity. Scores each gallery entry by
    store/weekday/time-band overlap; returns the top-k most relevant (score>0), recency tiebreak.
    Empty on cold-start. Never dumps the whole gallery."""
    q_mkey = merchant_key or (f"name:{norm_store(store)}" if store else None)
    q_wd = weekday(date) if date else None
    q_tb = time_band(time) if time else None
    scored = []
    for e in gallery_read():
        # "가게 맞춤" (store-tailored, G10): an entry MUST share the store to be a candidate;
        # weekday/time-band only REFINE the ranking. Unknown store ⇒ no candidates ⇒ honest cold-start.
        if q_mkey and e.get("merchant_key") == q_mkey:
            score = 3                                    # exact store (strongest signal)
        elif store and e.get("store") and norm_store(e["store"]) == norm_store(store):
            score = 1                                    # store-name fallback match
        else:
            continue                                     # not store-matched → excluded
        if q_wd and e.get("weekday") == q_wd:
            score += 2
        if q_tb and e.get("time_band") == q_tb:
            score += 1
        scored.append((score, e.get("week") or "", e))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [{**e, "_match_score": s} for s, _, e in scored[:k]]


# ============================================================================= 4. CLASSIFY-DB
def name_index_add(merchant_key, date, time, names):
    """Record observed attendee names for (store, weekday, time_band) — SPEC §4 name candidates."""
    db = _read(CLASSIFY_DB, {})
    ni = db.setdefault("name_index", {})
    wd_raw, tb_raw = weekday(date), time_band(time)
    # DB-9: validate date/time at ingest — an UNPARSEABLE value is SURFACED (ingest_warnings), not silently
    # bucketed under '?' where it would vanish.
    if date and wd_raw is None:
        db.setdefault("ingest_warnings", []).append({"type": "bad_date", "value": str(date), "merchant_key": merchant_key})
        print(f"  WARN (DB-9): unparseable date {date!r} in name_index_add — surfaced (not silent '?')", file=sys.stderr)
    if time and tb_raw is None:
        db.setdefault("ingest_warnings", []).append({"type": "bad_time", "value": str(time), "merchant_key": merchant_key})
        print(f"  WARN (DB-9): unparseable time {time!r} in name_index_add — surfaced", file=sys.stderr)
    wd = wd_raw or "?"; tb = tb_raw or "?"
    bucket = ni.setdefault(merchant_key, {}).setdefault(wd, {}).setdefault(tb, {})
    for nm in (names or []):
        bucket[nm] = bucket.get(nm, 0) + 1
    # DB-8: do NOT snapshot the live STORE_DB into classify-db here — caching an UNPROMOTED store-db would
    # leak unverified state into classification. store_sector is refreshed ONLY by classifydb_rebuild
    # (called post-verify, on promote/rollback).
    _write(CLASSIFY_DB, db)
    return db


def name_candidates(merchant_key, date, time):
    """Ranked attendee-name candidates for (store, weekday, time_band); widens to store-only on miss."""
    db = _read(CLASSIFY_DB, {})
    ni = db.get("name_index", {}).get(merchant_key, {})
    wd = weekday(date) or "?"; tb = time_band(time) or "?"
    bucket = ni.get(wd, {}).get(tb, {})
    if not bucket:                                       # widen: any time/any weekday for this store
        bucket = collections.Counter()
        for wmap in ni.values():
            for tmap in wmap.values():
                for nm, c in tmap.items():
                    bucket[nm] += c
        bucket = dict(bucket)
    return [nm for nm, _ in sorted(bucket.items(), key=lambda kv: kv[1], reverse=True)]


def classifydb_rebuild():
    """Refresh the store→sector view (Dinner probability etc.) from the live store-db."""
    db = _read(CLASSIFY_DB, {})
    db["store_sector"] = _read(STORE_DB, {})
    db.setdefault("name_index", {})
    _write(CLASSIFY_DB, db)
    return db


# ============================================================================= 5. SAFE-APPEND TXN (PORT req④)
def quarantine_week(week):
    """Stage a week's rollup (from its ledger records) — NOT merged into the live store-db."""
    db = rollup(ledger_week(week))
    _write(QUAR_DIR / f"{week}.json", {"week": week, "store_db": db})
    return db


def _canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def store_db_consistent():
    """DB-2 invariant: the live store-db (DERIVED) must equal rollup_from_ledger(PROMOTED) (the PROVENANCE
    source of truth). Returns (is_consistent, promoted)."""
    promoted = _read(PROMOTED, [])
    return _canon(_read(STORE_DB, {})) == _canon(rollup_from_ledger(promoted)), promoted


def startup_consistency_check(self_heal=True):
    """DB-2 / §6-b crash-safety: detect a half-committed promote (PROMOTED advanced but STORE_DB not yet
    rebuilt — or vice-versa) and SELF-HEAL by rebuilding store-db from the PROMOTED provenance (the source
    of truth), or fail-closed — NEVER leave a silently desynced store-db gating downstream classification.
    Idempotent: a no-op when already consistent. Call at startup (main) and before a logical promote."""
    consistent, promoted = store_db_consistent()
    if consistent:
        return {"consistent": True, "healed": False, "promoted": promoted}
    if not self_heal:
        return {"consistent": False, "healed": False, "promoted": promoted}
    _write(STORE_DB, rollup_from_ledger(promoted))         # heal: store-db ← provenance (PROMOTED is truth)
    classifydb_rebuild()
    return {"consistent": True, "healed": True, "promoted": promoted}


def promote_week(week, verdict=None, verdict_week=None):
    """After the master confirms verify PASS: snapshot the live store-db (once per week), add the week to
    the promoted provenance, rebuild store-db from ALL promoted weeks' ledger records. Reversible.

    DB-1 (arg HALF): a FAIL-CLOSED gate — refuse unless verdict == 'PASS' AND verdict_week == week. The
      orchestrator CALL that threads the real verify verdict is Batch F (deferred).
    DB-2 (crash-safety): write PROMOTED (provenance) BEFORE STORE_DB (derived) so a crash between leaves a
      recoverable state that startup_consistency_check self-heals — never a silent half-commit.
    DB-3 (idempotency): snapshot ONCE per logical promote (store-db.pre-<week>.json, skip if present); a
      retry of an already-promoted week SHORT-CIRCUITS (self-heal + no double snapshot of a polluted state)."""
    # DB-1 fail-closed gate (the orchestrator threads the real verify verdict in Batch F)
    if verdict != "PASS":
        raise RuntimeError(f"promote REFUSED: verify verdict must be 'PASS' (got {verdict!r}) — DB-1 gate")
    if verdict_week != week:
        raise RuntimeError(f"promote REFUSED: verdict week {verdict_week!r} != promote week {week!r} — DB-1 week-match")
    if not (QUAR_DIR / f"{week}.json").exists():
        raise RuntimeError(f"{week} not quarantined (run --quarantine {week} first)")
    promoted = _read(PROMOTED, [])
    # DB-3 idempotent retry: already promoted → heal any partial state, drop the stale quarantine, short-circuit
    if week in promoted:
        heal = startup_consistency_check(self_heal=True)
        q = QUAR_DIR / f"{week}.json"
        if q.exists():
            q.unlink()
        return {"promoted": promoted, "already_promoted": True, "healed": heal["healed"],
                "keys": len(_read(STORE_DB, {}))}
    # DB-3 snapshot ONCE per week (capture the CLEAN pre-promote store-db; a retry won't overwrite it)
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    snap = SNAP_DIR / f"store-db.pre-{week}.json"
    if not snap.exists():
        _write(snap, _read(STORE_DB, {}))
    # DB-2 crash-safe ordering: PROMOTED (provenance) BEFORE STORE_DB (derived)
    promoted = promoted + [week]
    _write(PROMOTED, promoted)
    db = rollup_from_ledger(promoted)
    _write(STORE_DB, db)
    classifydb_rebuild()
    (QUAR_DIR / f"{week}.json").unlink()
    return {"promoted": promoted, "snapshot": snap.name, "keys": len(db)}


def rollback():
    """Undo the last promote: pop the last promoted week and restore store-db from its per-week pre-snapshot
    (store-db.pre-<week>.json). DB-2 crash-safe ordering (PROMOTED before STORE_DB). Fully reversible."""
    promoted = _read(PROMOTED, [])
    if not promoted:
        raise RuntimeError("no promoted week to roll back")
    week = promoted[-1]
    snap = SNAP_DIR / f"store-db.pre-{week}.json"
    if not snap.exists():
        raise RuntimeError(f"no snapshot for {week} (store-db.pre-{week}.json missing) — cannot roll back")
    snap_data = _read(snap, {})
    promoted = promoted[:-1]
    _write(PROMOTED, promoted)                             # DB-2: provenance first
    _write(STORE_DB, snap_data)
    classifydb_rebuild()
    snap.unlink()
    return {"restored": snap.name, "undid": week, "promoted": promoted}


# ============================================================================= CLI
def main(argv=None):
    configure()
    args = argv if argv is not None else sys.argv[1:]
    if "--selftest" in args:
        return _selftest()

    def _opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    # DB-2: startup consistency self-heal (recover a half-committed promote before ANY operation)
    heal = startup_consistency_check(self_heal=True)
    if heal.get("healed"):
        print(json.dumps({"action": "startup-self-heal", "healed": True, "promoted": heal["promoted"]},
                         ensure_ascii=False), file=sys.stderr)
    if "--quarantine" in args:
        w = args[args.index("--quarantine") + 1]
        db = quarantine_week(w)
        print(json.dumps({"action": "quarantine", "week": w, "keys": len(db)}, ensure_ascii=False))
        return 0
    if "--promote" in args:
        w = args[args.index("--promote") + 1]
        # DB-1: the verify verdict must be supplied (PASS) + week-matched. The orchestrator threads this
        # in Batch F; the standalone CLI takes --verdict / --verdict-week (defaults verdict-week to the week).
        print(json.dumps({"action": "promote", "week": w,
                          **promote_week(w, verdict=_opt("--verdict"), verdict_week=_opt("--verdict-week", w))},
                         ensure_ascii=False))
        return 0
    if "--rollback" in args:
        print(json.dumps({"action": "rollback", **rollback()}, ensure_ascii=False))
        return 0
    if "--rollup" in args:
        promoted = _read(PROMOTED, [])
        db = rollup_from_ledger(promoted)
        _write(STORE_DB, db)
        classifydb_rebuild()
        print(json.dumps({"action": "rollup", "promoted": promoted, "keys": len(db)}, ensure_ascii=False))
        return 0
    print(__doc__)
    return 0


# ============================================================================= 실측 SELF-TEST
def _selftest():
    import tempfile
    base = Path(tempfile.mkdtemp(prefix="expr_db_selftest_"))
    configure(base)
    ok = True

    def check(label, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    # --- T1: ledger write/read round-trip ---
    recs = [
        {"store": "스팟마트", "date": "2026/06/02", "amount": 5000, "people": 1,
         "handwriting": "dinner alone", "time": "18:20:00", "sector": "Dinner",
         "week": "WK23_2026", "biz_no": "217-81-14493"},
        {"store": "폴바셋", "date": "2026.06.03", "amount": 24000, "people": 3,
         "handwriting": "홍길동", "time": "12:30:00", "sector": "STAFF MEETING",
         "week": "WK23_2026", "merchant_key": "220-81-15770"},
        {"store": "스팟마트", "date": "2026-06-09", "amount": 6000, "people": 1,
         "handwriting": "dinner alone", "time": "19:05:00", "sector": "Dinner",
         "week": "WK24_2026", "biz_no": "217-81-14493"},
    ]
    ledger_add(recs)
    led = ledger_read()
    check("ledger round-trip: 3 records persisted", len(led) == 3)
    check("ledger date normalized to YYYY-MM-DD", all(re.match(r"\d{4}-\d{2}-\d{2}", r["date"]) for r in led))
    check("ledger merchant_key = hyphenated card biz_no (matches receipt_key)",
          led[0]["merchant_key"] == "217-81-14493" and led[1]["merchant_key"] == "220-81-15770")
    check("ledger SPEC §3 core fields present",
          all(all(k in r for k in _LEDGER_CORE) for r in led))
    led2 = ledger_read()
    check("ledger read deterministic (re-read equal)", led == led2)
    ledger_add(recs)                                    # idempotent: same ids → no duplicates
    check("ledger idempotent on re-add (no dup ids)", len(ledger_read()) == 3)

    # --- T2: rollup correctness ---
    db = rollup_from_ledger(["WK23_2026", "WK24_2026"])
    spot = db.get("217-81-14493")
    check("rollup: 스팟마트 keyed by hyphenated biz_no (receipt_key-consistent)", spot is not None)
    check("rollup: 스팟마트 section_dist DINNER=2 (SPEC Dinner→short DINNER)", spot and spot["section_dist"].get("DINNER") == 2)
    check("rollup: 스팟마트 raw_confidence=1.0 single-sector (DB-10 shrunk conf=0.833 at occ=2)",
          spot and spot["raw_confidence"] == 1.0 and spot["confidence"] == 0.833)
    check("rollup: 스팟마트 typical.amount=[min,med,max]", spot and spot["typical"]["amount"] == [5000, 6000, 6000])
    check("rollup: STAFF store present + dominant", db.get("220-81-15770", {}).get("dominant_section") == "STAFF")

    # --- T3: gallery metadata-key few-shot (G10, NOT pixels) ---
    gallery_add("dinner alone", store="스팟마트", date="2026-06-02", time="18:20:00",
                week="WK23_2026", merchant_key="217-81-14493", crop_ref="crops/g1.png")
    gallery_add("dinner alone", store="스팟마트", date="2026-06-09", time="19:05:00",
                week="WK24_2026", merchant_key="217-81-14493", crop_ref="crops/g2.png")
    gallery_add("홍길동", store="폴바셋", date="2026-06-03", time="12:30:00",
                week="WK23_2026", merchant_key="220-81-15770", crop_ref="crops/g3.png")
    hits = gallery_query(store="스팟마트", date="2026-06-16", time="18:40:00",
                         merchant_key="217-81-14493", k=5)
    check("gallery: store-matched few-shot returned", len(hits) == 2)
    check("gallery: top hit is the same store (exact merchant_key)", hits[0]["merchant_key"] == "217-81-14493")
    check("gallery: other store excluded (no metadata overlap forced)",
          all(h["merchant_key"] == "217-81-14493" for h in hits))
    check("gallery: ranking by score desc", hits[0]["_match_score"] >= hits[-1]["_match_score"])
    check("gallery: cold-start empty for unknown store",
          gallery_query(store="없는가게", date="2026-06-16", time="18:00:00", k=5) == [])

    # --- T4: classify-db name candidates ---
    name_index_add("220-81-15770", "2026-06-03", "12:30:00", ["홍길동", "김철수"])
    cands = name_candidates("220-81-15770", "2026-06-10", "12:45:00")
    check("classify-db: name candidates for (store,weekday,time-band)", "홍길동" in cands)

    # --- T5: quarantine → promote → rollback leaves store-db IDENTICAL on rollback (★master 실측) ---
    promoted0 = ["WK23_2026"]
    _write(PROMOTED, promoted0)
    base_db = rollup_from_ledger(promoted0)
    _write(STORE_DB, base_db)
    classifydb_rebuild()
    s0 = json.dumps(_read(STORE_DB, {}), sort_keys=True, ensure_ascii=False)   # snapshot S0 (live state)
    quarantine_week("WK24_2026")
    check("txn: quarantine does NOT mutate live store-db",
          json.dumps(_read(STORE_DB, {}), sort_keys=True, ensure_ascii=False) == s0)
    pr = promote_week("WK24_2026", verdict="PASS", verdict_week="WK24_2026")   # DB-1 gated promote
    s1 = json.dumps(_read(STORE_DB, {}), sort_keys=True, ensure_ascii=False)
    check("txn: promote grows store-db (WK24 merged)", s1 != s0 and "WK24_2026" in pr["promoted"])
    rb = rollback()
    s2 = json.dumps(_read(STORE_DB, {}), sort_keys=True, ensure_ascii=False)
    check("txn: ROLLBACK restores store-db IDENTICAL to pre-promote (S2==S0)", s2 == s0)
    check("txn: rollback popped WK24 from promoted", rb["undid"] == "WK24_2026" and "WK24_2026" not in rb["promoted"])

    # ═══════════════ ★BATCH B — db SOT integrity (non-vacuous: each FAIL pre-fix / PASS post-fix) ═══════════════
    def _raises(fn):
        try:
            fn(); return False
        except Exception:
            return True

    # --- DB-1: promote_week fail-closed gate (verdict==PASS AND week-match) ---
    configure(base)
    quarantine_week("WK25_2026")
    check("DB-1: promote verdict='FAIL' → REFUSE", _raises(lambda: promote_week("WK25_2026", verdict="FAIL", verdict_week="WK25_2026")))
    check("DB-1: promote no verdict (None) → REFUSE (fail-closed)", _raises(lambda: promote_week("WK25_2026", verdict_week="WK25_2026")))
    check("DB-1: promote wrong-week verdict → REFUSE", _raises(lambda: promote_week("WK25_2026", verdict="PASS", verdict_week="WK99_2026")))
    check("DB-1: promote verdict='PASS' + week-match → proceeds",
          promote_week("WK25_2026", verdict="PASS", verdict_week="WK25_2026").get("keys") is not None)

    # --- DB-4: EXPR_DB_BASE == planning collision → reject ---
    check("DB-4: EXPR_DB_BASE == PROJECT_DIR/planning → reject (ValueError)", _raises(lambda: configure(PROJECT_DIR / "planning")))
    configure(base)   # restore temp base (DB-4 raise left _BASE half-set)

    # --- DB-2: crash-safety — half-committed promote → detected + self-heal (never silent desync) ---
    _write(PROMOTED, ["WK23_2026"]); _write(STORE_DB, rollup_from_ledger(["WK23_2026"]))
    _write(PROMOTED, ["WK23_2026", "WK24_2026"])          # CRASH: PROMOTED advanced, STORE_DB NOT rebuilt
    cb, _ = store_db_consistent()
    heal = startup_consistency_check(self_heal=True)
    ca, _ = store_db_consistent()
    check("DB-2: half-committed promote detected INCONSISTENT (PROMOTED has WK24, store-db stale)", cb is False)
    check("DB-2: startup_consistency_check SELF-HEALS → store-db == rollup_from_ledger(promoted)",
          heal["healed"] is True and ca is True)
    check("DB-2: healed store-db includes WK24 (DINNER=2, no silent half-commit)",
          _read(STORE_DB, {}).get("217-81-14493", {}).get("section_dist", {}).get("DINNER") == 2)
    _write(PROMOTED, ["WK23_2026", "WK24_2026"]); _write(STORE_DB, rollup_from_ledger(["WK23_2026"]))
    nh = startup_consistency_check(self_heal=False)
    check("DB-2: fail-closed mode surfaces inconsistency (consistent=False, no silent pass)",
          nh["consistent"] is False and nh["healed"] is False)

    # --- DB-3: idempotency — retry of an already-promoted week short-circuits (no double snapshot) ---
    for _f in SNAP_DIR.glob("store-db.pre-*.json"):
        _f.unlink()
    _write(PROMOTED, []); _write(STORE_DB, {})
    quarantine_week("WK23_2026")
    promote_week("WK23_2026", verdict="PASS", verdict_week="WK23_2026")
    snaps1 = sorted(p.name for p in SNAP_DIR.glob("store-db.pre-*.json"))
    quarantine_week("WK23_2026")                         # simulate a retry
    p2 = promote_week("WK23_2026", verdict="PASS", verdict_week="WK23_2026")
    snaps2 = sorted(p.name for p in SNAP_DIR.glob("store-db.pre-*.json"))
    check("DB-3: retry of already-promoted week SHORT-CIRCUITS (already_promoted)", p2.get("already_promoted") is True)
    check("DB-3: retry does NOT create a second snapshot (snapshot-once-per-week)",
          snaps1 == snaps2 == ["store-db.pre-WK23_2026.json"])
    check("DB-3: WK23 listed once in promoted (no double-add)", _read(PROMOTED, []).count("WK23_2026") == 1)

    # --- DB-5: NFC/canonical-case sector learned; unknown sector warned/counted (not dropped) ---
    db5 = rollup([{"sector": "Staff Meeting", "store": "A", "amount": 1000, "week": "WX"},
                  {"sector": "DINNER", "store": "B", "amount": 1000, "week": "WX"},
                  {"sector": "FOOBAR-SECTOR", "store": "C", "amount": 1000, "week": "WX"}])
    check("DB-5: 'Staff Meeting' case-variant → learned as STAFF", db5.get("name:a", {}).get("dominant_section") == "STAFF")
    check("DB-5: 'DINNER' case-variant → learned as DINNER", db5.get("name:b", {}).get("dominant_section") == "DINNER")
    check("DB-5: unknown 'FOOBAR-SECTOR' counted/surfaced (NOT silently dropped)", LAST_ROLLUP_UNKNOWN.get("FOOBAR-SECTOR") == 1)
    _det = rollup([{"sector": "PARKING/TOLLS", "store": "T", "amount": 1, "week": "WX"}])
    check("DB-5: deterministic PARKING/TOLLS excluded but NOT flagged unknown", _det == {} and not LAST_ROLLUP_UNKNOWN)

    # --- DB-6: gallery id = max+1 (collision-free after deletion) ---
    _write(GALLERY_JSON, [])
    gallery_add("a", store="S1"); gallery_add("b", store="S2"); gallery_add("c", store="S3")
    _write(GALLERY_JSON, [e for e in gallery_read() if e["id"] != "G-0002"])   # delete the middle
    g4 = gallery_add("d", store="S4")
    _ids = [e["id"] for e in gallery_read()]
    check("DB-6: post-deletion gallery_add = max+1 (G-0004), no duplicate id", g4["id"] == "G-0004" and len(_ids) == len(set(_ids)))

    # --- DB-7: amount int ≡ str → one ledger row (canonical content_sig) ---
    _write(LEDGER, [])
    ledger_add({"store": "Z", "date": "2026-06-02", "amount": 5000, "time": "18:00", "handwriting": None, "week": "WZ"})
    ledger_add({"store": "Z", "date": "2026-06-02", "amount": "5,000", "time": "18:00", "handwriting": None, "week": "WZ"})
    check("DB-7: int 5000 ≡ str '5,000' → single ledger row (canonical sig dedup)",
          len([r for r in ledger_read() if r.get("week") == "WZ"]) == 1)

    # --- DB-8: name_index_add does NOT cache the (unpromoted) store-db ---
    _write(STORE_DB, {"someStore": {"x": 1}}); _write(CLASSIFY_DB, {})
    name_index_add("mk1", "2026-06-03", "12:30", ["홍길동"])
    check("DB-8: name_index_add does NOT snapshot store_sector (no unpromoted leak)", "store_sector" not in _read(CLASSIFY_DB, {}))
    classifydb_rebuild()
    check("DB-8: store_sector refreshed ONLY via classifydb_rebuild (post-verify)",
          _read(CLASSIFY_DB, {}).get("store_sector") == {"someStore": {"x": 1}})

    # --- DB-9: unparseable date at ingest surfaced (not silent '?') ---
    _write(CLASSIFY_DB, {})
    name_index_add("mk2", "notadate", "12:30", ["김철수"])
    check("DB-9: unparseable date surfaced in ingest_warnings (not silent '?')",
          any(w.get("type") == "bad_date" and w.get("value") == "notadate" for w in _read(CLASSIFY_DB, {}).get("ingest_warnings", [])))

    # --- DB-10: single-observation store is NOT max-confidence (shrunk toward 0.5) ---
    solo = rollup([{"sector": "Dinner", "store": "Solo", "amount": 5000, "week": "WS"}]).get("name:solo")
    check("DB-10: single-observation conf shrunk (0.667 < 1.0); raw_confidence=1.0 retained",
          solo and solo["confidence"] == 0.667 and solo["raw_confidence"] == 1.0 and solo["occurrences"] == 1)

    shutil.rmtree(base, ignore_errors=True)
    print(f"\nreused project helpers (norm_store/parse_date): {_REUSED}")
    print("RESULT:", "PASS — all 실측 checks green" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
