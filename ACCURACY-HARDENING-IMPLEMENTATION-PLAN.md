# 정확성 강화 — 구체적 실행 계획 보고서

작성일: 2026-05-16
근거 보고서: `PYTHON-CONVERSION-FEASIBILITY-REPORT.md` §6 권고
적용 원칙: 절대 기준 1(품질 최우선) · 절대 기준 2(SOT) · 절대 기준 3(CCP — 의도·파급·변경설계)
조사 깊이: 4개 핵심 파일의 정확한 수정 지점을 코드 라인 단위로 확정

> **구현 상태 (2026-05-16 갱신)**: ✅ **P0-1·P1-1·P0-2·P1-2 전부 구현·회귀 완료** (ADR-041~044).
> 전 게이트 PASS: P0-2 scaffold-equivalence 12/12, P0-1 bbox guard, P1-1 toll integrity,
> P1-2 dual-read consistency. 잔여 개선 영역은 §6 P2(디지털 영수증 Python OCR 하이브리드)뿐.

---

## 0. 요약 — 4개 작업, 2개 트랙

| ID | 작업 | 트랙 | 데이터 계약 변경 | 사용자 승인 | 정확성 효과 |
|----|------|------|:---:|:---:|---|
| **P0-1** | bbox sanity-check 결정론 가드 | A (즉시) | 없음 | 불필요 | WK09형 bbox 과다 오류 차단 |
| **P1-1** | 톨 산술 무결성 검증 스크립트 | A (즉시) | 없음 | 불필요 | 톨 검증 사각지대(현재 0건) 봉쇄 |
| **P0-2** | OCR 출력 스키마 축소 (Python 파생) | B (계약변경) | **있음** | **필수** | LLM 오류 표면적 구조적 축소 |
| **P1-2** | 이중 판독 self-consistency | B (계약변경) | 실행모델 | 권장 | silent misread 결정론적 표면화 |

> **결정적 발견**: `write_excel.py:622-633`은 LLM이 보낸 `meal_type`을 **이미 무시하고 시각으로 재계산**한다. 톨 배치(`:560-598`)도 LLM `direction`이 아닌 시각 순서로 동작한다. 즉 LLM이 채우는 여러 필드가 **이미 사용되지 않거나 Python으로 재계산 가능**하다. P0-2는 새 로직 발명이 아니라 **이미 존재하는 결정론을 공식화하고 LLM 입력에서 제거**하는 작업이다.

실행 순서: **P0-1 → P1-1 → (사용자 승인) → P0-2 → P1-2**. 트랙 A는 계약 변경이 없어 즉시 착수 가능, 트랙 B는 LLM 데이터 계약을 바꾸므로 절대 기준 3에 의해 사전 승인 필수.

---

## P0-1. bbox Sanity-Check 결정론 가드

### Step 1 — 의도
LLM(Step 6)이 영수증당 정해진 개수의 bbox만 생성해야 하나, 규칙이 프롬프트(`wk.md:174-182`, `WK_workflow.md:197-210`)에만 존재하고 **코드 가드가 없다.** MEMORY 기록상 WK09에서 실제로 83개(정상 ~29개) 과다 생성 발생. 목적: 버그 차단(품질). 제약: 기존 정상 케이스 회귀 없음, hardcoded fallback 하위 호환.

### Step 2 — 영향 범위 분석 (Ripple)
- **수정 진입점**: `annotate_receipts.py:main()` — annotations 로드 직후(`:697` 이후, preview/inject 분기 `:699` 이전).
- **데이터 흐름**: `_load_annotations_json()`(`:629-655`)는 `{img: [(x1,y1,x2,y2)...]}`만 반환 — **섹션/라벨 정보 소실**. 가드는 섹션별 규칙이 필요 → 시그니처 변경(고-파급) 대신 `research/annotations/wk{n}-template.json`을 재오픈하여 이미지→섹션 매핑 획득(저-파급). 키 정합성: `generate_annotations.py`가 만든 template의 이미지 키 == LLM이 채운 `wk{n}.json` 키 (동일 template 파생이므로 정합 보장).
- **fallback 경로**(`:684-688`, hardcoded WK06-09): 가드 적용하되 레거시이므로 hard-fail 대신 warning.
- **교차 검증 소스**: `research/ocr-results.json`의 `toll_history` distinct date 수 = TOLLS 섹션 bbox 상한 근거로 활용 가능.
- **문서 파급**: `WK_workflow.md` Step 6/Phase3, `wk.md:203-206` phase3_admin 체크리스트, `DECISION-LOG.md`(ADR 추가).
- **테스트 인프라**: 프로젝트에 `tests/` 부재. `research/wk08_backup`, `research/wk09_backup` 실데이터를 픽스처로 사용하는 `--check-only` 모드 동봉.
- 강결합/샷건 서저리 위험: **없음** (단일 함수 추가 + main 1지점 호출).

