# WORKER_TODO — WK23 (EXPTR1 실행 워커, ws1/surface:2)

> 신원: 나는 master가 아니라 EXPTR1 실행 워커다(DE-MASTER). 설정 = EXPTR1 CLAUDE.md + AGENTS.md.
> 보고: master surface:1 평문 push (모달 금지). 입력 raw-data/input/WK23_2026/ = read-only 불변. git 금지.

## 상태 (2026-06-20)
- [x] 명령7-standby: directive 내면화 + CLAUDE/AGENTS/파이프라인 정독 + dry-run 계획 + ACK push.
- [x] 원래 run 보류 확정 (WK00 임베드 6장 = 스테일 템플릿, garbage-in — master 검증으로 BLOCKER B 확인).
- [→] **현재 과업: 실소스 ingestion 설계 (read-only DESIGN, 코드 0).** 이 문서에 설계 기록 → master push → master+§5(gemini/codex)+주인님 승인 후에만 빌드.
- [ ] (승인 후) 빌드 — 미착수.

---

## 검증된 WK23 실입력 (read-only)
| 소스 | 내용 | 비용 | 파이프라인 현재 처리 |
|---|---|---|---|
| WK23_2026.pdf (1쪽, ~90° 회전·3영수증 적층) | 스팟마트 9,500 / 까치화방커피 8,300 / 까치화방커피 8,700 | 26,500 | ❌ 미독취 |
| 매출전표 - 롯데카드.pdf (1쪽) | 세외수입_KICC 3,300 (전자전표) | 3,300 | ❌ 미독취 |
| 20260620_045132999_iOS.png (1284×4020) | 폴바셋 22,800 (iOS 스샷) | 22,800 | ❌ 미독취 |
| 2026-06-02-1.png (748×258) | Hi-pass 통행료 3건 (별도카드 …4552) | 3,120 | ❌ 미독취 |
| 카드승인내역_20260602.xls (30컬럼) | AMEX 3792 5건 (col24 사업자번호·col27 업종 포함) = 권위 spine | 52,600 | ✅ S2 |
| WK00 xlsx 임베드 6장 (image1-6) | TERADYNE/MYR/2021/더미 = **스테일 템플릿** | — | ⚠ S1/S5가 영수증으로 오인 |
- 실비용 합계 = **55,720원** (AMEX 52,600 + 통행료 3,120). ※무영수증이던 KICC·폴바셋 영수증 주인님 추가 투입 완료 → 입력 완전.

## 핵심 발견 (the crux)
파이프라인의 **annotation/RDR 사슬 전체(S1·S5·S6·S8)가 "영수증=WK00 xlsx의 임베드 이미지(xl/media, Receipt시트 drawing2.xml 앵커)"를 전제**한다:
- S1 extract_images → research/images/ (OCR 입력) ← input WK00 xl/media.
- S5 generate_annotations → research/annotations/wk23-images/ (bbox 입력) ← input WK00 xl/media + drawing2.xml 앵커(from_row로 섹션분류).
- S8 annotate_receipts → 출력 xlsx의 <pic> 위에 RDR <sp> 주입.
→ WK23 실영수증은 외부 PDF/PNG라 이 사슬이 전부 헛돈다. **풀-피델리티 산출물(번호+임베드 영수증+RDR)을 내려면 실영수증을 WK00 Receipt시트에 정상 임베드해야 한다.** 이것이 A/B 갈림길의 본질.
- WK00 **셀 골격은 유효**(Receipt시트 1-44행 = PARKING/TOLLS 헤더·날짜 라벨·SUM=0 깨끗한 빈 양식; write_excel:647-651이 출력 WK00의 FORM/Receipt에 기입). **임베드 그림(xl/media)만 스테일.** ⇒ 셀 골격 보존, 임베드 미디어 교체.
- 카드 spine 확정: col24 사업자번호(예 119-81-00851) = 결정론 merchant 키(build_store_db._biz_no), col27 업종(할인점/커피전문점) = 섹션 힌트. classify_section/classify_stage가 이미 사용.

## 빌드 가능성 (read-only 확인)
- Python PDF 라이브러리 전무(fitz/pdf2image/pdfplumber/pikepdf/cv2/numpy 모두 import 실패). **단 poppler CLI 존재**(/opt/homebrew/bin/pdftoppm·pdfimages) → PDF→이미지는 subprocess로 가능, **신규 pip 의존성 0**(결정론 스크립트 철학 부합).
- Receipt시트 = sheet3 → **drawing2.xml** (S5 하드코딩). 재임베드 시 이 불변식 유지 필수(openpyxl 재저장이 drawing 번호 바꾸면 S5 깨짐 — 빌드 시 실측 검증).
- scripts/에 기존 PDF/임베드 처리 없음 → 신규 범위(denylist ④ → 주인님 승인 필요).

