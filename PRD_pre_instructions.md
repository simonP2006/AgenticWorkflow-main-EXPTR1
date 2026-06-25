# Expense Report 자동화 시스템 - PRD 사전 지침서

---

## [목적]
expense report(회사 실비정산 문서) 작성을 자동화하는 에이전틱 워크플로우 오토메이션 시스템을 만들고 싶다.

---

## [Excel의 위치와 구성]

1. 원본 Excel file의 위치와 이름은 `/raw-data/input/WK**_2026/simon_park_T&E_WK00_2026.xlsx` 이다.  
   이 파일의 내용은 변경하면 안되고, 읽기만 해야 한다. (read only)  
   `**`는 정산하는 주차(week)의 숫자이고 내가 만들어 놓는다.  
   > ※ 주석: 폴더명의 `**`는 실제 주차 번호로 변경되지만(예: `WK08_2026`), 파일명의 `00`은 의도적으로 고정값 `00`을 유지한다. 이는 원본 입력 파일의 템플릿 네이밍 규칙이다.  
   > 예시: 2026년 8주차 → `/raw-data/input/WK08_2026/simon_park_T&E_WK00_2026.xlsx`

2. 작업할 Excel file의 위치는 `/raw-data/output/`이고,  
   `/raw-data/input/WK**_2026/simon_park_T&E_WK00_2026.xlsx`를 `/raw-data/output/`에 copy한다.

3. `/raw-data/output/simon_park_T&E_WK00_2026.xlsx`에는 총 5개 Sheet가 있다.  
   5개의 Sheet 중에 Claude가 기입할 수 있는 3 Sheet는 **FORM, Mileage log, Receipt**이다.

4. Receipt Sheet에는 `* PARKING /TOLLS`, `DINNER`, `[A] TRAVEL BUSINESS/ENTERTAINMENT`, `[F] STAFF MEETINGS`, `* TELEPHONE - LOCAL`로 총 5개 섹션이 있다.

5. 각 섹션에는 다양한 영수증 사진이 배치되어 있다. 매 주마다 이 영수증의 종류와 개수는 달라진다. 휴가와 주말인 경우 영수증이 없을 수 있다.

6. 각 섹션 이름 아래에 Summary table이 섹션의 목적에 맞게 각기 다른 형태로 있다.

---

## [절대적 기준]

`/raw-data/output/simon_park_T&E_WK00_2026.xlsx`의 각 Sheet 모든 cell은 내가 지정한 구역의 cell들 또는 cell만 변경할 수 있다.  

#FROM Sheet
[내가 지정한 구역의 cell]
K8
E24, F24, G24, H24, I24
E39, F39, G39, H39, I39
E46, F46, G46, H46, I46
B62, B63, B64, B65, B66, B67, B68
C62, C63, C64, C65, C66, C67, C68
D62, D63, D64, D65, D66, D67, D68
N62, N63, N64, N65, N66, N67, N68
U62, U63, U64, U65, U66, U67, U68
B95, B96, B97, B98, B99, B100,B101
C95, C96, C97, C98, C99, C100,C101
D95, D96, D97, D98, D99, D100,D101
N95, N96, N97, N98, N99, N100,N101
U95, U96, U97, U98, U99, U100,U101

#수식 무결성 원본
`/raw-data/simon_park_T&E_WK00_2026_ORG.xlsx`의 FORM Sheet A1:AH113 범위의 모든 수식은,
위 86개 cell을 제외하고 보존되어야 한다. §17-2에서 검사 및 복원한다.

#그 외 cell의 내용, 사진 자체, 사진의 위치 등 모든 data는 나의 허락 없이 일체 변경하지 말라.

---

## [인간의 수작업 순서]

### 1. 작업 파일 준비
`/raw-data/output/simon_park_T&E_WK00_2026.xlsx`을 대상으로 작업을 시작한다.  
이 파일은 5개의 Sheet를 가지고 있다. Sheet들의 이름은 **FORM, Mileage log, Receipt, Approval, Instructions and Tips**이다.

---