### Step 3 — 변경 설계
1. `annotate_receipts.py`에 신규 함수 추가:
   ```python
   def _validate_bbox_counts(annotations, week, base_dir, hard=True):
       """Deterministic bbox sanity-check. Returns (ok: bool, violations: list[str])."""
   ```
   규칙 (섹션은 template json에서 매핑):
   - DINNER / STAFF / TRAVEL / PARKING 영수증 이미지: bbox **정확히 2개** (≠2 → violation)
   - TELEPHONE: **4개**
   - TOLLS: ≤ `ocr-results.json` toll_history distinct date 수 (초과 → violation)
   - 전역 하드 상한: 총 bbox > 80 → 즉시 FAIL
   - 기대 범위 경고: 총 bbox ∉ [20, 45] → warning(차단 아님)
   - 로고/소형 이미지: `generate_annotations.py`가 `w<200 or h<100` 필터하므로 annotations에 비존재 — 존재 시 violation
2. `main()` `:697` 직후 호출:
   - JSON 경로(`_load_annotations_json` 성공): `hard=True`. violation 시 `print("ERROR: bbox sanity-check FAILED ...")` + `sys.exit(1)` (기존 에러 관례 `:680,:693`과 동일 → supervisor가 Step 6 재실행 트리거).
   - hardcoded fallback 경로: `hard=False` (warning만).
   - `--force` 플래그로 우회 가능(엣지 케이스 대비).
3. `--check-only WKnn_2026` 모드: inject 없이 가드만 실행 + 결과 출력 (CI/회귀용). `wk08_backup`/`wk09_backup`으로 자기 검증.
4. 문서 동기화: `wk.md` phase3_admin에 "P0 결정론 가드 통과(`--check-only`)" 항목 추가, `WK_workflow.md` Step 6에 가드 명시, `DECISION-LOG.md`에 ADR.

**검증**: WK09 과다(83개) 픽스처 → FAIL 재현 / WK08 정상 → PASS 확인. 회귀: 기존 wk08/wk09 정상 annotations로 false-positive 0건.
**롤백**: 함수 + 호출 2줄 제거로 완전 원복(부수효과 없음).
**작업량**: 함수 ~60줄 + main 호출 ~6줄 + 문서 3곳. 위험 낮음.

---

## P1-1. 톨 산술 무결성 검증 스크립트 (신규)

### Step 1 — 의도
`verify_card_matching.py:8-10`에 의해 **TOLLS·TELEPHONE은 카드 대조에서 명시적으로 제외** — 가장 기준이 되는 톨 금액에 결정론적 검증이 **0건**이다. 목적: 톨 OCR 결과의 내부 산술·논리 무결성을 결정론적으로 검사하여 silent misread를 표면화(품질). 제약: 카드 대조 로직 불간섭(단일 책임 분리).

### Step 2 — 영향 범위 분석
- 프로젝트는 관심사별 독립 validator 패턴 보유(`validate_pacs/review/translation/verification.py`). 톨 검증을 `verify_card_matching.py`에 끼우면 "TOLLS 제외" 단일 책임 위배 → **신규 독립 스크립트** `scripts/verify_toll_integrity.py`가 패턴 정합.
- 입력: `research/ocr-results.json` (`parking_tolls.toll_history`), 필요 시 PRD §16 거리 규칙(이미 `write_excel.py:get_distance:993-1011`에 존재 → import 재사용으로 SOT 단일화, 절대 기준 2).
- 출력: 콘솔 + JSON(`research/toll-integrity-report.json`), exit 0/1 (기존 관례 정합).
- 파급: `WK_workflow.md` Post-Pipeline, `wk.md:249-269` 카드 대조 섹션 뒤, 일괄 스크립트(`WK_workflow.md:343`), `DECISION-LOG.md` ADR. **코드 강결합 없음(신규 파일, 읽기 전용 소비)**.