---

## 설계 (CCP Step 1–3)

### Step 1 — 의도
파이프라인(run_week S1→V)이 **WK00 스테일 임베드 대신 실소스(PDF·PNG·카드xls)**를 처리하도록 ingestion/정규화 능력을 신설한다. 제약: 입력 read-only · 검증된 S1–V tail 재사용(절대기준2) · 신규 pip 의존성 회피(poppler CLI) · 풀-피델리티 산출물(절대기준1) · 재사용(차기 주차).

### Step 2 — 영향 범위 (Ripple)
| 컴포넌트 | 영향 |
|---|---|
| extract_images.py (S1) | 영수증 소스를 input WK00 xl/media → **정규화 WK00**(실영수증 임베드)로 변경 필요 |
| generate_annotations.py (S5) | input WK00 경로 + drawing2.xml 하드코딩 → 정규화 WK00 참조 필요 |
| annotate_receipts.py (S8) | 임베드 <pic> 위 RDR 주입 → 실영수증이 임베드돼 있어야 의미. |
| write_excel.py (S4) | 변경 최소 — ocr-results + card + manifest sections + 출력WK00 셀골격으로 동작 |
| aggregate_ocr_votes/classify_*/build_store_db | 변경 없음 (ocr-results+card+store-db 소비) |
| verify_week (V) | C06/C08(images)·C26(<pic>보존)·C24/C37(RDR)·C38(섹션불변식) 모두 유의미해짐 |
| store-db.json | WK23 가맹점(까치화방·스팟마트·폴바셋·KICC) 미관측 가능 → C38 advisory + classify_stage T3 escalation = **정직한 설계동작**(silent 금지) |
| run_week.py _stages() | ingestion 스테이지(S-ingest, S1 이전) 추가 / S1 소스 조정 — .bak 존재 |
| 테스트/문서 | holdout_eval·verify_* / WK_workflow.md §Step0·1 · wk 스킬 · ADR 갱신 |
> 비고: 이 WK 파이프라인은 워크플로우 state.yaml SOT가 아니라 결정론 harness + run-logs를 쓴다(SOT 스키마 영향 없음).

### Step 3 — 변경 설계 (옵션별)

**옵션 A (최소, WK23 한정):** ingest_sources.py(또는 수동)로 PDF 렌더+분할·PNG 정규화 → research/images/ 직접 배치 → `run_week.py WK23 --from S3`(S1 이미지추출 우회) → OCR→write_excel(번호 기입)→verify. S5/S6/S8(임베드 annotation) **스킵**.
- 장: 변경 최소·번호 정합 최단경로. 단: 산출물 풀-피델리티 아님(임베드 영수증·RDR 없음, 스테일 <pic> 잔존), 재사용 LOW, 절대기준1 품질부채 + 주인님 완전자동화 의도 미충족.

**옵션 B (완전자동화, 재사용) — 권고: "normalize-to-embedded-WK00":**
새 ingestion 프런트 스테이지(스킬 `wk-source-ingest` + 결정론 `ingest_sources.py` + PDF 다중영수증 분할 vision 서브스텝)가 이종 입력을 **S1–V tail이 이미 소비하는 단일 산출물 = 정규화 WK00 xlsx**(깨끗한 셀 골격 + 실영수증을 Receipt시트 섹션 앵커에 임베드, 스테일 미디어 제거)로 변환 → raw-data/output/에 배치. 이후 S1(+S5)을 정규화 WK00으로 지향 → S3 OCR→…→S8 RDR→V는 거의 무변경.
1. **결정론 렌더**(ingest_sources.py, poppler): `pdftoppm -r 300` PDF쪽→PNG; 단독 PNG(폴바셋·통행료)는 정규화 복사.
2. **다중영수증 분할(vision-assisted, card-anchored)** — WK23_2026.pdf: ~90° 회전정규화 후, **카드 spine이 영수증 정확히 3건**(스팟마트/까치화방/까치화방)임을 강한 prior로 → vision 서브스텝이 3개 영수증 영역 식별 → 결정론 PIL crop → 3 PNG. (b)답: **분할 권고**(전체-OCR은 3영수증 혼동·per-receipt bbox/RDR 불가; 파이프라인 전 구간이 per-receipt-image).
3. **카드-spine 결합**(c): 각 영수증 이미지를 (date,amount) join(기존 match_card)으로 AMEX 거래에 부착 → 사업자번호+업종 → 섹션 결정+merchant키. 통행료는 AMEX 부재 → parking_tolls 분리, verify_toll_integrity 대조.
4. **정규화 WK00 임베드**(d/e): 각 영수증을 Receipt시트 섹션 앵커행(TOLLS/PARKING<30·DINNER 120-300·STAFF 300-400·TRAVEL 400-550·TELEPHONE 550+ — generate_annotations.SECTION_BOUNDARIES)에 삽입, 스테일 xl/media 제거. ★drawing2.xml 불변식 실측 검증.
5. S1/S5를 정규화 WK00로 지향(소규모 파라미터화) 또는 S-ingest가 S1/S5 산출물 직접 생성.
- 장: 풀-피델리티·정합 HIGH·재사용 HIGH(차기 주차)·신규 복잡성 1개 프런트 모듈에 격리(검증된 tail 무변경, 절대기준2). 단: 임베드/drawing2 + PDF분할 vision = MED 빌드 리스크.