### 2. Receipt Sheet: PARKING /TOLLS 섹션 - 기준 영수증 확인
영수증은 항상 "기간별 사용내역"이다. 이 영수증은 고속도로 통행료 영수증이다.  
이 영수증은 이 Excel Sheet에서 가장 기준이 되는 영수증이며, 월요일부터 일요일까지의 통행료 내역이 표시된다.

---

### 3. Receipt Sheet: PARKING /TOLLS 섹션 - 날짜 기억
"기간별 사용내역" 영수증의 첫 번째 "거래일시"를 기억한다.

---

### 4. FORM Sheet: FOR WEEK ENDING 기입
기억한 "거래일시"를 참고해서 "FOR WEEK ENDING"이라는 이름의 cell 옆에 오른쪽 2번째 **K8 cell**에 거래일시가 있는 주(week)의 일요일 날짜를 `YYYY/MM/DD` 형태로 변환하여 가장 먼저 기입한다.

---

### 5. FORM Sheet: N8 cell 숫자 기억
K8 cell에 기입이 완료되면 N8 cell의 숫자가 바뀐다. N8 cell의 숫자를 기억한다.

---

### 6. FORM Sheet: G2 cell 문자열 수정
기억한 N8 cell의 숫자를 G2 cell의 문자열  
`"MAGNUM7H cHBM4E/sHBM4E WS PROJECT FOR SAMSUNG (LCL **WK)"`의  
`**`를 앞서 기억한 N8 cell의 숫자로 바꾼다.  
만약 숫자가 한 자리 숫자이면 앞에 0을 붙여준다.  
예) 8 → 08

---

### 7. Receipt Sheet: PARKING /TOLLS 섹션 - Summary table 기입
Summary excel table로 돌아와서 "기간별 사용내역" 영수증의 "거래일시"를 보고  
각 날짜의 Toll-Go, Stop-over, Toll-Back 아래에 있는 cell들에  
"기간별 사용내역"의 "거래금액"을 기입한다.

---

### 8. Receipt Sheet: PARKING /TOLLS 섹션 - 상세 기입 규칙

(1) "PARKING/TOLLS" 문구 바로 아래, 왼쪽에는 5일분 excel table이 있다.  
(2) "PARKING/TOLLS" 문구 바로 아래, 오른쪽에는 "기간별 사용내역" 사진이 있다.  
(3) "기간별 사용내역"의 거래일시를 보고 시간대별로 다음과 같이 table에 기입한다.  
(4) 해당일 첫 번째 시간 = Toll-Go 
(5) 해당일에 세 번째 시간이 있으면, Stop-over = 두 번째 시간, Toll-Back = 세 번째 시간. 
(6) 해당일에 두 번째 시간까지만 있으면, Stop-over = null, Toll-Back = 두 번째 시간.   
(7) "기간별 사용내역" 영수증 아래에 다음 섹션 시작 전까지 추가 사진이 있다면, 이것은 주차 "영수증" 사진이다.  
    "영수증"의 "진입일시"를 보고 table의 Parking에 해당 영수증의 신용카드 "결제금액"을 기입한다.

---

  ### 8-1. Receipt Sheet: 영수증 기반 작업의 대원칙               

  (1) §9(DINNER), §10(STAFF MEETINGS), §11(TRAVEL) 섹션의 모든 작업은 **Receipt Sheet에 실제로
  존재하는 영수증 사진**을 기준으로만 수행한다.
  (2) 카드 승인 내역에는 있지만 Receipt Sheet에 영수증 사진이 없는 거래는 해당 섹션의 excel table에
  기입하지 않는다.
  (3) 카드 승인 내역과 영수증의 대조는 §18에서 별도로 수행한다. §9-§11 단계에서는 오직 영수증
  사진만이 데이터 입력의 근거이다.

---

### 9. Receipt Sheet: DINNER 섹션

(1) "DINNER" 문구 바로 아래 excel table이 있다.  
(2) 위 excel table 바로 아래부터 다음 섹션 시작 전까지 영수증들이 있다.  
(3) 이 영수증들의 날짜와 시간을 보고 다음 기준으로 신용카드 "결제금액"을 기입한다.
   - 시간 < 11:00 AM → Breakfast cell
   - 11:00 AM ≤ 시간 < 5:00 PM → Lunch cell
   - 5:00 PM ≤ 시간 ≤ 11:59 PM → Dinner cell

