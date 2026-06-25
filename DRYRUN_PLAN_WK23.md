# WK23 SETTLEMENT — DRY-RUN PLAN (worker → master) · v2 보강

> Status: **PLAN ONLY — nothing staged / placed / executed / orchestrated.** Awaiting master **실행 GO**.
> Author: WK23 expensereceipt 정산 실행 워커 · 2026-06-21 · reports to surface:1. Identity: WORKER (de-master honored).
> v2 = master §5 적대검증(APPROVE_WITH_CONDITIONS)의 7개 보강조건 + 워커 adversarial Workflow(`w6pbu0vz8`, 4-agent, READ-ONLY, verdict PASS) 반영.

## 0. Master correction ACK (드 → me)
6/1 폴바셋 맨밑 필기 = **김병수 · 우석원 · 이정민 · me**(`me`=본인/주인님), 4명. `드`→`me` 오타정정(directive L27 반영 확인). owner 확정값 사용. vision이 실제 필기와 명백 불일치시만 HALT(§3-3).

## 0-b. Master §5 보강조건 반영 (7건)
1. ✅ stale-reset move-list 확장·검증(§6). 2. ✅ ocr-results 권위=명시적 manual move(harness S0 auto-clean 의존 금지, §6). 3. ✅ stage_inputs 필수 첫 단계(§7). 4. ✅ manifest 해시 `7b70b33745f4` staged 대조 + run후 입력 md5 byte-diff(§7). 5. ✅ H1 인벤토리 사실정정(§3, master §5 실판독). 6. ✅ store-db 스팟마트 DINNER prior cross-check(§8). 7. ✅ 폴바셋 owner이름 사용 + vision 불일치 HALT(§3).

## 0-c. ★주인님 인벤토리 확정 + 이창성 정정 (directive §3-4, 2026-06-21 AUTHORITATIVE)
주인님이 H1 전체 인벤토리를 직접 확정(directive §3-4 authoritative roster) → §3 반영. **까치(주문201) 동석자 = 이창성**(§5 vision '이정우'는 오독 → 주인님 정정). 까치386=이종희. 스팟마트=me 혼자(혼밥·DINNER). 폴바셋=김병수·우석원·이정민·me(4). 하이패스 통행료 3,120(3건)=**정산 포함 확정** PARKING/TOLLS. KICC=주차요금. T world=telephone. ★owner확정 이름/인원/포함여부 **우선**(authoritative); 공식 vision OCR이 명백히 다르면 HALT(§3-3). 폴바셋·까치 STAFF/TRAVEL = classify가 동석자 소속회사(name-DB)로 결정 → 비가역 place 직전 §6-4 매핑표로 주인님 최종확정.

## 0-d. ★★입력 무결성 경보 → ✅ RESOLVED-BENIGN (2026-06-21 — CSO 포렌식 완료)
**✅ 해소(BENIGN)**: CSO 포렌식 — 8ecb0ae9 원본 확보(`/tmp/cso-recovered-cardfile-orig-8ecb0ae9.xls`) → 현재본 `bd8e1d0c`와 xlrd 셀단위 대조 → **카드 거래 7행 전 셀 byte-identical**(승인번호·금액·날짜·가맹점·사업자번호 동일). md5차 = OLE 메타(Author/last-saved)만 = M9 동일 BENIGN. ★**data-intact precondition 충족** — 카드 재export 불요(현 데이터 = 검증 baseline과 동일). 재발차단(preventive)으로 입력 Spotlight 비활성은 잔여 권고.

