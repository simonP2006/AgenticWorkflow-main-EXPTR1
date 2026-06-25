# Workflow Completion Backup — WK06 + WK07 + WK08 (2026) + RDR PoC

> Backup timestamp: 2026-03-02T18:00
> Workflow: Expense Report Automation
> Status: ALL 10 STEPS COMPLETED for 3 weeks + 2 bugs RESOLVED + 1 hotfix APPLIED + RDR PoC TESTED
> Output files: WK06 (2.0MB) + WK07 (2.9MB) + WK08 (1.0MB) + WK09 RDR PoC (8.2MB) in raw-data/output/

---

## 1. SOT Final State (`.claude/state.yaml`)

```yaml
workflow:
  name: "Expense Report Automation"
  current_step: 10
  status: "completed"
  target_week: "WK08_2026"

  outputs:
    step-1: "research/input-manifest.json"
    step-2: "research/ocr-results.json"
    step-3: "research/card-approval-data.json"
    step-5: "planning/cell-mapping.json"
    step-7: "raw-data/output/simon_park_T&E_WK08_2026.xlsx"
    step-8: "raw-data/output/simon_park_T&E_WK08_2026.xlsx"
    step-10: "scripts/annotate_receipts.py"

  completed_weeks:
    WK06_2026:
      output: "raw-data/output/simon_park_T&E_WK06_2026.xlsx"
      date_range: "2026-02-02 ~ 2026-02-08"
      operations: 73
      annotations: 20
      status: "completed"
    WK07_2026:
      output: "raw-data/output/simon_park_T&E_WK07_2026.xlsx"
      date_range: "2026-02-09 ~ 2026-02-15"
      operations: 71
      annotations: 26
      status: "completed"
    WK08_2026:
      output: "raw-data/output/simon_park_T&E_WK08_2026.xlsx"
      date_range: "2026-02-16 ~ 2026-02-22"
      operations: 49
      annotations: 8
      status: "completed"

  resolved_issues:
    - id: "pax-undercount"
      code_fix: "applied — write_excel.py lines 444,489,532,573 (4 edits)"
      verified_weeks: ["WK06_2026", "WK07_2026"]
    - id: "mileage-stopover-missing"
      code_fix: "applied — write_excel.py lines 595-615: direction filter → entry/exit-based"
      verified_weeks: ["WK06_2026", "WK07_2026", "WK08_2026"]

  hotfix:
    - id: "mileage-friday-row" (applied)
```

---

## 2. WK06_2026 (2026-02-02 ~ 2026-02-08)

### Excel Cell Verification

```
=== FORM Sheet ===
K8 (Sunday): 2026-02-08
G2 (WK): MAGNUM7H cHBM4E/sHBM4E WS PROJECT FOR SAMSUNG (LCL 06WK)

=== FORM: DINNER (E24-I24) — card-matched KRW ===
F24 (Tue): KRW 8500
I24 (Fri): KRW 8400

=== FORM: TRAVEL[A] Detail (U62-U66) — card-matched KRW ===
U62 (Mon): KRW 12420
U63 (Tue): KRW 18700
U64 (Wed): KRW 25700
U65 (Thu): KRW 11250
U66 (Fri): KRW 21700
U69 (Sum): 49370

=== FORM: TRAVEL[A] PAX (C62-C66) — PAX BUG FIXED ===
C62 (Mon): PAX=4
C63 (Tue): PAX=3
C64 (Wed): PAX=5
C65 (Thu): PAX=3
C66 (Fri): PAX=4

=== FORM: STAFF[F] Detail (U95-U99) ===
U96 (Tue): KRW 5500

=== FORM: PARKING (E39-I39) — unconditional KRW ===
E39 (Mon): KRW 2160   (Go=960 + Back=1200)
F39 (Tue): KRW 3460   (Go=960 + Stop-over=2100 + Stop-over=400)
G39 (Wed): KRW 960    (Go=960 only)
I39 (Fri): KRW 1560   (Go=960 + Back=600)

=== FORM: TELEPHONE (E46) ===
E46: None (no phone bill this week)

=== Mileage log — STOPOVER FIX APPLIED ===
Mon: going=20 (F7), return=20 (F8)
Tue: going=20 (F13), return=42 (F14) ← FIXED (was 0, stopover 기흥동탄→서울)
Wed: going=20 (F19)
Fri: going=20 (F31), return=20 (F32)
```