---

### 10. Receipt Sheet: STAFF MEETINGS 섹션
(1) "STAFF MEETINGS" 문구 바로 아래 excel table이 있다.  
(2) 위 excel table 바로 아래부터 다음 섹션 시작 전까지 영수증들이 있다.  
(3) 각 영수증의 [가로'영수증 가로길이' x 세로'영수증 밑부터 1~10칸']의 넓이 이내의 cell안에 이름과 소속이 기입되어 있다. 이름의 개수(본인 "me" 포함)를 count하고, 각 영수증의 일시를 보고 해당 excel table의 how many의 cell에 해당 count값을 기입한다.
(4) 영수증 밑에 이름이 기입되어 있지 않은 경우, how many에 인원수는 0을 기입한다.
(5) 각 영수증의 일시를 보고 신용카드 결제금액을 excel table의 cell에 기입한다.  
(6) 간혹, 같은 날짜에 영수증이 2장이 있을 수 있다. 각 일자별로 1st/2nd라는 이름으로 cell이 2개 있다. 각각 시간이 빠른 순서대로 기입한다.  
(7) 영수증이 2장인 경우 인원수는 2장의 인원을 합산하여 how many의 cell에 기입한다.  
(8) 각 날짜별 영수증마다 기입한 이름을 나중에 FORM Sheet의 STAFF MEETINGS의 table 작업에 활용해야 하므로 날짜별로 누구,누구인지 database화해서 기억해 놓는다.  
(9) 만약 영수증이 2장인 경우, 중복되는 이름은 빼고 날짜 기준으로 이름들을 기억해 놓는다.

### 10-1. FROM Sheet의 [F] STAFF MEETINGS 설정
(1) FROM Sheet의 [F] STAFF MEETINGS 의 NO. OF PAX cell에는 해당 날짜의 총 참석 인원수(본인 포함)를 기입한다. 
    이 값은 Receipt Sheet의 해당 날짜 how many 값과 반드시 동일해야 한다.
(2) Receipt Sheet의 STAFF MEETINGS 섹션의 excel table의 해당날짜의 how many와 같은 인원수를 FORM Sheet의 [F] STAFF MEETINGS의 해당 날짜 NO. OF PAX  cell에도 기입한다.

---

### 11. Receipt Sheet: TRAVEL BUSINESS/ENTERTAINMENT 섹션
(1) "STRAVEL BUSINESS/ENTERTAINMENT" 문구 바로 아래 excel table이 있다.  
(2) 위 excel table 바로 아래부터 다음 섹션 시작 전까지 영수증들이 있다.  
(3) 각 영수증의 [가로'영수증 가로길이' x 세로'영수증 밑부터 1~10칸']의 넓이 이내의 cell안에 이름과 소속이 기입되어 있다. 이름의 개수(본인 "me" 포함)를 count하고, 각 영수증의 일시를 보고 해당 excel table의 how many의 cell에 해당 count값을 기입한다.
(4) 영수증 밑에 이름이 기입되어 있지 않은 경우, how many에 인원수는 0을 기입한다.
(5) 각 영수증의 일시를 보고 신용카드 결제금액을 excel table의 cell에 기입한다.  
(6) 간혹, 같은 날짜에 영수증이 2장이 있을 수 있다. 각 일자별로 1st/2nd라는 이름으로 cell이 2개 있다. 각각 시간이 빠른 순서대로 기입한다.  
(7) 영수증이 2장인 경우 인원수는 2장의 인원을 합산하여 how many의 cell에 기입한다.  
(8) 각 날짜별 영수증마다 기입한 이름을 나중에 FORM Sheet의 TRAVEL BUSINESS/ENTERTAINMENT의 table 작업에 활용해야 하므로 날짜별로 누구,누구인지 database화해서 기억해 놓는다.  
(9) 만약 영수증이 2장인 경우, 중복되는 이름은 빼고 날짜 기준으로 이름들을 기억해 놓는다.

