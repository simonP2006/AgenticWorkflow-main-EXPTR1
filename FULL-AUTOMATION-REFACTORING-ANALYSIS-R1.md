# EXPTR1 완전자동화 Refactoring — 분석 보고서 (Round 1)

작성일: 2026-06-19
작성: EXPTR1 refactoring 워커 (명령6)
원칙: 절대 기준 1(품질) · 2(SOT) · 3(CCP) + ②-3(현실적 역량평가·과장금지)
방법: 선행분석 6개 문서 정독 → 실제 코드 grep 검증 → 실데이터(14주 OCR·118건) 정량 분석

> **이 문서는 분석 산출물이다. 코드·DB 변경(build)은 master 검증·승인 후 착수한다.**

---

## 0. Executive Summary

1. **선행분석은 정확하고 근거 기반이다 (할루시네이션 없음).** 6개 보고서가 주장한 함수·ADR·스크립트가 실제 코드에 모두 존재함을 grep으로 확인했다. 단 1건의 staleness만 발견: CODE-VS-PROMPT 보고서의 "scripts/ 7개·3,560줄"은 hardening ADR(041~047) 이후 **11개·4,764줄**로 증가 → 보고서가 hardening 이전 시점.

2. **파이프라인 9단계 중 LLM 의존은 정확히 2개**(Step 3 OCR, Step 6 bbox). 나머지 7개는 이미 완전 결정론 Python. 이것은 PYTHON-CONVERSION 보고서의 핵심 결론이며, 코드로 재검증 완료.

3. **핵심 발견 (Goal 1) — "sub-agent"의 정체**: WK 파이프라인의 ~18개 에이전트(orchestrator·supervisor×4·admin×4·secretary×3·final_verifier·실행 sub-agent 7)는 **별도 agent 파일로 존재하지 않는다.** `.claude/agents/`엔 generic 3개(translator/reviewer/fact-checker)뿐이고, WK 에이전트는 `wk.md`가 런타임에 TeamCreate로 생성하는 일회성 멤버다. 그리고 이들 18개 중 **16개는 결정론 스크립트 실행 또는 결정론적 검증 체크리스트**이며 — **진짜 LLM 판단이 필요한 것은 2개(OCR·bbox)뿐이다.**

4. **대체 가능성 판정**: 18개 에이전트 중 **16개를 deterministic Python(+얇은 harness)으로 대체 가능하고, 대체하는 것이 품질상 우월하다.** 근거: LLM "검증자"는 PASS를 환각할 수 있으나(프로젝트가 P1으로 봉쇄하려는 바로 그 위험), Python assertion은 환각하지 않는다. 즉 검증 에이전트의 Python화는 "비용 절감"이 아니라 **할루시네이션 봉쇄(절대 기준 1)의 직접 강화**다.

5. **Goal 2 현실 평가 (②-3)**: "영수증 DB+자기학습 cell섹터 배치"는 **frequency-table 분류기 + fuzzy 정규화 + 신뢰도 게이트 escalation**으로 구현 가능하다 — "AI가 영수증을 학습한다"식 과장이 아니다. 실데이터 근거: 45개 store 중 **76%는 store명만으로 섹터 결정(deterministic)**, **24%(커피체인)는 시간대도 겹쳐 결정론 분류 불가 → LLM/human escalation 필수**. 자기학습 = 매주 검증된 산출물을 DB에 단조 누적(monotonic). 정직한 상한선이 분명히 존재한다.

---

## 1. 분석 범위 & 선행분석 검증 결과

### 1.1 정독·검증한 자산

| 자산 | 검증 방법 | 결과 |
|------|----------|------|
| CODE-VS-PROMPT-RATIO-REPORT | line/word/byte 재측정 | ✅ 정확, 1건 stale(7→11 스크립트) |
| PYTHON-CONVERSION-FEASIBILITY | 9단계 LLM/Python 분류 재확인 | ✅ 정확 |
| ACCURACY-HARDENING-PLAN (P0-1·P1-1·P0-2·P1-2) | 함수 grep | ✅ 전부 구현됨 |
| MULTI-READ-VOTING-EVALUATION (ADR-045) | `aggregate_ocr_votes.py` 로직 확인 | ✅ CONSENSUS/INCONCLUSIVE/FAIL exit 0/2/1 구현 |
| FORMULA-INTEGRITY-HARDENING (P-FG1~4) | `verify_formula_integrity.py`·`check_and_restore_all_sheets` 확인 | ✅ 구현됨 |
| DECISION-LOG | ADR 인덱스 | ✅ ADR-001~047, WK=041~047이 최신 |

