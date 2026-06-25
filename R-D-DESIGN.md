# R-D 설계 — 통합 + 자기학습 + 분류기 정련 (holdout 근거)

작성일: 2026-06-19 · EXPTR1 refactoring 워커 · R-C holdout 종결 후 · master R-D 지시
원칙: 절대 기준 1·2·3 + ②-3(현실적·과장금지)
상태: **설계 (저부하)**. build GO는 §5 gemini+codex 종합 + 주인님 θ 운영점 결정 후. 무거운 재-holdout은 GN-window.

> R-C holdout 실측 결론 내장: full-auto 90+ 불가(천장 87.5%·STAFF↔TRAVEL purpose-ambiguity). Goal2 = **보조분류 + 정량 escalation**(reframe, master가 주인님께 surface 중). R-D는 이 현실 위에서 정확도를 최대화하고 escalation을 정량 관리한다.

---

## 0. R-D 목표 (reframe 만장채택)

현재 human이 수행하는 **섹션 사전정렬**을 대체하되, **full-auto가 아니라 "신뢰 가능분만 auto + 모호분 escalation"**. 측정가능 성공 = (a) **낮은 wrong-auto-rate**(§0.5-2 최우선), (b) escalation의 빠짐없음(오배치 0 지향), (c) 주인님이 trade를 θ로 선택.

## 0.5 §5 변증 5요건 정련 (gemini Reframe-Correct + codex APPROVE+보강)

**(1) Framing 정정 (②-3 양방향 — 과장도 과잉비관도 금지):** 87.5%는 **"절대 천장"이 아니다.** 정확 표기 = **"현재 feature(store-frequency only)·14주·STAFF n=15 소표본·feature-ablation 미수행 설계의 holdout 천장"**. R-D feature(headcount/시간대) 개선여지 존재 — 환원불가 단정은 과잉비관(②-3 위반). store-db-holdout 보고·R-D 전반에 이 표기 사용. 단 "feature로 반드시 넘는다"도 과장 — §0.5-4 ablation으로 실측.

**(2) ★KPI 재정의 — wrong-auto-rate 최우선(accuracy 단독 아님):** T&E에서 **잘못된 auto-배치 > escalation** (오배치는 정산 downstream을 silent 오염; escalation은 human에 물을 뿐). 따라서 1차 지표 = **wrong-auto-rate = (auto-placed & wrong)/total**. 최적화 = "wrong-auto-rate ≤ 허용선(주인님 결정, 예 ≤2%) 제약 하에 auto-coverage 최대화". θ는 정확도가 아니라 **wrong-auto-rate 허용선**으로 설정. (실측참고: θ_mid=0.2시 wrong-auto≈cov84×(1-0.726)=~23% 高 / θ_mid=0.8시 ~4.4% — 허용선이 운영점을 결정.)

**(3) ambiguous = 기본 T3 escalation OR high-precision-rule only:** 저신뢰 auto-place 금지. STAFF/TRAVEL 모호 store는 (a)기본 T3 escalation, 또는 (b)high-precision 규칙만 auto(예 hc≥3→TRAVEL는 STAFF@amb hc≤2라 고정밀). 그 외(hc≤2 모호)는 T3. = wrong-auto-rate 최소화 직접수단.

**(4) headcount/시간대 feature = ablation으로 정직측정:** 단순 채택 금지. R-D 재-holdout에서 feature on/off ablation(baseline vs +headcount vs +time vs +both)으로 각 feature의 wrong-auto-rate·coverage 델타 실측. ★정직 가능성 인정: 프로젝트/동행자 맥락 없으면 STAFF↔TRAVEL이 feature로도 환원불가일 수 있음 — ablation이 판정. 과장(feature가 다 푼다)·과잉비관(절대 못 푼다) 양쪽 금지.

