#!/usr/bin/env python3
"""autodetect.py — M4: input-folder autodetect + file-kind classification (deterministic) + minimal
preprocess (G11). The deterministic front of expensereceipt-extract; the vision OCR/handwriting read
itself is an LLM HALT specified in SKILL.md, not code.

Folder (Q1 decision): default input = raw-data/input/WKnn_2026/ (owner-confirmed; ~/WKww_YYYY/ overridden).
File-kind classification (macOS NFD-safe — every name is unicodedata.normalize('NFC', ...) before matching,
mirroring build_store_db.find_card_file's '승인내역' rule):
  • card_statement : NFC name contains '승인내역' + .xls/.xlsx, excludes *FAIL*  (the 카드승인내역 export)
  • template       : NFC name contains 'T&E' + .xlsx                              (the Receipt-Sheet target)
  • card_slip      : NFC name contains '매출전표'                                  (card sales slip — informational)
  • receipt        : image (.png/.jpg/.jpeg/.heic/.heif/.webp/.bmp/.tif/.tiff) OR .pdf not matching above
  • other          : anything else

G11 preprocess minimization: only optional rotate + grayscale (PIL). NO Hough deskew / thermal pipeline —
Claude Vision's skew/low-light reading is trusted (net-NEW minimal principle). Preprocess is rarely needed
and never mutates the input (writes a copy).

SOT discipline (절대 기준 2): read-only over the input folder; RETURNs the manifest to the master; writes
no SOT. Input folder is immutable.

Usage:
    python3 autodetect.py WK23_2026                 # classify raw-data/input/WK23_2026 → JSON manifest
    python3 autodetect.py --dir /path/to/folder     # classify an explicit folder
    python3 autodetect.py --selftest                # 실측 (real WK23 + NFD-name robustness)
"""

import os
import re
import sys
import json
import shutil
import unicodedata
from pathlib import Path

_IMG_EXT = {".png", ".jpg", ".jpeg", ".heic", ".heif", ".webp", ".bmp", ".gif", ".tif", ".tiff"}

# AUTODETECT-1: carrier/telephone BILL tokens (NFC). A telephone bill is a TELEPHONE-sector document, NOT
# a receipt — it must NOT enter the receipts list (and so never the card consume-once match). The Korean
# tokens are specific (substring-safe); the short Latin carrier tokens require a non-letter boundary so
# 'kt' never matches mid-word (e.g. 'ticket'/'market').
_TEL_KO = ("청구내역", "통신비", "청구서")
_TEL_LATIN = re.compile(r"(?:^|[^a-z])(?:t\s?world|skt|kt|lg\s?u\+|lgu\+)(?:[^a-z]|$)", re.I)


def _is_telephone_bill(name_nfc):
    """AUTODETECT-1: True iff the NFC filename is a carrier/telephone bill (청구내역/통신비/청구서/T world/
    SKT/KT/LG U+) — routed to the TELEPHONE bucket, never the receipts list."""
    if any(tok in name_nfc for tok in _TEL_KO):
        return True
    return bool(_TEL_LATIN.search(name_nfc))


class PdfInfoUnavailable(RuntimeError):
    """AUTODETECT-2 fail-closed: the `pdfinfo` binary is absent / errored — a PDF's page count cannot be
    determined. NEVER assume 1 page (a multi-receipt-page PDF would silently drop receipts). HALT/ERROR."""


