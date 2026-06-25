# WK Expense Report Automation Workflow

> PRD: `PRD_pre_instructions.md`
> 이 워크플로우는 주차(WK**)별 경비 정산 Excel 파일을 자동 생성하는 전체 파이프라인을 정의한다.

> **실행 모델 (R-A refactoring, ADR-pending)**: 이 파이프라인은 이제 **결정론 harness `scripts/run_week.py` + 통합 검증기 `scripts/verify_week.py`**로 실행된다. 구 에이전트 팀(WK_orchestrator·phase1~4_supervisor·phase*_admin·secretary·final_verifier)은 LLM-PASS 환각 위험을 줄이기 위해 결정론 Python으로 대체되었다(구 모델 보존: `.claude/commands/wk.md.bak-RA`, `WK_agent_design_report.md` — superseded). LLM은 2개 vision 작업(Step 3 OCR · Step 6 bbox)만 수행한다. **아래 파이프라인 단계 정의는 canonical하며 불변**이다 — 본문의 `secretaryN`/`phase*` 라벨은 이제 harness/verify_week가 실행하는 **결정론 스테이지**를 가리키는 이름표이며, 더 이상 별도 에이전트가 아니다.

---

## 사전 조건


| 항목           | 경로 / 요건                                                              |
| ------------ | -------------------------------------------------------------------- |
| 원본 템플릿 (ORG) | `raw-data/simon_park_T&E_WK00_2026_ORG.xlsx` — 수식 무결성 SOT            |
| 주차별 입력 폴더    | `raw-data/input/WK**_2026/` — 사용자가 사전 준비                             |
| 입력 Excel     | `raw-data/input/WK**_2026/simon_park_T&E_WK00_2026.xlsx` (read-only) |
| 카드 승인 내역     | `raw-data/input/WK**_2026/카드승인내역_YYYYMMDD.xls(x)`                    |
| 영수증 이미지      | `raw-data/input/WK**_2026/*.PNG` (있는 경우)                             |
| OCR 데이터      | `research/ocr-results.json` — 주차별 swap 필요                            |
| Python 3.9+  | openpyxl, lxml, xlrd                                                 |


---

## 파이프라인 개요

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: Data Extraction (Steps 1-3)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ §1 extract   │  │ §2 extract   │  │ §3 OCR swap  │      │
│  │ _images.py   │→ │ _card_data.py│→ │ (manual)     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
├─────────────────────────────────────────────────────────────┤
│  Phase 2: Excel Data Entry (Step 4)                         │
│  ┌──────────────────────────────────────────────────┐      │
│  │ §4-§18 write_excel.py --all                       │      │
│  │  ├─ base: §4-§16 (Receipt + FORM + Mileage log)  │      │
│  │  ├─ §17-2: Formula integrity check & restore      │      │
│  │  └─ post: §18 (KRW prefix + rename)               │      │
│  └──────────────────────────────────────────────────┘      │
├─────────────────────────────────────────────────────────────┤
│  Phase 3: Annotation Prep + Formula Guard (Steps 5-6, 7)   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Step 5       │→ │ Step 6       │→ │ Step 7           │  │
│  │ generate_    │  │ Claude Vision│  │ §17-2 최종 수식   │  │
│  │ annotations  │  │ bbox 좌표 채움│  │ 복원 (openpyxl   │  │
│  │ §20 대상 분류 │  │ §20 pixel 좌표│  │ 마지막 사용 지점) │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Phase 4: RDR Shape Injection — FINAL (Step 8)              │
│  ┌──────────────────────────────────────────────────┐      │
│  │ §19-§21 annotate_receipts.py (lxml 직접 ZIP)      │      │
│  │ ⚠ 이후 openpyxl load/save 금지 — shape 소실 방지  │      │
│  └──────────────────────────────────────────────────┘      │
├─────────────────────────────────────────────────────────────┤
│  Post-Pipeline: Card Reconciliation (secretary2)             │
│  ┌──────────────────────────────────────────────────┐      │
│  │ verify_card_matching.py (read_only, save 금지)    │      │
│  │ Receipt 1st/2nd 금액 ↔ 카드승인내역 소거 대조      │      │
│  │ TELEPHONE/TOLLS(Hi-pass) 제외 (별도 카드 결제)    │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