**(5) self-learning append = quarantine/rollback(R-C 보유) + negative examples:** human/LLM이 escalation을 확정할 때 positive((store,section)=맞음)뿐 아니라 **negative((store, NOT-section)=틀림)**도 기록. negative examples는 향후 분류기가 "이 store를 이 섹션으로 auto 금지"를 학습 → wrong-auto-rate 직접 감소. quarantine→verify PASS→promote에 negative store도 포함.

---

## 1. 분류기 정련 (holdout 3대 발견 반영)

### 발견→설계 매핑
| holdout 발견 | R-D 설계 |
|------|------|
| T2(margin auto)에 오류집중·STAFF→TRAVEL 12/15 | **ambiguous(다중섹션) store → 기본 T3 escalation**(T2 auto 폐지/축소) |
| 천장 87.5%·θ_mid가 진짜 축 | **configurable-θ** — 주인님이 운영점 선택(0.4 acc80/cov73 … 0.8 acc87/cov35) |
| headcount 부분 분리(STAFF@amb hc≤2·TRAVEL hc≥3) | **headcount 보조규칙**: 모호 store라도 hc≥3→TRAVEL(T2 confident), hc≤2→T3 escalation |

### 정련된 3-tier (R-C classify_section.py 확장)
```
key = 사업자번호(card join) | norm_store(fallback)
e = store_db[key]
if not e:                              → T3-unseen (escalation)
elif confidence ≥ θ_high (단일섹션 지배): → T1 auto
elif store ambiguous(다중섹션):
    if headcount ≥ HC_TRAVEL(=3):       → T2 auto = TRAVEL (data-grounded: STAFF@amb hc≤2)
    else (hc ≤ 2):                      → T3 escalation (STAFF/small-TRAVEL 환원불가 overlap)
else (margin ≥ θ_mid):                  → T2 auto = dominant
else:                                   → T3 escalation
```
> headcount 임계 HC_TRAVEL=3은 실측 근거(STAFF@ambiguous 11건 전부 hc≤2; TRAVEL@ambiguous 61% hc≥3). configurable.

### 기대 효과 (정직·②-3)
- STAFF→TRAVEL 체계오류 감소: 모호 store의 hc≤2를 auto-TRAVEL 대신 escalation → STAFF 오배치↓.
- auto-accuracy 천장 상승 예상(87.5% 초과 가능)하나 **full-auto 90+ 보장 아님** — hc≤2 overlap은 escalation 잔존. **정확한 gain은 R-D 재-holdout으로 실측**(추측 금지).

---

## 2. R-D 재-holdout — feature ablation + wrong-auto-rate (§0.5-2·4)

`holdout_eval.py`에 (a) **feature ablation**: baseline(store-freq) vs +headcount vs +time-of-day vs +both — 각 조합의 **wrong-auto-rate(1차)·auto-coverage·escalation·STAFF-recall** 델타 실측. (b) **wrong-auto-rate 곡선**: θ(또는 wrong-auto 허용선)별 (wrong-auto-rate, auto-coverage) → 주인님 운영점 선택용. (c) **혼동 패턴**: STAFF↔TRAVEL이 어느 feature로 분리되는지.
- 판정: 각 feature가 wrong-auto-rate를 허용선 이하로 낮추며 coverage를 얼마나 보전하나. 환원불가분(맥락 부재)은 escalation으로 정직 처리.
- ②-3 양방향: feature가 효과 미미하면 정직보고(과장금지), 효과 있으면 정직보고(과잉비관 정정). GN-window 무거운 재실행.

---

## 3. 파이프라인 통합 (harness pre-step)

`run_week.py`에 신규 결정론 stage **S2.5 classify_section** 삽입(현재 human 사전정렬 대체):
```
S2 extract_card → S2.5 classify_section(영수증→섹션 예측) → S3 OCR …
  · T1/T2 auto → 해당 섹션 배치(input-manifest 섹션 위치에 대응)
  · T3 escalation → VISION-HALT(exit 10) "SECTION-ESCALATION: {receipts}" → LLM-vision 맥락판단/사용자 확인
```
- T3는 harness HALT로 표면화(silent 배치 금지 — C38 invariant 강제).
- configurable-θ는 SOT(state.yaml or config)에서 읽음 — 주인님 운영점.