### WK06 Key Facts
- Card file: `.xls` (xlrd) — different from WK07 `.xlsx`
- No phone bill PDF → TELEPHONE=0
- Tue has stop-over tolls (기흥동탄→서울 2100, →성남 400)
- Thu has no tolls (but has TRAVEL receipt)
- 5 TRAVEL days (Mon-Fri), 2 DINNER days (Tue, Fri)
- Personnel: 우석원/EDS, 정영진/HBM PE, 이정민/HBM PE, 김기정/TERADYNE, 이창성/EDS

---

## 3. WK07_2026 (2026-02-09 ~ 2026-02-15)

### Excel Cell Verification

```
=== FORM Sheet ===
K8 (Sunday): 2026-02-15
G2 (WK): MAGNUM7H cHBM4E/sHBM4E WS PROJECT FOR SAMSUNG (LCL 07WK)

=== FORM: DINNER (E24-I24) — card-matched KRW ===
E24 (Mon): KRW 8400
F24 (Tue): KRW 10000
G24 (Wed): KRW 10900
H24 (Thu): KRW 9500

=== FORM: TRAVEL[A] Detail (U62-U66) — card-matched KRW ===
U62 (Mon): KRW 23400
U64 (Wed): KRW 7290
U65 (Thu): KRW 12500

=== FORM: TRAVEL[A] PAX (C62-C66) — PAX BUG FIXED ===
C62 (Mon): PAX=4
C64 (Wed): PAX=2
C65 (Thu): PAX=3

=== FORM: STAFF[F] Detail (U95-U99) ===
U95 (Mon): KRW 5500

=== FORM: PARKING (E39-I39) — unconditional KRW ===
E39 (Mon): KRW 2160   (Go=960 + Back=1200)
F39 (Tue): KRW 1560   (Go=960 + Back=600)
G39 (Wed): KRW 1560   (Go=960 + Back=600)
H39 (Thu): KRW 6560   (Go=960 + Back=600 + Parking=5000)

=== FORM: TELEPHONE (E46) ===
E46: KRW 59840   (74800 * 0.8)

=== Mileage log ===
Mon: going=20 (F7), return=20 (F8)
Tue: going=20 (F13), return=20 (F14)
Wed: going=20 (F19), return=20 (F20)
Thu: going=20 (F25), return=20 (F26)
```

### WK07 Key Facts
- Card file: `.xlsx` (openpyxl)
- Phone bill: 74,800원, auto-debit (카드자동납부), 80% = 59,840
- Mon-Thu tolls Go+Back, Mon back=1200, rest=600, total=6,840
- Thu parking 5,000 at 센트럴파크
- 3 TRAVEL days (Mon, Wed, Thu), 4 DINNER days (Mon-Thu)
- Personnel: 임익범/EDS, 이창성/EDS, 박종훈/EDS (Mon TRAVEL only)
- No stopover pattern → mileage fix unaffected

---

## 4. WK08_2026 (2026-02-16 ~ 2026-02-22)

### Excel Cell Verification

```
=== FORM Sheet ===
K8 (Sunday): 2026-02-22
G2 (WK): MAGNUM7H cHBM4E/sHBM4E WS PROJECT FOR SAMSUNG (LCL 08WK)

=== FORM: DINNER (H24) — card-matched KRW ===
H24 (Thu): KRW 9500

=== FORM: TRAVEL[A] Detail (U62-U66) — card-matched KRW ===
U65 (Thu): KRW 8010
U66 (Fri): KRW 8280
U69 (Sum): 8010

=== FORM: TRAVEL[A] PAX (C62-C66) — IMAGE ANCHOR FIX APPLIED ===
C65 (Thu): PAX=2, NAMES="Mr.Kim Jiyong who is an engineer of SAMSUNG EDS and me."
C66 (Fri): PAX=2, NAMES="Mr.Lee Changsung who is an engineer of SAMSUNG EDS and me."

=== FORM: STAFF[F] Detail ===
(None — no STAFF meetings this week)

=== FORM: PARKING (E39-I39) ===
H39 (Thu): KRW 1920   (Go=960 + Back=960)
I39 (Fri): KRW 3700   (Go=1200 + Stop-over=2100 + Stop-over=400)

=== FORM: TELEPHONE (E46) ===
E46: None (no phone bill this week)

=== Receipt: TRAVEL howmany (row 404) ===
E404=2 (Thu), F404=2 (Fri)

=== Mileage log — STOPOVER FIX APPLIED ===
Thu: going=20 (F25), return=20 (F26)
Fri: going=20 (F31), return=42 (F32) ← stopover 기흥동탄→서울
```

