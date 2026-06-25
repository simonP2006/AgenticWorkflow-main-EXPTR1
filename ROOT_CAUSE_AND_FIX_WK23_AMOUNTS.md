# WK23 CRITICAL — 금액 미기입 근본원인 + Fix 계획 (master 승인 대기)

> Status: **조사 완료·수정 미실행.** master/주인님 승인 후에만 fix 집행. 입력 read-only.
> 검증: 워커 adversarial Workflow `wkmskc4qh` (4-agent, READ-ONLY, verdict=PLAN_READY).

## 1. 근본원인 (responsibility = SUITE_GAP_UNBUILT, 검증됨)
expensereceipt 스위트는 **영수증 이미지 배치(`<pic>` surgical 주입)만** 수행하고, **OCR 금액을 FORM/Receipt 입력셀에 기입하는 파이프라인 단계가 처음부터 없다.** 금액은 in-memory `run['receipts']` 와 -db 원장에만 존재하고 워크북 셀에 `.value=` 기입되지 않는다.

근거(file:line):
- SPEC §1(L19)/§5(L45-46): place 책임 = "Receipt Sheet 3개/줄 배치"(이미지 그리드)만. 금액 transcription 언급 0.
- orchestrator L219: `place(template, output, placements)` = twoCellAnchor 이미지 좌표뿐. run dict에 금액-셀 기입 필드/단계 없음.
- place.py: `.value` 유일 등장 L785 = physical verify의 **읽기** 비교(쓰기 아님). 이미지만 기입.
- classify.py L71: write_excel를 `read_name_database`(이름DB **읽기** 헬퍼)만 import. 금액-writer 경로 미연결.
- `scripts/write_excel.py` L642(phase_base)/L880(telephone)/L719-734(toll)/L1271/L1347(phase_post): ★금액-writer가 **존재**하나 어떤 expensereceipt 스킬도 호출 안함.
- HARDENING scope(L9-11): IN=이미지배치 / OUT=FORM header·Mileage. 금액-셀 기입은 **IN·OUT 어디에도 없음** → 설계에서 누락된 단계.

## 2. 내 4계층 검증이 못 잡은 이유 (검증됨)
- **verify-LOGICAL V4**(amount≠0, L338): in-memory receipts dict의 `r['amount']`를 읽음 — DATA에 금액 있는지만 확인·**셀에 써졌는지 미확인**. V1/V2/V5/V6/V7도 전부 run data dict 대상.
- **verify-PHYSICAL**: pic_delta·anchor·rdr·row_cell·reopen = **이미지/구조 무결성만**. 셀·M52 일절 안읽음.
- **db**: 원장만, 워크북 안씀.
- ⟹ 이미지 13개 정상 + 금액셀 전부 None인 워크북이 4계층 전부 PASS. **금액-셀 기입을 주장하는 단계가 없으니, 그 출력을 검증하는 체크도 없다.** existing_amount_check_anywhere = **false**.

## 3. ★★Critical 발견 2건 (master/주인님 결정 필요)
### 3-A. 전화비 80% 할인 → 내 "130,520" 총액이 틀림
- PRD §13(1) "영수증 금액의 80%의 금액이 기입" + write_excel.py L880 `tel_amount = payment_amount*0.8` + WK10 실증(74,800 bill → A601=59,840).
- ⟹ TELEPHONE 셀 A601 = 74,800 × 0.8 = **59,840** (POST-discount). D601=0.8·B601 'discount rate' = 표시용(재적용 금지). FORM!E46='=Receipt!A601'(추가 ×0.8 없음).
- ⟹ **올바른 M52 = 비전화 base 55,720 + 전화 59,840 = 115,560** (내가 보고한 130,520 아님 — 130,520은 전화 pre-discount 74,800 가정으로 PRD §13 위반).
- **base 55,720** = TRAVEL(22,800+8,700+8,300) + DINNER 9,500 + TOLL(1,200+960+960) + PARKING(KICC) 3,300.
- ★주인님 확인 필요: 전화비 회사 정산 = 80%(→59,840·M52 115,560)가 정책 맞나? (PRD 기준 yes. 만약 full 74,800 원하면 PRD §13 모순 — 주인님 재정의 필요.)

### 3-B. FORM!K8(주말 기준일) stale
- WK23 템플릿 현재 K8=2026-03-15(stale)·G2 'LCL 00WK'(stale). 올바른 K8 = 주말 **2026-06-07**(일).
- FORM header 기입 = SPEC OUT(주인님 수기영역). Receipt 셀 좌표는 K8 무관(detect_receipt_positions 고정)이나, FORM 요일컬럼(E9:I9=K8-WEEKDAY+N)·M52 정합은 K8 의존. → 주인님이 K8=2026-06-07 설정 or 파이프라인에 위임 인가 필요(2026-03-15 방치 금지).

