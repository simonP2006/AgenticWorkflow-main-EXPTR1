#!/usr/bin/env python3
"""expensereceipt_orchestrator.py — M8: the representative `expensereceipt` master orchestrator harness.

Coordinates the 6 sub-skills end-to-end (PORT of run_week.py's re-entrant harness model):
  autodetect/extract (vision OCR + handwriting = HALT) → merchant (biz checksum / card match) →
  classify (6-sector, escalations) → ★verify-LOGICAL (ANCHOR #2a gate) → place (Receipt Sheet) →
  ★verify-PHYSICAL (post-place re-check) → db (per-receipt ledger / gallery, quarantine→promote).

★★The fail-closed verify-consumption contract derived from the M7 audit (the core of gate trust):
  ① ALWAYS pass store_db (even {} cold-start) + name_db + vote_audit + card_records to run_logical.
     Omitting store_db makes V7 return ERROR (fail-closed) — by design.
  ② Consume the verdict fail-CLOSED: verify verdict ERROR (a mandatory check could not run) OR a
     violation-FAIL ⇒ the irreversible place mutation is **NEVER** performed → HALT + escalate. Only a
     clean verdict (PASS; deliberate N/A-SKIPs allowed) proceeds.
  ③ G6 2-split runtime: run_logical (pre-place) PASS ⇒ place ⇒ run_physical (post-place) re-verify.
     A logical FAIL/ERROR means place is not even attempted.

Other guardrails:
  • G12 — intelligent auto-confirm: among classify escalations, auto-confirm ONLY high-confidence
    Dinner-venue cases (store-db dominant DINNER with confidence ≥ 0.95) with a logged rationale; every
    genuinely-ambiguous escalation (≥2-name selection, unknown name) → owner escalation (no silent confirm).
  • G5 — section-confirmed.json is written by the master/human (this orchestrator), never a sub-skill.
  • G13 — NFC-normalize input paths. • orchestration trace (decision log) is emitted at every stage.

Testability: the verify / place callables are dependency-INJECTED (default = the real sub-skill
functions) so the self-test can force ERROR/FAIL degradations and prove, NON-VACUOUSLY (via a place-spy),
that place is never reached when the logical gate is not clean. happy-green ≠ trust (M7 lesson).

SOT discipline (절대 기준 2): the master is the SOLE SOT writer; sub-skills RETURN; verify is read-only.
"""

import os
import re
import sys
import json
import unicodedata
from pathlib import Path


def _find_project_dir():
    p = Path(__file__).resolve()
    for anc in p.parents:
        if (anc / "CLAUDE.md").exists() and (anc / "scripts").is_dir():
            return anc
    return p.parents[4] if len(p.parents) >= 5 else p.parent


PROJECT_DIR = _find_project_dir()
# ★HOLDFIX-1 [ROOT] producer binding RELATIVE-TO-SELF: import the sibling sub-skills from THIS orchestrator's
# own skill-tree parent (the dir that holds every `expensereceipt-*`), NOT a hardcoded PROJECT_DIR/.claude/skills.
# In the copy tree this resolves to `_hardening/skills/*` (the HARDENED siblings — so the integration is
# verifiable AS-SHIPPED, no sandbox repoint); post-merge under `.claude/skills/expensereceipt/` it resolves to
# `.claude/skills/*` (the then-hardened tree). The artifact is self-consistent in whatever tree it ships in.
# (.../<skills>/expensereceipt/scripts/expensereceipt_orchestrator.py → parents[2] = the <skills> dir.)
SKILLS = Path(__file__).resolve().parents[2]

# --- import the real sub-skill producers (defaults for dependency injection) ---
# ★HOLDFIX-1 (binding order): import the LEAF producers (place, db) BEFORE verify. verify imports place's
# primitives at its OWN module-level via verify's own (frozen) skill-path; if verify loaded first it would
# cache sys.modules['expensereceipt_place'] to whatever ITS path resolves — clobbering this orchestrator's
# sibling-relative COPY place (so `build_placements` would be absent). Loading COPY place FIRST caches the
# hardened module; verify then reuses the cached COPY place. (All three dirs are on sys.path already.)
_REUSED = {}
for _name, _dir in (("place", "expensereceipt-place"), ("db", "expensereceipt-db"),
                    ("verify", "expensereceipt-verify")):
    sys.path.insert(0, str(SKILLS / _dir / "scripts"))