### 1.2 코드로 확인한 핵심 함수 (할루시네이션 검사 통과)

`write_excel.py`: `derive_date_scaffold`(:42), `check_and_restore_all_sheets`(:1269), `check_and_restore_formulas`(:1182), `prd_form_writable`(:1153), `get_distance`(:1132), `_match_images_to_days_by_order`(:928) — **전부 실존**. `verify_toll_integrity.py`가 `get_distance`를 import(SOT 단일 — 절대 기준 2 준수) 확인.

**결론: 선행분석을 신뢰하고 그 위에 build한다. 재분석 낭비 없음.**

---

## 2. 파이프라인 전체 지도 (재검증)

```
Step 0  rm OCR ............... bash         [결정론]
Step 1  extract_images.py .... Python       [결정론]
Step 2  extract_card_data.py . Python       [결정론]
Step 3  OCR (N-read voting) .. 🔴 LLM Vision [비결정론] ← 유일 LLM #1
        → aggregate_ocr_votes.py ........... [결정론 게이트]
Step 4  write_excel.py --all . Python       [결정론] (셀 배치 100% Python)
Step 5  generate_annotations.py Python      [결정론]
Step 6  bbox 좌표 ............ 🔴 LLM Vision [비결정론] ← 유일 LLM #2
        → annotate_receipts --check-only ... [결정론 가드 P0-1]
Step 7  check_and_restore_all_sheets Python [결정론]
Step 8  annotate_receipts.py . Python(lxml) [결정론] ← 반드시 최종
Post    verify_card_matching / verify_toll_integrity / verify_formula_integrity [결정론×3]
```

**불변식**: 데이터를 "어느 셀에" 넣을지는 LLM이 단 한 번도 결정하지 않는다(write_excel 100% Python). LLM은 (a) 이미지→텍스트 판독, (b) bbox 픽셀 좌표 — 두 가지 vision 작업만 한다.

---

## 3. Sub-agent 대체구현 심층분석 (Goal 1 핵심)

### 3.1 18개 에이전트를 "실제 수행하는 판단"으로 분류

| Class | 에이전트 | 실제 하는 일 | 대체 후보 | 대체 시 품질 |
|-------|---------|------------|----------|------------|
| **A. 순수 기계실행** | image_extractor, card_data_extractor, excel_writer_base/post, annotation_generator, formula_restorer, rdr_injector, secretary0, secretary2, secretary2.5, secretary3 (10개) | 결정론 스크립트 1줄 호출 | **Python harness** (에이전트 래퍼 제거) | **동일+안정** (LLM 오보 표면 제거) |
| **B. 검증 체크리스트** | phase1~4_admin, final_verifier (5개) | 파일존재·키존재·값일치·exit0·셀비교 = 거의 전부 결정론 비교 | **통합 `verify_week.py`** (assertion) | **우월** (LLM PASS 환각 봉쇄 = P1 강화) |
| **C. 진짜 LLM vision** | ocr_preparer(Step3), bbox_detector(Step6) (2개) | 구겨진 감열지 한글 판독 / 1mm bbox | **Skill 또는 Worker** (Python 불가) | **유지** (전통 OCR은 silent misread로 악화) |
| **D. 오케스트레이션** | orchestrator, supervisor×4, secretary (6개, 일부 A/B와 중복) | 고정 순차 제어 + 오류 라우팅(누락=재실행/로직=중지) | **Python harness** (규칙 기반) | **동일** (순서·게이트가 결정론) |

> 합계가 18을 초과하는 것은 secretary류가 제어(D)와 검증실행(A/B)을 겸하기 때문. 핵심은 **판단이 필요 없는 16개 vs 진짜 LLM 2개**의 분리다.

### 3.2 판정: "기존 sub-agent를 skill/python/worker로 대체 가능한가?"

**가능하다. 그리고 대체가 품질상 우월하다.** 단 대체의 본질을 정확히 규정해야 한다(②-3):