### 11-1. FROM Sheet의 [F] TRAVEL BUSINESS/ENTERTAINMENT 설정
(1) FROM Sheet의 [F] TRAVEL BUSINESS/ENTERTAINMENT 의 NO. OF PAX cell에는 해당 날짜의 총 참석 인원수(본인 포함)를 기입한다. 
    이 값은 Receipt Sheet의 해당 날짜 how many 값과 반드시 동일해야 한다.
(2) Receipt Sheet의 TRAVEL BUSINESS/ENTERTAINMENT 섹션의 excel table의 해당날짜의 how many와 같은 인원수를 FORM Sheet의 [F] TRAVEL BUSINESS/ENTERTAINMENT의 해당 날짜 NO. OF PAX  cell에도 기입한다.

---

### 12. Receipt Sheet: TELEPHONE - LOCAL 섹션

(1) "* TELEPHONE - LOCAL" 문구 바로 아래 excel table이 있다.  
(2) excel table 밑에 통신요금 영수증이 있다.  
(3) 영수증의 *월 이용요금이 현재 월과 맞으면 "결제금액"을 excel table에 기입한다.  
(4) 현재 월과 맞지 않는 경우, 영수증 없음으로 처리한다(→ 항목 13 규칙 적용).

---

### 13. Receipt Sheet: TELEPHONE - LOCAL 섹션 - 금액 계산 규칙

(1) 영수증이 있을 때는 영수증 금액의 80%의 금액이 기입되어야 한다.  
(2) 영수증이 없을 때(현재 월 불일치 포함)는 `=0*0.8`로 한다.

---

### 14. FORM Sheet: [A] TRAVEL BUSINESS/ENTERTAINMENT - 이름 기재 규칙

[A] TRAVEL BUSINESS/ENTERTAINMENT의 NAMES AND COMPANY AFFILIATION OF PERSONS ATTENDING에 기입된 이름들을 보면 이름별로 그의 소속이 무조건 붙어 있다.  
같은 소속의 이름이 여러 개이면 여러 개의 이름을 먼저 나열하고, 나중에 그들의 소속을 한 번만 기입하도록 한다.

**좋은 예:**  
Mr.Park Gunwoo who is an engineer of Samsung HBM PE and Mr.Kim Kijung, Mr.Woo Seockwon, Mr.Lee Jungmin who are the engineers of Teradyne and me.

**나쁜 예:**  
Mr.Park Gunwoo who is a member of Samsung HBM PE and Mr.Kim Kijung who is a member of Teradyne and Mr.Woo Seockwon who is a member of Teradyne and Mr.Lee Jungmin who is a member of Teradyne and me.

---

### 15. FORM Sheet: 빈 열(column) 처리

(1) [A] TRAVEL BUSINESS/ENTERTAINMENT의 AMOUNT에 금액이 없는 열(column)의 모든 셀 값을 지워서(clear) 모두 빈칸(null)이 되어야 한다. 
(2) [F] STAFF MEETINGS의 AMOUNT에 금액이 없는 열(column)의 모든 셀 값을 지워서(clear) 모두 빈칸(null)이 되어야 한다. 

---

### 16. Mileage log Sheet: 거리 기입 규칙
"기간별 사용내역"의 해당 날짜 톨 기록을 **전부** 순회하면서, 각 기록의 입구/출구를 아래 규칙 (1)-(6)에 대조하여 실행한다. 
하루에 톨 기록이 3건 이상일 수 있다 (경유 패턴: Go + 경유 + Back).          
  (1) "기간별 사용내역"에서 해당 날짜의 입구가 "수원신갈"이고 출구가 "기흥동탄"이면                   
      → Mileage log Sheet 해당 날짜 Distance 첫 번째 cell에 **20** 기입                               
  (2) "기간별 사용내역"에서 해당 날짜의 입구가 "서울"이고 출구가 "기흥동탄"이면                       
      → Mileage log Sheet 해당 날짜 Distance 첫 번째 cell에 **42** 기입                               
  (3) "기간별 사용내역"에서 해당 날짜의 입구가 "기흥동탄"이고 출구가 "수원신갈"이면                   
      → Mileage log Sheet 해당 날짜 Distance 두 번째 cell에 **20** 기입                               
  (4) "기간별 사용내역"에서 해당 날짜의 입구가 "기흥동탄"이고 출구가 "서울" 또는 "성남"이면           
      → Mileage log Sheet 해당 날짜 Distance 두 번째 cell에 **42** 기입
  (5) "기간별 사용내역"에서 해당 날짜의 입구가 "기흥동탄"이고 출구가 "서수지" 또는 "금토"이면
      → Mileage log Sheet 해당 날짜 Distance 두 번째 cell에 **42** 기입
  (6) "기간별 사용내역"에서 해당 날짜의 입구가 "-"이면 무시(continue / skip)한다.
  (7) 해당 날짜에 출근 톨 기록만 있고 퇴근 톨 기록이 없는 경우(= Distance 첫 번째 cell에 값이 있으나 두 번째 cell이 비어있는 경우) 
      → 두 번째 cell에 첫 번째 cell의 값을 복사하여 기입한다.

  ※ 경유 패턴 예시: 수원신갈→기흥동탄(960) + 기흥동탄→서울(2100) + -→성남(400) 인 경우
     → (1)에 의해 첫 번째 cell = 20, (4)에 의해 두 번째 cell = 42, (6)에 의해 세 번째 기록은 무시.