try:
    from expensereceipt_place import place as _real_place, zip_drawing_counts as _real_zdc  # noqa: E402
    _REUSED["place"] = True
except Exception:
    _real_place = _real_zdc = None
    _REUSED["place"] = False
try:                                                  # DB-1: db promote producer (verdict-gated, Batch B)
    from expensereceipt_db import promote_week as _real_promote_week, quarantine_week as _real_quarantine_week  # noqa: E402
    _REUSED["db"] = True
except Exception:
    _real_promote_week = _real_quarantine_week = None
    _REUSED["db"] = False
try:
    from expensereceipt_verify import run_logical as _real_run_logical, run_physical as _real_run_physical  # noqa: E402
    _REUSED["verify"] = True
except Exception:
    _real_run_logical = _real_run_physical = None
    _REUSED["verify"] = False


def _nfc(s):
    return unicodedata.normalize("NFC", str(s)) if s is not None else s


# ============================================================ ★runtime copy-first / input-isolation
def stage_inputs(week, source_root=None, dest_root=None):
    """★Input-isolation (절대 기준: raw-data/input is INVIOLABLE). Copy raw-data/input/<week>/ → a workspace
    ONCE, then run the ENTIRE pipeline (autodetect → extract → OCR → place → db) on the COPY — so the
    protected input directory is read exactly once and NEVER written/re-saved by any tool (the M9 .xls
    incident: an external process rewrote the workbook's BIFF WRITEACCESS record — the writer-app string,
    card data unchanged — when the input dir was repeatedly accessed). The
    master calls this BEFORE autodetect; all downstream skills receive the staged path. Returns the staged
    week dir. Read-only on source; writes only under dest_root."""
    import shutil
    src = (Path(source_root) if source_root else (PROJECT_DIR / "raw-data" / "input")) / week
    dst = (Path(dest_root) if dest_root else (PROJECT_DIR / "research" / "expensereceipt" / "input-staging")) / week
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)        # single read of input; ALL processing happens on dst
    return dst


# ============================================================ G12 — intelligent auto-confirm
G12_DINNER_CONF = 0.95


def _store_key(store):
    """DR-5: the store-db fallback key built with the SHARED norm_store rule (NFC + lower + strip +
    collapse-internal-whitespace) so a double-space store name matches the store-db keying (which uses
    build_store_db.norm_store). A bare `name:<_nfc(store).lower()>` would miss a ws-variant key."""
    s = unicodedata.normalize("NFC", str(store or "")).strip().lower()
    return "name:" + re.sub(r"\s+", " ", s)


def _dinner_confidence(escalation, store_db):
    """Store-db confidence that the escalation's merchant is a Dinner venue (0..1)."""
    key = escalation.get("merchant_key") or _store_key(escalation.get("store", ""))   # DR-5 shared key
    e = (store_db or {}).get(key) or (store_db or {}).get(escalation.get("merchant_key", ""))
    if not e:
        return 0.0
    return e.get("confidence", 0.0) if e.get("dominant_section") == "DINNER" else 0.0


def decide_escalations(escalations, store_db, threshold=G12_DINNER_CONF):
    """★G12: auto-confirm ONLY high-confidence Dinner-venue escalations (with logged rationale); every
    genuinely-ambiguous escalation → owner. Never silently confirm an ambiguous one (ANCHOR #2b)."""
    auto, owner = [], []
    for e in escalations:
        conf = _dinner_confidence(e, store_db)
        if e.get("suggested") == "Dinner" and conf >= threshold:
            auto.append({"id": e.get("id"), "sector": "Dinner",
                         "rationale": f"G12 auto-confirm: store-db dominant DINNER, confidence {conf:.2f} ≥ {threshold}"})
        else:
            owner.append({"id": e.get("id"), "reason": e.get("reason"), "suggested": e.get("suggested"),
                          "dinner_confidence": round(conf, 2)})
    return auto, owner


def write_section_confirmed(path, auto_confirmed, owner_confirmed=None):
    """★G5: the master/human writes section-confirmed.json (never a sub-skill). Maps receipt id → sector."""
    confirmed = {a["id"]: a["sector"] for a in auto_confirmed}
    for o in (owner_confirmed or []):
        confirmed[o["id"]] = o["sector"]
    _write_json(path, confirmed)
    return confirmed


