# R-A 대체구현 설계 + 백업계획 (build 착수 전 — CSO re-sweep GO 대기)

작성일: 2026-06-19 · EXPTR1 refactoring 워커 · master Q1~Q3 승인 후 설계 단계
원칙: 절대 기준 1·2·3 + ②-3 · master 지시("신규파일 위주·기존파일 변경 전 백업·무거운테스트 전 push")

> **상태: 설계 문서 (가역). 코드 작성(`run_week.py`/`verify_week.py`)은 master의 CSO re-sweep GO 후 착수.**

---

## 1. R-A 범위 & 비목표

**목표**: 결정론 영역의 LLM 에이전트 오케스트레이션/검증을 결정론 Python으로 대체.
- (1) `run_week.py` — 9단계 파이프라인 harness (orchestrator+supervisor×4+secretary 제어 대체)
- (2) `verify_week.py` — 통합 결정론 검증기 (admin×4 + final_verifier 체크리스트 대체 = anti-hallucination 핵심)

**비목표 (R-A에서 안 함)**:
- OCR/bbox vision 로직 변경 — 그대로 LLM 위임 (R-B에서 skill화).
- 9개 기존 스크립트(write_excel·annotate_receipts·verify_*·extract_*·aggregate_ocr_votes·generate_annotations) **무수정** — harness/verifier가 호출만. 검증된 SOT 보존(절대 기준 2).
- `wk.md` 단순화(wrapper 제거)는 **regression PASS 후 최후에** 수행 — 백업 필수. (R-A 말미 또는 R-B 시작 시점, master 확인 후)

---

## 2. `run_week.py` 설계 (결정론 harness)

### 2.1 핵심 모델 — 파일상태 기반 재진입 (idempotent resume)

LLM vision 2개(Step3 OCR·Step6 bbox)는 Python이 실행 불가하므로, harness는 **세그먼트 사이에서 정지(HALT)하고 vision을 요청**한다. 매 호출 시 산출물 파일 존재로 진행지점을 자동 감지 → 다음 vision 게이트 또는 완료까지 전진. **재진입 가능(re-entrant)** = Claude 세션이 자연스럽게 구동.

```
1st call  run_week.py WK09_2026
  → S0 rm → S1 extract_images → S2 extract_card_data
  → ocr-results-*.json 없음 → HALT: "VISION-REQUIRED: OCR. research/ocr-results-{1,2,3}.json 생성 후 재호출"
(Claude Vision N-read 수행)
2nd call  run_week.py WK09_2026
  → reads 감지 → aggregate_ocr_votes.py
       exit 2 → HALT "+2 reads 필요(-4,-5)"      (적응형 3→7, ADR-045)
       exit 1 → STOP "OCR 미합의 — 에스컬레이션"
       exit 0 → consensus 확정 → S4 write_excel --all → S5 generate_annotations
  → wk09.json 없음 → HALT: "VISION-REQUIRED: BBOX. research/annotations/wk09.json 생성 후 재호출"
(Claude Vision bbox 수행)
3rd call  run_week.py WK09_2026
  → wk09.json 감지 → annotate --check-only (P0-1 가드; exit1 → STOP "bbox 재작업")
  → S7 formula restore (openpyxl 최종) → S8 annotate (RDR, 절대최종)
  → verify_week.py WK09_2026 (통합검증)
  → PASS → 완료보고 / FAIL → STOP+리포트
```

### 2.2 단계 테이블 (정확한 명령 — grep 검증된 CLI)

| Step | 명령 | 기대 산출 | 실패 분류 |
|------|------|----------|----------|
| S0 | `rm -f research/ocr-results.json research/ocr-results-[0-9]*.json research/ocr-vote-report.json research/wk{NN}_ocr-results.json` | — | MISSING(재시도) |
| S1 | `python3 scripts/extract_images.py WK{NN}_2026` | input-manifest.json, images/, WK00.xlsx | MISSING |
| S2 | `python3 scripts/extract_card_data.py` | card-approval-data.json | MISSING |
| S3 | **VISION(OCR)** → `python3 scripts/aggregate_ocr_votes.py WK{NN}_2026` | ocr-results.json, ocr-vote-audit.json | exit2=HALT, exit1=STOP |
| S4 | `python3 scripts/write_excel.py --all` | WK{NN}.xlsx, cell-mapping.json, date-scaffold.json | LOGIC |
| S5 | `python3 scripts/generate_annotations.py WK{NN}_2026` | wk{NN}-template.json, wk{NN}-images/ | MISSING |
| S6 | **VISION(bbox)** → `python3 scripts/annotate_receipts.py --check-only WK{NN}_2026` | wk{NN}.json (가드 PASS) | exit1=STOP(재bbox) |
| S7 | `python3 -c "...check_and_restore_all_sheets..."` | WK{NN}.xlsx (수식복원) | LOGIC |
| S8 | `python3 scripts/annotate_receipts.py WK{NN}_2026` | WK{NN}.xlsx (RDR, 최종) | LOGIC |
| V | `python3 scripts/verify_week.py WK{NN}_2026` | verify 리포트 | LOGIC |

