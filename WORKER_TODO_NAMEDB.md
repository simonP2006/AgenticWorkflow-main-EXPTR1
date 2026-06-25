# WORKER_TODO_NAMEDB.md — EXPTR1 제2워커 (store-db 전면 감사 / 참석자 이름-DB 포함)

> 워커: EXPTR1 제2 실행 워커 (surface:7, tab "EXPTR1-name-db-audit")
> master = surface:1 / 다른 워커(WK23 ingestion) = surface:2 (불간섭)
> 정본: WORKER_DIRECTIVE.md + /tmp/exptr1_namedb_worker_directive_0620.txt + (격상)주인님 store-db 전면감사 지시
> ★WORKER_TODO.md 절대 건드리지 말 것 — 이 파일만 갱신.
> 모드: read-only 우선. 코드/데이터 변경 = master검증 + (중대·비가역시)주인님 승인 + 백업(.bak) 후에만.

## 미션 (격상 — 주인님 직접 지시 2026-06-20)
'store-db가 내가 원하는 대로 database로 구축됐는지' 확인 → WK23 빌드 go/no-go 판단용 **종합보고서**.
4부: (1)구조·학습내용 (2)의도대비 완전성(설계문서 대조) (3)정확성 부분검증(표본) (4)갭·버그·CCP수정안.
특히 4대 역량: ①영수증 참석자 이름 DB화 ②merchant→섹션 ③headcount ④cell 자동배치 학습.
산출=일반인 이해가능·요약압축 금지·실데이터 근거. read-only 우선, CCP수정은 승인+백업 후.

## TODO
- [x] T0. 신원교정·정본 내면화·ACK push
- [x] T1. 스카우트: store-db.json 구조 / scripts / 설계문서 / 데이터 위치 확정
- [x] T2. store-db.json 전수 1차검사 — 참석자 이름 저장필드 없음 확정
- [x] T3. name-DB(Receipt!A999:H1007) 정체 규명 — 한국어→영문+회사 정적 참조사전(3社 약22명)
- [x] T4. ACK 격상 + 선행발견 push (surface:1)
- [x] T5. 【워크플로 병렬감사】 32에이전트(8포렌식+claim+적대검증) 완료. 11/13 confirmed, C7 refuted(평택폴바셋 버그혐의 반증), C6 정정(8→7).
- [x] T6. 정확성 표본검증 — 카드매칭96.6%; clean가맹점 typical 실제와 정확일치(C8); holdout +headcount 자동57.5%/정확89.2%/오배치6.2%/STAFF0%.
- [x] T7. 의도대비 완전성 — R-C/R-D: store-db 본업=섹션분류+통계. ①이름=설계대상아님(별도정적사전) ②섹션=구축(천장87.5%) ③headcount=부분(12/19) ④cell=결정론(학습아님).
- [x] T8. §6 변증 — gemini CLI 1R 완료·반영(5조건 엄정판정/수치해석/비파괴GO 정직화). codex=한도소진(Jul18) 불가→master 판단.
- [x] T9. 종합보고서 — audit-0620-store-db/STORE-DB-AUDIT-REPORT.md (+ store-db-structure.png, Mermaid, ASCII). 일반인용·실데이터·무압축.
- [x] T10. master surface:1 보고 push (경로안내 + §6결과). 수정안 8건 설계만·승인대기.
- [ ] T11. master 검증·주인님 go/no-go 결정 대기 (CCP 적용은 승인+백업 후).

## 확정 발견 로그 (실파일 근거만, 환각0)
- F1. store-db.json = 가맹점별 학습 DB. 키=사업자번호 or `name:<상호>`. 19 엔트리.
  필드: merchant_name, category, section_dist{DINNER/STAFF/TRAVEL count}, confidence,
  dominant_section, typical{headcount,amount,hour}, occurrences, source_weeks.
  → 참석자 '이름' 저장 안 함. headcount=인원'수'(숫자)지 '누구'가 아님.
  (build_store_db.py:153-224, agg는 receipt['headcount'] 숫자만 누적 165-166)
