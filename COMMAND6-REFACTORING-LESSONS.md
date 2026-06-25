# 명령6 — EXPTR1 완전자동화 Refactoring 교훈 아카이브

작성일: 2026-06-19 · EXPTR1 refactoring 워커 · master 지시(전과정 교훈 정리)
원칙: 절대 기준 1·2·3 + ②-3(현실적·과장금지) · git 금지(로컬 문서)
대상: 명령6 전 과정(R-A → R-B → R-C → R-D, §5 3자변증 3회, holdout 2회, headcount ablation)

> 이 문서는 명령6의 **방법론·기술·정직성 교훈**을 차기 명령/자식 시스템(soul §0 DNA 유전)에 전수하기 위한 아카이브다. 산출물 상세는 각 설계문서 참조.

---

## 0. Executive Summary

명령6은 반자동 T&E 영수증 분류도구 EXPTR1을 두 목표로 refactoring했다:
- **제1목표(완성·승인)**: 18개 LLM sub-agent 오케스트레이션을 **결정론 harness + assertion 검증기 + 2 vision skill**로 대체. LLM-PASS 환각을 Python assertion으로 봉쇄.
- **제2목표(core 완성·승인)**: 영수증 store→sector DB + 자기학습 분류를 파이프라인에 통합. **정직하게 reframe** — full-auto가 아니라 "신뢰분 auto-place + 모호분 escalation"(데이터가 full-auto 불가를 입증).

**핵심 교훈 한 줄**: *측정 전 단정하지 말 것(verify-before-assert) · 과장도 과잉비관도 ②-3 위반 · 모든 변경은 가역 · 결정론 검증 > LLM 자기보고.*

---

## 1. 전체 아크 + 산출물 인벤토리

| 단계 | 산출 | 성격 |
|------|------|------|
| **분석(R1/R1.5)** | FULL-AUTOMATION-REFACTORING-ANALYSIS-R1.md | 선행분석 검증(할루시네이션0)·파이프라인 9단계중 LLM 2개 확정·사업자번호 발견 |
| **R-A** | scripts/run_week.py(harness)·verify_week.py(38→21 assertion)·run_week.py.bak | 에이전트팀 제어/검증 대체·Gate-A 코어런트 입증 |
| **R-B** | .claude/skills/wk-receipt-ocr·wk-bbox-detect | 2 vision 작업 skill화(exit10 HALT 계약) |
| **전략(R2)** | FULL-AUTOMATION-REFACTORING-STRATEGY-R2.md | §5 3자변증 경화·자가88 |
| **R-C** | build_store_db.py·classify_section.py·holdout_eval.py·planning/store-db*.json | DB(사업자번호키 96.6%)·LOWO holdout·C38·quarantine/rollback |
| **R-D** | classify_stage.py·run_week S3c·R-C-DESIGN/R-D-DESIGN.md·store-db-holdout.json | headcount 분류·escalation·파이프라인 통합 |
| **doc-sync** | WK_workflow.md·wk.md(424→149) harness 모델 | SOT 일관성 |

**가역성**: 전부 신규파일 위주. 기존 9스크립트 무수정. 변경된 기존파일(wk.md·run_week.py)은 백업(.bak-RA·.bak) + 1줄 롤백. `_ra_backup/`(42파일) 트리 스냅샷.

---

## 2. 핵심 기술 결정 (차기 전수)

1. **Harness-over-agents**: 결정론 영역의 LLM 에이전트(오케스트레이터·supervisor·admin·secretary)는 오버헤드+환각표면. 결정론 harness(run_week)+assertion 검증기(verify_week)가 **더 신뢰성 높다**. LLM "검증자"는 PASS를 환각하나 Python assertion은 안 한다. → 결정론 우월 영역은 전부 Python, 환각불가 영역(vision)만 LLM.
2. **LLM 표면 최소화 = 정확도 최대화**: 18 에이전트 → 2 vision skill + 1 harness. vision HALT 계약(exit10)으로 LLM과 결정론을 명확히 분리·재진입.
3. **사업자번호 = 결정론 merchant 키**: OCR store명은 노이즈(DSR↔D5R·NFD/NFC·슬래시날짜). 카드 (date,amount) join→사업자번호가 결정론 키(coverage 96.6% 실측). OCR명은 fallback.
4. **wrong-auto-rate가 T&E 1차 KPI**(accuracy 아님): 잘못된 auto-배치는 silent 오염(escalation보다 나쁨). θ는 wrong-auto 허용선으로.
5. **headcount=부분 분리자**: STAFF@ambiguous hc≤2·TRAVEL hc≥3 → hc≥3→TRAVEL 고정밀, hc≤2→escalation. wrong-auto 23%→6.2%. 단 환원불가분은 escalation(맥락 부재).
6. **escalation=결함 아닌 정직처리**: purpose-ambiguity(동일 merchant 다른 목적)는 merchant+date+amount로 환원불가. silent 오배치 대신 escalation이 옳다(C38 강제).

---

## 3. §5 3자변증 3회 (gemini+codex+master) — 변증이 잡은 것