> **실행 순서 제약**: Step 8(RDR 주입)은 반드시 **파이프라인의 최종 단계**여야 한다.
> `annotate_receipts.py`는 lxml로 drawing XML을 직접 조작하므로, 이후에 openpyxl로
> 파일을 열고 저장하면 주입된 `<sp>` 요소가 소실된다. Step 7(수식 복원)이 openpyxl의
> 마지막 사용 지점이며, 이후에는 openpyxl을 사용하지 않는다.

---

## 실행 절차

### Phase 1: Data Extraction

#### Step 1. 이미지 추출 + 매니페스트 생성 (§1-§3)

```bash
python3 scripts/extract_images.py WK**_2026
```

**동작:**

- 입력 Excel을 `raw-data/output/`에 복사
- Receipt Sheet의 영수증 이미지를 `research/images/`에 추출
- drawing XML에서 이미지 앵커 위치를 파싱 (§17-1)
- `research/input-manifest.json` 생성 (섹션 위치, 이미지 목록, 카드 파일 경로)

#### Step 2. 카드 승인 데이터 추출 (§18(1))

```bash
python3 scripts/extract_card_data.py
```

**동작:**

- `input-manifest.json`에서 카드 파일 경로를 읽어 `.xls`/`.xlsx` 자동 판별
- 승인날짜, 승인시간, 거래금액을 추출하여 `research/card-approval-data.json` 생성

#### Step 0. OCR 데이터 초기화 (harness S0 — 구 secretary0)

**매 실행마다 기존 OCR 데이터를 삭제하고 새로 생성한다** (방안 A — 절대 기준 1 근거).

```bash
# 기존 OCR 데이터 + N회 판독 + 백업 삭제
rm -f research/ocr-results.json
rm -f research/ocr-results-[0-9]*.json
rm -f research/ocr-vote-report.json
rm -f research/wk**_ocr-results.json
```

기존 백업에 분류 오류가 영속적으로 재사용되는 것을 방지한다. 비용/시간보다 품질이 우선이다.

---

#### Step 3. OCR 데이터 생성 (적응형 N-read 다수결 — ADR-045, ADR-044 supersede)

기존 OCR은 Step 0에서 삭제되었으므로, Claude가 `research/images/`의 영수증 이미지를 **독립적으로 여러 번** 판독하여 `research/ocr-results-{i}.json`을 생성한다(각 판독은 직전 미참조, 실제 판독 분산 필요 — 결정론 복제 금지). 적응형 깊이: 우선 3회 → `python3 scripts/aggregate_ocr_votes.py WK**_2026`. **exit 2**(미해결)면 2회씩 추가(최대 7회) 후 재실행. **exit 0**이면 스크립트가 placement-critical 필드 다수결(만장일치/강다수 ≥⌈0.8N⌉) 합의본을 `ocr-results.json`으로 합성 확정. **exit 1**(7회 소진·미합의)이면 해당 영수증 재판독(최대 2회) 후 사용자 에스컬레이션. **결합 불변식**: 합의본은 정답 보증이 아니며, 이후 `verify_card_matching`·`verify_toll_integrity`·`derive_date_scaffold` 결정론 계층을 반드시 통과해야 한다 — 다수결은 확률적 오류 보강, 체계적 오류 최종 방어선은 독립 사실 대조 (절대 기준 1·2, 비용 무시).

**영수증 카테고리 분류 규칙**:

1. `input-manifest.json`의 섹션 위치 정보(STAFF_MEETINGS start_row, TRAVEL start_row 등)를 기준으로 각 영수증이 어느 섹션에 속하는지 결정한다. 이미지 내용만으로 추측하지 않는다.
2. **§8-1 대원칙**: Receipt Sheet에 실제로 존재하는 영수증 사진을 기준으로만 OCR 데이터를 생성한다. 카드 승인 내역에만 있고 Receipt Sheet에 영수증 사진이 없는 거래는 OCR에 포함하지 않는다. 카드 대조는 §18에서 별도 수행한다.