def pdf_page_count(pdf_path):
    """AUTODETECT-2 (D5 reuse: `pdfinfo` — NO new pypdf/PyMuPDF). Return the PDF's page count.
    ★FAIL-CLOSED: pdfinfo absent OR errored → raise PdfInfoUnavailable (HALT) — NEVER silently assume 1.
    Runs on a COPY of the input (input immutable; no metadata side-effect on the read-only input dir)."""
    import subprocess, tempfile
    if not shutil.which("pdfinfo"):
        raise PdfInfoUnavailable(f"pdfinfo binary not found — cannot determine page count of {pdf_path} "
                                 f"(fail-closed; a 1-page assumption could silently drop receipts)")
    tdir = Path(tempfile.mkdtemp(prefix="expr_pdfinfo_"))
    src = tdir / "src.pdf"
    try:
        shutil.copy(pdf_path, src)                      # copy out of the read-only input dir first
        r = subprocess.run(["pdfinfo", str(src)], capture_output=True, text=True)
        if r.returncode != 0:
            raise PdfInfoUnavailable(f"pdfinfo failed (rc={r.returncode}) on {pdf_path}: {r.stderr.strip()}")
        m = re.search(r"^Pages:\s+(\d+)", r.stdout, re.M)
        if not m:
            raise PdfInfoUnavailable(f"pdfinfo produced no 'Pages:' line for {pdf_path}")
        return int(m.group(1))
    finally:
        shutil.rmtree(tdir, ignore_errors=True)


def pdf_receipt_pages(pdf_path):
    """AUTODETECT-2: emit ONE receipt candidate per PDF page (stable page-ordinal id) so a multi-receipt
    PDF is not silently read as one. page_count>1 → multipage=True (the master HALTs/flags so the vision
    step reads each page). pdfinfo-absent/error propagates as PdfInfoUnavailable (fail-closed)."""
    n = pdf_page_count(pdf_path)
    stem = Path(pdf_path).stem
    return {"path": str(pdf_path), "page_count": n, "multipage": n > 1,
            "pages": [{"path": str(pdf_path), "page": i, "id": f"{stem}#p{i}"} for i in range(1, n + 1)]}


def _find_project_dir():
    p = Path(__file__).resolve()
    for anc in p.parents:
        if (anc / "CLAUDE.md").exists() and (anc / "scripts").is_dir():
            return anc
    return p.parents[4] if len(p.parents) >= 5 else p.parent


PROJECT_DIR = _find_project_dir()
INPUT_ROOT = PROJECT_DIR / "raw-data" / "input"


def classify_file(path):
    """Deterministic file-kind for one path (NFC-normalized name match).
    ★AUTODETECT-3 — the branch ORDER is LOAD-BEARING precedence (most-specific → least-specific):
      card_statement → template → card_slip → telephone_bill → receipt → other.
    A filename matching TWO patterns resolves to the FIRST matching branch deterministically — e.g.
    '통신비 T&E.xlsx' is a TEMPLATE (the T&E .xlsx Receipt-Sheet), not a telephone bill, because the
    template branch precedes telephone_bill. telephone_bill MUST precede the .pdf→receipt catch so a
    carrier-bill PDF routes to TELEPHONE, never a receipt that would wrongly enter the card match."""
    name = unicodedata.normalize("NFC", Path(path).name)
    suf = Path(path).suffix.lower()
    low = name.lower()
    if "승인내역" in name and suf in (".xls", ".xlsx") and "FAIL" not in name:
        return "card_statement"
    if "t&e" in low and suf == ".xlsx":
        return "template"
    if "매출전표" in name:
        return "card_slip"
    if _is_telephone_bill(name):    # AUTODETECT-1: carrier/telephone bill → TELEPHONE (NOT a receipt)
        return "telephone_bill"
    if suf in _IMG_EXT:
        return "receipt"            # receipt image
    if suf == ".pdf":
        return "receipt"            # receipt pdf (vision reads it directly)
    return "other"