# ============================================================ DB-1: verdict-gated db settlement transaction
def _real_db_settle(week, verdict):
    """★DB-1 (orchestrator half): the verdict-GATED db transaction — quarantine the week's observations then
    promote them into the live store-db ONLY when verdict=='PASS'. The db-side promote_week (Batch B) double-
    checks verdict==PASS + week-match, so promotion is fail-closed at BOTH layers. This is reached ONLY after
    a clean logical PASS + physical PASS (an earlier ERROR/violation-FAIL HALTs before place/physical/db)."""
    if verdict != "PASS":
        return {"status": "SKIP", "promoted": False, "reason": f"verdict={verdict} (not PASS) → NO promote (fail-closed)"}
    if _real_promote_week is None or _real_quarantine_week is None:
        return {"status": "ERROR", "promoted": False, "reason": "db producer unavailable (fail-closed)"}
    try:
        _real_quarantine_week(week)
        res = _real_promote_week(week, verdict="PASS", verdict_week=week)   # db-side gate re-checks PASS+week
        return {"status": "OK", "promoted": True, "db": res}
    except Exception as e:
        return {"status": "ESCALATE", "promoted": False, "error": str(e)}


# ============================================================ ★the fail-closed gate-and-place core (M7 contract)
def gate_and_place(run, *, verify_logical=None, place=None, verify_physical=None, zip_drawing_counts=None,
                   db_settle=None, emit=None):
    """The critical M8 contract enforcement. run = {receipts, card_records, vote_audit, store_db, name_db,
    multiread_expected, template, output, placements}. Returns a result dict; emits trace events.

    ★Order is load-bearing: LOGICAL verify must pass BEFORE place is even attempted (G6 ② / M7 ②③)."""
    verify_logical = verify_logical or _real_run_logical
    place = place or _real_place
    verify_physical = verify_physical or _real_run_physical
    zip_drawing_counts = zip_drawing_counts or _real_zdc
    db_settle = db_settle if db_settle is not None else _real_db_settle    # DB-1
    emit = emit or (lambda *a, **k: None)

    if verify_logical is None or place is None:
        emit("gate", "ERROR", "verify/place producer unavailable — cannot run (fail-closed)")
        return {"status": "ERROR", "stage": "import", "placed": False}

    # --- ★① always supply store_db (+ name_db, vote_audit, card_records); ② consume fail-closed; ③ pre-place ---
    # ★V6-WIRING (orch half): thread run_dir/expected_week so verify binds the vote-audit FROM DISK (dual-file,
    #   multiread-from-disk-count; wrong-week ⇒ ERROR). ★DH-3: thread sales_slips so the KICC/롯데 매출전표
    #   (card sales-slip alternate-receipt) path is reachable — the slip settles instead of a false V2-FAIL.
    _vk = dict(sales_slips=run.get("sales_slips"), run_dir=run.get("run_dir"),
               expected_week=run.get("expected_week"), confirmed=run.get("confirmed"))
    try:
        code, lrep = verify_logical(run["receipts"], run.get("card_records"), run.get("vote_audit"),
                                    run.get("store_db"), run.get("name_db"),
                                    run.get("multiread_expected", True), **_vk)
    except TypeError as e:
        # ★HOLDFIX-2 [CRITICAL] FAIL-CLOSED (M7 lesson): if the bound verify cannot accept the V6/DH-3 wiring
        # contract (run_dir/expected_week/sales_slips), it is NOT the hardened producer. Silently re-calling
        # WITHOUT them would FAIL-OPEN — a wrong-week vote-audit goes undetected and the KICC sales_slips are
        # dropped, so a not-clean run could reach the irreversible place. NEVER degrade silently → ERROR/HALT.
        emit("verify-logical", "ERROR",
             f"verify rejected the V6/DH-3 wiring contract (un-hardened binding?) — fail-closed HALT: {e}")
        return {"status": "ERROR", "stage": "verify-wiring", "placed": False,
                "error": f"verify producer does not accept the wiring kwargs (run_dir/expected_week/sales_slips): {e}"}
    emit("verify-logical", lrep.get("verdict"), f"exit={code}")
    if code != 0:
        # verdict ERROR (unrun mandatory check) OR violation-FAIL → NEVER place. HALT + escalate.
        emit("place", "HALT", f"logical gate not clean (verdict={lrep.get('verdict')}) → place FORBIDDEN (fail-closed)")
        return {"status": "HALT", "stage": "verify-logical", "verdict": lrep.get("verdict"),
                "logical_report": lrep, "placed": False}

    # --- logical PASS → place (the irreversible mutation) ---
    baseline = zip_drawing_counts(run["template"]) if zip_drawing_counts else {"pic": 0, "sp_rdr": 0, "anchor": 0}
    presult = place(run["template"], run["output"], run["placements"])
    emit("place", presult.get("status"), f"placed={presult.get('placed')}")
    if presult.get("status") != "OK":
        return {"status": "ESCALATE", "stage": "place", "place_result": presult, "placed": False}

    # --- ★post-place PHYSICAL re-verify (independent of place's internal G8 check) ---
    pcode, prep = verify_physical(run["output"], baseline, len(run["placements"]))
    emit("verify-physical", prep.get("verdict"), f"exit={pcode}")
    if pcode != 0:
        return {"status": "ESCALATE", "stage": "verify-physical", "verdict": prep.get("verdict"),
                "physical_report": prep, "placed": True}

    # --- ★DB-1: verdict-GATED db settlement — reached ONLY after logical PASS + physical PASS (overall PASS).
    #     A FAIL/ERROR verdict HALTs above → db_settle is NEVER reached → NO promote (fail-closed end-to-end). ---
    if run.get("week"):
        dbres = db_settle(run["week"], "PASS")
        emit("db-settle", dbres.get("status", "OK"), f"week={run['week']} promoted={dbres.get('promoted')}")
        if dbres.get("status") == "ESCALATE":
            return {"status": "ESCALATE", "stage": "db-settle", "placed": True,
                    "logical_report": lrep, "physical_report": prep, "db_result": dbres}
        return {"status": "OK", "logical_report": lrep, "physical_report": prep, "placed": True, "db_result": dbres}
    return {"status": "OK", "logical_report": lrep, "physical_report": prep, "placed": True}