- F2. name-DB = Receipt!A999:H1007 별도 영역. 한국어이름→영문romaji+회사 정적 사전.
  ORG실측: row999 헤더=TERADYNE/SAMSUNG EDS/SAMSUNG HBM PE; row1000-1007 = 인명매핑
  (박종진→Simon Park, 김기정→Kim Kijung … me→Simon Park). fix#1이 canonical ORG에서 복원
  (write_excel.py:365 read_name_database, 577 format_names_string, 893 fix#1, 1051/1090 FORM기입).
  ※romaji 점검대상 후보: 민병찬→"Miin Byeongchan", 김면기→"Kim Myoengi" (오기 의심 — 주인님 확인필요, 단정금지)
- F3. extract_names_data.py → research/names-data.json = 영수증 하단 이름 1회 추출(연구용, live DB 아님).
- F4. 데이터: 과거주차 OCR ground-truth=research/wk06..wk22_ocr-results.json(14주). 
  coverage/holdout/promoted=14주(WK06-WK22) 승급. quarantine/snapshots=빈 폴더.
  WK23=다음 빌드대상(run-logs/WK23_2026-run.json 계획 S0-S7, 입력 raw-data/input/WK23_2026/*.pdf).
- F5. holdout: theta_high=0.85, PRIMARY KPI=wrong_auto_rate_pct.
- F6. 학습알고리즘(build_store_db.py 직접정독): MEAL_SECTIONS=dinner/staff/travel만(45);
  PARKING/TOLLS/TELEPHONE 제외(195-200). 키=카드(date,amount)매칭시 사업자번호 else name:store(186/191).
  agg는 section_dist/headcount/amount/hour/occurrences/source_weeks만 누적(153-173)·이름無.
  typical=[min,median,max](224-226). confidence=max/total, dominant=argmax.
  ★req④ quarantine/promote/snapshot/rollback 코드 구현완료(250-313)지만 14주는 bulk-build(341 promote-all)
   → 증분 self-learning 사이클 미가동(WK23가 첫 실가동 대상). ※intended schema의 last_seen_wk는 실산출에 없음(minor gap).
- F7. ★통합상태(WK23 직결): classify_section.py(R-D headcount정책 기본) 빌드완료, θ 하드코딩
  (theta_high=0.85/mid=0.20/HC_TRAVEL=3, config미배선). run_week.py S3c=classify_stage.py(135-136)로 배선.
  classify_stage='비파괴'(non-disruptive): 섹션 예측+T3 escalation HALT(exit2, section-confirmed.json 확정후 재개)만,
  research/ocr-results.json 미수정 → write_excel는 기존 사람배치 섹션 사용. full pre-sort 자동대체 = 별도GO 대기(코드주석).
  store-db.json 부재시 SKIP(exit0).
- F8. ★설계 reframe(R-C holdout 결론·R-D §0/§7): full-auto 90+ 불가, 천장 87.5%(절대천장 아님·현 feature/14주/STAFF소표본),
  STAFF↔TRAVEL purpose-ambiguity. Goal2 = '신뢰가능분 auto + 모호분 escalation'으로 reframe. 1차KPI=wrong-auto-rate.
  configurable-θ는 주인님 운영점 결정 대기 → 통합 build 대기. self-learning에 negative examples 설계(R-D §0.5-5, 미구현추정).

## 4대 역량 매핑 (주인님 질문 직답 — 잠정, 워크플로/변증으로 확정)
- ① 참석자 이름 DB화: store-db엔 없음(설계상 대상아님). 이름=별도 name-DB(정적 romaji+회사 사전). 학습누적 아님.
  → 주인님이 '참석자 이름 학습DB'를 원했다면 미구축(신규기능 영역).
- ② merchant→섹션: 구축됨(section_dist/dominant/confidence). 단 정직천장 87.5%·assist+escalation.
- ③ headcount: 부분구축. OCR이 headcount 실을 때만 학습(다수 null 가능) → 실커버리지는 표본검증으로 정량화중.
- ④ cell 자동배치: 설계상 결정론(write_excel, 학습대상 아님). 학습되는건 '섹션'이지 'cell'아님. 현재도 비파괴 assist만.

## 진행 메모
- 워크플로 wf_5ebd05c1 READ 8개 가동중 → Claims → Verify. 완료 통지 대기(폴링 안함).
- 수신 후: 내가 직접 종합보고서 합성(일반인용·실데이터근거) + gemini/codex 변증 → surface:1 보고.
- 수정안은 '설계만'(CCP Step1-3), 적용은 master검증+주인님 승인+백업 후.