- **Class A·D (16개 중 다수) → Python harness로 대체.** 이것은 "skill/worker로 변환"이 아니라 **에이전트 래퍼를 제거하고 결정론 파이프라인을 그대로 노출**하는 것이다. WK_workflow.md에 이미 적힌 `run_week.sh` 의사코드가 그 증거 — 사실상 harness가 설계상 이미 존재하나 파일로 구현되지 않았을 뿐이다.
- **Class B(검증 5개) → 통합 `verify_week.py`로 대체.** 프로젝트는 이미 이 패턴을 안다(`validate_pacs/review/translation/verification.py`). admin 체크리스트 항목 대부분이 결정론 비교이므로, LLM 검증자보다 Python assertion이 **엄격히 더 신뢰성 높다**. 이것이 가장 강력한 대체 근거 — 프로젝트 자신의 P1 철학(결정론 검증 > LLM 자기보고)과 정확히 일치.
- **Class C(OCR·bbox 2개) → 대체 불가, 단 재배치 가능.** Python OCR 전면교체는 PYTHON-CONVERSION이 입증한 대로 정확성을 **악화**시킨다(감열지 silent misread). 그러나 이 2개를 inline orchestrator 작업이 아니라 **재사용 가능한 skill**(PRD 규칙·스키마·N-read 프로토콜 내장) 또는 **전용 worker**(ADR-045 §6 독립성 요건을 별도 컨텍스트로 자연 충족)로 패키징하는 것은 가능하고 바람직하다.

### 3.3 목표 아키텍처 (Round 1 제안)

```
run_week.py  (결정론 harness = orchestrator+supervisor+secretary 대체)
  │  순차 실행 · exit code 게이트 · 오류 라우팅(규칙기반)
  ├─ Step 1-2  extract_*.py ................... [그대로]
  ├─ Step 3    [SKILL: wk-receipt-ocr] N-read → aggregate_ocr_votes.py(게이트)
  ├─ Step 4    write_excel.py --all ........... [그대로]
  ├─ Step 5    generate_annotations.py ........ [그대로]
  ├─ Step 6    [SKILL: wk-bbox-detect] → annotate --check-only(가드)
  ├─ Step 7    check_and_restore_all_sheets ... [그대로]
  ├─ Step 8    annotate_receipts.py ........... [그대로 · 최종]
  └─ verify_week.py  (admin×4 + final_verifier 통합 = 결정론 검증)
        └─ 기존 verify_card_matching/toll/formula 흡수 + 체크리스트 항목 assertion화
```

**효과**: LLM 표면을 "18개 에이전트(각각 환각 위험)"에서 **"2개 vision skill + 1개 얇은 harness(vision 실패만 해석)"**로 축소. 이는 절대 기준 1(품질=정확도)을 직접 끌어올린다.

---

## 4. Goal 2 Scoping — 영수증 DB + 자기학습 (데이터 근거, ②-3 정직 평가)

### 4.1 "cell섹터 배치"가 실제로 요구하는 것

현재 영수증의 cell 배치는 3요소: **(1) 섹션** {TOLLS/PARKING/DINNER/STAFF/TRAVEL/TELEPHONE} **(2) 요일 컬럼 (3) 1st/2nd 슬롯**.
- (2)요일·(3)슬롯은 **이미 결정론 자동화**됨(date→weekday→column, 시각순 — write_excel).
- (1)섹션만 **현재 사람이 수동 분류**한다 — 사람이 영수증 이미지를 Receipt 시트의 섹션별 행 영역에 붙여넣고, 시스템은 `generate_annotations.classify_section(from_row)`로 **행 위치를 읽어** 섹션을 안다.

**∴ Goal 2가 제거하려는 유일한 human 판단 = "섹션 분류(사전 정렬)"다.** 요일/슬롯은 손댈 필요 없다.

### 4.2 실데이터 정량 분석 (14주·118건·45 store)

| 발견 | 수치 | 함의 |
|------|------|------|
| Store명만으로 섹터 결정 (unambiguous) | **34/45 store (76%)** | Tier-1 lookup이 다수 케이스 즉시 해결 |
| 다중 섹터 출현 (ambiguous) | **11/45 store (24%)** | 커피체인(폴바셋·스타벅스·투썸)이 STAFF/TRAVEL/DINNER 혼재 |
| 시간대로 ambiguous 분리 가능? | **불가** | 폴바셋: travel=[8,9,12,13]시, staff=[8,10]시 → **겹침** |
| Store명 표기 분열 (OCR 변이) | 다수 | "폴바셋 삼성 DSR점" vs "삼성 **D5R**점"(S→5 오인식) → **fuzzy 정규화 필수** |