---

### 17. Receipt Sheet의 excel table 위치 database화 FROM Sheet의 cell 수식 확인
(1) Receipt Sheet의 excel table들의 cell들 위치는 영수증을 많이 넣다보면 변경될 수 있으므로 이들의 각 위치를 database화 한다.

(2)Receipt Sheet의 excel table들의 cell들 위치 database가 FROM Sheet의 기입해야 하는 cell위치와 일치하는지 확인해야 한다.
예: FROM Sheet의 * TELEPHONE - LOCAL의 E46 cell가 바라보는 Receipt Sheet의 cell위치는 "=Receipt!A602"로 되어 있는데, * TELEPHONE - LOCAL 섹터의 excel tabel의 data위치는 A601에 있다.

---

### 17-1. Receipt Sheet: 영수증 사진 위치 및 이름 검색 규칙

(1) 영수증 사진의 위치(row, column)는 매주마다 다를 수 있다.
    영수증의 위치는 매주 Excel의 drawing XML에서 동적으로 읽어야 하며, 특정 row/column을 고정값으로 가정하면 안 된다.

(2) 각 영수증 밑에 기입된 이름의 검색 범위는 다음과 같다:
    - 가로: 해당 영수증 사진의 가로 길이 (from_col ~ to_col)
    - 세로: 해당 영수증 사진이 끝나는 위치(to_row)부터 아래 10칸

---

### 17-1-1. Receipt Sheet: 인원 이름 Database 범위 규칙     
(1) Receipt Sheet 하단에 인원 이름 Database가 있다.
    Row 999에 소속(회사명) 헤더가 있고, Row 1000부터 이름이 시작된다.
(2) 이름의 마지막 행은 매주 달라질 수 있다 (인원 추가/삭제에 따라 행 수가 변동).
    Row 1000부터 시작하여, 모든 열(A, D, G)이 비어있는 행이 나올 때까지를 이름 Database 범위로
  한다.
    특정 행 번호(예: 1006)를 고정값으로 가정하면 안 된다.

---

### 17-2. FORM Sheet: 수식 무결성 검사 및 복원 (§18 진입 전 필수)
   
(1) `/raw-data/simon_park_T&E_WK00_2026_ORG.xlsx`의 FORM Sheet를 수식 원본(Source of Truth)으로 사용한다. 
    이 파일의 FORM Sheet A1:AH113 범위에서 모든 수식 셀을 추출하여 database화한다.

(2) database화된 수식 셀에서 [절대적 기준]의 [내가 지정한 구역의 cell] 86개를 제외한 나머지를 "보존 필수
  수식 목록"으로 정의한다. 
    이 목록의 수식은 어떤 단계에서도 변경되거나 삭제되어서는 안 된다.

(3) §18 단계 진입 직전에, 작업 중인 `/raw-data/output/simon_park_T&E_WK00_2026.xlsx`의 FORM Sheet를
   "보존 필수 수식 목록"과 대조하여 검사한다.
    - 수식 누락(None): 원본 수식으로 복원한다.
    - 수식 불일치: 원본 수식으로 복원한다.
    - 정상: 아무것도 하지 않는다.