| 회차 | 대상 | 변증 결과 |
|------|------|----------|
| 1 | R2 전략(자가88) | codex REVISE: 90+엔 4실측(join coverage·holdout·section invariant·quarantine) 필요 → R-C build로 실측 확정 |
| 2 | R-C reframe | 만장 채택(gemini Correct Shift·codex APPROVE+5요건·master ②-3) — full-auto=데이터오염자동화·reframe=리스크관리 |
| 3 | R-D framing | codex 보강: "절대천장 87.5%" 금지(소표본·ablation부재=과잉비관도 ②-3위반)·KPI=wrong-auto·negative examples |

**교훈**: 변증은 (a) 과소(자가88의 미실측 격차)뿐 아니라 (b) **과잉비관**도 잡는다. ②-3은 양방향이다. 중요 산출물(전략)은 반드시 3자 변증.

---

## 4. Holdout 실측 (정직 결론)

- **R-C LOWO(store-freq only)**: auto-acc 72.6%·wrong-auto 23%·STAFF→TRAVEL 12/15 오분류. GT-divergence 4.2%(A OCR + B Excel cross-check). → full-auto 90+ 불가 실측.
- **R-D A/B(+headcount)**: wrong-auto **23%→6.2%**·auto-acc **89.2%**(직전 87.5% 초과=과잉비관 정정)·TRAVEL 39/39·STAFF 전량 escalation. coverage 84→57.5%·escalation 16→42.5% trade.
- **정직 결론**: headcount는 유효(1차KPI -16.8pt)하나 magic 아님. STAFF 커피미팅은 맥락없이 환원불가→escalation. Goal2 = 보조분류+정량escalation(주인님이 θ로 trade 선택).

---

## 5. 방법론 교훈 (가장 중요 — 차기 필수 전수)

1. **★Verify-before-assert (3회 자가정정)**: ① C36 "pre-existing" 단정 → read-only 검증으로 "replay-introduced"로 정정. ② coverage 40.7% → 2버그(NFD/NFC glob·슬래시날짜) 적출·수정 → 96.6%. ③ "절대천장 87.5%" → A/B로 89.2% 가능 입증, 과잉비관 정정. **단정 전 코드/데이터로 검증**하면 잘못된 보고를 master 도달 전 차단한다.
2. **★②-3 양방향 정직**: 과장(시장장악·full-auto)뿐 아니라 **과잉비관**(절대천장 단정)도 위반. 현실적 역량평가 = 실측이 말하게 하라.
3. **★전부 가역**: 신규파일 위주·기존변경 전 백업·1줄 롤백·트리 스냅샷. 비가역(삭제·무백업덮어쓰기)·외부발행(git)·무거운 build/테스트는 master GO + GN 스태거.
4. **★Master-gating + fail-loud**: 매 단계 평문 push yield → master 독립검증(+필요시 3자변증). 침묵대기 금지. 무거운/비가역 단계 전 재-push.
5. **결정론 P1 봉쇄**: 반복 100% 정확해야 하는 검증은 Python assertion으로(LLM 자기보고 금지). verify_week가 admin 체크리스트의 환각가능 PASS를 봉쇄.
6. **SOT 단일 재사용**: 기존 함수(get_distance·extract_card·prd_form_writable) import 재사용·재구현 금지(절대기준2). 의도적 중복(D-7)은 cross-ref 주석.

---

## 6. 정직한 성과 + 한계 + 게이트된 차기

**성과**: Goal1 완성(18→결정론+2skill)·Goal2 core 완성(DB+분류+escalation 통합)·wrong-auto 6.2%·전부 가역·환각0.

**정직한 한계(②-3)**: Goal2는 full-auto 아님 — auto-coverage 57.5%(보수운영점)·escalation 42.5%(STAFF 다수)·unseen cold-start 13.3%(자기학습으로 점감). purpose-ambiguity는 merchant데이터로 환원불가.

**게이트된 차기(주인님/master 결정)**: (a) full pre-sort 완전대체(예측섹션→write_excel 입력 교체=출력행동 변경, consequential→주인님 결정) (b) 자기학습 promote 루프 production 결선 (c) θ 운영점 주인님 선호 (d) 추가맥락(프로젝트/동행자) feature로 STAFF↔TRAVEL 추가분리 시도.

---

## 7. 차기 시스템을 위한 DNA (soul §0 유전)

자식 시스템이 내장할 것:
- **검증 우선 문화**: 단정 전 측정·verify-before-assert·assertion>LLM자기보고.
- **②-3 양방향 정직**: 과장도 과잉비관도 금지·실측이 말한다.
- **가역 기본**: 백업·롤백·스냅샷·비가역은 게이트.
- **결정론/LLM 명확분리**: 환각불가 영역만 LLM(vision)·나머지 결정론·HALT 계약으로 재진입.
- **3자변증**: 중요산출물은 독립 적대검증(과소·과잉 양방향).
- **escalation 정직**: 환원불가 모호성은 silent처리 금지·정량 escalation.

---

*명령6 교훈 아카이브 끝 — Goal1+Goal2 core 종결. full pre-sort 완전대체는 주인님 결정 대기(master surface). 워커 STANDBY.*