## 4. 정확한 셀 맵 (9 셀 / 7 영수증 — 검증됨, WK22 대조)
요일컬럼: Mon=B·Tue=C·Wed=D·Thu=E·Fri=F (FORM!E9:I9).
| 영수증 | 섹터 | 날짜(요일) | 셀 = 값 |
|--------|------|-----------|---------|
| 폴바셋 | TRAVEL | 06-01(월) | **Receipt!B401 = 22800** |
| 까치386 | TRAVEL | 06-02(화) | **Receipt!C401 = 8700** |
| 까치201 | TRAVEL | 06-04(목) | **Receipt!E401 = 8300** (travel_1st·다른날이므로 402 아님) |
| 스팟마트 | DINNER | 06-04(목) | **Receipt!E124 = 9500** (dinner행, time≥17) |
| T world | TELEPHONE | — | **Receipt!A601 = 59840** (=74800×0.8, §3-A) |
| 하이패스(화) | TOLL | 06-02(화) | **Receipt!B6 = 1200** (Toll-Go·단일) |
| KICC 주차 | PARKING | 06-02(화) | **Receipt!E6 = 3300** (Parking 컬럼) |
| 하이패스(목·왕) | TOLL | 06-04(목) | **Receipt!B10 = 960** (Toll-Go·시간 빠른쪽) |
| 하이패스(목·복) | TOLL | 06-04(목) | **Receipt!D10 = 960** (Toll-Back·시간 늦은쪽) |
> ★F6/F10 = 기존 `=SUM(Bn:En)` 공식 — **덮어쓰기 금지.** STAFF 0(전원 TRAVEL=name-DB 확정·§classify). C6/C10(Stop-over)/402 = 빈칸 유지.

## 5. Fix 방법 + ★순서 제약 (검증됨)
- ★**현 WK23 산출물에 openpyxl 금액기입 금지** — openpyxl은 자체 object model로 재직렬화하며 surgical 주입된 `<pic>` 앵커를 모름 → load+save시 **13 이미지 전부 파괴/고아화.** 따라서 **clean 템플릿부터 REDO**(금액 openpyxl 기입이 이미지 배치보다 먼저여야 함).
- 증거: run_week.py가 정확히 이 순서를 강제 — S4(금액 기입, openpyxl) → S7('openpyxl LAST use' 공식복원) → S8('RDR inject, no openpyxl after' 이미지). write_excel.py(amount-writer)는 run_week S4가 호출(이미지 前). 즉 **레거시 파이프라인은 원래 올바르게 동작**했고, expensereceipt 스위트가 이미지부분만 가져오며 금액단계를 빠뜨림.

### 정정 순서 (run_week S4→S7→S8 모델)
0. 7 영수증을 write_excel 입력 스키마 `research/ocr-results.json`(중첩: parking_tolls.{toll_history,parking_receipts}·dinner·travel·telephone + weekday_mapping)로 인코딩 + card-approval-data.json. (현재 부재 — 원래 OCR-vote 파이프라인 산출물.)
1. clean **image-free 템플릿**에서 시작(raw-data/output/simon_park_T&E_WK00_2026.xlsx; ORG 백업 raw-data/...WK00_ORG.xlsx). ★현 stale-reset에서 WK00 staged 사본은 PRISTINE(f33078a5)이므로 그것 사용 가능.
2. 금액 기입(openpyxl-safe·이미지 없음): write_excel.py 경로 → 9 셀 + 인원(howmany)·FORM 전파. WK00→WK23 rename.
3. (옵션) 공식복원 = openpyxl 마지막 터치.
4. 이미지 배치(FINAL·이후 openpyxl 금지): place 스킬 surgical-zip로 13 pic 재주입(2단계 금액셀 무손상).
5. verify: 신규 cell-occupancy + M52 정합 게이트(§6) + verify-PHYSICAL.

## 6. ★신규 검증 게이트 (반드시 추가 — 재발 방지)
verify에 결정론적 **cell-occupancy + total-reconciliation** 추가:
1. 각 영수증의 매핑 타깃 셀이 **비어있지 않고 기대값과 일치**(TRAVEL/DINNER raw·TELEPHONE ×0.8·toll 1/2/3 규칙) — DATA dict 아닌 **셀** 검증.
2. Σ(전 금액셀) == **FORM!M52 cached**(openpyxl data_only 재오픈) 정합(WK23=115,560).
3. PARKING SUM셀(F6/F10..)이 여전히 `=SUM` 공식(미덮어씀).
4. pic/sp ≥ bbox(이미지 보존 — 0원+이미지없음으로 통과 못하게).
⟹ 이미지 정상+금액셀 빈 워크북이 (1)(2)에서 결정론적 FAIL.

## 7. 잔여 리스크 (master 인지)
1. 130,520 vs 115,560 = PRD 모순(전화 pre/post-discount). 주인님 결정 전 total 게이트 타깃 미확정.
2. K8/G2 header(OUT-of-scope·수기). 미정정시 FORM 요일·M52 표시 오류.
3. Toll Go/Back = ocr-results 시간순 의존(목 960 2건). GO를 시간 빠르게 인코딩해야 B10/D10 방향 정확.
4. (해소) Sector TRAVEL vs STAFF: 내 classify가 전원 TRAVEL 확정(name-DB: 이창성/이종희 EDS·김병수 HBM-PE) → *401 확정. (workflow 일반 caveat이나 실제 해소됨.)
5. clean 템플릿 pristine 필요(이미지-free·공식 무결). staged WK00(f33078a5) 사용 권장.
6. 손-인코딩 ocr-results.json은 3→7 OCR consensus 우회 — owner-authoritative로 신뢰(게이트는 셀==인코딩값 검증, 인코딩값==현실은 owner 확정).

## 8. 의사결정 요청 (master/주인님)
- **A.** 전화비 80%(59,840·M52 115,560) 확정? (PRD 기준 권고)
- **B.** K8=2026-06-07 정정 주체(주인님 수기 vs 파이프라인 위임)?
- **C.** Fix 실행 경로: (i) write_excel.py 재사용(ocr-results 인코딩·완전) vs (ii) 9셀 타깃 openpyxl 기입(간단·단 howmany/FORM 전파 누락 위험) — 권고 (i).
- **D.** 스위트 영구수정(금액-fill 단계 + cell-occupancy 게이트 추가)은 별도 과업으로? (WK23는 위 fix로 우선 정산)
★승인 전 수정 미실행.
