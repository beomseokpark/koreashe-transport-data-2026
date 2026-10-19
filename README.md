# 서울 장애인콜택시 대기시간 격차 분석 및 근무시간대 조정·택시 연계 방안

서울 장애인콜택시 2025년 탑승기록 172만 건으로 시간대·지역별 대기·포기 격차를 측정하고, 포기(취소)를 반영한 배차 시뮬레이션으로 단시간 운전원 근무시간대 조정·증원 배치·택시 연계(온디맨드·라스트마일)·전기차 전환의 대기·비용·탄소 효과를 비교한 분석 코드입니다.
「AI와 함께하는 교통문제 해결을 위한 데이터 분석 공모전」(숲과나눔 풀씨행동연구소 × 한겨레) 예선 제출물의 분석 코드입니다.

## 재실행 순서
Python 3.12, `pip install -r requirements.txt`, `playwright install chromium`. 모든 스크립트는 `src/`에서 실행합니다.

| 단계 | 스크립트 | 내용 | 산출물 |
|---|---|---|---|
| 0 | `p0_fetch.py` | 공공데이터포털 파일 7종(Playwright), 서울 열린데이터광장 등록장애인 통계, 행정동 경계(vuski/admdongkor) 내려받기 | `data/raw/` |
| 0 | `geocode_depots.py`, `geocode_fix.py` | 차고지 44곳 주소 → 좌표(OSM Nominatim, 1초 간격) | `data/processed/depots.csv`(저장소에 포함) |
| 1 | `p1_prepare.py` | 탑승내역 정리(대기·포기·예약 여부), 출발·목적 행정동 매칭(옛 동명 처리) | `trips.parquet`, `dongs.parquet` |
| 2 | `p2_gap.py` | 공식 통계 대조, 시간대 곡선, 자치구·행정동 격차, 로렌츠·지니, Gi* 핫스팟, OLS, 생활권 수지, Kaplan–Meier 인내시간 | `gap.json` 외 |
| 2b | `p2b_theil.py` | 대기 불평등 Theil 분해(시간대·생활권·자치구·행정동 간 몫) | `theil.json` |
| 2c | `p2c_extra.py` | 예약 호출 지연(06시대·출근/통학), 임차택시 시간대 분포, 공단 공식 대기 통계와 수준 대조 | `extra.json` |
| 3 | `p3_sim_calib.py` | 배차 시뮬레이터(`sim.py`, 입력 `simdata.py`) 보정(2025-11 평일)·표본 밖 검증(2025-09 평일) | `sim_calib.json` |
| 4 | `p4_policies.py` | 근무조 근사(정수계획) → 출근 시각 국소탐색(9월 학습) → 11월 평가, MEXCLP 대기 거점, 증차 비교 | `policies.json`, `scenarios.csv` |
| 4b | `p6_isa.py` | 시간 안정 근무 곡선(무한서버 부하 분위수, 9월 학습) → 낮(05~18시) 재배분 혼합안 → 근무조 정수계획(4~10시간 / 2~3시간 포함) → 11월 평가, 차량·일 주행거리(전기차 점검) | `isa.json`, `isa_scenarios.csv` |
| 4c | `p7_shift.py` | 단시간 운전원 근무시간대 이동(16∼21시→14∼19시)·증원 배치·14∼18시 수요 분담 시나리오(9월·11월), 매개변수 민감도 | `shift.json` |
| 4d | `p8_sim_ab.py` | 시뮬레이터 v2: 배차 전 취소 호출 포함, 호출별 인내시간(조건부 Kaplan–Meier)으로 포기 반영, 11월 보정(준비시간·가동률·배차 규칙)·9월 검증 | `sim_ab_calib.json` |
| 4e | `p9_package.py`, `p11_candidates.py`, `p12_final.py` | 근무 이동·증원 배분 탐색(9월 선택·11월 평가, 시간대별 악화 금지) → 오전·저녁·지역 후보 비교 → 통합안 확정·민감도 | `package.json`, `candidates.json`, `final.json` |
| 4f | `p10_lastmile_carbon.py`, `p13_cost.py` | 지하철역(OSM) 1㎞·5㎞ 기준 라스트마일 연계 대상과 전환 시뮬레이션, 수단별 1건당 CO₂, 바우처 1건당 보조금·라스트마일 손익분기 | `lastmile.json`, `cost.json` |
| 5 | `p5_carbon.py` | 운행거리 × 대표 차종 연비 × 배출계수, 전기차 전환(4·4b 시나리오 모두) | `carbon.json` |
| 6 | `figures.py`, `figures3.py` | 보고서 그림(그림 1·2·한 장 요약) | `figures/` |
| 7 | `build_report_hwpx.py`(`report_content.py`·`formfill.py`), `build_form1_hwpx.py`, `build_preview.py` | 원본 HWP 양식(붙임1·2)을 HWPX로 바꿔 칸만 채움 → 한글에서 PDF로 저장. 미리보기 PDF는 근사 | `output/*.hwpx` |