### Step 3 — 변경 설계
1. `scripts/verify_toll_integrity.py` 신규. 검사 항목(전부 결정론):
   - **T-1 동일 구간 금액 일관성**: 동일 `(entry, exit)` 구간의 금액이 주중 상이하면 이상치 플래그 (예: 수원신갈→기흥동탄 4일은 960, 1일만 900 → 900 의심 misread).
   - **T-2 go/back 페어링**: 근무일(weekday_mapping 범위)에 go만 있고 back 없으면 경고(휴가/조퇴 가능 → warning).
   - **T-3 금액 0 검사**: `amount==0`인데 stopover 아닌 정상 구간 → violation.
   - **T-4 거리 규칙 정합**: 각 톨의 entry/exit가 PRD §16 (1)-(6) 규칙에 매핑 불가하면 경고(미등록 게이트명 = OCR 지명 오인 가능).
   - **T-5 일요일 정합**: `sunday_date`가 toll 최초 거래일 **이후** 6일 이내 일요일인가 (PRD §2-§4) — 위반 시 FAIL.
   - **T-6 시각 단조성**: 동일 날짜 toll들의 시각이 정렬 후 중복/역전이면 경고.
2. 심각도 2단계: `violation`(exit 1, FAIL 리포트) / `warning`(exit 0, 콘솔 경고).
3. 호출 위치: `wk.md` secretary2(`:254`) 직후 secretary2.5로 추가, `WK_workflow.md` Post-Pipeline 표에 행 추가, 일괄 스크립트에 라인 추가.
4. `get_distance` 재사용: `from write_excel import get_distance` (Step 7가 이미 동일 import 패턴 사용 → 관례 정합, SOT 단일).

**검증**: wk09_backup ocr-results.json으로 실행 — 알려진 값 PASS. 인위적 960→900 변조 픽스처로 T-1 FAIL 재현.
**롤백**: 신규 파일 삭제 + 호출 1줄 제거. 부수효과 0.
**작업량**: ~120줄 신규 + 문서 3곳. 위험 낮음(읽기 전용, 추가적).

---

## P0-2. OCR 출력 스키마 축소 — Python 파생 (계약 변경, 승인 필수)

### Step 1 — 의도
LLM이 채우지만 **이미 무시되거나 단일 입력에서 결정론적으로 파생 가능**한 필드를 LLM 책임에서 제거하여, LLM이 틀릴 수 있는 항목 수 자체를 구조적으로 축소(품질). 제약: `write_excel.py`/`verify_*` 출력 동일, 하위 호환(구 스키마 ocr-results.json도 동작).

### Step 2 — 영향 범위 분석 (대규모 — 데이터 계약 변경)
근거 코드로 확정한 "축소 가능 필드":

| 필드 | 현재 LLM이 채움 | 실제 사용 현황 (코드 근거) | 처리 |
|------|:---:|---|------|
| `meal_type` (dinner) | O | **미사용** — `write_excel.py:622-633`이 시각으로 재계산 | 스키마/프롬프트에서 **제거** |
| `weekday_mapping` | O | `date_to_day`(`:31-34`)가 사용. **단 sunday_date에서 100% 파생 가능** | Python 파생 (LLM 제거) |
| `sunday_date` | O | FORM K8. **toll 최초 거래일에서 파생 가능** (PRD §2-§4) | Python 파생 |
| `week_number` | O | FORM G2. `= ISO_week(sunday_date)` | Python 파생 |
| `direction` (toll) | O | 배치는 시각순(`:560-598`), 거리는 entry/exit(`get_distance`). **미사용** | 스키마/프롬프트에서 제거(또는 Python 파생, 검증용) |

→ LLM의 본질 책임은 **`toll_history`(date/time/amount/entry/exit) + dinner/staff/travel(date/time/amount/headcount) + telephone(payment_amount, month_matches)** 의 *순수 판독*으로 축소. 날짜 스캐폴드 전체(sunday/week/weekday_mapping)는 단일 anchor(toll 최초일)에서 Python이 산출.