> 실행 완료 후에는 반드시 `research/ocr-results.json`을 `research/wk**_ocr-results.json`으로 백업해 둔다.

**OCR JSON 필수 스키마 (P0-2 — ADR-043으로 축소):**

```json
{
  "parking_tolls": {
    "toll_history": [{"date", "time", "entry", "exit", "amount"}],
    "parking_receipts": [{"date", "time", "amount"}]
  },
  "dinner": [{"date", "time", "amount", "store"}],
  "staff_meetings": [{"date", "time", "amount", "store", "headcount"}],
  "travel": [{"date", "time", "amount", "store", "headcount"}],
  "telephone": {"month_matches": bool, "payment_amount": N}
}
```

> **P0-2 (ADR-043) — 날짜 스캐폴드는 Python이 산출**: `sunday_date`,
> `week_number`, `weekday_mapping`은 `write_excel.derive_date_scaffold()`가
> **통행료 첫 거래일에서 결정론적으로 파생**한다(12개 백업 byte-equivalence
> 입증). LLM은 더 이상 이 3개를 생성하지 않으며, 톨 거래의 `date`만 정확히
> 판독하면 된다. `dinner.meal_type`(write_excel가 시각으로 재계산)과 toll
> `direction`(미사용)도 불필요 — LLM 오류 표면적 축소(절대 기준 1).
> **D-7 의도적 중복**: 이 스키마는 `.claude/commands/wk.md`(스키마 +
> phase1_admin)와 동기화 필수. 변경 시 3곳(+ `write_excel.py`) 동시 수정.

---

### Phase 2: Excel Data Entry

#### Step 4. write_excel.py 실행 (§4-§18)

```bash
python3 scripts/write_excel.py --all
```

**내부 실행 순서:**


| 단계            | PRD 참조                            | 동작                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| base §4       | FORM K8                           | week ending 일요일 날짜 기입 (통행료 첫 거래일시 기준, 해당 주(월~일)의 일요일 — PRD §2-§4. 거래일 **이후** 일요일이어야 함)                                                                                                                                                                                                                                                                                                                      |
| base §5-§6    | FORM G2                           | 주차 번호 문자열 수정                                                                                                                                                                                                                                                                                                                                                                                                |
| base §7-§8    | Receipt PARKING/TOLLS             | 통행료 Summary table 기입                                                                                                                                                                                                                                                                                                                                                                                        |
| base §9       | Receipt DINNER                    | 시간대별 식사비 기입                                                                                                                                                                                                                                                                                                                                                                                                 |
| base §10      | Receipt STAFF                     | 금액 기입 + how many(이미지 anchor 기반 [가로'영수증 가로길이' x 세로'밑 1~10칸'] 영역에서 이름 count. 이름 없으면 how many=0). 동일 날짜 2장 시 1st/2nd 시간순 + 인원 합산. 이름을 날짜별 database로 보존 (PRD §10(3)(4)). **이미지→요일 매핑: order-based matching** (좌→우 이미지 순서 = OCR 시간순 엔트리, `_match_images_to_days_by_order()`). **이미지 정렬: row-group clustering** (`_get_receipt_image_anchors()` — 행 갭 >30 rows로 시각적 행 구분 후 행 그룹별 from_col 정렬. 2행 그리드에서 열 인터리브 방지) |
| base §10-1    | FORM [F] STAFF                    | Receipt how many → FORM NO. OF PAX 동기화 (PRD §10-1)                                                                                                                                                                                                                                                                                                                                                          |
| base §11      | Receipt TRAVEL                    | 금액 기입 + how many(이미지 anchor 기반 [가로'영수증 가로길이' x 세로'밑 1~10칸'] 영역에서 이름 count. 이름 없으면 how many=0). 동일 날짜 2장 시 1st/2nd 시간순 + 인원 합산. 이름을 날짜별 database로 보존 (PRD §11(3)(4)). **이미지→요일 매핑: order-based matching** (동일 방식). **이미지 정렬: row-group clustering** (동일 방식)                                                                                                                                                  |
| base §11-1    | FORM [A] TRAVEL                   | Receipt how many → FORM NO. OF PAX 동기화 (PRD §11-1)                                                                                                                                                                                                                                                                                                                                                          |
| base §12-§13  | Receipt TELEPHONE                 | 통신비 80% 기입                                                                                                                                                                                                                                                                                                                                                                                                  |
| base §14      | FORM [A] TRAVEL + [F] STAFF names | **각 영수증 이미지 anchor** 기반 [가로x세로 밑 10칸] 영역에서 이름+소속 읽기 (이미지별 독립 — PRD §10(3), §11(3)). 이름 DB 범위는 row 999(헤더) 이후 빈 행까지 **동적 탐지** (PRD §17-1-1). 수식이 name DB 범위 내 참조 → 이름, row 999 참조 → 소속. 이름 DB로 영문 변환 → 소속별 그룹화 포맷팅 (PRD §14). 이름 없으면 how many=0 (§10(4), §11(4)). 중복 이름 제거 (§10(9), §11(9))                                                                                                                  |
| base §15      | FORM clear                        | 빈 날짜 열 데이터 삭제                                                                                                                                                                                                                                                                                                                                                                                               |
| base §16      | Mileage log                       | 입구/출구 규칙별 거리 기입                                                                                                                                                                                                                                                                                                                                                                                             |
| base §17      | Receipt→FORM 수식 정합                | 테이블 위치 database 대조                                                                                                                                                                                                                                                                                                                                                                                          |
| **§17-2**     | **FORM 수식 무결성**                   | **ORG 대비 663개 수식 검사 + 자동 복원**                                                                                                                                                                                                                                                                                                                                                                               |
| post §18(2-3) | FORM KRW                          | 카드 대조 후 KRW 접두어                                                                                                                                                                                                                                                                                                                                                                                             |
| post §18(4)   | 파일명                               | `WK00` → `WK`** 리네임                                                                                                                                                                                                                                                                                                                                                                                         |
| post §18(5-6) | FORM 톨/전화                         | 무조건 KRW 접두어                                                                                                                                                                                                                                                                                                                                                                                                 |