### 옵션 비교 요지
| | 품질 | 정합 | 재사용 | 리스크 |
|---|---|---|---|---|
| A 최소 | 中(번호만) | 中(image체크 공허) | 低 | 빌드低/품질부채中 |
| **B normalize-to-WK00** | **高(풀)** | **高** | **高** | 빌드中(격리) |
**권고 = B.** 근거: 주인님 완전자동화+재사용(f), 절대기준1 품질. 리스크 완화: poppler CLI(무의존성)·카드앵커 분할수·drawing2 불변식 사전 실측·S1–V tail 무변경. 분할(b)=split, spine(c)=card-사업자번호, WK00(d)=셀골격 보존·미디어 교체.

### 가역성/CCP (g)
입력 불변 · 정규화 WK00은 output(파생물) · 수정 스크립트 .bak · harness S0가 research/ 매 fresh run 정리 · git 미접촉. 대규모/신규범위 → 빌드 전 master+§5+주인님 승인 필수.

---

## ★ 설계 정정 v2 (master 실측 정정 반영 — read-only 검증 완료)
master 정정: **표준 프로세스 자체가 "사용자가 standalone 영수증을 WK00 xlsx에 임베드"**다(실측: WK20=18·WK21=18·WK22=14 media, WK23=6 스테일만). ⇒ **gap = 분류가 아니라 INGESTION(임베드 자동화)**. 즉 Option B는 "신규 침습 능력"이 아니라 **과거 매주 수동으로 하던 임베드 단계의 자동화**이며, 목표 산출물(실영수증 임베드 WK00)은 **WK10–22에서 13주간 검증된 정확한 형상** → S1–V tail 무변경 보장. (B 권고 더 강화, 리스크 하향.)

**분류는 이미 작동(gap 아님) — store-db 실측:**
- 119-81-00851 스팟마트 → DINNER (obs 14) · 341-81-00540 까치화방 → TRAVEL (obs 3) · 220-81-15770 폴바셋 → STAFF7/TRAVEL36/DINNER1 (obs 44, conf 0.82<0.85 = ambiguous-zone → hc≥3이면 TRAVEL, 아니면 T3 = 설계대로 escalation).
- **116-81-19948 세외수입 KICC = 유일 신규가맹점** → T3-unseen escalation 1건(주인님 섹션 확인). 이전 "cold-start 다수" 우려 철회.

**통행료 = 1급 표준 경로(별도 설계 불요):** verify_toll_integrity.py가 기간별 사용내역(=주인님 PNG)을 ocr-results `parking_tolls.toll_history`로 검증(docstring·L57 확인), cell-mapping Toll-Go/Back/Parking(PRD §8) 존재. 통행료 PNG는 표준 toll 경로로 흐름.

**정정 후 설계 초점(단일 능력):** standalone WKww 영수증파일(PDF 페이지분리+PNG)을 **WK00 xl/media 섹션앵커 임베드**(주: 풀-피델리티, 표준형상) [또는 research/images 스테이징 = 최소 fallback]로 자동 정규화. 나머지(분류·통행료·write_excel·verify)는 검증완료 무변경.
- 임베드 시 주의: drawing2.xml=Receipt시트 불변식 유지 · generate_annotations 미니멀 가드(w≥200·h≥100) 통과하도록 분할 영수증 해상도 확보.

## 승인 게이트 (빌드 전)
master 검증 → §5 gemini·codex 변증 → **주인님 승인** → 그 후에만 빌드 착수.