(4) 복원이 발생한 경우, 복원된 셀 목록(셀 주소, 원본 수식)을 로그로 출력한다.

(5) 검사 결과 누락 0건·불일치 0건이면 "수식 무결성 검사 통과"를 출력하고 §18로 진행한다.

---

### 18. FORM Sheet: 카드 승인 내역 대조 및 "KRW" 접두어 기입

(1) `/raw-data/input/카드승인내역_YYYYMMDD.xlsx`의 "승인날짜"와 "승인시간"별로 있는 "거래금액"을 추출하여 database화한다.

(2) database화 한 해당 날짜와 시간별 거래금액이  
    `/raw-data/output/simon_park_T&E_WK00_2026.xlsx`의 아래 항목들과 일치하는지 한 줄씩 전부 확인한다.
   - FORM Sheet의 excel table: DINNER의 E24, F24, G24, H24, I24), * BUSINESS/ENTERTAINMENT[A]의 U62~U69, * STAFF MEETING [F]의 U95~U99

(3) 비교한 금액이 일치하면, FORM Sheet의 해당 금액 앞에 `KRW ` 를 붙여준다.  
    (주의: 큰따옴표`"`까지 붙이면 안 됨. `KRW ` 뒤의 공백 1칸 포함)

(4) 마지막으로 `/raw-data/output/simon_park_T&E_WK00_2026.xlsx`의 파일 이름을  
    `/raw-data/output/simon_park_T&E_WK**_2026.xlsx`로 바꾼다.  
    (기억한 N8 cell의 숫자로 `**`를 치환. 한 자리 숫자이면 앞에 0을 붙인다. 예: 8 → 08)

(5) FROM Sheet의 * PARKING /TOLLS의 column(줄)의 cell(E39, F39, G39, H39, I39)에 금액이 있을 경우(= null이 아닌 경우), 예외적으로 앞에 'KRW' 를 붙여준다.

(6) FORM Sheet의 * TELEPHONE - LOCAL의 column(줄)의 cell(E46, F46, G46, H46, I46)에 금액이 있을 경우(= null이 아닌 경우), 예외적으로 앞에 'KRW' 를 붙여준다.
  
---

### 19. Red Dotted Rectangle 구현 방식 제약

(1) 영수증 **원본 사진을 직접 수정하는 것은 금지**한다.
사진 위에 투명한 빨간 점선 도형을 겹쳐 놓는 방식이어야 한다.

(2) 원본 Excel(`WK00`)의 Receipt Sheet "* PARKING /TOLLS" 섹션 excel table 아래에 미리 만들어둔 **Red Dotted Rectangle 도형**이 있다. 
    이 도형을 **복사(copy)**하여 각 영수증 사진 위에 위치시킨다.                                                   

---

### 20. Receipt Sheet: 모든 영수증 사진 대상 - Red Dotted Rectangle 표시

모든 영수증 사진에 빨간 점선 사각형 표시(Red Dotted Rectangle)를 다음과 같이 표시한다.

(1) **PARKING/TOLLS**  
    "기간별 사용내역" 영수증의 날짜별 Group 구분

(2) **DINNER**  
    각 영수증의 일시(YYYY MM DD HH MM SS)와 결제금액

(3) **STAFF MEETINGS**  
    각 영수증의 일시(YYYY MM DD HH MM SS)와 결제금액

(4) **TRAVEL BUSINESS/ENTERTAINMENT**  
    각 영수증의 일시(YYYY MM DD HH MM SS)와 결제금액

(5) **TELEPHONE - LOCAL**  
    통신요금명세서 안의 이름(박종진), 전화번호(010-23**-99**), *월 이용요금, 결제금액

---

### 21. Red Dotted Rectangle 정밀도 기준

(1) Red Dotted Rectangle을 영수증에 위치시키는 작업은 ###20에서 지정된 영수증의 정보 위에 사각형의 가로/세로 라인과 글자의 간격이  1mm이내로 위치하도록 정밀하게 작업해야 한다. 
 
(2) 이 정밀 작업은 너의 능력에 위임한다. 토큰과 시간의 자원을 고려하지 말고 작업하라.   

---

*문서 끝*