### 4.3 현실적 아키텍처: 신뢰도 3-tier 분류기 (자기학습 = DB 단조 누적)

```
[base DB 구축] 완성 Excel(WK06~20, ground truth) + wk*_ocr-results.json(보조) 파싱
   → store_db[정규화_store] = {섹션분포, 전형_headcount, 시간대, 금액대, 출현수}

[배치 시] 새 영수증 (store, time, amount, headcount):
   Tier-1  정규화 store가 단일 섹션만 → 자동 배치 (신뢰 高, ~76% store)
   Tier-2  ambiguous store → (headcount/금액/요일 보조특징) 시도하되, 데이터상 분리력 弱
            → 대부분 Tier-3로 escalation 권장 (과신 금지 — ②-3)
   Tier-3  unseen/ambiguous → 🔴 LLM-vision이 풍부한 맥락 판독 or human 확인
            → 확인 결과를 DB에 append (= 자기학습 루프)
```

### 4.4 정직한 상한선 (과장·몽상 차단 — ②-3)

- 이것은 **"frequency-table 분류기 + fuzzy 정규화 + 신뢰도 게이트"**이지 신경망·"영수증을 이해하는 AI"가 아니다. 데이터 규모 ~118건/15주 = small-data. 적정 기법은 lookup+nearest-neighbor 수준.
- "자기학습" = 매주 검증된 결과를 DB에 단조 누적 → coverage가 점진 증가. **모델 재학습이 아니다.**
- **24% ambiguous(커피체인)는 store+time으로 결정 불가가 데이터로 입증됨.** 이 부분은 LLM 또는 human escalation이 영구적으로 필요할 수 있다 — "완전 무인 100%"는 현 데이터로 보장 불가. 정직한 목표는 **"76%+ 자동 + 나머지 신뢰도 게이트 escalation"**.
- Goal 2는 LLM 표면을 1개(ambiguous 섹션 판단) 추가하지만, 76% 케이스의 human 사전정렬을 제거한다 — 순 효과는 human 노동 대폭 감소.

---

## 5. McKinsey급 Refactoring 전략 — Round 1 Draft

### 5.1 전략 원칙
1. **LLM 표면 최소화 = 정확도 최대화** (절대 기준 1). 대체의 목적은 비용이 아니라 환각 봉쇄.
2. **결정론 우월 영역은 전부 Python**, 환각 불가 영역(vision)만 LLM skill/worker.
3. **기존 자산 보존 + 흡수** — write_excel/verify_* 9개 스크립트는 검증된 SOT. 재작성 금지, harness로 감싸기.
4. **점진·가역** — 각 단계 백업 후 변경, 회귀 게이트(wk08/wk09 backup byte-diff) 필수.

### 5.2 단계적 로드맵 (제안 — master 승인 후 build)
- **R-A (Goal 1, 무위험)**: `run_week.py` harness + `verify_week.py` 통합 검증기 신설. 기존 스크립트 무수정, 에이전트 오케스트레이션을 결정론 harness로 대체. 회귀: WK09 재실행 결과가 현 산출물과 동일.
- **R-B (Goal 1, 계약무변)**: OCR·bbox를 skill로 패키징(`wk-receipt-ocr`, `wk-bbox-detect`). wk.md는 harness 호출로 단순화.
- **R-C (Goal 2, 신규)**: `build_store_db.py`(완성 Excel→DB) + `classify_section.py`(3-tier). base DB를 WK06~20으로 부트스트랩.
- **R-D (Goal 2, 통합)**: 분류기를 파이프라인에 결선 + 자기학습 append 루프 + escalation 게이트.

### 5.3 Round 1 자기평가 (최고전문가 관점) → Round 2 목표
**현 Round 1 점수 자가추정: ~70/100 (McKinsey급=90+).** 약점:
- (F-실현성) `run_week.py`/`verify_week.py`의 오류 라우팅·재시도·escalation 상태머신이 아직 추상적. Round 2에서 상태 전이도(state machine) 구체화 필요.
- (C-완결성) Goal 2 Tier-2의 "보조특징 분리력 약함"을 정량화만 했고 대안(예: 프로젝트·동행자 맥락, 카드 가맹점 코드 활용)을 미탐색. Round 2에서 추가 신호원 조사.
- (L-논리) forecasting/trend(문서지능·agentic 설계 트렌드) 반영이 미흡 — 전략 ANCHOR(a) 요구. Round 2에서 foresight-env-scan으로 자동화 트렌드 스캔 후 아키텍처에 반영.
- **Round 2 목표(+10%→~80)**: 상태머신 구체화 + Goal 2 추가신호원(카드 가맹점명/MCC, 영수증 자체 vision 섹션판단) 탐색 + 트렌드 반영.

