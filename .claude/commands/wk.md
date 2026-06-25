---
description: "WK_workflow 실행 — 경비 정산 Excel 자동 생성 (R-A: 결정론 harness + vision)"
---

## WK Expense Report — Harness-Driven Execution (R-A)

> 인수: `$ARGUMENTS` = 주차 번호 (예: `WK21_2026`)
> 설계: `WK_workflow.md` · 분석: `FULL-AUTOMATION-REFACTORING-ANALYSIS-R1.md` · `R-A-DESIGN-AND-BACKUP-PLAN.md`
> 직전 버전(에이전트 팀 오케스트레이션): `.claude/commands/wk.md.bak-RA`

**R-A refactoring (ADR-pending)**: 구 에이전트 팀(WK_orchestrator + phase1~4_supervisor + phase*_admin×4 + secretary×3 + final_verifier, `wk.md`가 런타임 TeamCreate로 생성)을 **결정론 Python**으로 대체한다:
- **`scripts/run_week.py`** — 결정론 harness. 구 orchestrator/supervisor/secretary의 **순차 제어·게이트·오류 라우팅**을 대체. 파이프라인 9단계(S0–S8) 구동.
- **`scripts/verify_week.py`** — 통합 결정론 검증기. 구 admin×4 + final_verifier의 검증 체크리스트(38 line-item, 단계 간 중복 포함)를 **21개 고유 deterministic assertion으로 통합**. LLM "검증자"의 PASS 환각을 Python assertion이 봉쇄(anti-hallucination 강화).

**LLM(당신)의 책임은 단 2개 vision 작업으로 축소**: Step 3 OCR 판독, Step 6 bbox 좌표. 나머지(추출·기입·수식복원·RDR주입·전 검증)는 전부 결정론 Python이 수행한다. (근거: 파이프라인 9단계 중 LLM 의존은 이 2개뿐 — PYTHON-CONVERSION-FEASIBILITY-REPORT.)

---

### 역할 정의 (R-A 이후)

| 역할 | 정체 | 수행 |
|------|------|------|
| **당신** (메인 세션) | vision 수행자 + harness 구동자 | `run_week.py` 호출 → HALT 시 vision 수행 → 재호출. 결과를 사용자에 보고 |
| **`run_week.py`** | 결정론 harness | S0→S8 순차 + exit-code 게이트 + 오류 라우팅(MISSING/LOGIC/VISION). 재진입 가능 |
| **`verify_week.py`** | 결정론 검증기 | 최종 산출물 38→21 체크 (구 admin+final_verifier 대체) |

---

### 사전 점검

`run_week.py`가 내부에서 입력 존재를 검증하지만, 착수 전 아래를 확인한다:
1. `raw-data/input/$ARGUMENTS/` 폴더 + `simon_park_T&E_WK00_2026.xlsx` + `카드승인내역_*.xls(x)` 존재
2. `raw-data/simon_park_T&E_WK00_2026_ORG.xlsx` (수식 SOT) 존재
3. Python 3.9+, openpyxl, lxml, xlrd 설치

---

### 실행 프로토콜 (harness 구동 — 완전 순차·재진입)

**당신은 아래 루프를 수행한다:**

```bash
python3 scripts/run_week.py $ARGUMENTS
```

harness는 진행지점을 디스크 상태로 자동 감지하여 다음 vision 게이트 또는 완료까지 전진한다. **exit code로 다음 행동을 결정한다:**

| exit | 의미 | 당신의 행동 |
|-----:|------|-----------|
| **10** | **VISION HALT** | harness 메시지가 지시하는 vision 작업 수행(아래) 후 **`run_week.py` 재호출** |
| **0** | 완료 (verify_week 게이트 PASS) | 사용자에 완료 보고 |
| **1** | **LOGIC 오류** (검증 위반) | **즉시 중지.** `run-logs/$ARGUMENTS-run.json` + 해당 validator 리포트 확인 → 오류 보고서 작성 → 사용자 에스컬레이션. **위반 무시하고 진행 절대 금지** |
| **20** | MISSING (재시도 후 실패) | 누락 원인 확인 → 입력 보완 후 재호출, 또는 사용자 보고 |

> **재진입 원리**: S0(OCR reset)은 fresh-start에서만 실행. S1-2(추출)·S4(write_excel)·S5(annotation)·S7(수식복원)·S8(RDR)은 결정론 Python. S3·S6에서만 HALT하여 당신에게 vision을 위임한다. 깨끗한 재실행이 필요하면 `--from S3g`(OCR 공급 후) 등으로 강제. (auto-resume는 산출물 *존재*로 완료를 판정하므로, 다른 주차의 stale 산출물이 있으면 `--from`으로 강제할 것.)

---

### Vision Task 1 — Step 3 OCR (harness가 "VISION-REQUIRED: OCR"로 HALT 시)

`research/images/`의 영수증 이미지를 **독립적으로 여러 번 판독**하여 `research/ocr-results-{i}.json`(i=1,2,3,…) 생성. 각 판독은 직전 결과를 **참조하지 않고** 이미지를 처음부터 다시 읽는다(ADR-045 독립성 요건 — 기계적 복사 금지, 실제 판독 분산 필요).

**적응형 깊이 (3→7)**: 우선 3회 → `run_week.py` 재호출이 `aggregate_ocr_votes.py`를 실행. INCONCLUSIVE(harness가 다시 HALT)면 2회 더(최대 7). 합의 시 harness가 `ocr-results.json`으로 합성 확정하고 전진한다.