[기록] 최초 경보: `카드승인내역_20260602.xls` content 변경 baseline **`8ecb0ae9`** → **`bd8e1d0c`**. 워커 read-only corroborate.
- **Blast radius = 이 1파일만**. 나머지 6 입력 PRISTINE(§1 표 baseline과 동일).
- **Stat 시그니처 = stealth OLE 재기록**: size 동일(16384) · **mtime 보존**(2026-06-20 12:52:11) · **ctime 점프**(2026-06-21 22:54:52, 오늘). = 내용 재기록 + mtime 복원 → directive §4가 예고한 macOS Spotlight/QuickLook **BIFF WRITEACCESS(writer-app 문자열) 재기록**(M9 사고: card data 불변, 메타만 변경)과 정확히 일치하는 패턴.
- **위험도**: 이 xls = **V2 카드대조 원천**(R2 KICC 주차 · R7 폴바셋 22,800 롯데카드가 여기 대조). card DATA가 변조됐다면 V2가 오염데이터로 검증 → 정산 무결성 붕괴. **데이터 불변 확인 전 실행 절대 금지.**
- **현 가설(미확정)**: size 동일 + mtime 보존 = OLE 메타만 변경·card data 불변일 개연성 높음(M9 선례). 단 **가정 금지** — 확인 필요.
- **복구 권고(master/owner 결정 — 입력 수정=denylist, 워커 미집행)**:
  1. **owner 재export**: 카드사(롯데/KICC) 승인내역 새로 내려받아 pristine 재baseline (최선·byte-clean).
  2. **read-only 구조 대조**: 현 `bd8e1d0c`의 승인번호/금액/사업자번호 행을 독립소스(매출전표 R2 / 직전 export)와 대조 → card data 불변 입증시 master가 `bd8e1d0c`를 신규 pristine으로 재baseline.
  3. **재발 차단(preventive)**: 입력 디렉토리 Spotlight 인덱싱 비활성(`mdutil -i off` 또는 `.noindex`) → 추가 read 접근(워커 md5 포함)이 또 재기록 트리거하는 것 방지. (시스템 조치 — master 승인 후.)
- ★워커 조치: 무결성 ✅해소됨. 입력 무접촉 read-only 유지. 파이프라인 실행은 **주인님 최종 GO → master phase1 신호** 전까지 보류.

## 1. 입력 디렉토리 — 실제 파일 개수 · 전체 목록
`raw-data/input/WK23_2026/` = **8 entries = 7 실파일 + `.DS_Store`(무시)**. content-md5 PRISTINE(읽기전용; PDF 3종 pdfinfo 전후 md5 동일=접근 변조無; card xls `8ecb0ae9…`=하드닝 baseline 일치).

| # | 파일 | 형상 | md5 |
|---|------|------|-----|
| 1 | `카드승인내역_20260602.xls` | 16 KB | `8ecb0ae9…` |
| 2 | `simon_park_T&E_WK00_2026.xlsx` | 154 KB | `f33078a5…` |
| 3 | `매출전표 - 롯데카드.pdf` | 1 page | `478ead37…` |
| 4 | `청구내역 인쇄하기 _ T world.pdf` | 1 page | `51fb740e…` |
| 5 | `2026-06-02-1.png` | 748×258 | `c620751d…` |
| 6 | `20260620_045132999_iOS.png` | 1284×4020 | `4e3c31b8…` |
| 7 | `WK23_2026.pdf` | **1 page (★3 receipts)** | `85d9594b…` |

## 2. 각 파일 처리경로 (autodetect 결정론, AUTODETECT-3 precedence)
| 파일 | file-kind | 경로 | 배치 |
|------|-----------|------|------|
| `카드승인내역_20260602.xls` | card_statement | V2 카드대조 원천(승인번호·금액·사업자번호) | ✗ |
| `simon_park_T&E_WK00_2026.xlsx` | template | 출력 베이스 + name-DB(Receipt!A999:H1007) | ✗ |
| `매출전표 - 롯데카드.pdf` | card_slip (KICC) | DH-3 sales_slip → V2 매칭시 영수증 소비 | ✓ |
| `청구내역 인쇄하기 _ T world.pdf` | telephone_bill | TELEPHONE 섹터(영수증 아님·카드 consume 진입 안함) | ✓ |
| `2026-06-02-1.png` | receipt | 하이패스 통행료 문서 | ✓ |
| `20260620_045132999_iOS.png` | receipt | 폴바셋 단일 영수증 | ✓ |
| `WK23_2026.pdf` | receipt | ★1 page에 영수증 3장(스팟마트·까치·까치) | ✓ |

## 3. ★영수증 인벤토리 + 섹터 맵 (★주인님 확정 AUTHORITATIVE — directive §3-4, 2026-06-21)
주인님이 H1 인벤토리를 직접 확정(directive §3-4 roster). master §5 vision 판독을 주인님이 검수·정정: **까치201 동석자 = 이창성**(§5 '이정우'는 vision 오독). owner확정 이름/인원/포함여부가 **우선**(authoritative); 공식 vision OCR이 명백히 다르면 HALT(§3-3). 멀티영수증 소스 = **WK23_2026.pdf(3장)**.