---

### Phase 3: Annotation Prep + Formula Guard (Steps 5-7)

#### Step 5. Annotation 템플릿 생성

```bash
python3 scripts/generate_annotations.py WK**_2026
```

**동작:**

- 출력 Excel에서 Receipt 이미지를 `research/annotations/wk**-images/`에 추출
- 이미지별 섹션 분류 (TOLLS/DINNER/STAFF/TRAVEL/TELEPHONE)
- `research/annotations/wk**-template.json` 생성 (bboxes 비어있음)

#### Step 6. Bbox 좌표 채우기 (Claude Vision)

Claude가 각 추출된 이미지를 Read tool로 읽고, PRD §20 기준에 따라 날짜/금액 위치의 `[x1, y1, x2, y2]` pixel 좌표를 식별하여 `wk**-template.json` → `wk**.json`으로 저장한다.

**섹션별 bbox 대상 (아래 항목만 — store_logo, store_info, items, discount, tax_info 등 포함 금지):**


| 섹션        | bbox 대상                 | 영수증당 bbox 수 |
| --------- | ----------------------- | ----------- |
| TOLLS     | 날짜별 Group 구분 (행 단위)     | 날짜 수만큼      |
| DINNER    | 일시 + 결제금액               | 정확히 2개      |
| STAFF     | 일시 + 결제금액               | 정확히 2개      |
| TRAVEL    | 일시 + 결제금액               | 정확히 2개      |
| TELEPHONE | 이름 + 전화번호 + 이용요금 + 결제금액 | 4개          |
| PARKING   | 일시 + 결제금액               | 정확히 2개      |


> **예상 총 bbox 수**: 1주일 기준 ~25-35개. 80개 이상이면 사양 위반.

> **P0-1 결정론 가드 (ADR-041)**: Step 6 완료 후 Step 8 진입 전, `annotate_receipts.py`가
> `wk**.json`을 결정론적으로 검증한다. DINNER/STAFF/TRAVEL/PARKING 영수증은 bbox {0, 2}개만
> 허용(0=정상 스킵), TELEPHONE 4/page, TOLLS per-image ≤10, 전역 하드 상한 80. 위반 시
> exit code 1로 Step 8을 차단하고 Step 6 재실행을 유도한다. 사전 단독 검증:
> `python3 scripts/annotate_receipts.py --check-only WK**_2026`.

