# 수식 보존 원칙 위반 할루시네이션 — 해결 계획 보고서

작성일: 2026-05-16
대상 원칙: PRD [절대적 기준] — "지정 구역 cell 외 모든 cell의 내용·수식을 일체 변경하지 말라" (FORM 86 허가 cell + ORG 수식 보존)
조사 방법: `check_and_restore_formulas` 코드 정독 + ORG 시트별 수식 분포 실측 + 호출 체인·cell-mapping 구조 확인
원칙: 절대 기준 1·2·3

> **구현 상태 (2026-05-16)**: ✅ **P-FG1·P-FG2·P-FG3 구현·회귀 완료 (ADR-046)**. `scripts/verify_formula_integrity.py` 신규(차단 게이트), `write_excel.check_and_restore_all_sheets`+`prd_form_writable` 추가(범위 확장·SOT), 프롬프트 4곳+매트릭스 정합. 회귀 7+2 PASS — Mileage 817·Receipt 44 무방비 갭 폐쇄, FORM 타게팅 할루시네이션 포착. ✅ **P-FG4a(정적내용 hard)+P-FG4b(부유write 경고) 구현·회귀 완료 (ADR-047)** — 실증(라운드트립 노이즈 0, 정적셀 458) 기반. MergedCell 버그 수정. 회귀 S1~S5 PASS.

---

## 0. 결론 요약

**근본 원인은 "방어 범위가 FORM 시트 1개로 한정 + 자가치유만 있고 차단 게이트가 없음"이다.**

실측으로 확정한 사실:

| 시트 | ORG 수식 수 | 현재 보호 | 파이프라인이 쓰는가 |
|------|-----------:|----------|:---:|
| FORM | **694** | ✅ `check_and_restore_formulas` | O (86 허가 cell) |
| **Mileage log** | **817** | ❌ **무방비** | O (§16 거리) |
| **Receipt** | **44** | ❌ **무방비** | O (전 데이터 기입) |
| Approval / Instructions | 0 | N/A | X |

→ 현재 1,555개 수식 중 **694개(FORM)만 보호**되고 **861개(Mileage 817 + Receipt 44)는 검증·복원 대상이 전혀 아니다.** 사용자가 관찰한 "가끔 수식이 바뀌는" 할루시네이션의 주 무대는 바로 이 무방비 861개다 — 특히 수식이 가장 많은 Mileage log.

추가로 확인된 결함:
- **자가치유만 존재, 차단 게이트 없음**: `check_and_restore_formulas`는 조용히 복원·로그만 한다. 복원이 못 잡는 경우(다른 시트, 허가 cell 내부에 잘못된 수식 주입)를 **차단·표면화하는 결정론적 검증 게이트가 없다.**
- **문서·구현 불일치**: 절대 기준 매트릭스가 "663개 수식 보존 = §17-2 + **Phase 4 이중 검증**"이라 명시하나, `annotate_receipts.py`에는 수식 재검증이 **존재하지 않는다**(drawing XML만 조작). "이중 검증"은 문서에만 있고 미구현.
- **수식만 검사, 정적 내용 미검사**: PRD는 "그 외 cell의 **내용**...일체 변경 금지"이나, 현재 로직은 ORG가 *수식*인 cell만 비교한다. 비-허가 cell의 정적 라벨/값 변조는 미검출.

---

## 1. 현재 메커니즘 정밀 분석 (`write_excel.py:1087-1144`)

- 비교 SOT: `simon_park_T&E_WK00_2026_ORG.xlsx`, **FORM 시트만**, 범위 A1:AH113.
- 허가 cell 86개 하드코딩(`:1104-1116`, PRD 정합).
- 로직: ORG가 `=`로 시작하는 수식이고 86 cell이 아닌데 working ≠ ORG → **working을 ORG 수식으로 덮어씀**(restore). 반환 리스트 로그만.
- 호출: `phase_post`(`:1158`) + Step 7(wk.md/WK_workflow.md가 write_excel import 재호출). 즉 FORM은 2회 복원, **Mileage/Receipt는 0회**.
- 성격: **self-heal(복원)** — FAIL로 파이프라인을 멈추지 않음. 복원 누락분은 그대로 통과.

### 할루시네이션이 새는 경로 (정확한 벡터)