`p4_policies.py`의 근무표 탐색은 시뮬레이션을 수백 번 돌려 2코어 기준 수 시간 걸립니다.

`build_report.py`·`build_forms.py`·`figures2.py`는 양식 전환 전(HTML 조판) 판입니다.

## 데이터
- 지하철역 위치: OpenStreetMap(Overpass API, ODbL) `data/raw/osm_subway_stations.json`
- 단시간 운전원 근무 편성(07:00∼12:00 / 16:00∼21:00 / 17:00∼22:00, 일 5시간)은 서울시설공단 2025년 계약직원 공개채용 공고에서 확인(시나리오 기준값)
- 서울시설공단 장애인콜택시 탑승내역·시간대별 대기시간·차고지·차량정보, 한국교통안전공단 특별교통수단 운행현황, 한국에너지공단 자동차 표시연비(공공데이터포털, 이용허락범위 제한 없음)
- 서울특별시 장애인 현황(장애유형별/동별) 통계(서울 열린데이터광장, 공공누리 1유형)
- 행정동 경계: 통계청 SGIS 원자료, vuski/admdongkor 가공(CC BY 4.0) · 차고지 좌표: © OpenStreetMap contributors(ODbL)
- 원자료는 저장소에 넣지 않았습니다(`p0_fetch.py`로 다시 받기). 탑승내역에는 개인식별정보가 없습니다.

## 방법 요약
- 형평성: Delbosc & Currie(2011) 로렌츠·지니, Lucas et al.(2016) 충분성 기준(60분)
- 핫스팟·요인: Getis-Ord Gi*(esda), OLS(HC1) — Akcicek et al.(2024) 덴버 장애인 교통 분석 틀
- 포기: Brown et al.(2005)처럼 취소=인내 소진, 승차=중도절단인 Kaplan–Meier
- 배차 시뮬레이션: 실제 호출 재배차, 근무 차량 = 관측 운행 중 차량 × 보정계수
- 근무표: Green, Kolesar & Whitt(2007)·Halfin & Whitt(1981)의 정상상태 산정은 과부하라 부적합, Feldman et al.(2008) ISA는 포기 없는 시뮬레이터에서 발산 → Jennings et al.(1996) 무한서버 부하 방식으로 시간 안정 곡선, Dantzig(1954)식 근무조 정수계획
- 불평등 분해: Theil(1967) T 지수(지니는 Delbosc & Currie 2011, Jang et al. 2017)
- 전기차: 차량·일 주행거리 vs 1회 충전 주행거리(CALSTART 2023 방식), 택시 연계 근거는 MBTA(2017)
- 대기 거점: Daskin(1983) MEXCLP 탐욕 해법
- 근무시간대 시나리오: 공단 채용공고의 단시간 편성을 그대로 옮기는 구조 변경이라 학습 단계 없이 9월·11월에 각각 적용, 준비시간·우회계수·배차 규칙·가동률 민감도 확인

## AI 활용
분석 코드 작성·실행, 문헌 검색, 보고서 조판에 Claude Code(Anthropic)를 사용했습니다. 모든 수치는 위 스크립트로 공개 원자료에서 다시 계산됩니다.