#### Step 7. 최종 수식 복원 (openpyxl 마지막 사용 지점)

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
import openpyxl
from write_excel import check_and_restore_all_sheets
path = 'raw-data/output/simon_park_T&E_WK**_2026.xlsx'
wb = openpyxl.load_workbook(path)
restored = check_and_restore_all_sheets(wb)   # FORM(86)+Receipt+Mileage (P-FG2 ADR-046)
if restored: wb.save(path)
wb.close()
"
```

**근거:** `write_excel.py`의 openpyxl 저장 과정에서 FORM Sheet의 빈 셀 수식(row 27, 44 등)이 소실된다. 이 단계에서 ORG 대비 663개 수식을 검사하고 누락분을 복원한다.

> **⚠ 이 단계가 openpyxl의 마지막 사용 지점이다.** 이후 Step 8에서 lxml이 직접 ZIP을 조작하므로, Step 7 이후에 openpyxl로 파일을 열면 Step 8의 RDR shape가 소실된다.

---

### Phase 4: RDR Shape Injection — FINAL (Step 8)

#### Step 8. RDR Shape 주입 (§19-§21)

```bash
python3 scripts/annotate_receipts.py WK**_2026
```

> **⚠ 이 단계는 반드시 파이프라인의 최종 단계로 실행한다.**
> `annotate_receipts.py`는 lxml으로 Excel ZIP 내부의 drawing XML을 직접 조작한다.
> 이후 openpyxl `load_workbook` → `save`를 수행하면 주입된 `<sp>` 요소가 소실된다.

**내부 실행 순서 (7단계 — Per-Image Anchor Calibration):**


| 단계  | 동작                                                                                                                                      | PRD 참조     |
| --- | --------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| 8-1 | `wk**.json`에서 이미지별 bbox 좌표 로드                                                                                                           | §20        |
| 8-2 | 입력 Excel(`WK00`)에서 `직사각형 2` RDR 템플릿 도형 추출 (`_extract_template_rdr`)                                                                     | §19(2)     |
| 8-3 | 출력 Excel의 Receipt Sheet 워크시트 경로 탐색 + `drawing2.xml` 및 rels 파싱                                                                           | —          |
| 8-4 | drawing XML에서 이미지 앵커 좌표(from/to + xfrm) 파싱                                                                                              | §17-1      |
| 8-5 | **Per-Image Anchor Calibration**: 각 이미지의 from/to/xfrm에서 avg_col_width, avg_row_height를 자체 산출. 전역 EMU 그리드 불필요 — cross-image xfrm 불일치에 면역 | §21 정밀도    |
| 8-6 | 각 bbox의 pixel 좌표를 `_per_image_pixel_to_cell()`로 해당 이미지 앵커 기준 cell 좌표 변환                                                                 | §21(1) 1mm |
| 8-7 | 변환된 좌표로 RDR shape를 clone하여 `drawing2.xml`에 `twoCellAnchor > sp` 요소 주입                                                                   | §19(2)     |


**제약:**

- 원본 영수증 이미지(`<pic>`)는 일체 변경하지 않는다 (§19(1))
- RDR은 이미지 위에 겹쳐 놓는 투명한 빨간 점선 도형(`<sp>`)이다
- §21(1): bbox 라인과 영수증 글자 간격이 1mm 이내가 되도록 EMU 변환 정밀도를 유지한다
- §21(2): 정밀도는 Step 6(bbox 좌표)과 Step 8-5~8-6(per-image anchor calibration)의 조합으로 결정된다
- **잔여 리스크**: col A-E 비균일 구간(일부 이미지) 수평 최대 ~2mm 오차 가능
- **이 단계 이후 openpyxl로 파일을 열지 않는다** — shape 소실 방지

---

### Post-Pipeline: 카드 대조 검증 (verify_week C34 / verify_card_matching — 구 secretary2)

Phase 4 완료 후, `verify_card_matching.py`가 Receipt Sheet 금액과 카드 승인 내역을 소거(consume) 방식으로 전수 대조한다.

```bash
python3 scripts/verify_card_matching.py WK**_2026
```

**동작:**

1. Receipt Sheet의 섹션별 1st/2nd 셀 금액을 전수 읽기 (DINNER breakfast/lunch/dinner, STAFF 1st/2nd, TRAVEL 1st/2nd, PARKING 주차비)
2. 카드 승인 기록을 "미소거 풀"에 넣고, Receipt 금액마다 `(date, amount)` 일치 기록을 하나씩 소거
3. 소거 완료 후 풀에 남은 카드 기록은 모두 **FAIL** (정산 손실 방지 알림):
   - 사유 구분: 영수증 사진 있는데 금액 미기입 vs 영수증 미제출 (사유를 FAIL 보고서에 기록)
- 출력 Excel은 `read_only=True`로만 열고 **절대 save하지 않음** (Phase 4 이후 openpyxl save 금지)

**대조 제외 (별도 카드 결제):**

- **TELEPHONE**: 별도 카드로 결제 — 카드승인내역에 미포함
- **TOLLS (Hi-pass)**: 별도 카드로 결제 — 카드승인내역에 미포함

**결과 처리:**


| 결과                        | Exit Code | 산출물                                                        |
| ------------------------- | --------- | ---------------------------------------------------------- |
| 전체 카드 기록 소거 완료 (잔여 0건)   | 0         | 없음 — PASS 보고                                               |
| FAIL 발견 (미소거 카드 또는 Receipt 미매칭) | 1   | `raw-data/output/카드승인내역_YYYYMMDD_FAIL.xlsx` (FAIL 행 빨간색 + 사유 기록) |


---

### Post-Pipeline: 톨 산술 무결성 검증 (verify_week C35 / verify_toll_integrity — 구 secretary2.5, ADR-042)

카드 대조 검증 후, `verify_toll_integrity.py`가 `ocr-results.json`의 톨 기록을
결정론적으로 검사한다. TOLLS는 카드 대조에서 제외(별도 Hi-pass 카드)되므로
가장 기준이 되는 톨 영수증에 대한 유일한 결정론적 검증 계층이다.

```bash
python3 scripts/verify_toll_integrity.py WK**_2026
```

**검사 항목 (전부 결정론, 읽기 전용):**

- **T-1**: 동일 `(entry, exit)` 구간 금액 일관성 (이상치 → 경고)
- **T-2**: go/back 페어링 (go만 있고 back 없음 → 경고)
- **T-3**: 실제 구간(entry/exit ≠ "-")인데 amount=0 → **위반**
- **T-4**: PRD §16 거리 규칙 미해결 경로(미등록 게이트명) → 경고
- **T-5**: 모든 톨 날짜가 Python 파생 주[monday..sunday] 범위 내 (PRD §2-§4) → **위반** (P0-2 후 sunday_date는 `derive_date_scaffold` 산출이므로, 톨 날짜가 다른 주로 misread된 경우를 검출하도록 재정의 — ADR-043)
- **T-6**: 동일 날짜 시각 중복/단조성 → 경고

**결과 처리:**

| 결과 | Exit Code | 산출물 |
| --- | --- | --- |
| violation 0건 (warning 허용) | 0 | 없음 — PASS 보고 |
| violation ≥ 1건 | 1 | `research/toll-integrity-report.json` (violations + warnings) |

> 거리 규칙은 `write_excel.get_distance`를 import 재사용한다 (SOT 단일 — 절대 기준 2).

---

### Post-Pipeline: 셀 무결성 게이트 (verify_week C36 / verify_formula_integrity — 구 secretary3, 진짜 최종, ADR-046/047)

모든 단계(Phase 4 RDR 주입 포함) 완료 후, `verify_formula_integrity.py`가 **진짜 최종 산출물**을 ORG와 대조하여 PRD [절대적 기준](지정 구역 외 cell 내용·수식 일체 변경 금지)을 결정론적으로 **차단 검증**한다. 자가치유(`check_and_restore_all_sheets`)의 하드 backstop이며 절대 기준 매트릭스의 "이중 검증"을 실체화한다.

```bash
python3 scripts/verify_formula_integrity.py WK**_2026
```

**범위 (FORM-only 갭 폐쇄)**: 3개 시트. 승인=FORM **PRD-86만**(cell-mapping 무시 → 타게팅 할루시네이션 포착), Receipt/Mileage `cell-mapping.json`. 읽기 전용. 검사 3종 — 수식 1,555(P-FG1 위반) + 정적내용 458 라벨/헤더(P-FG4a 위반) + ORG 빈 셀 부유 write(P-FG4b 경고·비차단·단계적). 실증 근거: openpyxl 라운드트립 비-수식 노이즈 0(ADR-047).

| 결과 | Exit Code | 산출물 |
| --- | --- | --- |
| 수식·정적내용 위반 0건 | 0 | warning 있으면 `formula-integrity-report.json`(PASS_WITH_WARNINGS) |
| 위반 ≥ 1건 | 1 | `research/formula-integrity-report.json` (violations + warnings) |

> SOT 단일(절대 기준 2): PRD-86 셋과 cell-map 정규화는 `write_excel.prd_form_writable`·`_norm_col`을 import 재사용 — 재구현 금지.

---

## 일괄 실행 스크립트

> **R-A**: 아래 bash 의사코드는 `scripts/run_week.py`(결정론 harness)로 대체되었다. run_week가 동일 단계를 순차 구동하되, Step 3 OCR·Step 6 bbox에서 HALT하여 LLM vision에 위임하고 exit-code 게이트(10=VISION/0=완료/1=LOGIC/20=MISSING)로 제어한다. 아래는 단계 순서의 참조용으로만 유지한다.

```bash
#!/bin/bash
# Usage: ./run_week.sh WK06_2026  (참조용 — 실제 실행은 python3 scripts/run_week.py WK06_2026)