| # | 영수증 | 소스 | 금액 | 인원·이름(owner확정) | 예상 섹터 | 비고 |
|---|--------|------|------|----------|----------|------|
| R1 | 하이패스 통행료(기간별내역, 3건) | `2026-06-02-1.png` | 3,120 | — (toll 문서) | **PARKING/TOLLS** | 결정론 "기간별 사용내역" 트리거. ★정산 포함=주인님 확정. 필기영수증 아님. |
| R2 | KICC 주차(롯데카드 매출전표) | `매출전표 - 롯데카드.pdf` | (vision) | — | **PARKING/TOLLS (주차요금)** | 주인님 확정 §3-1. + DH-3 consume → V2 카드대조 (섹터·결제정산 둘다). |
| R3 | T world 통신 | `청구내역…T world.pdf` | (vision) | — | **TELEPHONE-LOCAL** | 결정론 telephone_bill. |
| R4 | 스팟마트 | `WK23_2026.pdf` ① | 9,500 | 1 · me 혼자(혼밥) | **DINNER** | owner확정 혼밥. store-db 119-81-00851 DINNER conf1.0(§8)와 정합 → G12 auto-confirm 유력. |
| R5 | 까치(주문 201) | `WK23_2026.pdf` ② | 8,300 | 2 · **이창성** + me | **STAFF/TRAVEL** | ★이창성(주인님 정정, §5 vision '이정우' 오독). 섹터=동석자 소속회사(name-DB) → §6-4 owner 최종확정. |
| R6 | 까치(주문 386) | `WK23_2026.pdf` ③ | 8,700 | 2 · 이종희 + me | **STAFF/TRAVEL** | 이종희=SAMSUNG EDS(하드닝#4)→TRAVEL 유력. 섹터=name-DB → §6-4 owner 최종확정. |
| R7 | 폴바셋 삼성DSR점 | `20260620_045132999_iOS.png` | 22,800 | 4 · 김병수·우석원·이정민·me | **STAFF/TRAVEL** | owner확정 이름. 섹터=동석자 소속회사(name-DB, SAMSUNG 포함→TRAVEL/전원 Teradyne→STAFF) → §6-4 owner 최종확정. 롯데카드→V2 대조. vision 명백불일치→HALT(§3-3). |

> 섹터 집계(예상): PARKING/TOLLS = R1+R2(2) · TELEPHONE = R3(1) · DINNER = R4(1) · STAFF/TRAVEL = R5·R6·R7(이름=owner확정, 섹터=name-DB→§6-4 owner 최종확정).
> ★3-in-1 페이지(WK23_2026.pdf): 영수증 3장이 단일 물리 페이지 이미지를 공유 → 서로 다른 섹터(DINNER + 까치×2)로 분기. multi-receipt 분할=owner 수작업영역(하드닝 OUT-of-scope). place는 물리이미지당 1회 배치(Batch D PLACE-1/2 dedup) → 3장이 분할 crop 없이 한 이미지면 배치 표현 방식 master/owner 확인 필요(H1-place).

## 4. (완전 해소) v1 H1 인벤토리 불일치
v1의 "receipt-kind 소스 3 vs 필기 4 → multi-receipt 추정·첫 HALT"는 master §5 실판독 → **주인님 직접 확정**(directive §3-4)으로 완전 해소. 4 필기영수증 = 폴바셋(iOS png) + 까치201(이창성) + 까치386(이종희) + 스팟마트(혼밥); 모두 WK23.pdf 3장 + iOS png. `2026-06-02-1.png`=toll 문서. 인벤토리·이름·인원·포함여부 = owner authoritative(§3). 실행시 공식 vision OCR은 owner값 **확인 게이트**(명백 불일치시만 HALT §3-3), best-guess 0.

## 5. 예상 HALT 지점 (fail-closed · honesty)
| ID | 단계 | 트리거 | 동작 |
|----|------|--------|------|
| H1-place | extract/place | WK23.pdf 3-in-1 페이지의 3영수증 배치표현(분할 crop 부재) | master/owner 확인 후 진행(분할=수작업영역). |
| H2 | vision | 공식 OCR이 owner확정값(이름/금액/인원)과 **명백 불일치** | HALT(§3-3): owner값 우선이나 명백 모순시 정지·master 보고. (이름 전부 owner확정 → vision=확인 게이트, best-guess 0.) |
| H3 | classify | 폴바셋·까치 동석자 STAFF↔TRAVEL 라우팅 — name-DB에 동석자(이창성·이종희·김병수·우석원·이정민) 미등재시 | 섹터 결정불가 → owner escalation → §6-4 매핑표에서 주인님 소속회사 확정. (이름은 owner확정, **섹터만** 미정.) G12 auto는 R4 스팟마트 DINNER(≥0.95)만. |
| H4 | verify-LOGICAL (ANCHOR#2a) | V2 카드대조(폴바셋22800·KICC 롯데카드) 불일치 / 항목합≠카드 / V6 wrong-week vote-audit / producer 부재 | verdict ERROR or violation-FAIL → **place 절대금지** HALT+escalate. |
| H5 | place | pre-sized 섹터밴드 초과(true overflow) | insert-row fail-loud → ESCALATE → master 결정. |
| H6 | verify-PHYSICAL | post-place drawing/pic count 불일치 | ESCALATE(placed 플래그). |

## 6. Stale-state 리셋 (★master 조건1·2 — adversarial Workflow `w6pbu0vz8` PASS 검증)
research/+planning/ top-level 전수 점검 → **전부 직전 WK22_2026 잔재 확인**(0 AMBIGUOUS, 0 preserve-wrongly-included, 0 stale-missed). 리셋 대상 = **16 파일(§6-A) + 4 dir(§6-B, ✅master 승인)**.

### 6-A. MOVE_STALE (16) — stage_inputs **실행 前** 타임스탬프 백업폴더(`_stale_backup_wk22_<ts>/`)로 **이동**(가역·삭제 아님)
- planning/ (7): `cell-mapping.json`(★WK22 "LCL 22WK"·2026/05/31) · `date-scaffold.json`(week_number 22) · `ocr-adjudication-note.md`(제목 WK22 Run) · `ocr-correction-audit.json` · `ocr-vote-audit.json`(week WK22) · `section-confirmed.json`(★`{confirmed:true}` 잔재) · `section-predictions.json`(week WK22)
- research/ (9): `ocr-results.json` · `ocr-results-1.json` · `ocr-results-2.json` · `ocr-results-3.json` ← **★최고위험: 4개 모두 `wk22_ocr-results.json`과 byte-identical(md5 `aca53b04…`, 2026-05-26~29) → default 경로서 WK23 OCR vote에 garbage-in** · `input-manifest.json`(WK22) · `_section_map.json`(WK22) · `card-approval-data.json`(WK22) · `image-positions.json`(WK22) · `formula-integrity-report.json`(WK22)
- ★조건2: 위 ocr-results 4종은 **명시적 manual move**로 권위확보. legacy `run_week.py` S0 auto-clean에 의존 금지(S0는 `run_if_fresh_only`이고 fresh=input-manifest 부재인데 stale WK22 input-manifest가 존재 → **S0 skip됨** → auto-clean 작동 안함).

### 6-B. ★dir-level 벡터 (Workflow 발견 → ✅ master 백업이동 승인 2026-06-21 · reset move-list 포함 · fail-closed defense-in-depth)
| 디렉토리 | risk | 사유 | 처리 |
|---------|------|------|------|
| `research/images/` | **HIGH** | `extract_images.py`가 dir 안 비움·파일명 순차(image1..N). WK22 image1-22+phone_bill 잔존 → legacy `wk-receipt-ocr`(globs `research/images/*.png`) 호출시 WK23로 오인 glob. | ✅ **BACKUP_MOVE (승인)** |
| `research/ocr-enhanced/` | MEDIUM | `_section_map.json`(이미 리셋대상)이 read-hint로 참조 | ✅ **BACKUP_MOVE (승인)** |
| `research/ocr-crops/` · `research/ocr-grid/` | LOW | default reader 없음(위생 목적) | ✅ **BACKUP_MOVE (승인)** |
| `research/annotations/` | — | 주차 prefix 격리(wk{nn}); WK23는 fresh wk23-* 작성 | **LEAVE** |
| wk07_backup·wk08/09/21/22_* 8개 archive | NONE | 주차 prefix archive·default 경로 밖 | **LEAVE** |
> ★아키텍처 단서: WK23 실 파이프라인 = **expensereceipt orchestrator**(input-isolated: `raw-data/input → research/expensereceipt/input-staging`, 위 default 경로 **안 읽음**) → dir-level 위험은 legacy `run_week.py`/`wk-receipt-ocr` 경로 호출시만 실현. ✅ **master 결정 = (b) 백업이동 승인**(fail-closed defense-in-depth): `images/`·`ocr-enhanced/`·`ocr-crops/`·`ocr-grid/` 4개 dir을 §6-A 16파일과 함께 `_stale_backup_wk22_<ts>/`로 이동(가역).

### 6-C. ★보존(불변 — 절대 이동 금지)
- planning/: `store-db.json` · `store-db-promoted.json` · `store-db-coverage.json` · `store-db-holdout.json` · `store-db-quarantine/` · `store-db-snapshots/`
- research/: `names-data.json`(인사 name-DB) · 주차 prefix OCR archive 15종(`wk06_…wk22_ocr-results.json` + `WK19-ocr-gate-escalation.md` + `wk21-ground-truth-analysis.md`)

### 6-D. 재검증 기준 (move 후)
- `grep -rIE '"confirmed"[: ]*true' planning/*.json research/*.json` → **0** (달성가능; section-confirmed.json이 유일했고 move됨).
- `grep -rIE 'WK22_2026' planning/*.json research/*.json` (★`store-db*.json` 제외) → **0**. store-db* 4종은 누적 `source_weeks`(WK06~22)로 WK22 토큰 보유 = **정상 누적이력, 잔재 아님**(Workflow 확인) → 재검증서 제외.
- 입력 raw-data/ 불변(1바이트도 안건드림). store-db 일가 불변.

## 7. 실행 모델 (master GO 후 — 조건3·4)
```
-1. ✅ PRECONDITION (§0-d 무결성) 충족: CSO 포렌식 BENIGN(card data 7행 byte-identical) → data-intact 확인 완료. 재export 불요. (재발차단 Spotlight 비활성 권고.)
 0. ★stale-reset (§6-A 16파일 + §6-B 4 dir ✅승인) — stage_inputs 실행 前 완료, 재검증(§6-D) 0 확인
1. ★stage_inputs(WK23_2026)        # 필수 첫 단계(orchestrate auto-stage 안함). raw-data/input → input-staging 1회 read
2. ★manifest 무결: staged manifest 해시 = 7b70b33745f4 대조
3. autodetect → manifest
4. ★vision OCR + 맨밑필기 (= 내 LLM HALT; 폴바셋 owner값, 까치/스팟마트 vision; master §5 판독 독립 재확인)
5. merchant (NTS 체크섬 / 카드매칭)
6. classify (6섹터; escalation → G12 R4 auto / R5·R6·R7 owner)
7. verify-LOGICAL (ANCHOR#2a fail-closed)   ── ERROR/FAIL → HALT, place 금지
8. place (Receipt Sheet 3개/줄, surgical direct-zip)
9. verify-PHYSICAL (post-place 재검증)
10. db (per-receipt ledger / gallery; verdict=PASS시만 promote)
11. ★run후 입력 byte-diff: raw-data/input/WK23_2026 전파일 md5 = §1 값과 동일 확인(외부 OLE 재기록 사고 감시)
```
- 출력 = `raw-data/output/simon_park_T&E_WK23_2026.xlsx` (출력만).
- 각 체크포인트 master §5 독립검증 병행. **비가역 place 직전(§6-4)**: R1~R7 6섹터 매핑표 master 보고 → 주인님 확인 후에만 place.

## 8. store-db 스팟마트 prior cross-check (조건6)
`planning/store-db.json` key `119-81-00851`: merchant `스팟마트`, category 할인점, `section_dist {DINNER:14}`, confidence **1.0**, dominant **DINNER**, occurrences 14, source_weeks WK06/07/08/09/11/14/16/21. ⇒ WK23 스팟마트 "dinner alone" 필기와 **정합** → R4 DINNER 분류 신뢰·G12 auto-confirm 근거. (불일치 없음.)

## 9. 정지점
**여기서 멈춤.** §0-d 무결성 ✅해소(BENIGN). 잔여 게이트 = **주인님 최종 GO → master phase1 신호** 1건. 그 전까지 stale-reset 집행/stage/place/orchestrate/실행 일체 안함, 입력 read-only 유지. phase1 신호 수신시 §7(-1 충족 → 0단계 stale-reset부터) 착수.