### WK08 Key Facts
- Card file: `.xls` (xlrd), 3 records only
- Fewest receipts: only 4 images in Receipt sheet
- No STAFF meetings, no phone bill, no parking receipts
- Thu TRAVEL names fixed via image anchor adjustment (to_row 442→443 in drawing2.xml)
- Fri tolls: 3 entries with stop-over (same pattern as WK06 Tue)
- Personnel: 김지용/EDS (Thu), 이창성/EDS (Fri)
- Input template modified: image3 anchor `to_row` 442→443 in `xl/drawings/drawing2.xml`

---

## 5. Resolved Issues

### Issue #1: PAX Undercount (FIXED 2026-03-01)

**Root Cause:**
- Bug 1: "me" excluded from FORM PAX — `name_affiliations` never contains "me" → always -1
- Bug 2: OCR `headcount` field ignored — `len(all_names)` used instead of item count

**PRD Update (user-applied):**
- §10(0),(3),(3-1),(3-2): STAFF PAX includes "me", item-count fallback, FORM sync
- §11(0),(3),(3-1),(3-2): TRAVEL identical pattern

**Code Fix (4 edits in write_excel.py):**
1. Line ~444: Receipt STAFF → `max(len(all_names), ocr_hc)` + `sm_headcount_by_day` dict
2. Line ~489: Receipt TRAVEL → `max(len(all_names), ocr_hc)` + `travel_headcount_by_day` dict
3. Line ~532: FORM TRAVEL PAX → `travel_headcount_by_day[day]`
4. Line ~573: FORM STAFF PAX → `sm_headcount_by_day[day]`

**Verified:** WK06 (8 cells PASS), WK07 (7 cells PASS)

### Issue #2: Mileage Stopover Missing (FIXED 2026-03-02)

**Root Cause:**
- `direction == "go"` / `direction == "back"` filter at write_excel.py lines 596-597
- Stopover toll records (direction="stopover") excluded from mileage distance calculation
- 기흥동탄→서울 stopover matches §16(4) → should write 42 to back cell

**PRD Update (user-applied):**
- §16 preamble revised: "전건 순회" instead of go/back binary
- Added: "하루에 톨 기록이 3건 이상일 수 있다 (경유 패턴)"
- Added stopover example at end

**Code Fix (write_excel.py lines 595-615):**
- Replaced: direction-based filtering (`go_tolls`, `back_tolls`)
- With: entry/exit-based cell determination
  - `exit_point == "기흥동탄"` → first cell (go row)
  - `entry == "기흥동탄"` → second cell (back row)

**Affected Cells:**
- WK06 F14 (Tue back): 0 → **42** (기흥동탄→서울 stopover)
- WK08 F32 (Fri back): 0 → **42** (기흥동탄→서울 stopover)
- WK07: no stopover pattern → unaffected

### Hotfix #1: Mileage Friday Row Missing
- `day_to_mileage_row()` dict had Mon-Thu only, missing `"friday": 31`
- Fix: Added `"friday": 31` to mapping (line 71)
- Status: Applied

---

## 6. WK06 vs WK07 vs WK08 Comparison

| Item | WK06 | WK07 | WK08 |
|------|------|------|------|
| Date range | 02-02 ~ 02-08 | 02-09 ~ 02-15 | 02-16 ~ 02-22 |
| Card file format | `.xls` (xlrd) | `.xlsx` (openpyxl) | `.xls` (xlrd) |
| Phone bill | None | 74,800원 (59,840) | None |
| Toll pattern | Mon Go+Back, Tue Go+2 stopovers, Wed Go, Fri Go+Back | Mon-Thu Go+Back | Thu Go+Back, Fri Go+2 stopovers |
| DINNER days | Tue, Fri (2 days) | Mon-Thu (4 days) | Thu only (1 day) |
| TRAVEL days | Mon-Fri (5 days) | Mon, Wed, Thu (3 days) | Thu, Fri (2 days) |
| STAFF day | Tue (U96) | Mon (U95) | None |
| Parking | None | Thu 5000 | None |
| Mileage days | Mon, Tue, Wed, Fri | Mon-Thu | Thu, Fri |
| Stopover mileage | Tue F14=42 | None | Fri F32=42 |
| Card records | 8 | 8 (11 raw, 3 cancelled) | 3 |
| Operations | 73 (47+26) | 71 (41+30) | 49 (23+26) |
| Annotations | 20 rects / 9 images | 26 rects / 11 images | 8 rects / 4 images |

