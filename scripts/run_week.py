#!/usr/bin/env python3
"""run_week.py — Deterministic pipeline harness (R-A, ADR-pending).

Replaces the WK agent team's *control flow* (WK_orchestrator + phase1~4
_supervisor + secretary) with a deterministic, re-entrant Python harness.
The LLM agent team added orchestration latency and a hallucination surface
(an agent can misreport a step's success). A harness cannot. The only
genuinely non-deterministic work — Step 3 OCR and Step 6 bbox (Claude
Vision) — is NOT performed here; the harness HALTS at those points and hands
control back to the LLM with an exact spec, then resumes on the next call.

Re-entrant by design: each invocation detects the furthest completed stage
from on-disk artifacts and runs forward until the next vision gate or the
end. A Claude session drives it by: run → (do requested vision) → run again.

Error routing (deterministic, mirrors wk.md):
  MISSING  — expected output absent / script exit≠0 from missing input
             → retry once, then ESCALATE (stop + report).
  LOGIC    — a validator reports a value/integrity mismatch (exit 1)
             → STOP immediately, no retry (never ignore a violation).
  VISION   — Step 3 / Step 6 output not yet produced
             → HALT with exact handoff spec (not an error).

CSO compliance: per-week only; never bulk-loads workbooks; every script it
calls opens xlsx read_only where it reads. No long-running server.

Usage:
    python3 scripts/run_week.py WK21_2026            # auto-resume from disk state
    python3 scripts/run_week.py WK21_2026 --dry-run  # print plan, run nothing
    python3 scripts/run_week.py WK21_2026 --verify-only
    python3 scripts/run_week.py WK21_2026 --from S4   # force start stage
"""

import sys
import json
import subprocess
import re
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"
RESEARCH_DIR = PROJECT_DIR / "research"
PLANNING_DIR = PROJECT_DIR / "planning"
OUTPUT_DIR = PROJECT_DIR / "raw-data" / "output"
ANNOT_DIR = RESEARCH_DIR / "annotations"
RUN_LOG_DIR = PROJECT_DIR / "run-logs"

# Special exit codes
EXIT_OK = 0
EXIT_LOGIC = 1        # validator violation — stop
EXIT_VISION = 10      # vision handoff required (not a failure)
EXIT_ESCALATE = 20    # MISSING after retry — escalate to human/master


def _wk_num(week):
    m = re.match(r"WK?(\d{2})", week)
    return m.group(1) if m else week[2:4]


def _bbox_count(week):
    nn = _wk_num(week)
    p = ANNOT_DIR / f"wk{nn}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    imgs = d.get("images", d) if isinstance(d, dict) else d
    if isinstance(imgs, dict):
        imgs = list(imgs.values())
    total = 0
    if isinstance(imgs, list):
        for im in imgs:
            if isinstance(im, dict):
                bb = im.get("bboxes") or im.get("bbox") or []
                total += len(bb) if isinstance(bb, list) else 0
    return total


def _ocr_reads_present():
    return sorted(RESEARCH_DIR.glob("ocr-results-[0-9]*.json"))


def _sp_count(week):
    """Count injected RDR <sp> shapes in the output workbook (ns-agnostic)."""
    import zipfile
    xlsx = OUTPUT_DIR / f"simon_park_T&E_{week}.xlsx"
    if not xlsx.exists():
        return None
    sp = 0
    try:
        with zipfile.ZipFile(xlsx) as z:
            for n in z.namelist():
                if n.startswith("xl/drawings/drawing") and n.endswith(".xml"):
                    xml = z.read(n).decode("utf-8", "ignore")
                    sp += len(re.findall(r"<\w*:?sp\b", xml))
    except Exception:
        return None
    return sp