def autodetect(folder):
    """Scan a folder and return a manifest classifying every file (NFD-safe). Read-only."""
    folder = Path(folder)
    manifest = {
        "input_dir": str(folder),
        "exists": folder.is_dir(),
        "card_statement": None,
        "template": None,
        "card_slips": [],
        "telephone_bills": [],
        "receipts": [],
        "other": [],
    }
    if not folder.is_dir():
        return manifest
    cards, templates = [], []
    for p in sorted(folder.iterdir(), key=lambda x: unicodedata.normalize("NFC", x.name)):
        if p.is_dir() or p.name.startswith(".") or p.name.endswith(".tmp"):
            continue
        kind = classify_file(p)
        if kind == "card_statement":
            cards.append(p)
        elif kind == "template":
            templates.append(p)
        elif kind == "card_slip":
            manifest["card_slips"].append(str(p))
        elif kind == "telephone_bill":          # AUTODETECT-1: TELEPHONE sector — NOT a receipt
            manifest["telephone_bills"].append(str(p))
        elif kind == "receipt":
            manifest["receipts"].append({"path": str(p), "ext": p.suffix.lower()})
        else:
            manifest["other"].append(str(p))
    # card statement: prefer .xls over .xlsx, then shortest name (mirrors find_card_file tie-break)
    if cards:
        cards.sort(key=lambda p: (p.suffix.lower() != ".xls", len(p.name)))
        manifest["card_statement"] = str(cards[0])
        manifest["other"].extend(str(p) for p in cards[1:])
    if templates:
        templates.sort(key=lambda p: len(p.name))
        manifest["template"] = str(templates[0])
        manifest["other"].extend(str(p) for p in templates[1:])
    manifest["counts"] = {
        "receipts": len(manifest["receipts"]),
        "card_slips": len(manifest["card_slips"]),
        "telephone_bills": len(manifest["telephone_bills"]),     # AUTODETECT-1
        "other": len(manifest["other"]),
        "has_card_statement": manifest["card_statement"] is not None,
        "has_template": manifest["template"] is not None,
    }
    return manifest


def autodetect_week(week):
    """Classify raw-data/input/<week>/ (Q1 primary path)."""
    return autodetect(INPUT_ROOT / week)


def sales_slip_candidates(manifest):
    """★KICC: card-company 매출전표 slips are replacement-receipt CANDIDATES (e.g. when the merchant's
    receipt machine breaks, an official card-company sales slip is a valid receipt). Each candidate is
    OCR'd (vision: 승인번호, amount, card_last) and accepted as a receipt ONLY if its 승인번호+amount matches
    a card-statement row — the deterministic guard lives in expensereceipt-verify.check_card_match
    (no double-consume, stray/tamper rejected, statement-승인번호 = source of truth)."""
    return list((manifest or {}).get("card_slips") or [])


# --------------------------------------------------------------------------- G11 minimal preprocess
def preprocess_minimal(in_path, out_path, rotate_deg=0, grayscale=True):
    """G11: the ONLY preprocessing — optional rotation + grayscale. No deskew/thermal. Writes a COPY
    (input immutable). Returns out_path. Rarely needed — Claude Vision reads skew/low-light directly."""
    from PIL import Image                            # Pillow (already a project dep)
    img = Image.open(in_path)
    if rotate_deg:
        img = img.rotate(-rotate_deg, expand=True)   # PIL rotates CCW; negate for intuitive CW degrees
    if grayscale:
        img = img.convert("L")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return str(out_path)


# --------------------------------------------------------------------------- CLI
def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if "--selftest" in args:
        return _selftest()
    if "--dir" in args:
        folder = args[args.index("--dir") + 1]
        print(json.dumps(autodetect(folder), ensure_ascii=False, indent=2))
        return 0
    weeks = [a for a in args if not a.startswith("--")]
    if not weeks:
        print(__doc__)
        return 0
    print(json.dumps(autodetect_week(weeks[0]), ensure_ascii=False, indent=2))
    return 0


