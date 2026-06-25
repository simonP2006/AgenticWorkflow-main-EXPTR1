# EXPTR1 완전자동화 Refactoring — 전략 보고서 (Round 2)

작성일: 2026-06-19 · EXPTR1 refactoring 워커 · ANCHOR(a) 재귀개선 라운드
원칙: 절대 기준 1·2·3 + ②-3(현실적 역량평가·과장금지)
선행: `FULL-AUTOMATION-REFACTORING-ANALYSIS-R1.md`(자가 70/100) · R-A 빌드·Gate-A 실증 · master 검증 로그
방법: R1을 **R-A에서 실측·검증된 사실**로 정련 → McKinsey 90+ 목표. 미검증 단정 금지(R-A에서 자가정정 학습 반영).

> **상태: 전략 산출물. R-B/R-C/R-D build는 master 검증 + gemini·codex 변증(§5) 경화 후 착수.**

---

## 0. R1 → R2 — 무엇이 바뀌었나 (실측 기반)

R1은 *가설+설계*였다(자가 70/100, 약점 F/C/L 명시). R2는 R-A에서 **실제로 빌드·실행·검증된 사실**로 그 약점을 닫는다.

| R1 약점 (자가 식별) | R1 상태 | R-A 실측 후 R2 상태 |
|--------------------|---------|---------------------|
| **F (실현성)**: run_week/verify_week 상태머신이 추상적 | 설계만 | ✅ **빌드·실증** — run_week.py(harness, exit-code 상태머신 MISSING/LOGIC/VISION) + verify_week.py(38→21 dedup assertion) 작성, Gate-A에서 S0→S8→V 코어런트 구동(WK21 sp=bbox=27·18 PASS), 16/18 sub-agent 대체 입증 |
| **C (완결성)**: Goal 2 ambiguous 24% 추가 신호원 미탐색 | 미탐색 | ✅ **카드 사업자번호=결정론 merchant키**(master GROUNDED 검증) + 업종(MCC급 prior) 확보 → R-C tier 설계 구체화 |
| **L (논리)**: forecasting/trend 반영 미흡 | 미반영 | ⚠ §6에서 2025-26 agentic/문서지능 트렌드 반영(지식기반). foresight-env-scan 전면가동은 별도 heavy 옵션 |
| **신규 통찰 (R-A 부산물)** | — | ✅ replay-OCR-gap·cell-mapping 완전성·doc-sync 3건 |

**핵심: R2는 더 이상 가설이 아니다.** Goal 1은 빌드·검증으로 닫혔고(R-A APPROVE), R2의 무게중심은 **검증된 사실 위에서 Goal 2(R-C/R-D)를 McKinsey급 엄밀성으로 설계**하는 데 있다.

---

## 1. R-A 학습 5건 — 전략에 내장 (master 지정 반영점)

### L1. Harness 검증 완료 → "결정론 우월" 가설이 실증됨
R1 §3.2의 "16개 에이전트 Python대체 가능+품질우월"은 가설이었다. R-A가 **실측으로 입증**: run_week가 파이프라인을 결정론적으로 구동하고, verify_week가 LLM 검증자의 PASS 환각을 assertion으로 봉쇄(Gate-A 18 PASS, 2 FAIL은 replay artifact를 *정확 적출*=anti-hallucination 작동). → **전략 함의: R-B/R-C/R-D도 동일 패턴(결정론 harness/검증 + 최소 LLM)을 따른다. "LLM 표면 최소화=정확도 최대화"가 검증된 설계 원칙으로 격상.**

### L2. Replay-OCR-gap → 자기학습 DB는 ground-truth에서만 build
Gate-A에서 canned OCR백업(≠원본 OCR)으로 replay 시 C34/C36 divergence 발생. **통찰: 과거 산출물의 research 아티팩트는 drift한다(주차별 ocr만 백업·cell-mapping은 최신주만).** → **전략 함의: R-C store DB는 (a) 완성 Excel(human-verified ground truth) 우선, (b) ocr 백업은 보조, (c) 어떤 replay·regression도 coherent 아티팩트 셋으로만 수행.** verify_week가 divergence를 잡으므로 garbage-in이 silent하게 들어가지 않음(절대기준 2 강화).