# ----------------------------------------------------------- stage plan ----
def _stages(week):
    nn = _wk_num(week)
    out_named = OUTPUT_DIR / f"simon_park_T&E_{week}.xlsx"
    out_wk00 = OUTPUT_DIR / "simon_park_T&E_WK00_2026.xlsx"
    return [
        dict(id="S0", kind="py", desc="OCR reset (secretary0)",
             cmd=["bash", "-c",
                  f"rm -f research/ocr-results.json research/ocr-results-[0-9]*.json "
                  f"research/ocr-vote-report.json research/wk{nn}_ocr-results.json"],
             produces=[], done=lambda: False, run_if_fresh_only=True, fail="MISSING"),
        dict(id="S1", kind="py", desc="extract_images.py",
             cmd=[sys.executable, "scripts/extract_images.py", week],
             produces=[RESEARCH_DIR / "input-manifest.json", out_wk00],
             done=lambda: (RESEARCH_DIR / "input-manifest.json").exists(), fail="MISSING"),
        dict(id="S2", kind="py", desc="extract_card_data.py",
             cmd=[sys.executable, "scripts/extract_card_data.py"],
             produces=[RESEARCH_DIR / "card-approval-data.json"],
             done=lambda: (RESEARCH_DIR / "card-approval-data.json").exists(), fail="MISSING"),
        dict(id="S3", kind="vision", desc="Step 3 OCR — Claude Vision N-read (3→7, ADR-045)",
             vision_check=lambda: bool(_ocr_reads_present()) or (RESEARCH_DIR / "ocr-results.json").exists(),
             handoff=("VISION-REQUIRED: OCR. Read research/images/*.png independently "
                      "3 times → research/ocr-results-{1,2,3}.json (schema: parking_tolls/"
                      "dinner/staff_meetings/travel/telephone; P0-2 reduced). Then re-run me.")),
        dict(id="S3g", kind="gate", desc="aggregate_ocr_votes.py (consensus gate)",
             cmd=[sys.executable, "scripts/aggregate_ocr_votes.py", week],
             produces=[RESEARCH_DIR / "ocr-results.json"],
             done=lambda: (RESEARCH_DIR / "ocr-results.json").exists(),
             gate_codes={0: "OK", 2: "VISION-MORE", 1: "LOGIC"}, fail="LOGIC"),
        dict(id="S3c", kind="gate", desc="classify_section — section predict + T3 escalation (R-D, non-disruptive)",
             cmd=[sys.executable, "scripts/classify_stage.py", week],
             produces=[], done=lambda: False,
             gate_codes={0: "OK", 2: "VISION-MORE", 1: "LOGIC"}, fail="LOGIC"),
        dict(id="S4", kind="py", desc="write_excel.py --all",
             cmd=[sys.executable, "scripts/write_excel.py", "--all"],
             produces=[out_named, PLANNING_DIR / "cell-mapping.json"],
             done=lambda: out_named.exists() and (PLANNING_DIR / "cell-mapping.json").exists(),
             fail="LOGIC"),
        dict(id="S5", kind="py", desc="generate_annotations.py",
             cmd=[sys.executable, "scripts/generate_annotations.py", week],
             produces=[ANNOT_DIR / f"wk{nn}-template.json"],
             done=lambda: (ANNOT_DIR / f"wk{nn}-template.json").exists(), fail="MISSING"),
        dict(id="S6", kind="vision", desc="Step 6 bbox — Claude Vision pixel coords (§20)",
             vision_check=lambda: (_bbox_count(week) or 0) >= 1,
             handoff=(f"VISION-REQUIRED: BBOX. Read research/annotations/wk{nn}-images/*.png, "
                      f"fill date/amount bboxes → research/annotations/wk{nn}.json "
                      f"(DINNER/STAFF/TRAVEL/PARKING exactly 2/receipt, TELEPHONE 4, "
                      f"TOLLS per-date; total ~25-35, >80 = spec violation). Then re-run me.")),
        dict(id="S6g", kind="gate", desc="annotate --check-only (P0-1 bbox guard)",
             cmd=[sys.executable, "scripts/annotate_receipts.py", "--check-only", week],
             produces=[], done=lambda: False,
             gate_codes={0: "OK", 1: "LOGIC"}, fail="LOGIC"),
        dict(id="S7", kind="py", desc="formula restore (check_and_restore_all_sheets — openpyxl LAST use)",
             cmd=[sys.executable, "-c",
                  "import sys; sys.path.insert(0,'scripts'); import openpyxl; "
                  "from write_excel import check_and_restore_all_sheets; "
                  f"p='raw-data/output/simon_park_T&E_{week}.xlsx'; "
                  "wb=openpyxl.load_workbook(p); r=check_and_restore_all_sheets(wb); "
                  "wb.save(p) if r else None; print(f'restored {len(r)}'); wb.close()"],
             produces=[out_named], done=lambda: False, fail="LOGIC"),
        dict(id="S8", kind="py", desc="annotate_receipts.py — RDR inject (FINAL, no openpyxl after)",
             cmd=[sys.executable, "scripts/annotate_receipts.py", week],
             produces=[out_named],
             done=lambda: (_sp_count(week) or 0) >= (_bbox_count(week) or 1), fail="LOGIC"),
        dict(id="V", kind="verify", desc="verify_week.py (unified gate)",
             cmd=[sys.executable, "scripts/verify_week.py", week],
             produces=[], done=lambda: False, gate_codes={0: "OK", 1: "LOGIC"}, fail="LOGIC"),
    ]