---

## 7. Step 10: Red Dotted Rectangle (§19-§20)

Implementation: `scripts/annotate_receipts.py` (PIL dashed line + ZIP image replacement)
Methodology: Grid-overlay calibration (50px grid) for precise pixel coordinates

### WK07 Annotations (26 rectangles, 11 images)
| Image | Receipt Type | Section | Rectangles |
|-------|-------------|---------|------------|
| image2 | Toll history | §19(1) | 4 date groups |
| image3 | Parking 센트럴파크 | §19(1) | 2 (진입일시 + 결제금액) |
| image4 | Spot Mart Mon | §19(2) | 2 (일시 + 합계) |
| image5 | Starbucks Mon | §19(4) | 2 (일시 + 결제금액) |
| image6 | Pandora Tue | §19(2) | 2 (일시 + 합계) |
| image7 | Starbucks Wed | §19(2) | 2 (일시 + 결제금액) |
| image8 | Paris Baguette Wed | §19(4) | 2 (일시 + 합계금액) |
| image9 | 까치화방 Thu | §19(4) | 2 (일시 + 판매금액) |
| image10 | Spot Mart Thu | §19(2) | 2 (일시 + 합계) |
| image11 | 폴 바셋 Mon | §19(3) | 2 (일시 + 총 결제금액) |
| image12 | SK Telecom bill | §19(5) | 4 (이름 + 전화번호 + 이용요금 + 납부정보) |

### WK06 Annotations (20 rectangles, 9 images)
| Image | Receipt Type | Section | Rectangles |
|-------|-------------|---------|------------|
| image2 | Starbucks Tue | §19(4) | 2 (일시 + 결제금액) |
| image3 | Paris Baguette Mon | §19(4) | 2 (일시 + 합계금액) |
| image4 | 스위치 Tue | §19(2) | 2 (발행일시 + 받을금액) |
| image5 | Spot Mart Fri | §19(2) | 2 (일시 + 합계) |
| image6 | Paris Baguette Thu | §19(4) | 2 (일시 + 합계금액) |
| image7 | 폴 바셋 Tue | §19(3) | 2 (일시 + 총 결제금액) |
| image8 | 폴 바셋 Wed | §19(4) | 2 (일시 + 총 결제금액) |
| image9 | 폴 바셋 Fri | §19(4) | 2 (일시 + 총 결제금액) |
| image10 | Toll history | §19(1) | 4 date groups |

### WK08 Annotations (8 rectangles, 4 images)
| Image | Receipt Type | Section | Rectangles |
|-------|-------------|---------|------------|
| image2 | Toll history | §19(1) | 2 date groups (Feb 19, 20) |
| image3 | Paris Baguette Thu | §19(4) | 2 (일시 + 합계금액) |
| image4 | Paris Baguette Fri | §19(4) | 2 (일시 + 합계금액) |
| image5 | Spot Mart Thu | §19(2) | 2 (일시 + 합계) |

---

## 8. Complete File Inventory

### Output (Final Deliverables)
| File | Size | MD5 (first 12) |
|------|------|-----------------|
| `raw-data/output/simon_park_T&E_WK06_2026.xlsx` | 2,009,487 bytes | 5c89aa4dd981 |
| `raw-data/output/simon_park_T&E_WK07_2026.xlsx` | 2,941,955 bytes | 9257797302eb |
| `raw-data/output/simon_park_T&E_WK08_2026.xlsx` | 999,687 bytes | c4e27a701e16 |

### Scripts (reusable across weeks)
| File | Size | MD5 (first 12) |
|------|------|-----------------|
| `scripts/write_excel.py` | 34,867 bytes | 20fbfaa239da |
| `scripts/extract_images.py` | 9,834 bytes | ea3a43fb16cd |
| `scripts/extract_names_data.py` | 11,982 bytes | c381c43adebe |
| `scripts/extract_card_data.py` | 6,330 bytes | 8f4b901d5e9e |
| `scripts/annotate_receipts.py` | 13,793 bytes | ca437c515733 |