> S7 이후 openpyxl 금지(S8 RDR 소실 방지) — harness가 순서 강제(절대 제약 #3).

### 2.3 오류 라우팅 상태머신 (R1 F-약점 해소 — 구체화)

wk.md의 2분류를 결정론 규칙으로:

```
on_step_result(step, exit, expected_outputs):
  if expected_outputs missing OR exit≠0 due-to-missing-input:
      class = MISSING → retry once → still fail → ESCALATE(master push)
  elif validator exit==1 (값불일치/무결성위반):
      class = LOGIC → STOP, write run-logs/WK{NN}-run.json, ESCALATE(no retry)
  elif step in {S3,S6} and exit==2:
      class = VISION-MORE → HALT (추가 vision 요청)
  else: continue
```

- **MISSING**: 1회 재시도 (wk.md "처음부터 재실행 최대 1회" 정합).
- **LOGIC**: 즉시 중지+보고 (절대 금지: 위반 무시 완료보고).
- **VISION**: Python 실행 불가 → HALT + 명확한 요청 메시지. harness는 vision을 흉내내지 않음(②-3 — 환각 금지).

### 2.4 CLI · 로깅 · SOT
- `run_week.py WK09_2026` (자동 재진입) · `--verify-only` · `--dry-run`(계획만 출력) · `--from-step N`(강제).
- 로그: `run-logs/WK{NN}-run.json` (step·status·exit·산출경로). **신규 디렉터리.**
- SOT: harness가 orchestrator 역할이므로 `.claude/state.yaml`의 `current_step`/`outputs` 갱신 권한 보유(절대 기준 2 — 단일 writer). R-A 1차에서는 **읽기+append 최소화**, state.yaml 쓰기는 기존 포맷 보존하며 단계 완료 시만.

---

## 3. `verify_week.py` 설계 (통합 결정론 검증기 — anti-hallucination 핵심)

admin×4 + final_verifier의 LLM 체크리스트를 **단일 Python assertion 스크립트**로. master 강조점: LLM "검증자"의 PASS 환각을 Python이 봉쇄.

### 3.1 체크 인벤토리 (wk.md에서 정확 추출 — 38항목) + 결정론 등급

범례: [D]=완전결정론 · [D-rx]=regex/format 결정론 · [D-re]=기존 validator 위임 · [A]=advisory(판단잔여)

**Phase 1 (8)** — manifest/카드/OCR:
1. [D] input-manifest.json 존재+비어있지않음 · 2. [D] card-approval records≥1 · 3. [D] ocr-results 4키 + toll_history[].date · 4. [D-re] aggregate_ocr_votes exit0 + ocr-vote-audit.json · 5. [D] date-scaffold.json 존재 · 6. [D] §8-1: OCR dinner/staff/travel 항목수 ≤ 해당섹션 이미지수(개수기반) · 7. [D] WK00.xlsx 존재 · 8. [D] images≥1

**Phase 2 (10)** — Excel 기입:
9. [D] WK{NN}.xlsx 존재(WK00 아님) · 10. [D] cell-mapping total_operations≥50 · 11. [D] FORM K8 == date-scaffold.sunday_date · 12. [D] FORM G2 ⊇ week_number · 13. [D] Receipt 5섹션 데이터 존재 · 14. [D] Mileage 거리 존재 · 15. [D] KRW 접두어(카드매칭셀) · 16. [D-rx] FORM [A] D62-66 이름포맷(소속그룹화·"and me." 종결 regex + name-DB 대조) · 17. [D-rx] FORM [F] D95-99 동일 · 18. [D] FORM PAX == Receipt how many

**Phase 3 (4)**:
19. [D] wk-template.json images≥1 · 20. [D] wk{NN}.json 각 이미지 bboxes≥1 · 21. [D-re] annotate --check-only exit0 (P0-1) · 22. [D] 수식복원 결과(restored 카운트)

**Phase 4 (4)**:
23. [D] 파일크기 증가 · 24. [D] drawing2.xml `<sp>` 수 ≥ bbox 수 · 25. [D-rx] RDR 빨간점선 스타일 속성 존재 · 26. [D] 원본 `<pic>` 미변경(해시대조)

**Final verifier + secretary2/2.5/3 (12)**:
27. [D] FORM K8 vs date-scaffold · 28. [D] FORM G2 vs week_number · 29-33. [D] Receipt PARKING/DINNER/STAFF/TRAVEL/TEL 금액·인원 == ocr-results(TEL=×0.8) · 34. [D-re] verify_card_matching exit0 · 35. [D-re] verify_toll_integrity exit0 · 36. [D-re] verify_formula_integrity exit0 · 37. [D] RDR shape 수 == wk{NN}.json bbox 총수 · 38. [D] 원본 이미지 미변경

### 3.2 결정론 비율 (정직 — ②-3)
- [D]+[D-rx]+[D-re] = **38/38**. 진짜 [A](LLM 판단 필수) = **0건**.
- 단 정직 단서: #6(§8-1)·#16/17(이름포맷)은 "개수/포맷 결정론 + name-DB 대조"로 구현 — 의미판단이 아니라 **구조비교**다. content 일치는 ocr-results/name-DB라는 결정론 소스 대조로 환원. → "LLM 판단 없이 100% 결정론" 주장 가능 (과장 아님, 구현으로 입증 예정).

### 3.3 기존 자산 재사용 (절대 기준 2)
- `verify_card_matching/toll_integrity/formula_integrity.py` → **subprocess 호출**(재구현 금지).
- `get_distance`·`derive_date_scaffold`·`prd_form_writable`·`_norm_col` → `from write_excel import` (SOT 단일).
- 출력: `verification-logs/WK{NN}-verify.json` (38항목 PASS/FAIL + Evidence). exit 0(전PASS)/1(1+FAIL). 기존 `validate_*.py` JSON 패턴 정합.

---

## 4. 백업계획 + 파일 영향 인벤토리 + 롤백

| 파일 | 변경유형 | 백업 | 롤백 |
|------|---------|------|------|
| `scripts/run_week.py` | **신규** | 불요(신규) | 삭제 |
| `scripts/verify_week.py` | **신규** | 불요(신규) | 삭제 |
| `run-logs/` | **신규 디렉터리** | 불요 | 삭제 |
| 9개 기존 스크립트 | **무수정** | — | — |
| `.claude/state.yaml` | (선택) current_step 갱신 | `state.yaml.bak-RA` | git/백업 복원 |
| `.claude/commands/wk.md` | **최후·gated** wrapper 제거 | **`wk.md.bak-RA` 필수** | 백업 복원 |

**원칙 준수**: R-A는 **99% 신규파일**. 유일한 기존파일 실질변경(`wk.md`)은 regression PASS 후 최후, 백업 후. `state.yaml`은 포맷보존 append만. **비가역 변경 0건**(모든 변경 가역).

---

## 5. Build 시퀀스 + Regression 게이트 (무거운 테스트 = master GO 필요 표시)

```
[GO 후] 1. run_week.py + verify_week.py 작성 (신규파일, 무거운실행 없음 — 경량)
        2. ⚠[무거운테스트·GO필요] verify_week.py를 기존 WK09 산출물에 실행
             → admin/final_verifier 38항목 전부 재현 PASS 입증 (검증기 완전성)
        3. ⚠[무거운테스트·GO필요] run_week.py로 WK09 재실행(파이프라인 전체)
             → 산출물이 기존 WK09와 기능적 동일(수식·셀·RDR) 입증 (harness 동등성)
        4. [최후·백업후] wk.md를 harness 위임으로 단순화 (wrapper 제거) — 재검증
```

- **경량(GO 내 허용)**: 파일 작성, `--dry-run`, 읽기전용 단위검사.
- **무거움(별도 GO/통지)**: WK09 전체 재실행(write_excel·annotate·RDR = load), verify_week 전수실행. → master CSO re-sweep 상태 확인 후 진행, 착수 전 push.

---

## 6. 위험 등록부 · CCP · 가정

**CCP (절대 기준 3)**:
- *의도*: 결정론 영역의 LLM 오케스트레이션/검증을 Python으로 대체 → 환각표면 제거(품질).
- *영향범위*: 신규 2파일 + run-logs/; 기존 9스크립트 무수정; wk.md(최후·백업)·state.yaml(선택). 강결합/샷건서저리 없음(호출 관계만 추가).
- *변경설계*: §2~5 순서. regression 2게이트가 배포 전 필수.

**위험**:
- W1. verify_week.py가 admin 항목을 누락 → 검증약화. 완화: §3.1의 38항목 1:1 매핑 + 게이트2(WK09 재현 PASS).
- W2. harness vision-HALT 메시지가 모호하면 Claude가 잘못된 vision 산출. 완화: HALT 메시지에 정확한 산출경로·스키마·N-read 규칙 명시.
- W3. WK09 재실행이 vision 재수행 요구(비결정). 완화: 게이트3은 기존 ocr-results/wk09.json 백업 재사용으로 vision 고정 → 결정론 부분만 동등성 비교.
- W4. state.yaml 동시쓰기. 완화: harness 단일 writer, 단계완료 시점만.

**가정**: 기존 WK09 산출물이 동등성 기준 baseline(SOT pacs 85~92, master 확인). 9개 스크립트 현 동작이 정확(선행 회귀 PASS 기록).

---

*R-A 설계 끝 — master에 [의도·영향파일·위험·가정] 보고 후 CSO re-sweep GO 대기. GO 전 코드 미작성.*
