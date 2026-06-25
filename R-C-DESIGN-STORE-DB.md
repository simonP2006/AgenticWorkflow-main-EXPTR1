# R-C 설계 — Store→Sector DB + 자기학습 (codex 4요건 선반영)

작성일: 2026-06-19 · EXPTR1 refactoring 워커 · R2 §5 변증 codex REVISE 반영
원칙: 절대 기준 1·2·3 + ②-3(현실적·과장금지)
상태: **설계 v1 (codex 4요건 선반영)**. gemini 변증 종합 후 master가 요건 확정 → R-C build GO(무거운 holdout = GN W2 peak 후 스태거). **이 문서는 저부하 설계 — build/실측 아님.**

> Goal 2 핵심: 현재 human이 수행하는 **유일한 판단(영수증 섹션 사전정렬)**을 DB+자기학습으로 대체. 요일/슬롯 배치는 이미 결정론(write_excel).

---

## 0. codex 4요건 ↔ 내 5 stress-point ↔ R-C 설계요소 매핑

| codex 요건 (90+ 위해 실측 필요) | 내 stress-point | R-C 설계요소 | 산출 |
|------|------|------|------|
| ① **join coverage matrix** | #1 사업자번호 join 효과는 카드매칭 비중 의존 | `build_store_db.py --coverage` | 주차×{card-matched/fallback/excluded} 행렬 |
| ② **holdout confusion/escalation metrics** | #2 purpose-ambiguity·#3 cold-start | `holdout_eval.py` (LOWO) | confusion matrix·tier별 정확도·escalation율·unseen율 |
| ③ **verify_section_distribution invariant** | #4 verify_week 섹션 오배치 검출 부재 | `verify_week.py` 신규 체크 C38 | 결정론 invariant (오배치 차단) |
| ④ **append quarantine/rollback** | #5 self-learning 오배치 DB오염 | `store_db` 트랜잭션 append | quarantine→verify PASS→promote+snapshot |

**핵심: R-C는 '주장'을 build로 '실측 증명'한다.** 90+는 self-round가 아니라 이 4 실측이 닫는다.

---

## 1. `build_store_db.py` — DB 구축 (결정론) + 요건① join coverage matrix

### 1.1 소스 우선순위 (L2 ground-truth 원칙)
1. **완성 Excel** `raw-data/input/WKnn_2026/simon_park_T&E_WKnn_2026.xlsx` (+ sample/) — human-verified 최종 섹션배치 = ground truth.
2. **카드** `카드승인내역_*.xls(x)` — (date,amount) join → 사업자번호·업종 (결정론 merchant 식별).
3. **OCR 백업** `research/wk*_ocr-results.json` — store명·headcount 보조(drift 가능 — L2 경고).

### 1.2 DB 스키마
```
store_db[키] = {                       # 키 = 사업자번호(card-matched) | norm_store(fallback)
  merchant_name, 업종,
  section_dist: {DINNER:n, STAFF:n, TRAVEL:n, PARKING:n},
  typical: {headcount:[min,med,max], amount:[..], hour:[..]},
  occurrences, last_seen_wk,
  confidence: max(section_dist)/sum(section_dist),   # 단일섹션 지배율
  source_weeks: [WKnn,...]              # 감사추적(rollback 단위)
}
```

### 1.3 요건① — Join Coverage Matrix (stress-point #1 실측)
`--coverage` 모드: 각 주차의 영수증을 3분류하여 행렬 산출.
```
              card-matched(사업자번호)  fallback(현금/미매칭)  excluded(TOLLS/TEL)
WK06          n / %                     n / %                 n / %
...
TOTAL         Σ / %                     Σ / %                 Σ / %
```
- **목적**: 사업자번호 결정론 키의 실제 coverage 정량화. card-matched%가 낮으면 Tier-1 이득 제한 → 정직 표면화(②-3).
- **결정론**: verify_card_matching의 consume-join 로직 재사용(SOT 단일). 산출 `planning/store-db-coverage.json`.

---

## 2. `classify_section.py` — 3-tier 분류기 + θ (holdout로 확정)

```
입력: 미분류 영수증 (store/OCR, date, amount, headcount, time)
1. (date,amount) 카드 join → 성공시 사업자번호 키, 실패시 norm_store 키
2. store_db[키] 조회:
   T1 자동:     confidence ≥ θ_high      → section = argmax(section_dist)   [신뢰 高]
   T2 보조:     margin(top1-top2) ≥ θ_mid + (headcount/hour/amount 정합) → section + Decision Log
   T3 escalation: ambiguous(폴바셋류) | unseen(cold-start) → 🔴 LLM-vision/human → 결과 append
```
- **θ_high·θ_mid는 §3 holdout이 실측으로 확정** (R2 §7의 미실측 격차 해소).
- confidence/margin은 결정론 산식. escalation은 silent 금지(반드시 플래그).

---

## 3. `holdout_eval.py` — 요건② Holdout Confusion/Escalation (무거운 실측 · GN 스태거)