### Research Data (currently WK08)
| File | Description |
|------|-------------|
| `research/images/image{1-10}.png` | 10 extracted receipt images (WK08) |
| `research/image-positions.json` | 10 image anchor positions (WK08) |
| `research/input-manifest.json` | WK08 metadata + section boundaries |
| `research/ocr-results.json` | WK08 OCR data |
| `research/names-data.json` | WK08 name extraction + cell data |
| `research/card-approval-data.json` | 3 card approval records (WK08 .xls) |

### Input Files (Preserved, Read-Only)
```
raw-data/input/WK06_2026/
├── simon_park_T&E_WK00_2026.xlsx  (original template)
├── 카드이용내역_20260207.xls       (card approval, .xls)
├── IMG_2262.PNG, IMG_2263.PNG, IMG_2264.PNG, IMG_2267.PNG

raw-data/input/WK07_2026/
├── simon_park_T&E_WK00_2026.xlsx  (original template)
├── 카드승인내역_20260214.xlsx      (card approval, .xlsx)
├── IMG_2275.PNG, IMG_2278.PNG, IMG_2279.PNG
├── 법인카드영수증.pdf              (card receipts PDF)
└── 청구내역 인쇄하기 _ T world.pdf (phone bill)

raw-data/input/WK08_2026/
├── simon_park_T&E_WK00_2026.xlsx  (template, image3 anchor modified)
├── 카드승인내역_20260301.xls       (card approval, .xls)
└── 2026-03-01 06_24_24 PM에서 스캔.pdf (receipts scan)

raw-data/input/WK09_2026/              ← PENDING (not yet processed)
├── simon_park_T&E_WK00_2026.xlsx
├── 카드승인내역_20260301.xls
├── 2026-03-01 06_30_46 PM에서 스캔.pdf
├── IMG_2331.PNG ~ IMG_2335.PNG, IMG_2337.PNG
```

### Configuration
| File | Description |
|------|-------------|
| `.claude/state.yaml` | SOT — 3 weeks completed, 2 bugs resolved |
| `workflow.md` | 10-step workflow definition |
| `PRD_pre_instructions.md` | PRD — §10/§11 PAX + §16 mileage updated |

---

## 9. Personnel Database

### Romanize Map (scripts/write_excel.py)
```python
ROMANIZE = {
    "임익범": "Lim Ikbeom",
    "이창성": "Lee Changsung",
    "박종훈": "Park Jonghun",
    "정영진": "Jung Youngjin",
    "이정민": "Lee Jeongmin",
    "우석원": "Woo Seokwon",
    "김기정": "Kim Kijeong",
    "김지용": "Kim Jiyong",
    "김명기": "Kim Myoengi",
    "박건우": "Park Gunwoo",
    "박태수": "Park Taesu",
    "홍희민": "Hong Heemin",
    "박상일": "Park Sangil",
}
```

### Company Mapping
| Korean | English | Personnel DB Column |
|--------|---------|-------------------|
| SAMSUNG EDS | SAMSUNG EDS | D (col 4) |
| SAMSUNG HBM PE | SAMSUNG HBM PE | G (col 7) |
| TERADYNE | TERADYNE | A (col 1) |

### Per-Week Personnel
| Week | TRAVEL | STAFF | DINNER |
|------|--------|-------|--------|
| WK06 | 우석원, 정영진, 이정민, 김기정, 이창성 | (me only) | — |
| WK07 | 임익범, 이창성, 박종훈 | (me only) | — |
| WK08 | 김지용, 이창성 | — | — |

---

## 10. Key Code Patterns

### Card Matching (§18)
```python
# build_card_lookup: (date, amount) → record
card_lookup = {}
for rec in card_data["records"]:
    key = (rec["date"], rec["amount"])
    card_lookup[key] = rec
# Match: if (date, amount) in card_lookup → prefix "KRW "
```

### Mileage Entry/Exit (§16 — revised)
```python
# Iterate ALL toll records, determine cell by entry/exit
for toll in tolls:
    entry = toll["entry"]
    exit_point = toll["exit"]
    distance = get_distance(entry, exit_point)
    if not distance:
        continue
    if exit_point == "기흥동탄":  # go direction
        ws_mileage.cell(row=mileage_row, column=6, value=distance)
    elif entry == "기흥동탄":     # back direction (incl. stopover)
        ws_mileage.cell(row=mileage_row + 1, column=6, value=distance)
```