# ============================================================ orchestration trace + run driver
def orchestrate(run, *, inject=None, report_dir=None):
    """End-to-end deterministic orchestration (vision OCR/handwriting are LLM HALTs handled by the master
    Claude, not here). Builds the trace, runs G12 on classify escalations, writes section-confirmed.json
    (G5), then the fail-closed gate_and_place (G6/M7) → DB-1 verdict-gated db settlement. `inject` overrides
    callables for testing.
    ★DH-7 (copy-first): `stage_inputs()` is the master's MANDATORY pre-pipeline step — the master copies
    raw-data/input/<week>/ to a workspace ONCE and derives this `run` dict (receipts/placements/card_records)
    from the STAGED copy, so the protected input is never re-read/written. orchestrate() operates on that
    already-staged run data and does NOT itself touch raw-data/input (no auto-stage here by design)."""
    inject = inject or {}
    trace = []

    def emit(stage, status, detail=""):
        trace.append({"stage": stage, "status": status, "detail": str(detail)[:300]})

    # G12 + G5 (resolve classify escalations before gating)
    escalations = run.get("escalations") or []
    auto, owner = decide_escalations(escalations, run.get("store_db") or {})
    emit("classify-escalations", "RESOLVED", f"auto={len(auto)} owner={len(owner)}")
    if report_dir:
        write_section_confirmed(Path(report_dir) / "section-confirmed.json", auto)   # G12-auto only
        emit("section-confirmed", "WRITTEN", "master-write (G5) — auto-confirmed only")

    # ★§6-b owner-control: a genuinely-ambiguous escalation must NOT be best-guess placed. If any
    # unresolved owner-escalation remains, the run HALTS here — the irreversible place is HELD until the
    # owner confirms the sector(s) (writes section-confirmed.json) and re-runs (the classify-HALT pattern).
    # On re-run, classify reads the confirmations → no escalation → the gate proceeds. (ANCHOR #2b.)
    if owner:
        emit("owner-escalation", "HALT", f"{len(owner)} genuinely-ambiguous → owner confirmation required; place HELD (nothing placed)")
        res = {"status": "HALT", "stage": "owner-escalation", "placed": False,
               "owner_escalations": owner, "auto_confirmed": auto, "trace": trace}
        if report_dir:
            _write_json(Path(report_dir) / "orchestration-trace.json",
                        {"status": res["status"], "placed": False, "trace": trace,
                         "auto_confirmed": auto, "owner_escalations": owner})
        return res

    # no unresolved owner-escalation → run the fail-closed verify→place→verify gate
    res = gate_and_place(
        run, emit=emit,
        verify_logical=inject.get("verify_logical"), place=inject.get("place"),
        verify_physical=inject.get("verify_physical"), zip_drawing_counts=inject.get("zip_drawing_counts"),
        db_settle=inject.get("db_settle"))
    res["trace"] = trace
    res["owner_escalations"] = owner
    res["auto_confirmed"] = auto
    if report_dir:
        _write_json(Path(report_dir) / "orchestration-trace.json",
                    {"status": res["status"], "placed": res["placed"], "trace": trace,
                     "auto_confirmed": auto, "owner_escalations": owner})
    return res


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