### L3. ★카드 사업자번호 = R-C 결정론 merchant 키 (R1.5, master GROUNDED 검증)
R1은 store명 fuzzy정규화를 "필수"로 봤다(노이즈: DSR↔D5R OCR변이). R-A에서 카드승인내역에 **사업자번호(고유 결정론 키)·가맹점업종(커피전문점/제과점=섹터-family prior)** 실재 확인. → **전략 함의: R-C의 1차 키를 OCR store명 → (date,amount) join→사업자번호로 교체.** OCR store명은 cash/미매칭 fallback으로 격하. 정규화 ceiling 대폭 상승. ★단 ②-3 불변: 동일 merchant(폴바셋)가 staff·travel 양쪽=purpose-ambiguity는 사업자번호·업종 동일이라 미해결 → escalation 영구 잔존, 100% 무인 보장불가.

### L4. cell-mapping 완전성 갭 (C36 실증)
Gate-A C36이 Receipt name-DB(H1004/G1005/H1005)에서 write가 cell-mapping에 미인가됨을 노출(replay 케이스였으나 근본은 FORMULA-INTEGRITY-PLAN이 "미입증"으로 남긴 P-FG4b cell-mapping 완전성). → **전략 함의: R-D 이전에 write_excel의 모든 `.value=` write가 cell-mapping operations에 로깅되는지 결정론 감사(audit) 추가 = P-FG4b를 warning→hard화 가능케 하는 선행조건.** R-C/R-D가 새 write를 추가하므로 이 완전성이 전제.

### L5. doc-sync = SOT 일관성 (절대기준 2)
R-A에서 wk.md를 harness로 단순화하며 WK_workflow.md doc-sync 완료. → **전략 함의: R-B/R-C/R-D 각 단계는 산출물뿐 아니라 SOT 문서(WK_workflow.md·CLAUDE.md·DECISION-LOG)를 동기 갱신 — 자식 시스템 DNA 유전(soul §0)과 정합.**

---

## 2. 정련된 목표 아키텍처 (Goal 1 닫힘 + Goal 2 상세)

```
[Goal 1 — R-A 완료·검증]
  run_week.py (harness) ─ S0..S8 결정론 구동 + exit-code 상태머신
    └ LLM vision 2점: S3 OCR(N-read 다수결) · S6 bbox
  verify_week.py ─ 38→21 dedup 결정론 assertion (구 admin+final_verifier)
  [R-B 예정] S3·S6를 재사용 skill(wk-receipt-ocr·wk-bbox-detect)로 패키징

[Goal 2 — R-C/R-D 설계]
  build_store_db.py (R-C) ─ 완성Excel(ground truth)+카드(사업자번호) → store_db
    store_db[사업자번호] = {섹션분포, 업종, 전형 headcount/금액/시간대, 출현수, 신뢰도}
  classify_section.py (R-C) ─ 3-tier 신뢰도 분류기
  [R-D] 분류기를 harness에 결선 + 검증된 주간결과 DB append(self-learning) + escalation 게이트
```

핵심: Goal 2는 **현재 human이 수행하는 유일한 판단(섹션 사전정렬)**을 대체한다(요일·슬롯은 이미 결정론). 그 외 파이프라인은 R-A로 이미 자동.

---

## 3. R-C 정밀 설계 — Store DB + 자기학습 (데이터 근거·②-3 정직)

### 3.1 DB 키 = 사업자번호 (L3) + fallback 계층
```
영수증 → (date, amount) → 카드 join 성공? 
  ├ YES → 사업자번호(결정론 merchant 고유키) + 업종  [Tier-1 신뢰 高]
  └ NO (cash/미매칭) → OCR store명 fuzzy정규화 + 시간대/금액 휴리스틱  [Tier-2 신뢰 中]
```