---

## 6. 위험 · 가정 · master 결정 필요 사항

**가정**:
- A1. WK 에이전트는 wk.md 런타임 생성물이며 별도 파일 없음 (확인됨).
- A2. 완성 Excel(WK06~20)이 섹션분류 ground truth (directive 명시).
- A3. 현 산출물 품질은 신뢰 가능 baseline (WK09 SOT pacs 85~92).

**위험**:
- W1. harness화가 4계층 검증 의도를 희석할 우려 → verify_week.py가 admin 항목을 **빠짐없이** 흡수해야 함(회귀로 입증).
- W2. Goal 2 ambiguous 24%의 escalation 누락 시 오배치 → 신뢰도 게이트 hard화 필수.
- W3. skill 패키징이 ADR-045 독립성 요건을 깨면 N-read가 무의미화 → worker 격리 권장.

**master 결정 필요 (build 착수 전)**:
- Q1. 로드맵 R-A~R-D 순서/범위 승인 여부.
- Q2. Round 반복을 워커 단독 진행 vs gemini·codex 3자 변증 포함 진행.
- Q3. Goal 1(harness) 먼저 vs Goal 2(DB) 먼저 — 권장: **Goal 1 R-A 먼저**(무위험·즉시 품질이득·Goal 2의 실행 기반).

---

---

## 7. Round 1.5 증분 — 카드 데이터가 Goal 2의 핵심 신호원 (read-only 검증)

R1 §5.3에서 Round 2 과제로 지목한 "추가 신호원(카드 가맹점명/MCC)"을 즉시 검증했다. **카드승인내역(`card-approval-data.json`)은 가정보다 훨씬 풍부하다.** 각 레코드가 보유:

| 필드 | 예시 | Goal 2 활용 |
|------|------|------------|
| **사업자번호** | 폴바셋=`220-81-15770`, 투썸=`823-15-02706` | **결정론 merchant 고유키** — OCR store명 분열(DSR↔D5R) 우회 |
| **가맹점업종** | `커피전문점`·`제과점/아이스크림점`·`PG(온라인)` | **섹터-family prior** (unseen merchant 폴백) |
| 가맹점명·주소·부가세·가맹점번호 | `삼성전자 파리바게트 화성점` 등 | 보조 식별·감사 |

**R1 §4 수정 (정직 갱신)**:
- §4.2의 "store명 fuzzy 정규화 **필수**" → **격하**. 카드결제 영수증은 (date,amount) join(이미 `verify_card_matching.py`가 수행)으로 **사업자번호를 결정론적으로 획득** → fuzzy는 cash/미매칭 폴백으로만. 정규화 ceiling 대폭 상승.
- §4.3 Tier 구조 보강: Tier-1 키를 **OCR store명 → 사업자번호**로 교체. 업종을 Tier-2 폴백 prior로 추가.
- **단 핵심 한계는 불변(②-3)**: 24% ambiguity의 본질은 *동일 merchant(폴바셋 커피전문점)가 staff·travel·dinner 양쪽*이라는 **purpose ambiguity**이며, 사업자번호·업종이 같으므로 **카드데이터로도 해결 불가.** escalation(LLM 맥락판단/human)은 영구적으로 일부 잔존. "완전무인 100%"는 여전히 보장 불가 — 정직목표는 "사업자번호 join으로 정규화 ceiling↑ + purpose-ambiguous만 escalation".
- **제약**: 카드데이터는 TOLLS/TELEPHONE(별도카드)·현금영수증 미포함. join은 (date,amount) 기준 — 이미 파이프라인에 존재.

**효과**: Goal 2 자동분류율 추정 상한을 76%(store명)에서 **사업자번호 기반으로 상향**(정확한 수치는 전 주차 카드파일 파싱 후 확정 — build 단계). 단 purpose-ambiguous 잔존분은 escalation. → Round 2 정식 설계에 반영.

---

*Round 1(+1.5 증분) 끝 — master 독립검증 대기. build는 승인 후.*