# --------------------------------------------------------------------------- 실측 SELF-TEST
def _selftest():
    import tempfile, shutil
    ok = True

    def check(label, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    # --- T1: ★SYNTHETIC WK23-shaped folder in /tmp (input-isolation: selftests NEVER read raw-data/input).
    #     autodetect classifies by FILENAME only (never opens content), so same-named empty files give full
    #     coverage without touching the protected input directory. ---
    syn = Path(tempfile.mkdtemp(prefix="expr_wk23syn_"))
    for fn in ("2026-06-02-1.png", "20260620_045132999_iOS.png", "WK23_2026.pdf",
               "simon_park_T&E_WK00_2026.xlsx", "카드승인내역_20260602.xls", "매출전표 - 롯데카드.pdf"):
        (syn / fn).write_bytes(b"x")
    m = autodetect(syn)
    check("synthetic WK23: card_statement detected (카드승인내역*.xls, NFD-safe)",
          m["card_statement"] is not None and "승인내역" in unicodedata.normalize("NFC", Path(m["card_statement"]).name))
    check("synthetic WK23: template detected (*T&E*.xlsx)",
          m["template"] is not None and "T&E" in Path(m["template"]).name)
    check("synthetic WK23: card_slip detected (매출전표, NFD-safe)",
          len(m["card_slips"]) >= 1)
    check("synthetic WK23: ≥2 receipt files (png/pdf) detected",
          m["counts"]["receipts"] >= 2)
    check("★KICC: sales_slip_candidates surfaces the 매출전표 (replacement-receipt candidate)",
          len(sales_slip_candidates(m)) == 1 and "매출전표" in unicodedata.normalize("NFC", sales_slip_candidates(m)[0]))
    shutil.rmtree(syn, ignore_errors=True)
    print(f"      → counts: {m['counts']}")

    # --- T2: NFD-encoded Korean names still classify (the macOS trap) ---
    tmp = Path(tempfile.mkdtemp(prefix="expr_autodetect_"))
    nfd_card = unicodedata.normalize("NFD", "카드승인내역_20260602.xls")
    nfd_slip = unicodedata.normalize("NFD", "매출전표 - 롯데카드.pdf")
    (tmp / nfd_card).write_text("x")
    (tmp / nfd_slip).write_text("x")
    (tmp / "simon_park_T&E_WK00_2026.xlsx").write_text("x")
    (tmp / "2026-06-02-1.png").write_text("x")
    (tmp / "receipt_bundle.pdf").write_text("x")
    (tmp / ".DS_Store").write_text("x")
    m2 = autodetect(tmp)
    check("NFD card_statement classified", m2["card_statement"] is not None)
    check("NFD card_slip classified", len(m2["card_slips"]) == 1)
    check("template classified", m2["template"] is not None)
    check("receipts = png + pdf (2), dotfile ignored", m2["counts"]["receipts"] == 2)
    check("classify_file direct: NFD '승인내역' → card_statement",
          classify_file(tmp / nfd_card) == "card_statement")

    # --- T3: missing folder → exists False, empty manifest (no crash) ---
    m3 = autodetect(tmp / "does-not-exist")
    check("missing folder → exists False, no crash", m3["exists"] is False and m3["card_statement"] is None)

    # --- T4: G11 preprocess minimal (rotate+grayscale, input untouched) ---
    try:
        from PIL import Image
        src = tmp / "img.png"; Image.new("RGB", (40, 20), (200, 100, 50)).save(src)
        out = preprocess_minimal(src, tmp / "out.png", rotate_deg=90, grayscale=True)
        oimg = Image.open(out)
        check("G11 preprocess: grayscale mode 'L'", oimg.mode == "L")
        check("G11 preprocess: rotate 90 swaps dims (40x20→20x40)", oimg.size == (20, 40))
        check("G11 preprocess: input file untouched", Image.open(src).size == (40, 20))
    except Exception as e:
        check(f"G11 preprocess (PIL error: {e})", False)

    # ═══════════ ★BATCH E — autodetect ingest hardening (non-vacuous; synthetic /tmp, NEVER real input) ═══════════
    bd = Path(tempfile.mkdtemp(prefix="autodetect_be_"))
    for fn in ("청구내역 인쇄하기 _ T world.pdf", "2026 통신비.pdf", "SKT_청구서.pdf",
               "2026-06-02-1.png", "WK23_2026.pdf"):
        (bd / fn).write_bytes(b"x")
    mE = autodetect(bd)
    # AUTODETECT-1: carrier/telephone bills → telephone_bill (NOT receipts → never the card consume-once match)
    check("AUTODETECT-1: owner T-world bill (청구내역 … T world.pdf) → telephone_bill (NOT receipt)",
          classify_file(bd / "청구내역 인쇄하기 _ T world.pdf") == "telephone_bill")
    check("AUTODETECT-1: 통신비 / SKT 청구서 → telephone_bill",
          classify_file(bd / "2026 통신비.pdf") == "telephone_bill" and classify_file(bd / "SKT_청구서.pdf") == "telephone_bill")
    check("AUTODETECT-1: 3 telephone bills bucketed; only 2 receipts (telephone NOT in card-match path)",
          mE["counts"]["telephone_bills"] == 3 and mE["counts"]["receipts"] == 2)
    check("AUTODETECT-1: a plain receipt png/pdf still classifies as receipt (no over-capture)",
          classify_file(bd / "2026-06-02-1.png") == "receipt" and classify_file(bd / "WK23_2026.pdf") == "receipt")
    check("AUTODETECT-1: 'backtrack' does NOT false-match the 'kt' carrier token (boundary-safe)",
          not _is_telephone_bill("backtrack_receipt.png"))
    # AUTODETECT-3: dual-token precedence — '통신비 T&E.xlsx' is the TEMPLATE (template precedes telephone_bill)
    check("AUTODETECT-3: dual-token '통신비 T&E.xlsx' → template (deterministic precedence)",
          classify_file(bd / "통신비 T&E.xlsx") == "template")

    # AUTODETECT-2: pdfinfo page_count + per-page emit + multipage flag; pdfinfo-absent → ERROR (fail-closed)
    def _mkpdf(path, npages):
        objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
                ("<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join(f"{3+i} 0 R" for i in range(npages)), npages)).encode()]
        objs += [b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>"] * npages
        out = b"%PDF-1.4\n"; offs = []
        for i, o in enumerate(objs, 1):
            offs.append(len(out)); out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
        xat = len(out); out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
        for off in offs:
            out += f"{off:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xat}\n%%EOF".encode()
        Path(path).write_bytes(out)
    _p2 = bd / "two.pdf"; _mkpdf(_p2, 2)
    _p1 = bd / "one.pdf"; _mkpdf(_p1, 1)
    if shutil.which("pdfinfo"):
        rp = pdf_receipt_pages(_p2)
        check("AUTODETECT-2: 2-page PDF → page_count 2 + multipage flag + 2 per-page candidates (stable page-ordinal id)",
              rp["page_count"] == 2 and rp["multipage"] is True and len(rp["pages"]) == 2 and rp["pages"][1]["id"].endswith("#p2"))
        check("AUTODETECT-2: 1-page PDF → page_count 1, multipage False",
              pdf_receipt_pages(_p1)["page_count"] == 1 and pdf_receipt_pages(_p1)["multipage"] is False)
    else:
        check("AUTODETECT-2: pdfinfo unavailable on host — count path skipped (fail-closed path below still tested)", True)
    # ★FAIL-CLOSED: pdfinfo binary absent (simulated) → ERROR/HALT, NEVER a 1-page assumption
    _orig_which = shutil.which
    shutil.which = lambda b: None if b == "pdfinfo" else _orig_which(b)
    try:
        _failclosed = False
        try:
            pdf_page_count(_p2)
        except PdfInfoUnavailable:
            _failclosed = True
        check("★AUTODETECT-2 FAIL-CLOSED: pdfinfo absent → PdfInfoUnavailable (ERROR/HALT, NOT 1-page)", _failclosed)
    finally:
        shutil.which = _orig_which
    shutil.rmtree(bd, ignore_errors=True)

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print("RESULT:", "PASS — all 실측 checks green" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