WEEK=$1
WK_NUM=${WEEK:2:2}

echo "===== Processing $WEEK ====="

# Phase 1: Extraction (Steps 1-3)
python3 scripts/extract_images.py $WEEK
python3 scripts/extract_card_data.py
# Step 3: Claude Vision 적응형 N-read (3→7) → ocr-results-{i}.json (ADR-045)
# >>> Claude가 영수증 이미지를 독립적으로 3회 판독, exit 2면 +2회 반복 <<<
python3 scripts/aggregate_ocr_votes.py $WEEK   # 다수결 집계 게이트 (ADR-045)
# exit 0=합의(ocr-results.json 확정) / 2=추가판독 / 1=FAIL 에스컬레이션

# Phase 2: Data Entry (Step 4)
python3 scripts/write_excel.py --all

# Phase 3: Annotation Prep + Formula Guard (Steps 5-7)
python3 scripts/generate_annotations.py $WEEK
# >>> Claude Vision으로 wk${WK_NUM}.json 생성 필요 <<<

# Step 7: Formula restore (openpyxl 마지막 사용 지점)
python3 -c "
import sys; sys.path.insert(0, 'scripts')
import openpyxl
from write_excel import check_and_restore_all_sheets
path = 'raw-data/output/simon_park_T&E_WK${WK_NUM}_2026.xlsx'
wb = openpyxl.load_workbook(path)
restored = check_and_restore_all_sheets(wb)   # FORM(86)+Receipt+Mileage (P-FG2 ADR-046)
if restored: wb.save(path)
wb.close()
"