**파급 (절대 기준 2 — SOT 위반 위험 지점)**:
- OCR 스키마가 **3개 프롬프트 파일에 중복**: `WK_workflow.md:125-141`, `wk.md:103-115`, `wk.md:120`(phase1_admin "필수 키 7개"). 이는 D-7형 의도적 중복 → **세 곳 동시 수정 필수**, cross-reference 주석 명기.
- `write_excel.py`: 신규 `derive_date_scaffold(ocr) -> ocr'` 추가, `load_data()`(`:23-28`) 직후 호출하여 scaffold를 Python 산출값으로 **덮어씀**(있으면 무시, 없으면 생성 → 하위 호환). `toll_history` 비면 fallback: 기존 제공값 유지.
- `verify_card_matching.py:34-36`(`weekday_mapping` col→date 사용, `:130`)·신규 `verify_toll_integrity.py`(T-5): 동일 scaffold를 써야 정합 → `from write_excel import derive_date_scaffold`로 **단일 SOT**(Step 7의 import 관례 재사용).
- `wk.md:120` phase1_admin "필수 키 7개" → LLM 필수 키 축소판으로 갱신. `wk.md:234-235` final_verifier가 `ocr-results.json`의 sunday_date/week_number 참조 → Python 파생값 기준으로 변경. 결정론 감사 위해 `write_excel.py`가 `planning/date-scaffold.json`(파생 근거: anchor date, 산출 sunday/week/weekday_mapping) 출력 → verifier·secretary2가 이를 참조.
- `research/wk**_ocr-results.json` 백업(`wk.md:354`): 구 스키마 백업 다수 존재 → `derive_date_scaffold`의 하위 호환(구 스키마도 동작)이 회귀 방어.

### Step 3 — 변경 설계 (순서 = 의존성 전파)
1. **`write_excel.py`**: `derive_date_scaffold(ocr)` 추가 — 알고리즘:
   - `anchor = min(t["date"] for t in toll_history)` (없으면 dinner/staff/travel 최소일)
   - `sunday_date = anchor + (6 - weekday(anchor)) days` (anchor 이후 첫 일요일, PRD §2-§4)
   - `monday..friday = sunday_date - 6 .. -2`; `weekday_mapping` 구성
   - `week_number = sunday_date.isocalendar()[1]` (기존 N8 규칙과 정합 확인 후 확정)
   - 반환 ocr에 scaffold 덮어쓰기 + `planning/date-scaffold.json` 기록.
   `load_data()` 호출부에서 `ocr = derive_date_scaffold(ocr)` 적용.
2. **`verify_card_matching.py` / `verify_toll_integrity.py`**: 동일 함수 import하여 scaffold 통일.
3. **프롬프트 3곳 동시 수정** (`WK_workflow.md`, `wk.md` 스키마+admin, cross-ref 주석): LLM 스키마에서 `meal_type`·`direction`·`sunday_date`·`week_number`·`weekday_mapping` 제거. Step 3 지시문에 "날짜 스캐폴드는 Python이 toll 최초 거래일에서 산출하므로 LLM은 toll 거래의 date/time/amount/entry/exit만 정확히 판독" 명시.
4. **`DECISION-LOG.md`**: ADR — 스키마 축소 근거 + 3-파일 의도적 중복(D-7) 동기화 규칙.
5. **하위 호환 검증**: `wk08_backup`/`wk09_backup`(구 스키마) → `derive_date_scaffold` 통과 후 `write_excel` 산출물이 변경 전과 **byte-동일**한지 회귀(가장 중요한 게이트).

**검증**: (a) wk08/wk09 backup으로 신·구 경로 산출 Excel diff = 0. (b) sunday_date 의도적 오류 백업 → Python 파생이 교정. (c) 3개 프롬프트 스키마 일치 grep 검사.
**롤백**: `derive_date_scaffold` 호출 1줄 주석처리 시 구 동작 복귀(함수는 순수, 부수효과는 audit json 생성뿐). 프롬프트는 git revert.
**작업량**: 함수 ~50줄 + import 2곳 + 프롬프트 3파일 + ADR. **위험 중간 — 데이터 계약 변경이므로 (b) 회귀 게이트 통과 전 배포 금지. 절대 기준 3: 사용자 사전 승인 필수.**