## 4. 자기학습 루프 (R-C ④ 재사용)

```
주차 완료 → verify_week PASS(C38 포함) → build_store_db --promote WK → snapshot
  · 오배치(C38 위반)면 PASS 실패 → quarantine 폐기(DB 미오염)
  · escalation에서 human/LLM이 확정한 (store,section)도 promote에 포함 → coverage 단조증가
```
- 단조누적(frequency-table 성장), 모델 재학습 아님. unseen율(13.3%) 점진 감소 기대.

## 5. Build 시퀀스 + 게이트

```
[저부하 설계반영 GO 내, but build GO는 §5+주인님θ 후]
  1. classify_section.py에 headcount 규칙 + configurable-θ 추가(가역)
  2. holdout_eval.py에 headcount on/off 비교 추가
[무거운 재-holdout = GN-window]
  3. R-D 재-holdout 실행 → headcount gain 실측 → 천장 재판정
[통합 = 별도 GO]
  4. run_week.py S2.5 classify stage 결선(기존 R-A 파일 확장·가역·회귀: WK21 동등성)
  5. 자기학습 promote 루프 결선
```
- 주인님 θ 결정 전엔 운영점 미확정 → 통합 build 대기.
- 통합은 run_week.py 변경(내 R-A 파일) → 백업·회귀(WK21 coherent 동등성) 필수.

## 6. CCP · 위험 · 가정

**CCP**: *의도* 섹션 사전정렬 자동화(보조+escalation)·정확도 최대화. *영향범위* classify_section.py(R-C 신규)+holdout_eval.py 확장, run_week.py S2.5 결선(R-A 파일·백업), state.yaml θ config. 기존 9스크립트 무수정. *변경설계* §5 순서, 재-holdout·통합 gated.

**위험**: (W1) headcount gain 미미→천장 못 넘음: R-D 재-holdout이 정직 측정, 미미하면 escalation 비중↑로 정확도 확보(주인님 θ). (W2) S2.5 결선이 기존 OCR-section 분류(input-manifest 의존)와 충돌: 통합 시 회귀로 검증. (W3) configurable-θ 오설정→과소/과대 escalation: 기본값 안전점(예 θ_mid=0.4) + 주인님 가이드. (W4) unseen 13.3% cold-start: 신규점은 항상 escalation(안전), 자기학습으로 점감.

**가정**: headcount OCR 판독 신뢰(staff/travel에 존재). 주인님이 운영점 θ를 선호로 결정. §5 변증이 headcount 설계와 큰 충돌 없을 것(충돌 시 종합 반영).

---

## 7. 정직 요약 (②-3 양방향)

R-D는 R-C가 측정한 **현재 설계의 holdout 천장(87.5%, 절대천장 아님 — §0.5-1)**을 feature(headcount/시간대)로 **개선 시도**하되, ablation(§0.5-4)으로 정직 측정한다 — full-auto 90+도, "feature가 다 푼다"도 약속하지 않는다. ★1차 성공지표 = **wrong-auto-rate ≤ 주인님 허용선**(accuracy 단독 아님 — §0.5-2). 현실적 산출 = "wrong-auto-rate 허용선 하에서 auto-coverage 최대 + 나머지 escalation". escalation은 결함이 아니라 purpose-ambiguity(+맥락부재)의 정직 처리. negative examples(§0.5-5)로 오배치 학습 차단. 가치 = human 사전정렬 노동 상당부분 제거 + 오배치 silent 0 지향(C38 게이트).

---

*R-D 설계 끝 — §5 종합 + 주인님 θ 후 build GO. 무거운 재-holdout은 GN-window. 저부하 설계만 완료.*