# Phase 4: RDR Shape Injection — FINAL (Step 8)
# ⚠ 이후 openpyxl load/save 금지
python3 scripts/annotate_receipts.py $WEEK

# Post-Pipeline: 카드 대조 검증 (secretary2)
python3 scripts/verify_card_matching.py $WEEK

# Post-Pipeline: 톨 산술 무결성 검증 (secretary2.5 — ADR-042)
python3 scripts/verify_toll_integrity.py $WEEK

# Post-Pipeline: 수식 무결성 게이트 (secretary3 — 진짜 최종, ADR-046)
python3 scripts/verify_formula_integrity.py $WEEK

echo "===== $WEEK Complete ====="
```

---

## 절대 기준 준수 매트릭스


| PRD 절대 기준       | 구현 위치                                       | 검증 방법                        |
| --------------- | ------------------------------------------- | ---------------------------- |
| 86개 지정 셀만 변경    | `write_excel.py` — 명시적 셀 주소                 | `cell-mapping.json` 감사 로그    |
| 1,555 수식 보존 (FORM 694·Mileage 817·Receipt 44) | `check_and_restore_all_sheets()` 자가치유 + `verify_formula_integrity.py` 차단 게이트 | §17-2(Step 7) + verify_week(C36)/verify_formula_integrity 최종 검증 (구 secretary3, ADR-046) |
| 원본 사진 미변경       | `annotate_receipts.py` — shape overlay only | RDR은 `<sp>`, 이미지는 `<pic>` 분리 |
| 입력 파일 read-only | `extract_images.py` — copy to output        | 입력 폴더 쓰기 없음                  |


---

## 산출물

각 주차 실행 시 아래 파일이 생성된다:


| 항목                      | 경로                                              |
| ----------------------- | ----------------------------------------------- |
| 완성 Excel                | `raw-data/output/simon_park_T&E_WK**_2026.xlsx` |
| 셀 매핑 로그                 | `planning/cell-mapping.json`                    |
| Annotation JSON         | `research/annotations/wk**.json`                |
| 추출 이미지                  | `research/annotations/wk**-images/`             |
| 카드 대조 FAIL 보고서 (불일치 시만) | `raw-data/output/카드승인내역_YYYYMMDD_FAIL.xlsx`     |


> 파일 크기와 RDR shape 수는 해당 주차의 영수증 개수에 따라 매주 달라진다.

---

## 알려진 제약사항

1. **OCR 데이터 수동 관리 + 적응형 N-read 다수결(ADR-045)**: 매 주차 Claude가 영수증 이미지를 **독립적으로 3~7회 판독**하고 `aggregate_ocr_votes.py` 다수결 게이트(만장일치/강다수)를 통과해야 한다. 미합의 시 재판독(최대 2회) 후 에스컬레이션. **잔여 한계**: N회가 *모두 동일하게* 잘못 읽는 *체계적* 오독은 다수결로 미검출 — 이는 결합 계층(`verify_card_matching`/`verify_toll_integrity`)이 독립 사실로 차단하며, 그조차 못 잡는 잔여(카드 미대조 항목의 순수 체계적 오독)는 영수증 원천 품질 개선(고해상도 재촬영/디지털 영수증) 영역이다.
2. **openpyxl 수식 손실**: openpyxl이 빈 셀 수식을 저장 시 소실하는 버그가 있다. Step 7 `check_and_restore_all_sheets`가 **FORM(86 외)·Receipt·Mileage log 전체**를 ORG로 자가치유하고(P-FG2 ADR-046 — 기존 FORM-only 갭 폐쇄), verify_week(C36)/`verify_formula_integrity.py`가 진짜 최종 산출물을 차단 검증한다.
3. **Bbox 좌표 수동**: Claude Vision 기반 좌표 식별은 자동화되지 않는다. 매 주차마다 `wk**.json`을 새로 생성해야 한다.
4. **Per-Image Anchor Calibration 잔여 리스크**: col A-E 비균일 구간(일부 이미지)에서 수평 최대 ~2mm 오차 가능 (PRD §21 1mm 기준 미달). 수직 오차는 per-image 방식으로 0mm.
5. **매주 변동 요소**: 영수증 종류/개수, 참석자 이름, 톨 기록, 통신비 월 일치 여부 등이 매주 달라진다. OCR 데이터와 Annotation JSON은 주차별로 독립 생성해야 한다.
6. **이미지 정렬 ROW_GAP_THRESHOLD=30**: `_get_receipt_image_anchors()`의 행 그룹 클러스터링 임계값. 현재 Receipt Sheet 레이아웃(행간 갭 ~70 rows)에는 충분하나, 레이아웃이 크게 변경되면 조정 필요.

---

*문서 끝*