def _run_cmd(cmd, timeout=600):
    try:
        p = subprocess.run(cmd, cwd=str(PROJECT_DIR), capture_output=True,
                           text=True, timeout=timeout)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 999, "", str(e)


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 scripts/run_week.py WK21_2026 [--dry-run] [--verify-only] [--from S4]",
              file=sys.stderr)
        sys.exit(2)
    week = [a for a in args if not a.startswith("--")][0]
    dry = "--dry-run" in args
    verify_only = "--verify-only" in args
    from_stage = None
    if "--from" in args:
        i = args.index("--from")
        if i + 1 < len(args):
            from_stage = args[i + 1]

    stages = _stages(week)
    RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = {"week": week, "events": []}

    def emit(stage_id, status, detail=""):
        log["events"].append({"stage": stage_id, "status": status, "detail": detail[:300]})
        print(f"  [{status:9s}] {stage_id:4s} {detail}")

    if verify_only:
        stages = [s for s in stages if s["id"] == "V"]

    print(f"=== run_week {week} === ({'DRY-RUN' if dry else 'EXECUTE'})")

    # auto-resume: skip leading stages whose `done()` is already satisfied,
    # unless an explicit --from was given.
    started = from_stage is None
    fresh = not (RESEARCH_DIR / "input-manifest.json").exists()

    for st in stages:
        if from_stage and st["id"] == from_stage:
            started = True
        if not started:
            continue

        if dry:
            emit(st["id"], "PLAN", st["desc"])
            continue

        # skip already-complete deterministic stages (auto-resume)
        if from_stage is None and st["kind"] in ("py",) and st.get("done") and st["done"]():
            if not st.get("run_if_fresh_only"):
                emit(st["id"], "SKIP-DONE", st["desc"])
                continue
        if st.get("run_if_fresh_only") and not fresh:
            emit(st["id"], "SKIP-FRESH", f"{st['desc']} (not a fresh start)")
            continue

        # vision gate
        if st["kind"] == "vision":
            if st["vision_check"]():
                emit(st["id"], "VISION-OK", st["desc"] + " (output present)")
                continue
            emit(st["id"], "HALT", st["handoff"])
            _flush(log, week)
            print(f"\nHARNESS HALTED for vision. {st['handoff']}")
            sys.exit(EXIT_VISION)

        # runnable stage (py / gate / verify)
        code, out, err = _run_cmd(st["cmd"])
        tail = (out[-300:] + " " + err[-200:]).strip()

        if st["kind"] in ("gate", "verify") and "gate_codes" in st:
            label = st["gate_codes"].get(code, "UNKNOWN")
            if label == "OK":
                emit(st["id"], "PASS", f"{st['desc']} (exit 0)")
            elif label == "VISION-MORE":
                emit(st["id"], "HALT", f"{st['desc']} :: {tail[-220:]}")
                _flush(log, week)
                sys.exit(EXIT_VISION)
            else:  # LOGIC
                emit(st["id"], "FAIL-LOGIC", f"{st['desc']} exit={code} :: {tail[-160:]}")
                _flush(log, week)
                print(f"\nSTOP (LOGIC error at {st['id']}). Do not proceed. Escalate.")
                sys.exit(EXIT_LOGIC)
            continue

        # plain py stage
        produces_ok = all(Path(p).exists() for p in st.get("produces", []))
        if code == 0 and produces_ok:
            emit(st["id"], "PASS", f"{st['desc']}")
        else:
            # MISSING → retry once
            emit(st["id"], "RETRY", f"{st['desc']} exit={code} produces_ok={produces_ok}")
            code2, out2, err2 = _run_cmd(st["cmd"])
            produces_ok2 = all(Path(p).exists() for p in st.get("produces", []))
            if code2 == 0 and produces_ok2:
                emit(st["id"], "PASS", f"{st['desc']} (after retry)")
            else:
                emit(st["id"], "ESCALATE", f"{st['desc']} failed twice exit={code2} :: {(err2 or out2)[-160:]}")
                _flush(log, week)
                print(f"\nESCALATE (MISSING at {st['id']} after retry).")
                sys.exit(EXIT_ESCALATE)

    _flush(log, week)
    print(f"\nrun_week {week}: reached end of plan ({'dry-run' if dry else 'execute'}).")
    sys.exit(EXIT_OK)


def _flush(log, week):
    try:
        (RUN_LOG_DIR / f"{week}-run.json").write_text(
            json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    main()
