---
name: wk-receipt-ocr
description: WK 경비정산 영수증 OCR 판독 스킬. run_week.py harness가 "VISION-REQUIRED: OCR"(exit 10)로 HALT할 때, research/images/*.png 영수증 이미지를 독립적으로 N회 판독하여 research/ocr-results-{i}.json을 생성한다(적응형 3→7회 다수결, ADR-045). "WK OCR", "영수증 판독", "ocr-results 생성", harness OCR HALT 시 사용. Step 3 vision 작업의 재사용 패키지(R-B).
---

# WK Receipt OCR — Step 3 Vision (N-read 다수결)

> **호출 시점**: `run_week.py WK**_2026`가 `exit 10` + `"VISION-REQUIRED: OCR"` 메시지로 HALT할 때. 이 스킬로 OCR을 수행한 뒤 **`run_week.py WK**_2026` 재호출**하면 harness가 `aggregate_ocr_votes.py` 게이트로 진행한다.
> **계약 불변**: 이 스킬은 harness의 vision HALT 계약(exit 10)을 구현하는 LLM 측 작업이다. harness/스크립트는 수정하지 않는다.

## 목적

`research/images/`의 영수증 이미지를 판독하여 `research/ocr-results-{i}.json`(i=1,2,3,…)을 생성한다. **셀 배치·날짜 스캐폴드는 생성하지 않는다** — 그것은 `write_excel.py`(결정론)의 책임이다. 이 스킬의 본질은 **이미지 픽셀 → 텍스트(날짜·시각·금액·지명·이름·인원) 정확 판독**뿐이다.

## 절대 기준 (맥락화)

- **기준 1 (품질)**: 속도/토큰 무시. 경계 가독성 숫자는 N회 판독으로 신뢰도를 확보한다. 구겨진 감열지 한글은 의미 맥락(과세표준/공급가/결제금액 중 올바른 값 선택)으로 판독 — 전통 OCR이 못하는 영역이라 LLM vision이 본질적으로 필요(PYTHON-CONVERSION-FEASIBILITY-REPORT 근거).
- **기준 2 (SOT)**: `research/ocr-results-{i}.json`에만 쓴다. `state.yaml`·입력파일·완성 Excel을 수정하지 않는다.
- **할루시네이션 방지 (②)**: 이미지에 없는 거래를 지어내지 않는다(§8-1). 불확실하면 N회 분산으로 표면화하고, 다수결 미합의 시 escalation(추측 채움 금지).

## N-read 독립성 요건 (이것 없으면 N회가 1회로 붕괴 — ADR-045 §6)

각 판독은 **직전 결과를 참조하지 않고** 이미지를 처음부터 다시 읽는다. 기계적 복사 금지 — 실제 판독 분산이 있어야 다수결이 확률적 오류를 교정한다. 가능하면 판독 순서·표현을 회마다 미세 변주.

## 적응형 깊이 (3→7)

1. 우선 **3회** 독립 판독 → `research/ocr-results-1.json`, `-2.json`, `-3.json`.
2. `run_week.py` 재호출(또는 `python3 scripts/aggregate_ocr_votes.py WK**_2026`):
   - **CONSENSUS (exit 0)**: placement-critical 필드(톨 amount, dinner/staff/travel amount·headcount, telephone, 영수증 존재)가 만장일치 또는 강다수(support ≥ ⌈0.8N⌉, 동률 아님) → harness가 합의본을 `ocr-results.json`으로 합성 확정하고 전진.
   - **INCONCLUSIVE (harness 재HALT)**: 미해결 필드 → **2회 더** 판독(`-4`,`-5`) 후 재호출. 최대 7회.
   - **FAIL (7회 소진·미합의)**: `research/ocr-vote-report.json`이 가리키는 영수증만 재판독(최대 2회) 후 **사용자 에스컬레이션**. 체계적 오독 의심.

## 카테고리 분류 규칙

1. `research/input-manifest.json`의 섹션 위치(STAFF_MEETINGS/TRAVEL start_row 등) 기준으로 각 영수증의 섹션을 결정. **이미지 내용만으로 추측 금지.**
2. **§8-1 대원칙**: Receipt Sheet에 실제 영수증 사진이 있는 거래만 OCR에 포함. 카드 내역에만 있고 사진 없는 거래는 제외(카드 대조는 verify_week가 별도 수행).

## OCR JSON 스키마 (P0-2 — ADR-043 축소판)

```json
{
  "parking_tolls": {
    "toll_history": [{"date", "time", "entry", "exit", "amount"}],
    "parking_receipts": [{"date", "time", "amount"}]
  },
  "dinner": [{"date", "time", "amount", "store"}],
  "staff_meetings": [{"date", "time", "amount", "store", "headcount"}],
  "travel": [{"date", "time", "amount", "store", "headcount"}],
  "telephone": {"month_matches": bool, "payment_amount": N}
}
```

> `sunday_date`/`week_number`/`weekday_mapping`은 **생성하지 않는다** — `write_excel.derive_date_scaffold()`가 통행료 첫 거래일에서 결정론적으로 파생(P0-2). 톨 거래의 `date`만 정확히 판독하면 된다. `meal_type`(시각으로 재계산)·toll `direction`(미사용)도 불필요. **D-7 의도적 중복**: 이 스키마는 `WK_workflow.md`·`.claude/commands/wk.md`와 동기화 필수.

## 결합 불변식 (다수결은 정답 보증이 아니다 — 절대 기준 2)

합의본(`ocr-results.json`)은 그대로 신뢰되지 않는다. 이후 harness가 `verify_card_matching`·`verify_toll_integrity`·`derive_date_scaffold` 결정론 계층을 반드시 통과시킨다. 다수결은 **확률적 오류**를 줄이는 선행 보강이며, **체계적 오류**(N회 모두 동일 오독)의 최종 방어선은 독립 사실 대조다. 카드 미대조(톨·통신비)의 순수 체계적 오독 잔여는 영수증 원천 품질(고해상도 재촬영) 영역이다.

## 산출물 + 다음 행동

- 생성: `research/ocr-results-{i}.json` (i=1,2,3,… 적응형).
- 백업: 합의 확정 후 `research/wk**_ocr-results.json`로 백업(harness S0가 다음 fresh run에서 정리).
- **다음**: `run_week.py WK**_2026` 재호출 → harness가 aggregate 게이트 후 S4(write_excel)로 전진.

## 가역성

이 스킬은 LLM 판독 작업의 명세일 뿐 코드를 변경하지 않는다. 산출물(`ocr-results-*.json`)은 harness S0가 매 fresh run에서 삭제·재생성하므로 완전 가역.
