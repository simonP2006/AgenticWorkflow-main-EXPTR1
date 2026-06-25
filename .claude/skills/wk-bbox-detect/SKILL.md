---
name: wk-bbox-detect
description: WK 경비정산 영수증 bbox 좌표 식별 스킬. run_week.py harness가 "VISION-REQUIRED: BBOX"(exit 10)로 HALT할 때, research/annotations/wk**-images/*.png를 읽고 날짜/금액 위치의 pixel 좌표 [x1,y1,x2,y2]를 식별하여 research/annotations/wk**.json을 생성한다(PRD §20). "WK bbox", "bbox 좌표 식별", "RDR 좌표", harness bbox HALT 시 사용. Step 6 vision 작업의 재사용 패키지(R-B).
---

# WK Bbox Detection — Step 6 Vision (영수증 좌표 식별)

> **호출 시점**: `run_week.py WK**_2026`가 `exit 10` + `"VISION-REQUIRED: BBOX"` 메시지로 HALT할 때. 이 스킬로 bbox를 생성한 뒤 **`run_week.py WK**_2026` 재호출**하면 harness가 `annotate_receipts.py --check-only`(P0-1 가드)로 검증 후 S7→S8(RDR 주입)로 진행한다.
> **계약 불변**: harness의 vision HALT 계약(exit 10)을 구현하는 LLM 측 작업. harness/스크립트는 수정하지 않는다.

## 목적

`research/annotations/wk**-images/`의 각 영수증 이미지를 Read tool로 읽고, **날짜/금액 위치의 pixel 좌표** `[x1, y1, x2, y2]`를 식별하여 `research/annotations/wk**-template.json`(빈 bboxes) → `research/annotations/wk**.json`으로 채운다. **pixel→cell 변환은 하지 않는다** — 그것은 `annotate_receipts.py`(per-image anchor calibration, 결정론)의 책임이다. 이 스킬은 **pixel 좌표 찾기**만 한다.

## 절대 기준 (맥락화)

- **기준 1 (품질)**: PRD §21 — bbox 라인과 영수증 글자 간격 1mm 이내 목표. 정밀하게 텍스트 블록 경계를 식별. 속도보다 정확도.
- **기준 2 (SOT)**: `research/annotations/wk**.json`에만 쓴다. 원본 이미지·Excel·state.yaml 수정 금지.
- **할루시네이션 방지 (②)**: 지정된 대상(날짜/금액 등)만 bbox. 과다 생성 금지(MEMORY: WK09에서 LLM이 83개 과다생성한 실제 오류 — P0-1 가드가 차단).

## bbox 대상 (아래만 — store_logo·store_info·items·discount·tax_info 등 절대 포함 금지)

| 섹션 | bbox 대상 | 영수증당 bbox 수 |
|------|----------|-----------------|
| TOLLS | 날짜별 Group 구분 (행 단위) | 날짜 수만큼 |
| DINNER | 일시 + 결제금액 | **정확히 2개** |
| STAFF | 일시 + 결제금액 | **정확히 2개** |
| TRAVEL | 일시 + 결제금액 | **정확히 2개** |
| PARKING | 일시 + 결제금액 | **정확히 2개** |
| TELEPHONE | 이름 + 전화번호 + 이용요금 + 결제금액 | 4개 |

> **예상 총 bbox 수: 1주일 기준 ~25–35개. 80개 이상이면 사양 위반** — 재검토 필요.

## P0-1 결정론 가드 연계 (ADR-041)

재호출 시 harness가 `python3 scripts/annotate_receipts.py --check-only WK**_2026`를 실행한다. 이 가드는 결정론적으로 검증한다:
- DINNER/STAFF/TRAVEL/PARKING 영수증: bbox **{0, 2}개**만 허용(0=정상 스킵).
- TELEPHONE: 4/page. TOLLS: per-image ≤10. 전역 하드 상한: 총 bbox > 80 → 즉시 FAIL.
- 위반 시 harness가 `exit 1`(LOGIC)로 차단 → **이 스킬로 bbox 재작업**.

## 산출물 구조 (template에서 bboxes 채움)

`wk**-template.json`의 각 이미지 엔트리(`section`, `from_row`, `from_col`, `dims`, 빈 `bboxes`)에서 `bboxes` 배열을 `[x1, y1, x2, y2]` pixel 좌표로 채운다. template의 이미지 키·섹션을 그대로 유지(generate_annotations.py가 만든 구조).

## 정밀도 (PRD §21)

- bbox는 픽셀 좌표만. annotate_receipts.py 8-5~8-6의 **per-image anchor calibration**이 pixel→cell EMU 변환을 결정론적으로 수행(전역 그리드 불필요·cross-image xfrm 불일치 면역).
- 잔여 리스크: col A–E 비균일 구간 일부 이미지 수평 ~2mm 오차 가능(수직은 0mm).

## 산출물 + 다음 행동

- 생성: `research/annotations/wk**.json` (각 이미지 bboxes 채움).
- **다음**: `run_week.py WK**_2026` 재호출 → harness가 P0-1 가드(exit 0 확인) → S7(formula restore) → S8(RDR 주입, lxml, 최종) → V(verify_week).

## 가역성

LLM 좌표 식별 작업의 명세일 뿐 코드 미변경. 산출물(`wk**.json`)은 주차별 재생성 대상이며 harness가 관리. 완전 가역.