### 3.1 Leave-One-Week-Out (LOWO) 교차검증
```
for W in [WK06..WK22]:
    db = build_store_db(all weeks except W)        # W 제외 학습
    for receipt in W (ground-truth section 보유):
        pred = classify_section(receipt, db)
        record(pred.tier, pred.section, actual_section)
```
### 3.2 산출 metrics (`planning/store-db-holdout.json`)
- **Confusion matrix**: predicted_section × actual_section (오배치 패턴 노출).
- **Tier별 정확도**: T1/T2 accuracy, T1/T2 coverage(자동율).
- **Escalation율**: T3 비율 (= 무인 불가 잔여).
- **Unseen율**: cold-start (stress-point #3) — W의 store가 학습셋에 없던 비율.
- **θ 민감도 곡선**: θ_high 변화 vs (T1 정확도·자동율) → 운영점 선택.
### 3.3 정직 해석 (②-3)
- 이 실측이 R2의 "76% 자동" 주장을 **확정 or 반증**한다. 결과가 낮으면 정직 보고(과장 금지).
- ambiguous(폴바셋) 오배치가 confusion matrix에 STAFF↔TRAVEL 혼동으로 나타날 것 — 예측됨.
- **이것이 master가 지목한 "무거운 hold-out 실측"** — per-week DB rebuild × 17주 = 반복 openpyxl 로드. **GN W2 torch peak 후 스태거·별도 GO 필수.**

---

## 4. 요건③ — `verify_section_distribution` invariant (verify_week 신규 C38, stress-point #4)

verify_week에 섹션 오배치 검출 체크 신설(현재 부재 — 내 stress-point #4 자인):
- **C38a**: 자동배치(T1/T2)된 각 영수증의 section ∈ 해당 store의 `store_db.section_dist` 관측 섹션. 미관측 섹션에 자동배치 → **위반**(unseen이면 T3 escalation이어야 함).
- **C38b**: T3 escalation 항목이 silent 배치되지 않고 플래그됨(escalation 로그 존재).
- **C38c**: 주차 섹션 분포가 sane 범위(예: 한 섹션에 전체의 >90% 몰림 = 이상). 
- 결정론·읽기전용. verify_week 패턴 정합(기존 21체크에 추가). FAIL → exit 1(LOGIC) → 중지.

---

## 5. 요건④ — Append Quarantine / Rollback (self-learning 안전, stress-point #5)

```
주차 처리 완료 → 자기학습 append:
  1. 신규 (키, section, headcount...) 관측을 store_db_quarantine/WKnn.json에 격리
  2. verify_week(WKnn) PASS 확인 (verify_section_distribution C38 포함)
     ├ PASS → store_db snapshot(store-db.v{N}.json) 후 quarantine 내용 promote(merge)
     └ FAIL → quarantine 폐기 (DB 미오염 — L2 ground-truth 불변)
  3. rollback: store-db.v{N-1}.json로 복원 (오염 append 발견 시)
```
- **오염 차단**: 미검증 데이터는 절대 DB 본체에 들어가지 않음(stress-point #5). verify PASS가 promote 전제.
- **rollback**: 버전 스냅샷 체인 → 임의 시점 복원 가능(가역·절대기준1 품질).
- snapshot은 작은 json(수십KB) — 저장 부담 무시.

---

## 6. Build 시퀀스 + 게이트 (heavy 실측 = GN 스태거 + GO)

```
[저부하·설계반영 GO 내] 
  1. build_store_db.py 작성 (신규) + --coverage (요건①)
  2. classify_section.py 작성 (신규)
  3. verify_week.py에 C38 추가 (요건③ — 기존 R-A 신규파일 확장, 가역)
  4. append quarantine/rollback 로직 (요건④)
[★무거운 실측 = 별도 GO + GN W2 peak 후 스태거]
  5. holdout_eval.py 실행 (요건② — 17주 LOWO, 반복 openpyxl) → confusion/escalation/θ 실측
  6. 실측 기반 θ_high/θ_mid 확정 → 90+ 판정
```
- 1-4는 신규파일/내-R-A파일 확장(가역·저부하). 5-6은 무거운 실측 → master GO + 스태거.
- 회귀: build를 ground-truth(완성Excel)로 검증, coherent 아티팩트만(L2).

---

## 7. 90+ 도달 경로 (R2 88 → 90+, 실측이 닫는다)

| R2 잔여격차 (자가) | R-C 실측이 닫는 방법 |
|------|------|
| θ 임계값 미실측 (L 85) | 요건② holdout θ 민감도 곡선 → 운영점 확정 |
| 자동율/정확도 주장 미검증 (C 88) | 요건② confusion/tier 정확도 실측 |
| 사업자번호 join 효과 미측정 (stress #1) | 요건① coverage matrix |
| verify_week 섹션 갭 (stress #4) | 요건③ C38 신설 |
| append 오염 위험 (stress #5) | 요건④ quarantine/rollback |
→ 4 실측 산출이 전부 PASS·정직보고되면 McKinsey 90+ 달성 판정. 미달이면 정직 보고 후 R-D 재설계.

---

## 8. CCP · 위험 · 가정

**CCP**: *의도* Goal2 섹션분류 자동화(human 사전정렬 대체)+자기학습 안전장치. *영향범위* 신규 build_store_db/classify_section/holdout_eval + verify_week C38 확장(내 R-A파일) + planning/ DB·snapshot. 기존 9스크립트·write_excel 무수정(읽기 소비). *변경설계* §6 순서, holdout은 gated.

**위험**: (W1) join coverage 낮으면 사업자번호 이득 제한 → 요건①이 정직 표면화. (W2) holdout 정확도 낮으면 R2 주장 반증 → 정직 보고(②-3, 과장 금지). (W3) 브랜드 다중 사업자번호(폴바셋 본사PG vs 평택점) → 키 정규화(브랜드 롤업) 옵션 필요. (W4) ground-truth 완성Excel의 섹션 추출 자체가 정확해야 — 추출 로직 검증 선행.

**가정**: 완성 Excel(WK06~22)이 섹션 ground-truth(human-verified). 카드 (date,amount) join이 verify_card_matching 수준으로 신뢰. gemini 변증이 codex 4요건과 큰 충돌 없을 것(충돌 시 master 종합 반영).

---

*R-C 설계 v1 (codex 4요건 선반영) 끝 — gemini 종합 후 요건 확정 → R-C build GO 대기. 무거운 holdout은 GN W2 peak 후 스태거.*