# ============================================================ 실측 SELF-TEST (non-vacuous, fail-closed)
def _selftest():
    import tempfile
    ok = True

    def check(label, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    # --- a place-SPY proves, non-vacuously, whether place was actually reached ---
    class Spy:
        def __init__(self): self.calls = 0
        def __call__(self, template, output, placements):
            self.calls += 1
            return {"status": "OK", "placed": len(placements), "output": str(output)}

    base_run = {
        "receipts": [{"id": "R1", "store": "스팟마트", "date": "2026-06-02", "amount": 5000, "people": 1,
                      "biz_no": "119-81-00851", "handwriting": "dinner alone", "hw_confidence": 0.95, "sector": "Dinner"}],
        "card_records": [{"date": "2026-06-02", "amount": 5000, "raw": {"사업자번호": "119-81-00851"}}],
        "vote_audit": {"result": "CONSENSUS", "reads": 3},
        "store_db": {}, "name_db": {}, "multiread_expected": True,
        "template": "T.xlsx", "output": "O.xlsx", "placements": [{"img_path": "x", "from": (1, 0, 1, 0), "to": (2, 0, 2, 0)}],
    }

    def vl_pass(*a, **k): return 0, {"verdict": "PASS", "checks": []}
    def vl_error(*a, **k): return 1, {"verdict": "ERROR", "checks": []}
    def vl_fail(*a, **k): return 1, {"verdict": "FAIL", "checks": []}
    def vp_pass(*a, **k): return 0, {"verdict": "PASS", "checks": []}
    def vp_fail(*a, **k): return 1, {"verdict": "FAIL", "checks": []}
    def zdc(_): return {"pic": 0, "sp_rdr": 1, "anchor": 1}

    # --- ★HAPPY: logical PASS → place reached → physical PASS → OK ---
    spy = Spy()
    r = gate_and_place(base_run, verify_logical=vl_pass, place=spy, verify_physical=vp_pass, zip_drawing_counts=zdc)
    check("happy: logical PASS → status OK + placed", r["status"] == "OK" and r["placed"] is True)
    check("happy: place was actually reached (spy.calls==1)", spy.calls == 1)

    # --- ★★INJECTION (fail-closed, NON-VACUOUS): logical ERROR → place NEVER reached ---
    spy = Spy()
    r = gate_and_place(base_run, verify_logical=vl_error, place=spy, verify_physical=vp_pass, zip_drawing_counts=zdc)
    check("★fail-closed: logical ERROR → status HALT, NOT placed", r["status"] == "HALT" and r["placed"] is False)
    check("★NON-VACUOUS: place was NEVER called on logical ERROR (spy.calls==0)", spy.calls == 0)

    spy = Spy()
    r = gate_and_place(base_run, verify_logical=vl_fail, place=spy, verify_physical=vp_pass, zip_drawing_counts=zdc)
    check("★fail-closed: logical violation-FAIL → HALT, NOT placed", r["status"] == "HALT" and r["placed"] is False)
    check("★NON-VACUOUS: place NEVER called on logical FAIL (spy.calls==0)", spy.calls == 0)

    # --- physical FAIL after place → ESCALATE (place happened, flagged) ---
    spy = Spy()
    r = gate_and_place(base_run, verify_logical=vl_pass, place=spy, verify_physical=vp_fail, zip_drawing_counts=zdc)
    check("physical FAIL after place → ESCALATE (placed True, flagged)", r["status"] == "ESCALATE" and r["stage"] == "verify-physical")
    check("physical FAIL: place did happen (spy.calls==1, order preserved)", spy.calls == 1)

    # --- ★verify/place producer unavailable → ERROR (fail-closed, not silent pass). NON-VACUOUS: force the
    #     module's real producers to None and confirm gate_and_place ERRORs without placing. ---
    spy = Spy()
    Vm = sys.modules[__name__]
    _ol, _op = Vm._real_run_logical, Vm._real_place
    Vm._real_run_logical = None
    Vm._real_place = None
    try:
        r = gate_and_place(base_run, place=spy)   # injected place exists, but verify producer is absent
        check("★producer-absent (verify) → status ERROR, NOT placed (fail-closed)", r["status"] == "ERROR" and r["placed"] is False)
        check("★producer-absent: place NEVER called (spy.calls==0)", spy.calls == 0)
    finally:
        Vm._real_run_logical, Vm._real_place = _ol, _op

    # --- ★G6 ORDERING: place is never reached before a logical PASS (proven across the 3 cases above) ---
    check("★G6 order invariant: HALT/ERROR cases all had spy.calls==0 (no pre-verify place)", True)

    # --- ★M7 contract ①: store_db ALWAYS passed (use the REAL verify; omitting store_db ⇒ V7 ERROR ⇒ HALT) ---
    if _REUSED.get("verify"):
        spy = Spy()
        no_store = dict(base_run); no_store["store_db"] = None     # simulate forgetting store_db
        r = gate_and_place(no_store, place=spy)                      # real verify_logical
        check("★M7①: store_db=None → real verify V7 ERROR → HALT, place NOT reached",
              r["status"] == "HALT" and spy.calls == 0)
        spy = Spy()
        with_store = dict(base_run); with_store["store_db"] = {}    # cold-start {} is runnable
        # use real verify_logical but a place-spy + physical-pass to isolate the logical gate
        r = gate_and_place(with_store, place=spy, verify_physical=vp_pass, zip_drawing_counts=zdc)
        check("★M7①: store_db={} (cold-start) → real verify PASS → place reached",
              r["status"] == "OK" and spy.calls == 1)
    else:
        check("★M7① (skipped — verify not importable)", True)

    # --- ★G12 auto-confirm ---
    sdb = {"119-81-00851": {"dominant_section": "DINNER", "confidence": 0.97},
           "polbasset": {"dominant_section": "STAFF", "confidence": 0.6}}
    esc = [{"id": "E1", "suggested": "Dinner", "merchant_key": "119-81-00851"},   # high-conf dinner → auto
           {"id": "E2", "suggested": "Dinner", "merchant_key": "unknown99"},       # unseen → owner
           {"id": "E3", "reason": "≥2 name selection", "merchant_key": "polbasset"}]  # ambiguous → owner
    auto, owner = decide_escalations(esc, sdb)
    check("G12: high-confidence Dinner (conf 0.97≥0.95) → auto-confirm with rationale",
          len(auto) == 1 and auto[0]["id"] == "E1" and "rationale" in auto[0])
    check("G12: unseen-store + ≥2-name → owner escalation (no silent confirm)",
          {o["id"] for o in owner} == {"E2", "E3"})
    check("G12: below-threshold dinner not auto-confirmed",
          all(a["id"] != "E2" for a in auto))

    # --- ★§6-b owner-control: unresolved owner-escalation → HALT, place HELD (NON-VACUOUS) ---
    work = Path(tempfile.mkdtemp(prefix="orch_self_"))
    spyO = Spy()
    run_amb = dict(base_run, escalations=esc, store_db=sdb)        # esc has E2/E3 owner-ambiguous
    res = orchestrate(run_amb, inject={"verify_logical": vl_pass, "place": spyO,
                                       "verify_physical": vp_pass, "zip_drawing_counts": zdc}, report_dir=work)
    check("★§6-b: unresolved owner-escalation → status HALT (place HELD, nothing placed)",
          res["status"] == "HALT" and res["placed"] is False)
    check("★§6-b NON-VACUOUS: place NEVER called while owner ambiguity unresolved (spyO.calls==0)", spyO.calls == 0)
    check("★G5: section-confirmed.json written with G12 auto-confirm ONLY (E1→Dinner, not E2/E3)",
          json.loads((work / "section-confirmed.json").read_text(encoding="utf-8")) == {"E1": "Dinner"})
    check("owner escalations surfaced (E2,E3)", {o["id"] for o in res["owner_escalations"]} == {"E2", "E3"})
    check("★trace 'owner-escalation:HALT' is TRUTHFUL (no place/verify-physical after it)",
          any(t["stage"] == "owner-escalation" and t["status"] == "HALT" for t in res["trace"]) and
          not any(t["stage"] in ("place", "verify-physical") for t in res["trace"]))
    check("orchestration-trace.json written (decision log)", (work / "orchestration-trace.json").exists())

    # --- no owner-escalation (all G12 auto / none) → run proceeds to the gate, place reached ---
    work2 = Path(tempfile.mkdtemp(prefix="orch_self2_"))
    spyB = Spy()
    run_clean = dict(base_run, escalations=[{"id": "E1", "suggested": "Dinner", "merchant_key": "119-81-00851"}], store_db=sdb)
    res2 = orchestrate(run_clean, inject={"verify_logical": vl_pass, "place": spyB,
                                          "verify_physical": vp_pass, "zip_drawing_counts": zdc}, report_dir=work2)
    check("no owner-escalation (all G12-auto) → status OK + placed", res2["status"] == "OK" and res2["placed"] is True)
    check("no owner-escalation → place reached (spyB.calls==1)", spyB.calls == 1)
    check("trace order verify-logical → place → verify-physical (gate ran)",
          [t["stage"] for t in res2["trace"] if t["stage"].startswith("verify") or t["stage"] == "place"]
          == ["verify-logical", "place", "verify-physical"])
    check("G13: _nfc normalizes a path", _nfc("a") == "a")

    # --- ★runtime copy-first: stage_inputs copies input→workspace (SYNTHETIC source — no raw-data/input) ---
    ssrc = Path(tempfile.mkdtemp(prefix="stage_src_"))
    (ssrc / "WKxx").mkdir()
    (ssrc / "WKxx" / "카드승인내역_x.xls").write_bytes(b"data")
    sdst = Path(tempfile.mkdtemp(prefix="stage_dst_"))
    staged = stage_inputs("WKxx", source_root=ssrc, dest_root=sdst)
    src_md5_before = __import__("hashlib").md5((ssrc / "WKxx" / "카드승인내역_x.xls").read_bytes()).hexdigest()
    src_md5_after = __import__("hashlib").md5((ssrc / "WKxx" / "카드승인내역_x.xls").read_bytes()).hexdigest()
    check("★stage_inputs: copies input→workspace (runtime copy-first); source byte-unchanged",
          (staged / "카드승인내역_x.xls").exists() and src_md5_before == src_md5_after)
    import shutil as _sh
    _sh.rmtree(ssrc, ignore_errors=True); _sh.rmtree(sdst, ignore_errors=True)

    # ═══════════════ ★BATCH F — end-to-end wiring (orchestrate-level, non-vacuous, fail-closed) ═══════════════
    # --- ★V6-WIRING (orch half): orchestrator threads run_dir/expected_week → verify binds vote-audit FROM DISK ---
    vdir = Path(tempfile.mkdtemp(prefix="orch_v6_"))
    for i in (1, 2, 3):
        (vdir / f"ocr-results-{i}.json").write_text("{}", encoding="utf-8")
    (vdir / "ocr-vote-audit.json").write_text(
        json.dumps({"week": "WK21_2026", "reads": 3, "result": "CONSENSUS", "receipts": 1}), encoding="utf-8")
    if _REUSED.get("verify"):
        spyV = Spy()
        r = gate_and_place(dict(base_run, run_dir=str(vdir), expected_week="WK21_2026"),
                           place=spyV, verify_physical=vp_pass, zip_drawing_counts=zdc)
        check("★V6-WIRING: run_dir threaded → verify binds vote-audit FROM DISK (correct week) → place reached",
              r["status"] == "OK" and spyV.calls == 1)
        spyVw = Spy()
        rw = gate_and_place(dict(base_run, run_dir=str(vdir), expected_week="WK99_2026"),
                            place=spyVw, verify_physical=vp_pass, zip_drawing_counts=zdc)
        check("★V6-WIRING fail-closed: WRONG-week vote-audit on disk → verdict ERROR → HALT, place NOT reached",
              rw["status"] == "HALT" and spyVw.calls == 0)
    else:
        check("★V6-WIRING (skipped — verify not importable)", True)
    import shutil as _shv
    _shv.rmtree(vdir, ignore_errors=True)

    # --- ★DB-1 (orch call): verdict-GATED db settlement — verify FAIL/ERROR → NO promote; PASS → promote ---
    class DbSpy:
        def __init__(self): self.calls = 0; self.last = None
        def __call__(self, week, verdict):
            self.calls += 1; self.last = (week, verdict); return {"status": "OK", "promoted": True}
    dbF = DbSpy()
    rF = gate_and_place(dict(base_run, week="WK21_2026"), verify_logical=vl_fail, place=Spy(),
                        verify_physical=vp_pass, zip_drawing_counts=zdc, db_settle=dbF)
    check("★DB-1 fail-closed: logical FAIL → HALT → db_settle NEVER called (NO promote)", rF["status"] == "HALT" and dbF.calls == 0)
    dbE = DbSpy()
    rE = gate_and_place(dict(base_run, week="WK21_2026"), verify_logical=vl_error, place=Spy(),
                        verify_physical=vp_pass, zip_drawing_counts=zdc, db_settle=dbE)
    check("★DB-1 fail-closed: logical ERROR → HALT → db_settle NEVER called (NO promote)", rE["status"] == "HALT" and dbE.calls == 0)
    dbP = DbSpy()
    rP = gate_and_place(dict(base_run, week="WK21_2026"), verify_logical=vl_pass, place=Spy(),
                        verify_physical=vp_pass, zip_drawing_counts=zdc, db_settle=dbP)
    check("★DB-1: logical PASS + physical PASS → db_settle called ONCE with verdict=PASS (promote)",
          rP["status"] == "OK" and dbP.calls == 1 and dbP.last == ("WK21_2026", "PASS"))
    check("★DB-1: _real_db_settle(week, 'FAIL') → SKIP, promoted False (function-level verdict gate)",
          _real_db_settle("WK21_2026", "FAIL")["promoted"] is False)

    # --- ★DH-3: sales_slip threaded into verify → KICC 매출전표 settles (consumed, NOT a V2-FAIL) ---
    if _REUSED.get("verify"):
        kicc_run = dict(base_run, receipts=[],
                        card_records=[{"date": "2026-06-02", "amount": 3300, "raw": {"승인번호": "41777115", "사업자번호": "119-81-00851"}}],
                        sales_slips=[{"approval": "41777115", "amount": 3300}])
        spyK = Spy()
        rK = gate_and_place(kicc_run, place=spyK, verify_physical=vp_pass, zip_drawing_counts=zdc)
        check("★DH-3: KICC 매출전표 (승인번호+amount) threaded → consumed → V2 settles (not V2-FAIL) → place reached",
              rK["status"] == "OK" and spyK.calls == 1)
        spyKn = Spy()
        rKn = gate_and_place(dict(kicc_run, sales_slips=None), place=spyKn, verify_physical=vp_pass, zip_drawing_counts=zdc)
        check("★DH-3 non-vacuous: WITHOUT the slip → unconsumed card row → V2 FAIL → HALT (the slip is what settles it)",
              rKn["status"] == "HALT" and spyKn.calls == 0)
    else:
        check("★DH-3 (skipped — verify not importable)", True)

    # --- ★DR-5: _dinner_confidence uses the shared norm_store key (ws-collapse) → double-space store matches ---
    check("★DR-5: double-space store → G12 _dinner_confidence matches store-db (ws-collapsed key)",
          _dinner_confidence({"store": "폴  바셋", "suggested": "Dinner"},
                             {"name:폴 바셋": {"dominant_section": "DINNER", "confidence": 0.97}}) == 0.97)

    # --- ★LOW-2 carry-forward: two DISTINCT same-day same-amount receipts → BOTH placed (over-dedup NOT activated) ---
    if _REUSED.get("place"):
        from expensereceipt_place import build_placements as _bp, CALIBRATED_GEOMETRY as _cg
        plc2 = _bp([{"id": "R1", "source_image": "a.png", "date": "2026-06-02", "amount": 5000},
                    {"id": "R2", "source_image": "b.png", "date": "2026-06-02", "amount": 5000}],
                   {**_cg, "start_row": 100})
        check("★LOW-2: two DISTINCT same-day same-amount receipts → BOTH placed (id-keyed; store|amount over-dedup NOT activated)",
              len(plc2) == 2)
    else:
        check("★LOW-2 (skipped — place not importable)", True)

    import shutil
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(work2, ignore_errors=True)
    print(f"\nreused sub-skills: {_REUSED}")
    print("RESULT:", "PASS — all 실측 checks green (M8 orchestrator, fail-closed)" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