1. **무방비 시트 손상**: Mileage log(817)·Receipt(44)에 잘못된 cell 타게팅 또는 openpyxl 빈-수식 손실(알려진 버그, WK_workflow 제약 #2)이 발생해도 비교·복원 대상이 아님 → **영구 손상**.
2. **허가 cell 내부 수식 오염**: 86 허가 cell은 비교에서 제외(`:1126-1127`)되므로, 그 안에 잘못된 수식/값이 들어가도 미검출.
3. **검증 게이트 부재**: 복원이 놓친 잔여를 "0건"으로 단정·차단하는 독립 검증이 없어, 손상된 산출물이 PASS로 보고됨.
4. **최종 산출물 미검증**: Phase 4(RDR 주입, lxml ZIP) 이후의 *진짜 최종 파일*을 ORG와 대조하는 단계가 없음("이중 검증" 미구현).

---

## 2. 해결 설계 — 4계층 (CCP 구조)

### P-FG1. 수식 무결성 결정론 검증 게이트 (신규, 최우선)

**Step 1 의도**: 복원이 못 잡는 모든 위반을 *차단*하는 독립 검증. 자가치유의 backstop. (품질 — 절대 기준 1)

**Step 2 파급**: 신규 `scripts/verify_formula_integrity.py`(읽기 전용, 추가적). 입력: 최종 워크북 + ORG + `planning/cell-mapping.json`. 기존 코드 무수정 — 신규 파일 + 호출 1줄(파이프라인 최종 단계). `validate_*.py` 패턴 정합.

**Step 3 변경 설계**:
- 3개 쓰기 시트(FORM·Receipt·Mileage log) 전부에 대해, ORG가 수식인 cell 중 **승인되지 않은** cell에서 `최종값 ≠ ORG 수식`이면 **VIOLATION**.
- 승인(allowlist) = PRD-86(FORM) ∪ `cell-mapping.json`의 `phase_base`+`phase_post` operations `(sheet,row,col)`. 즉 "파이프라인이 의도적으로 기록한 cell"은 허용, **그 외 수식 변경은 전부 위반**.
- 추가 검출: 비-허가 cell이 cell-mapping에 *있더라도* ORG에서 수식인데 변경됐다면(= 파이프라인이 수식 cell을 잘못 타게팅) → **VIOLATION**(타게팅 할루시네이션 포착).
- 결과: violation ≥ 1 → exit 1 + `research/formula-integrity-report.json`(sheet, cell, expected, actual). 0 → PASS.
- **실행 위치**: 모든 단계(Phase 4 포함) **이후 진짜 최종**에 실행 — 산출물 수준 불변식을 진짜로 보장(§3 "이중 검증" 구현 실체화).

### P-FG2. 자가치유 범위 확장 (`check_and_restore_formulas` 일반화)

**의도**: openpyxl 빈-수식 손실 등 *복원 가능한* 손상을 Mileage/Receipt까지 방어.
**파급**: 함수 시그니처를 `(ws, permitted_set=None)` 형태로 일반화하되 **기존 호출부(FORM, 86 cell)는 기본 인자로 byte-identical 유지**(회귀 0). Receipt/Mileage용 호출 추가(허가셋 = cell-mapping operations).
**변경 설계**: ORG의 해당 시트를 SOT로 비교·복원. FORM 경로 무변경 보장이 배포 게이트.

### P-FG3. 문서·구현 불일치 해소

절대 기준 매트릭스의 "Phase 4 이중 검증"을 **실제 구현**(P-FG1을 Phase 4 이후 호출)으로 충족시키고, "FORM 663" → "전 시트 1,555 수식(FORM 694·Mileage 817·Receipt 44, 허가/승인 제외)"으로 정정.

### P-FG4. (선택, 2차) 정적 내용 보존

PRD "그 외 cell **내용** 일체 변경 금지"의 완전 준수 — ORG가 수식이 아닌 cell도 비-승인 변경 검출. 단 Receipt는 동적 영역이 많아 false-positive 위험 → cell-mapping allowlist 기반으로만 적용, 1차(P-FG1~3) 안정화 후 별도 판단.

---

## P-FG4 착수 검토 (2026-05-16, 실증 기반)

P-FG4의 최대 우려는 두 가지였다 — (a) Receipt 동적영역 false-positive, (b) openpyxl 라운드트립 표현 노이즈. **둘 다 실측으로 정량 평가했고, 결론은 P-FG4가 계획 당시 우려보다 명백히 안전하다는 것이다.**

### 실측 결과

| 항목 | FORM | Receipt | Mileage log | 합계 |
|------|-----:|--------:|------------:|-----:|
| ORG 정적 내용 셀(비-수식 비-빈) | 221 | 87 | 150 | **458** |
| 주 타입 | str 215 | str 86 | str 90·int 60 | 대부분 라벨/헤더 |
| **라운드트립 노이즈(load→save→reload 비-수식 변화)** | **0** | **0** | **0** | **0** |

핵심 함의:
1. **노이즈 바닥 = 0**: openpyxl 왕복이 비-수식 내용을 일절 변형하지 않는다(수식만 손상 — 그건 P-FG1이 이미 담당). 우려 (b) **완전 소거**. 즉 P-FG4 단순 값 비교는 표현 노이즈로 false-positive를 내지 않는다.
2. **보호 대상 = 458개로 작고 안정적**: 대부분 템플릿 라벨/헤더 문자열. 파이프라인은 *데이터*(금액·이름·날짜)를 **빈 데이터 셀**에 쓰지 이 458개 라벨을 건드리지 않는다 → 우려 (a)도 실질 위험 낮음. Receipt 정적 셀은 87개(섹션 헤더 류)뿐, 데이터는 20,009개 빈 셀에 기록됨.
3. P-FG1과 **동일 아키텍처 재사용 가능**: "ORG가 비-수식 내용인 셀이 승인(FORM=PRD-86 / Receipt·Mileage=cell-mapping) 외에서 변경 → 위반". `is_formula` 필터만 반전.

### 2계층 설계 권고

| 계층 | 정의 | 위험 | 권고 |
|------|------|------|------|
| **P-FG4a 정적 내용 보존** | ORG 비-수식 **내용 셀 458개**가 승인 외 변경 시 위반 | 낮음(노이즈 0, 라벨은 파이프라인이 안 씀) | **착수 권장** — PRD "내용 일체 변경 금지"의 직접 충족 |
| **P-FG4b 부유 write 탐지** | ORG **빈 셀**이 승인 외에서 비게 됨→값 채워짐 시 위반 | 중(allowlist 100% 완전성 필요 — write~41 vs logged~35+6, 갭 가능) | **경고(warning, 비차단)로 시작** 또는 보류. cell-mapping 완전성 감사 후 hard화 |

근거: PRD는 "내용 일체 변경 금지"라 P-FG4b까지가 완전 준수이나, 빈 셀 20k(Receipt) 대상 + cell-mapping 로깅 완전성 미입증 상태에서 hard-block하면 정상 실행을 오탐할 수 있다. P-FG4a는 노이즈 0·대상 458·라벨 불변이라 즉시 안전. **단계적: P-FG4a 차단 게이트로, P-FG4b는 동일 게이트의 warning 채널로 동시 도입(차단 아님) → 운용 데이터로 cell-mapping 완전성 확인 후 P-FG4b를 hard화.**

### 구현 방식 (P-FG1 확장 — 신규 파일 불요)

`verify_formula_integrity.py`를 `verify_cell_integrity.py`로 일반화(또는 옵션 `--include-static`): ORG 순회 시 수식 셀 → 기존 위반 로직, 비-수식 내용 셀 → P-FG4a 위반 로직, ORG 빈 셀 & 최종 비-빈 & 비승인 → P-FG4b warning. SOT(`prd_form_writable`/`_norm_col`) 그대로 재사용. 회귀: 라운드트립 0 재확인 + 라벨 1개 변조→P-FG4a FAIL + 비승인 빈셀 채움→P-FG4b warning + 정상 cell-mapping write→무탐지.

### 잔여 한계

P-FG4b를 warning으로 시작하면 *비차단* 부유 write는 통과한다(운용 후 hard화 전까지). 또한 ORG 빈 셀에 대한 cell-mapping 완전성은 P-FG4b 도입과 함께 별도 감사 권장(write_excel의 모든 `.value=`가 operations에 로깅되는지 — 현재 ~41 vs ~41 근사이나 미입증).

---

## 3. 실행 순서·게이트·회귀

```
P-FG1 verify_formula_integrity.py 신규 ─┐
P-FG2 check_and_restore 일반화 ────────┼─→ 회귀(아래) → P-FG3 문서/호출 배선
                                        │
회귀 게이트(배포 전 필수):
  (1) ORG vs ORG → violation 0 (clean baseline)
  (2) FORM/Receipt/Mileage 각각 비-허가 수식 1개 변조 사본 → 각 exit 1 핀포인트
  (3) PRD-86 허가 cell 기록 → 미플래그
  (4) cell-mapping 승인 write → 미플래그 / 승인됐어도 ORG-수식 cell이면 → 위반
  (5) P-FG2: Mileage 빈-수식 손실 모사 → 복원됨, FORM 경로 byte-identical
```

- **독립성**: P-FG1은 읽기 전용·추가 — 기존 파이프라인 동작 불변(절대 기준 2). P-FG2만 기존 함수 손대므로 (5) FORM byte-identical이 필수 게이트.
- **D-7 동기화**: `wk.md`(phase admin·secretary final_verifier·실행 순서), `WK_workflow.md`(절대 기준 매트릭스·post-pipeline·일괄 스크립트), `DECISION-LOG.md` ADR-046.

---

## 4. 절대 기준 정합성

- **기준 1(품질)**: 무방비 861 수식을 차단 게이트로 봉쇄 — 비용 무시.
- **기준 2(SOT)**: ORG가 수식 SOT, cell-mapping이 승인-write SOT. 검증 게이트는 읽기 전용(쓰기 없음). 복원 로직 중복 금지 — P-FG2는 기존 함수 일반화(재구현 아님).
- **기준 3(CCP)**: 각 계층 의도·파급·변경설계 명시. P-FG2(기존 함수 변경)는 FORM byte-identical 회귀를 배포 게이트로 강제.

---

## 5. 권고

P-FG1(검증 게이트)+P-FG2(범위 확장)+P-FG3(문서 정합)을 1차로 함께 착수 권장. 이는 **사용자가 지적한 할루시네이션의 주 무대(Mileage 817·Receipt 44)를 처음으로 방어 범위에 넣고**, 자가치유가 놓친 위반을 차단·표면화하는 결정론 게이트를 신설한다. P-FG4(정적 내용)는 1차 안정화 후 별도 판단.

> 착수 여부 / P-FG4 포함 여부 지시를 요청한다.