### 3.2 DB 스키마 (ground-truth build, L2)
```
store_db[사업자번호 | norm_store] = {
  merchant_name, 업종,
  section_dist: {DINNER: n, STAFF: n, TRAVEL: n, ...},   # 섹션 빈도
  typical: {headcount_range, amount_range, hour_range},
  occurrences: n, last_seen: WKxx,
  confidence: section_dist 최빈도/총합                     # 신뢰도 = 단일섹션 지배율
}
```
Build 소스 우선순위: 완성 Excel(WKxx, human-verified) > wk*_ocr-results.json 백업(보조).

### 3.3 분류기 — 3-tier 신뢰도 게이트 (R1 §4.3 정련)
| Tier | 조건 | 동작 |
|------|------|------|
| **T1 자동** | 사업자번호/norm_store가 단일섹션 지배(confidence ≥ θ_high, 예 0.9) | 자동 배치 + DB 강화 |
| **T2 보조** | 다중섹션이나 (업종+headcount+시간대+금액)로 분리 가능(margin ≥ θ_mid) | 자동 배치 + Decision Log 기록 |
| **T3 escalation** | ambiguous(폴바셋류 purpose-ambiguity) or unseen | 🔴 LLM-vision 맥락판단 or human 확인 → 결과 DB append |

### 3.4 자기학습 = 단조 누적 (과장 금지·②-3)
- "학습" = 매주 **검증된**(verify_week PASS) 산출물의 (사업자번호/store, section, headcount) 튜플을 store_db에 append → coverage·confidence 단조 증가. **모델 재학습 아님 = frequency-table 성장.**
- 정직한 상한: ambiguous 24%(R1 실측, 14주·118건·45store)의 purpose-ambiguity는 카드데이터로도 미해결(L3) → T3 escalation 영구 잔존. **목표는 "T1+T2 자동률↑ + T3 빠짐없는 escalation"이지 100% 무인이 아니다.**
- 측정가능 KPI(현실적): build 후 hold-out 주차로 자동분류 정확도/escalation율 측정. 과장된 "시장장악" 식 목표 금지.

### 3.5 R-C 위험
- 사업자번호 join은 카드결제분만 — TOLLS/TELEPHONE(별도카드)·현금은 fallback. → Tier-2 비중 측정 필요.
- 동일 브랜드 다른 사업자번호(폴바셋 본사PG 220-81-15770 vs 평택점 211-88-92541) → 키 정규화 규칙 필요(브랜드 롤업 옵션).

---

## 4. R-B 설계 — OCR/bbox skill화 (Goal 1 마무리)

- `wk-receipt-ocr` skill: PRD OCR 스키마(P0-2)·N-read 독립성 요건(ADR-045 §6)·§8-1 내장. harness S3 HALT 시 호출.
- `wk-bbox-detect` skill: PRD §20 bbox 규칙(섹션별 개수·로고제외)·P0-1 가드 연계 내장. harness S6 HALT 시 호출.
- 근거: 재사용성·버전관리·독립성(별도 컨텍스트=N-read 독립성 자연충족). worker 격리 옵션(autopilot/headless).
- 위험: skill 패키징이 ADR-045 독립성 깨면 N-read 무의미 → 별도 컨텍스트 보장 필수.

---

## 5. R-D 설계 — 통합 + self-learning 루프

1. classify_section.py를 harness 신규 stage(S2.5 or S3 전처리)로 결선 — 섹션 사전정렬 자동화.
2. verify_week PASS 산출물 → store_db append(자기학습, L2 ground-truth 원칙).
3. T3 escalation 게이트를 harness exit-code(VISION/HUMAN)로 표면화 — silent 오배치 금지.
4. **선행조건(L4)**: cell-mapping 완전성 audit 통과 후 P-FG4b hard화.

---