### PAX Headcount (§10/§11 — fixed)
```python
# max(name count, OCR headcount) — ensures "me" and unnamed persons counted
headcount = max(len(all_names), ocr_hc)
headcount_by_day[day] = headcount
```

---

## 11. Research Data Swap Protocol

`research/` 디렉터리에는 한 번에 한 주(week)의 데이터만 보관.
다른 주를 실행하려면:

```bash
# 1. Run extraction scripts for target week
python3 scripts/extract_images.py WK0X_2026
python3 scripts/extract_names_data.py WK0X_2026
python3 scripts/extract_card_data.py WK0X_2026

# 2. Reconstruct/provide ocr-results.json for target week

# 3. Run write_excel.py
python3 scripts/write_excel.py --all WK0X_2026

# 4. Run annotations
python3 scripts/annotate_receipts.py WK0X_2026
```

---

## 12. PRD Changes Log

### §10 STAFF PAX (2026-03-01, user-applied)
- Added: (0) STAFF PAX = names + "me"
- Added: (3) `max(len(names), ocr_headcount)` fallback
- Added: (3-1) item-count fallback for unnamed
- Added: (3-2) FORM STAFF PAX syncs with Receipt headcount

### §11 TRAVEL PAX (2026-03-01, user-applied)
- Identical pattern to §10

### §16 Mileage (2026-03-02, user-applied)
- Preamble: "전건 순회" instead of go/back binary
- Added: "하루에 톨 기록이 3건 이상일 수 있다 (경유 패턴: Go + 경유 + Back)"
- Added: Stopover example at end
- Rules (1)-(6): Unchanged

---

## 13. Next Week (WK09_2026)

Pending input detected at `raw-data/input/WK09_2026/`:
- Template: `simon_park_T&E_WK00_2026.xlsx` (8.3MB — larger than previous, likely more images)
- Card: `카드승인내역_20260301.xls` (19KB)
- Receipts scan: `2026-03-01 06_30_46 PM에서 스캔.pdf` (2.4MB)
- Additional photos: IMG_2331~2335, IMG_2337 (6 PNG files)
- Expected date range: 2026-02-23 ~ 2026-03-01

To start WK09: Reset SOT `current_step: 1`, `target_week: WK09_2026`

---

## 14. Step 10 Enhancement: Excel Shape-based RDR (PoC — 2026-03-02)

### Background
- 기존 방식: `annotate_receipts.py`가 PIL로 이미지에 직접 빨간 점선 사각형을 그림 → **원본 이미지 훼손** (PRD 절대기준 위배)
- 새 방식: Excel 도형(`<xdr:sp>`)을 ZIP XML 조작으로 삽입 → **이미지 무훼손**

### 기술 검증 결과

| 항목 | 결과 |
|------|------|
| openpyxl 도형 보존 | **불가** — 저장 시 `<xdr:sp>` 전부 삭제 (이미지만 보존) |
| ZIP XML 조작 도형 삽입 | **성공** — openpyxl 저장 후 lxml으로 drawing XML에 도형 추가 |
| 파이프라인 | `openpyxl(데이터) → .xlsx → XML조작(도형) → 최종 .xlsx` |
| 도형 스타일 | 사용자가 삽입한 원본과 동일: #FF0000, sysDash, 1pt, noFill |

### 도형 원본 XML (모든 WK 템플릿 공통)
```xml
<xdr:twoCellAnchor>
  <xdr:sp> ... <a:ln w="12700"><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill>
  <a:prstDash val="sysDash"/></a:ln> ... prst="rect" ... </xdr:sp>
</xdr:twoCellAnchor>
```
- 위치: `xl/drawings/drawing2.xml` (Receipt sheet)
- 앵커: `twoCellAnchor` rows 13-17, cols 0-4 (PARKING/TOLLS 테이블 아래)

### 좌표 변환 방식
- 이미지 앵커 (from_row/col → to_row/col) + 이미지 픽셀 크기 → 셀 EMU 매핑
- `pixel_to_cell(px, py, anchor)`: 픽셀 좌표 → (row, col, row_off_emu, col_off_emu)
- 행 높이: default 14pt (177800 EMU) + custom heights from worksheet XML
- 열 너비: character width → pixel → EMU 변환

### WK09 PoC 결과 (28 shapes, 13 images)

