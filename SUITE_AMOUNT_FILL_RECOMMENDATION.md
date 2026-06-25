# 권고: expensereceipt 스위트 영구 통합 — 금액-fill 단계 + cell-occupancy 게이트 (option D/Z)

> Status: **권고만 — 미구현.** 주인님 기상 후 결정(master 지시). WK23 실 정산은 본 권고와 별개로 (X) openpyxl add_image로 완료됨.
> 근거 전문: [[ROOT_CAUSE_AND_FIX_WK23_AMOUNTS.md]] · 진단 Workflow `wkmskc4qh`.

## 문제 (WK23에서 노출된 구조적 결함)
expensereceipt 스위트(orchestrator: extract→merchant→classify→verify-LOGICAL→place→verify-PHYSICAL→db)에 **금액을 워크북 셀에 기입하는 단계가 없다.** place는 이미지만 주입(`<pic>`), 금액은 in-memory dict·-db 원장에만 존재. → 산출물 0원 정산. 4계층 검증도 **셀 점유를 검사하지 않아** 못 잡음.

## WK23 임시 해결(이번 실행)
- 금액: 레거시 `scripts/write_excel.py --all` 재사용(63셀: 9 영수증금액+headcount+FORM KRW+attendee roster+Mileage+week label). = method (i).
- 이미지: openpyxl `add_image` (= option X). 이유: openpyxl 금액기입이 Receipt placeholder drawing을 드롭→스위트 surgical-zip place와 **합성 불가**(place가 Instructions 시트에 오배치). openpyxl add_image는 같은 워크북 내에서 Receipt drawing을 재생성하므로 합성됨.
- ★이 두 레거시 도구 조합은 **WK23 1회용**. 스위트에 영구 통합 안 됨.

## ★영구 통합 권고 (option Z/D — 재하드닝 필요)
스위트가 자체적으로 금액을 기입하려면 **surgical 금액-fill 단계**가 필요하다(openpyxl은 surgical place와 합성 불가하므로):

1. **신규 sub-skill 또는 place 확장 `expensereceipt-fill`** (det):
   - 입력: classify 산출 receipts(섹터·금액·날짜·인원) + store-db.
   - 출력: 템플릿의 Receipt/FORM 입력셀에 금액·인원·요일컬럼·telephone×0.8·toll Go/Back·KRW·week K8 기입.
   - ★**surgical 방식**(zip 셀 XML 직접 편집·inline value/string)으로 drawing 구조 보존 → 이후 surgical place와 합성 가능. (openpyxl 금지 — drawing 재번호 회피.)
   - 또는: write_excel.py의 셀-매핑 로직을 PORT하되 surgical 출력으로 변환.

2. **orchestrator 배선**: classify PASS 후 → fill → verify-LOGICAL → place → verify-PHYSICAL. (fill을 place 前에.)

3. **신규 검증 게이트 `cell-occupancy + total-reconciliation`** (verify에 추가):
   - 각 영수증 매핑 셀이 비어있지 않고 기대값 일치(TRAVEL/DINNER raw·TELEPHONE ×0.8·toll 1/2/3 규칙).
   - pure-python 기대총액 == FORM!M52 (openpyxl 미재계산 → cached==None이므로 M52 **공식 보존**만 체크 + pure-python 총액 assert. ★Σ셀==M52 cached 금지: false-FAIL).
   - PARKING SUM셀(F6/F10..) `=SUM` 공식 보존.
   - pic ≥ 영수증수 & Receipt 시트(drawing2) 배치 확인.
   - PNG 무손실(embedded dims==source).
   ⟹ 이미지 정상+금액 빈 워크북이 결정론적 FAIL(WK23 재발 봉쇄).

4. **재하드닝**: 신규 fill 단계 + 게이트 = 적대검증(§5)·10-fresh-prompt 게이트·머지·머지검증(HARDENING 캠페인 패턴) 필요. = 대공사.

## DNA 유전 함의
이 결함은 자식 시스템에 유전되면 안 됨 — workflow-generator/DNA에 "산출물 셀 점유 검증(L2.5)" 추가 권고.