## 6. 자동화·Agentic·문서지능 트렌드 반영 (forecasting ANCHOR a, ②-3 현실적)

지식기반(cutoff 2026-01) 트렌드 → 본 아키텍처 정합성 평가:

| 2025-26 트렌드 | 본 전략 정합 |
|---------------|------------|
| **Deterministic guardrails around LLM** (production agent 신뢰성의 지배 패턴) | ✅ 정확히 이 패턴 — LLM 표면 2점, 나머지 결정론+검증 게이트 |
| **문서지능: vision-OCR이 전통 OCR 대체(감열지·다국어)** | ✅ Step3 LLM vision 유지(전통 OCR silent misread 회피, PYTHON-CONVERSION 입증) |
| **Small-data incremental(frequency/kNN) > heavy ML for niche tasks** | ✅ R-C는 frequency-table 성장(과장된 신경망 아님) |
| **Human-in-the-loop for irreducible ambiguity** | ✅ T3 escalation 영구 설계(purpose-ambiguity 정직 수용) |
| **Self-verifying pipelines(assertion/property gates)** | ✅ verify_week 38→21 assertion |

> 정직(②-3): 이는 "혁신적 신기술"이 아니라 **검증된 production 패턴의 성실한 적용**이다. foresight-env-scan 전면가동(8 sub-skill 오케스트레이션)은 트렌드를 더 넓게 스캔할 수 있으나 heavy op — master GO 시 별도 수행 권고.

---

## 7. R2 자가평가 (최고전문가 McKinsey lens) → R3 필요여부

**R2 자가추정: ~88/100** (R1 70 대비 +18, McKinsey 90+ 근접).
- F(실현성) 70→**92**: Goal 1 빌드·검증 완료. R-C/D는 설계지만 사업자번호·tier가 데이터근거.
- C(완결성) 70→**88**: R-C/B/D 상세 + 트렌드 반영. 잔여: R-C/D 미빌드(검증 전), cell-mapping audit 미실행.
- L(논리) 70→**85**: replay-gap·escalation 정직. 잔여: foresight-env-scan 미가동(지식기반 트렌드만), θ_high/θ_mid 임계값 미실측(build 후 hold-out 필요).

**90+ 도달 잔여 격차(R3 or build로 해소):** (a) R-C build + hold-out 정확도 실측 → θ 임계값 확정, (b) cell-mapping 완전성 audit 실행, (c) [선택] foresight-env-scan 트렌드 심화. → **권고: R2를 gemini·codex 변증으로 경화(약점 반박) 후, R-B→R-C build에서 실측으로 90+ 확정.** 변증 없는 추가 self-round(R3)보다 변증+build 실측이 효율적.

---

## 8. 변증 준비 (master §5 gemini+codex 가동용 — 적대적 검증 포인트)

전략의 stress-test 대상 claim(반박 환영):
1. "사업자번호 join이 정규화 ceiling을 올린다" — 반박각: 카드 미매칭(현금/TOLLS) 비중이 크면 join 효과 제한. → 실측 필요(Tier-2 비중).
2. "purpose-ambiguity 24%는 카드로 미해결" — 반박각: headcount+동행자맥락+프로젝트로 일부 해소 가능? → T2 margin 실측.
3. "frequency-table로 충분(신경망 불필요)" — 반박각: store 다양성↑·신규점 빈출 시 cold-start 문제. → unseen율 실측.
4. "verify_week가 garbage-in 차단" — 반박각: verify_week 자체 커버리지 갭(예: 섹션 오배치를 잡는 체크 부재)? → 분류기 오배치 검출 체크 신설 필요.
5. "self-learning=단조누적, 재학습 불필요" — 반박각: 오배치가 DB에 append되면 오염 전파. → append 전 verify_week PASS 게이트 필수(설계 반영됨, 재확인).

---

*Round 2 끝 — master 검증 + gemini·codex 변증(§5) 대기. 경화 후 R-B→R-C build.*
