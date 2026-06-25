# EXPENSERECEIPT 스킬 — 빌드 계약서(설계-SPEC) · 명령8 · 2026-06-20

> ★이 문서 = grill-me로 **주인님과 완전 합의된 설계의 SOT**. /clear 후 fresh master가 이걸 읽고 → 주인님 "승인/빌드" → 이 설계 그대로 빌드. **빌드 전엔 산출물 0**(ABSOLUTE ANCHOR #4).
> 상태: **설계 locked·가정 6건 전부 확인·빌드 미착수·주인님 승인 대기.**
>
> **[Changelog] 2026-06-20 — G7 설계편차 (정직화, §6-b)**: insert-row(formula-aware row shift)는 **미구현·fail-loud**(`insert_rows_lxml`가 `InsertRowsNotImplemented` raise). 사유: 템플릿의 1555개 formula에 대한 원자적 row shift(`<row r>`+`<c r>`+`<f>`+`mergeCells`+drawing anchor 동시 이동)는 천장폭발 risk이며 부분 shift는 침묵 desync를 유발(M6 적대검증서 확정). **주전략 = 템플릿의 pre-sized 섹터밴드**(삽입 불필요), true overflow 시 → `plan_insert_rows` ESCALATE → master 결정(pre-sizing vs hybrid). 본 편차는 §1 place 행·§5 배치규칙에 반영. master 승인·주인님 통지 대상. (surgical `<pic>`-injection 배치 자체는 실측 검증됨 — 그건 사실.)

## 0. 목적 (1문장)
`~/WKww_YYYY/` 폴더의 영수증을 1장씩 판독(가게/날짜/금액/인원/맨밑필기)→ per-receipt DB 적재 → 6섹터 규칙분류 → Receipt Sheet에 3개/줄 배치하는, **EXPTR1 전용·본인전용·자기학습형** 클로드 스킬 스위트(**1 대표 + 6 하위**).

## 1. 아키텍처 = 1 대표 + 6 하위 (전부 prefix `expensereceipt-`)
| 스킬 | 책임 | 엔진 |
|---|---|---|
| **`expensereceipt`** (대표·model-invocable·유일 대화창) | 오케스트레이션 · ★orchestration trace(발동마스터 cycle / 호출 sub 순서·시점 / sub별 산출 분리 / 마스터 synthesis 4섹션) · master-owned SOT 단독작성 · 주인님 상호작용(이름선택·필기확정·escalation) | LLM |
| `expensereceipt-extract` | `~/WKww_YYYY/` 폴더의 PDF/이미지 자동감지·1장씩 분할 + 전처리(deskew/회전/thermal보정) + vision OCR(가게/날짜/금액/**인원**/**사업자번호**) + **맨밑 필기판독**(갤러리 few-shot) · multi-read 3→7 투표(EXPTR1 aggregate_ocr_votes 이식, identity키=(date,amount)·time제외) · raw필드만 | LLM+det |
| `expensereceipt-merchant` | **사업자번호 10자리 NTS 체크섬 검증** + merchant키 + 가게명 정규화 (★EXPTR1 미활용=최대 정확도 업그레이드; k-skill:nts-business-registration 옵션) | det |
| `expensereceipt-classify` | 6섹터 규칙엔진(§2). 결정론 트리거 + Dinner 가게명 LLM확률 + STAFF/TRAVEL 이름 **주인님+DB 선택** | det+LLM+human |
| `expensereceipt-verify` ★필수(ANCHOR #2a) | 반환각 게이트: 사업자번호 체크섬·카드(date,amount)대조·**항목합==카드금액**·금액≠0·필기신뢰·multi-read합의·규칙정합. read-only·결정론·producer 룰 IMPORT(재구현 금지). 실패시 재read(플래그분만·max2)→주인님 escalation·silent winner-pick 금지 | det |
| `expensereceipt-place` | Receipt Sheet 배치: 섹터별 3개/줄·줄채우면 아래로(템플릿 pre-sized 섹터밴드 내)·true overflow 시 master ESCALATE(insert-row=formula-aware shift **미구현·fail-loud**, 상단 changelog). ★**surgical direct-zip**(openpyxl 금지=anchor파괴 실증)·twoCellAnchor(from+to)·drawing rels·EXPTR1 write_excel 배치로직 이식 | det |
| `expensereceipt-db` | per-receipt 원장(§3) + **필기 자기학습 갤러리**(§4) + 분류학습DB(가게→Dinner / 가게+요일+시간→이름후보) | det |

> 하위 6개: `disable-model-invocation:true` · ~500토큰 desc(★Claude 1024자 상한과 충돌 → 빌드시 reconcile: 본체는 SKILL.md로) · 3-layer desc(TLDR/Triggers/Methodology) · foresight-env-scan authoring-spec 계약 + EXPTR1 절대기준 게놈 "## Inherited DNA" 상속.

## 2. 6섹터 분류 규칙 (우선순위 순)
1. **PARKING/TOLLS** ← 영수증명 "기간별 사용 내용"(통행료내역) [결정론]
2. **TELEPHONE-LOCAL** ← 영수증명 "T world" [결정론]
3. **맨밑 필기 트리거(최우선)** [필기판독=LLM+갤러리, 라우팅=결정론]:
   - "dinner alone" → **Dinner**
   - Teradyne 직원 한글이름 → **STAFF MEETING**
   - SAMSUNG EDS 또는 HBM-PE 한글이름 1명이상 → **TRAVEL BUSINESS/ENTERTAINMENT**
4. **필기 없을 때 규칙**:
   - **Dinner**: 17:50後 + **1인분(=1)** + 1인 식사식당(밥/면/샌드위치)이나 편의점 음식 → 과거DB 가게명기반 LLM확률 → Dinner
   - **STAFF**: (a) 이미 Dinner 1개 등록+Dinner조건 영수증 OR (b) **≥2인분** 식사/디저트(음료포함) → DB(가게+요일+시간)기반 **Teradyne 직원이름** 주인님+LLM 선택 → STAFF
   - **TRAVEL**: (a) **≥2인분** → DB기반 **SAMSUNG EDS/HBM-PE 이름 1명** 선택 → TRAVEL  /  (b) **≥3인분** → SAMSUNG EDS/HBM-PE 1명 **+ Teradyne 1명** 선택 → TRAVEL
5. **OTHERS-LOCAL** ← 위 미해당 [결정론 fallback]
- ★STAFF↔TRAVEL 구분 = **참석자 회사**(Teradyne=STAFF / SAMSUNG EDS·HBM-PE=TRAVEL). ≥2 무필기는 본질 모호 → DB확률후보+주인님 확정으로 섹터 결정(silent 금지).
- ★인원수(인분) 추론 = **메인항목 카운트**(밥/면/음료/디저트 각1) · **옵션 제외**(사이즈업·디카페인·샷추가·휘핑·변경 등 수식어) · 검증=**항목합==카드결제금액** · 경계케이스(1인2주문/공유/세트)는 escalation.

## 3. per-receipt DB 스키마 (이중역할: 저장 + 분류참고)
`{가게, 날짜, 금액, 인원, 맨밑필기[dinner alone·이름]}` per 영수증. 쌓일수록 분류 똑똑해짐.

## 4. 필기 자기학습 (정직 메커니즘 — 모델훈련 아님)
주인님 확인한 **(필기 crop ↔ 확정텍스트)** 쌍을 **갤러리 누적** → 새 판독시 유사샘플을 **few-shot 예시**로 vision-LLM에 제공(in-context). 갤러리는 **주인님 확정으로 성장**(human-in-loop와 한 루프). → 인식률 실제 향상(예시누적 효과). "AI 재훈련"은 불가(스킬 한계)임을 명시.

## 5. 배치 규칙
섹터 cell group에 **3개씩 한 줄** 차례 나열 → 줄채우면 아래 또 3개. 배치는 템플릿의 **pre-sized 섹터밴드** 내에서 수행(primary). 아래 섹터 침범(true overflow) 우려 시 → **master ESCALATE**(insert-row=formula-aware shift는 템플릿 1555 formula 천장폭발 risk로 **미구현·fail-loud**; 상단 [Changelog 2026-06-20] 참조).

## 6. 입력 / 위치
- **입력** = `~/WKww_YYYY/` 폴더(PDF + 사진파일). EXPTR1과 동일 주차폴더 패턴.
- **위치** = `~/spJavis/AgenticWorkflow-main-EXPTR1/.claude/skills/expensereceipt*` (★project-scope=EXPTR1 전용·자동발견·disable-model-invocation 안정). ★발견신뢰성 위해 user-scope(`~/.claude/skills/`) 심볼릭 링크 or 플래그 실작동 빌드시 재검증(rename-8단계 "심볼릭링크 재생성" 커버).

## 7. EXPTR1 검증자산 재사용 (새 코드 최소)
`extract_card_data.py`(카드파싱) · `aggregate_ocr_votes.py`(multi-read투표) · `store-db.json`/`build_store_db.py`(merchant학습) · `write_excel.py`(배치) · `verify_*.py`(반환각) · `.claude/skills/wk-receipt-ocr`(OCR) · name-DB(Receipt!A999:H1007 회사사전) — 직접 갖다 씀.

## 8. 6 확정 가정 (주인님 전부 확인)
①TRAVEL오타→TRAVEL섹터(수정확인) ②이름선택=DB후보순위→주인님확정(반자동) ③입력=~/WKww_YYYY/ 폴더 PDF+사진 ④DB=저장+분류 둘다 ⑤자기학습=갤러리+few-shot ⑥≥2 무필기=DB+주인님 이름선택이 STAFF/TRAVEL 결정.

## 9. 위험 + 안전장치
필기 cold-start(갤러리 점진개선) · ≥2 STAFF↔TRAVEL(DB+주인님) · 인원 경계(escalation) · 사업자번호 추출신규 · surgical-zip 배치(openpyxl금지) · plugin disable-model-invocation 불안정→project-scope/심볼릭 · 항목합≠카드금액시 플래그 · NFD/NFC 한글파일명 정규화 · 날짜포맷 다양성(YYYY.MM.DD/YYYY년/YYMMDD).

## 10. 빌드 방식 (승인 후·전부 위임)
클린 셋업 → 워커 위임(스킬별 빌드·§5 검증·마일스톤마다 주인님 승인) → 설치/심볼릭 + **rename-8단계 검증**(grep전형태·perl치환·mv·심볼릭재생성·메모리갱신·루트시스템파일·frontmatter↔폴더명·references cross-link). master=지휘·검증만(직접코딩 금지). ABSOLUTE ANCHOR: 품질절대·반환각 전담 verify·grill-me·승인후산출.

## 11. 재개 프로토콜 (/clear 후)
fresh master: 이 스펙 정독 → 주인님께 "설계 locked·승인 대기" 보고 → 주인님 "승인/빌드" → §10 빌드 착수. (3-pane CSO/gemini/codex 재기동 §5-1. 워커지침 재생성.) **WK23·store-db 감사 등 다른 스레드는 SESSION_STATE 참조.**