---

## P1-2. 이중 판독 Self-Consistency (계약/실행모델 변경, 설계만 — 선택)

### Step 1 — 의도
구겨진 감열지 영수증의 silent misread는 단일 판독으로 검출 불가. LLM이 각 영수증을 **독립 2회 판독** → Python이 숫자 필드 차분 → 불일치만 재판독. 절대 기준 1(품질) 근거로 토큰/시간 비용 무시.

### Step 2 — 영향 범위 (실행 모델 변경)
- `wk.md` Step 3(`:96-115`): 1회 → 2회 독립 판독(이상적으로 별도 컨텍스트). 산출 `ocr-results.json` + `ocr-results-2.json`.
- 신규 `scripts/verify_ocr_consistency.py`: 두 파일의 amount/date/time/headcount/payment_amount diff → 불일치 (image, field, v1, v2) 리포트, exit 0/1.
- phase1_admin(`wk.md:117-124`)에 일관성 게이트 추가. P0-2 적용 후라면 비교 대상이 축소된 핵심 필드뿐이라 잡음 감소(P0-2 선행 권장).
- 비용: LLM 판독 1회 추가 — 절대 기준 1에 의해 허용.

### Step 3 — 변경 설계 (요지)
- 2-pass 산출 → `verify_ocr_consistency.py` diff(허용오차 0, 금액/날짜는 완전 일치 요구) → 불일치 시 해당 이미지만 3차 판독·다수결 또는 사용자 에스컬레이션(최대 2회 후 에스컬레이션, AGENTS.md 재시도 관례 정합).
- 본 보고서에서는 **설계까지만 제출**, 구현은 P0/P1-1 안정화 후 사용자 판단으로 착수.

---

## 시퀀싱 · 의존성 · 게이트

```
트랙 A (즉시, 계약변경 없음)
  P0-1 bbox 가드 ──┐
  P1-1 톨 무결성 ──┴─→ 회귀(wk08/wk09 backup) PASS → 배포

────── 사용자 승인 게이트 (절대 기준 3, P0-2 계약변경) ──────

트랙 B (승인 후)
  P0-2 스키마 축소 ─→ 하위호환 회귀(diff=0) PASS → 배포
        │
        └─→ P1-2 이중판독 (P0-2 선행 시 잡음 최소 — 권장 순서)
```

- **P0-1·P1-1은 상호 독립**, 병렬 작업 가능, 데이터 계약 불변 → 즉시 착수 가능.
- **P0-2는 P1-1과 `get_distance`/scaffold SOT를 공유**하므로 P1-1 먼저가 통합 단순.
- **P1-2는 P0-2 이후**가 diff 잡음 최소(축소된 필드만 비교).
- 공통 회귀 자산: `research/wk08_backup`, `research/wk09_backup` (실데이터, 추가 픽스처 불필요).

---

## 절대 기준 정합성 점검

- **절대 기준 1(품질)**: 4개 작업 모두 비용/속도가 아닌 정확성을 목적으로 함. P1-2는 명시적으로 비용 무시.
- **절대 기준 2(SOT)**: `get_distance`·`derive_date_scaffold`를 `write_excel.py` 단일 정의 후 import 공유(중복 정의 금지). OCR 스키마의 3-파일 중복은 D-7 의도적 중복으로 격상하고 cross-ref 주석 + ADR로 동기화 강제.
- **절대 기준 3(CCP)**: 각 작업에 의도·파급·변경설계 3단계 명시. P0-2(대규모, 계약변경)는 사용자 사전 승인 게이트를 명시적으로 배치.

---

## 권고

트랙 A(P0-1, P1-1)는 위험이 낮고 계약 변경이 없으며 정확성 효과가 즉시적이므로 **선승인 없이 착수 권장**한다. 트랙 B(P0-2)는 LLM 데이터 계약을 바꾸므로 본 계획 승인 후 진행하되, **하위 호환 회귀(wk08/wk09 backup 산출물 byte-diff = 0)를 배포 전 필수 게이트**로 둔다. P1-2는 트랙 B 안정화 후 별도 판단.

> 다음 행동: 트랙 A 착수 승인 여부, 그리고 P0-2 계약 변경 승인 여부를 지시해 주십시오.