**카테고리 분류**: ① `input-manifest.json`의 섹션 위치(STAFF_MEETINGS/TRAVEL start_row 등) 기준 — 이미지 내용으로 추측 금지. ② **§8-1 대원칙**: Receipt Sheet에 실제 영수증 사진이 있는 거래만 OCR에 포함. 카드 내역에만 있고 사진 없는 거래는 제외(카드 대조는 verify_week가 별도 수행).

**OCR 스키마 (P0-2 — ADR-043 축소판):**
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
> `sunday_date`/`week_number`/`weekday_mapping`은 LLM이 생성하지 않는다 — `write_excel.derive_date_scaffold()`가 통행료 첫 거래일에서 결정론적으로 파생(P0-2). `meal_type`/toll `direction`도 불필요. **D-7 의도적 중복**: 이 스키마는 `WK_workflow.md`와 동기화 필수.

---

### Vision Task 2 — Step 6 bbox (harness가 "VISION-REQUIRED: BBOX"로 HALT 시)

`research/annotations/wk**-images/`의 각 이미지를 Read tool로 읽고, PRD §20 기준 날짜/금액 위치의 `[x1,y1,x2,y2]` pixel 좌표를 식별하여 `research/annotations/wk**.json`(template에서 bboxes 채움)에 저장.

**bbox 대상 (아래만 — store_logo/store_info/items/discount/tax_info 등 절대 포함 금지):**

| 섹션 | bbox 대상 | 영수증당 |
|------|----------|---------|
| TOLLS | 날짜별 Group 행 단위 | 날짜 수만큼 |
| DINNER / STAFF / TRAVEL / PARKING | 일시 + 결제금액 | **정확히 2개** |
| TELEPHONE | 이름 + 전화번호 + 이용요금 + 결제금액 | 4개 |

> **예상 총 ~25–35개. 80개 이상이면 사양 위반.** 재호출 시 `run_week.py`가 `annotate_receipts.py --check-only`(P0-1 결정론 가드, ADR-041)로 검증 — 위반 시 LOGIC(exit 1)으로 차단하니 bbox 재작업.

---

### 검증 게이트 (harness가 자동 실행 — 구 admin/secretary 대체)

harness 마지막 단계 `V`가 `verify_week.py $ARGUMENTS`를 실행한다. 이는 38개 체크리스트 항목(구 phase1~4_admin + final_verifier, 단계 간 중복 포함)을 **21개 고유 결정론 assertion**으로 통합한 것이다(단주 실행 시 적용 가능 항목이 평가됨). 기존 deep validator(`verify_card_matching`·`verify_toll_integrity`·`verify_formula_integrity`)를 subprocess로 위임 재사용하고(SOT 단일·재구현 0), 구조·존재·값·카운트 체크를 추가한다. `verification-logs/$ARGUMENTS-verify.json`에 항목별 PASS/FAIL/SKIP + Evidence 기록. FAIL ≥ 1 → exit 1(LOGIC) → 중지.

---

### 오류 처리

| harness 신호 | 유형 | 조치 |
|-------------|------|------|
| exit 20 (MISSING, 재시도 실패) | 누락 오류 | 입력 보완 후 재호출, 또는 사용자 보고 |
| exit 1 (LOGIC, validator 위반) | 로직 오류 | 모든 수행 중지 → `run-logs/`·validator 리포트 기반 오류 보고서 → 사용자 제출 후 대기 |

**오류 보고서 형식 (로직 오류 시):**
```
## WK** 실행 오류 보고서
### 오류 위치: harness stage {S*/V}, validator {이름}
### 오류 유형: 로직 오류
### 상세: {verify_week/validator 리포트의 FAIL 항목 + Evidence}
### 영향 범위 / 산출물 상태
```

---

### 정상 완료 시 (exit 0)

사용자에게 보고:
```
## WK** 실행 완료 보고
### 최종 산출물
- Excel: raw-data/output/simon_park_T&E_$ARGUMENTS.xlsx
- Cell mapping: planning/cell-mapping.json
- Annotations: research/annotations/wk**.json
### 검증 결과 (verify_week.py)
- verification-logs/$ARGUMENTS-verify.json: PASS=N FAIL=0 (SKIP 허용)
- 카드 대조 / 톨 무결성 / 셀 무결성 게이트: PASS
### 통계: 총 operations / RDR shapes / 수식 무결성
```

---

### 절대 제약 (불변)

1. **순차 실행** — harness가 S0→S8→V를 강제. 병렬 금지.
2. **openpyxl→lxml 순서** — S7(formula restore)이 openpyxl 최종. S8(RDR) 이후 openpyxl 금지(harness가 순서 강제).
3. **원본 이미지 불변** (`<pic>`), **입력 read-only** (`raw-data/input/` 쓰기 금지).
4. **vision은 당신만** — harness는 OCR/bbox를 흉내내지 않고 HALT한다. 당신이 실제 판독을 수행.
5. **LOGIC(exit 1) 무시 금지** — 검증 위반 시 완료 보고 절대 금지.

> **롤백**: 구 에이전트 팀 프로토콜이 필요하면 `cp .claude/commands/wk.md.bak-RA .claude/commands/wk.md`로 즉시 복원.