| 섹션 | 이미지 | 영수증 | 도형 |
|------|-------|--------|------|
| §19(1) TOLLS | image2 | 톨 내역 테이블 | 4 (Feb 23/24/25/27 그룹) |
| §19(1) PARKING | image7 | 트릴파크 주차 | 2 (날짜+금액) |
| §19(2) DINNER | image3 | 아디지 | 2 (날짜+금액) |
| §19(2) DINNER | image8 | Spot Mart | 2 (날짜+금액) |
| §19(3) STAFF | image4 | Starbucks 2/24 | 2 (날짜+결제금액) |
| §19(3) STAFF | image5 | Starbucks 2/25 | 2 (날짜+결제금액) |
| §19(3) STAFF | image12 | 폴 바셋 평택 2/25 | 2 (날짜+총 결제금액) |
| §19(4) TRAVEL | image9 | 폴 바셋 DSR 2/23 | 2 (날짜+총 결제금액) |
| §19(4) TRAVEL | image10 | 폴 바셋 DSR 2/24 | 2 (날짜+총 결제금액) |
| §19(4) TRAVEL | image11 | 폴 바셋 DSR 2/25 | 2 (날짜+총 결제금액) |
| §19(4) TRAVEL | image6 | 까치지맘방 2/27 | 2 (날짜+판매금액) |
| §19(4) TRAVEL | image13 | 폴 바셋 DSR 2/26 | 2 (날짜+총 결제금액) |
| §19(4) TRAVEL | image14 | 폴 바셋 평택 2/27 | 2 (날짜+총 결제금액) |

### PoC 출력
| File | Size | MD5 |
|------|------|-----|
| `raw-data/output/WK09_RDR_POC_TEST.xlsx` | 8,183,338 bytes | efffd062c41e |

### WK09 Receipt Images (13개)
| Image | Section | Receipt | Date | Amount | Pixels |
|-------|---------|---------|------|--------|--------|
| image2 | TOLLS | 톨 내역 테이블 (12건) | 02/23~02/27 | 총 10,200 | 747×492 |
| image7 | PARKING | 트릴파크 주차 | 02/27 | 10,000 | 554×1084 |
| image3 | DINNER | 아디지 평택삼성전자 | 02/24 | 10,200 | 666×1290 |
| image8 | DINNER | Spot Mart | 02/25 | 11,300 | 694×1172 |
| image4 | STAFF | Starbucks 평택고덕 | 02/24 | 9,700 | 646×700 |
| image5 | STAFF | Starbucks 평택고덕 | 02/25 | 9,500 | 700×818 |
| image12 | STAFF | 폴 바셋 평택점 | 02/25 | 14,200 | 780×1080 |
| image9 | TRAVEL | 폴 바셋 DSR점 | 02/23(Mon) | 26,300 | 758×1898 |
| image10 | TRAVEL | 폴 바셋 DSR점 | 02/24(Tue) | 16,800 | 734×1470 |
| image11 | TRAVEL | 폴 바셋 DSR점 | 02/25(Wed) | 10,800 | 806×1384 |
| image6 | TRAVEL | 까치지맘방 원삼점 | 02/27(Fri) | 20,900 | 758×1524 |
| image13 | TRAVEL | 폴 바셋 DSR점 | 02/26(Thu) | 23,400 | 756×1704 |
| image14 | TRAVEL | 폴 바셋 평택점 | 02/27(Fri) | 15,200 | 766×1414 |

### 사용자 피드백 (pending)
- 도형이 없는 영수증이 많았음 → 13/13 이미지 전체 커버로 개선
- 위치 정밀도 부족 → 픽셀-셀 EMU 변환기 구현으로 개선
- 추가 미세 조정 필요 시 픽셀 좌표 수정 후 재생성 가능

### 장점 (기존 PIL 대비)
- 원본 이미지 **무훼손** (PRD 절대기준 준수)
- 벡터 도형 → 확대해도 깨지지 않음
- Excel에서 사용자가 직접 이동/크기 조절/삭제 가능
- 파일 크기 미미한 증가 (XML 텍스트만 추가)

### 남은 과제
- 도형 위치 미세 조정 (사용자 피드백 기반 픽셀 좌표 보정)
- annotate_receipts.py를 XML 방식으로 전환 (PIL → lxml)
- 기존 WK06/07/08 출력물에도 새 방식 적용 여부 결정

---

*Backup complete. 3 weeks verified + RDR PoC tested. Ready for WK09 full execution.*
