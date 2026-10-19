"""분석보고서 원고(붙임2 양식 칸별 블록). 숫자는 data/processed/*.json에서 읽음. build_report_hwpx.py·build_preview.py가 같이 씀
칸: name, topic, background, data(머리 블록 + 목록 표 행 + 꼬리 블록), method, ai, results, policy, refs, images"""
import json
import numpy as np, pandas as pd
from common import PROC, FIG, ROOT

A = json.load(open(ROOT / "applicant.json", encoding="utf-8"))
G = json.load(open(PROC / "gap.json")); TH = json.load(open(PROC / "theil.json")); EX = json.load(open(PROC / "extra.json"))
CAL = json.load(open(PROC / "sim_ab_calib.json")); PK = json.load(open(PROC / "package.json")); F = json.load(open(PROC / "final.json"))
CD = json.load(open(PROC / "candidates.json")); LM = json.load(open(PROC / "lastmile.json")); CB = json.load(open(PROC / "carbon.json"))
CO = json.load(open(PROC / "cost.json")); IJ = json.load(open(PROC / "isa.json"))
H = pd.read_csv(PROC / "hour_profile.csv", index_col=0)
REPO = A.get("repo", "https://github.com/beomseokpark/koreashe-transport-data-2026")

f0 = lambda x: f"{x:,.0f}"; f1 = lambda x: f"{x:,.1f}"
pc = lambda x, d=1: f"{x * 100:.{d}f}%".replace("-", "−")
sg = lambda x, d=1: f"{x * 100:+.{d}f}%".replace("-", "−")
O = G["overall"]; N = G["counts"]; L = G["lorenz"]; HS = G["hotspot"]; PT = G["patience"]
coef = {r["index"]: r["b"] for r in G["ols"]["coef"]}
LIFE = "C(life, Treatment('동북권'))[T.{}]"; bal = {r["life"]: r for r in G["balance_pm"]["table"]}; dl = {r["life"]: r for r in G["depot_life"]}
R6, CR, TX, LV = EX["res6"], EX["commute_res"], EX["taxi_share"], EX["level"]

# 시뮬레이션 결과(11월 평일, v2)
NV = F["nov"]; S0 = NV["S0 현행"]; PKG = NV["PKG 통합안"]; PR1 = NV["PKG+R1 도심·동남권 오후 택시 우선 20%"]; PR2 = NV["PKG+R2 오후 조 도심·동남권 출근"]
SEP = F["sep"]; P9 = PK["nov"]; C11 = CD["nov"]
am = lambda r: np.mean(r["hour_mean"][1:4]); pm = lambda r: np.mean(r["hour_mean"][8:12]); hr = lambda r, h: r["hour_mean"][h - 6]
chg = lambda r, b=S0: r["mean"] / b["mean"] - 1
sens = [v["chg"] for v in F["sensitivity"].values()]
la30, lb30 = LM["sim"]["LA30 라스트마일 30% 전환(양끝 민간 택시)"], LM["sim"]["LB30 라스트마일 30% 전환(양끝 특장차)"]
co2 = LM["carbon"]["per_trip_kg"]
van, taxi, metro, fam, van_ev = (co2[k] for k in ("특장차(현행 차량 구성, 빈 차 포함)", "바우처 일반택시(LPG)", "지하철+양끝 택시(LPG, 각 1㎞)", "가족 차량 동행(휘발유, 왕복)", "특장차 전기 승합"))
t_of = lambda e: CB["pass_km_obs"] * (1 + e) * CB["fleet_kgkm"] / 1000
T0, TP = t_of(S0["empty"]), t_of(PKG["empty"])
am_trips_yr = PKG["diverted"] * 250
PT_YEAR = CO["pt_year"]
recov = (S0["ab"] - PKG["ab"]) * N["imm_n"]

TITLE = "서울 장애인콜택시 대기시간 격차 분석 및 근무시간대 조정·택시 연계 방안"
SUB = "2025년 탑승기록 172만 건 진단, 포기 반영 배차 시뮬레이션과 탄소 감축 효과 분석"

CELLS = {}
CELLS["name"] = [("p", f"{A['name']} (개인 참가, {A['affiliation']})")]
CELLS["topic"] = [("p", f"<b>{TITLE}</b>"), ("p", f"- {SUB}")]

CELLS["background"] = [
    ("sq", "현황: 차량 확충 이후에도 출퇴근 시간대 장시간 대기 지속"),
    ("o", "2021년 632대에서 2025년 854대(법정 기준 569대의 151%)로 확충 추진, 평균 대기는 2023년 47분 → 2025년 3월 32분(서울시, 2025.5)", "확충"),
    ("o", "그러나 출근 평균 48분·퇴근 50분·최장 301분 대기가 확인되어 60·90분 초과율·최대 대기를 관리지표로 삼자는 요구 제기(서울신문, 2026.9.4)", "한계"),
    ("o", f"2025년 탑승기록(특장차 {f0(N['sp'])}건) 분석 결과 즉시 호출 대기 중앙값 {f1(O['med'])}분, <b>60분 초과 {pc(O['over60'])}</b>, 접수 후 취소 {pc(O['cancel'])}", "실태"),
    ("sq", "기존 대책과 분석으로 확인한 공백"),
    ("tab", "기존 대책과 공백", ["구분", "기존 대책", "분석으로 확인한 공백"], [
        ["차량 확충", "854대 계획(법정 기준 151%)", f"동시 운행 최대 {G['busy_max']['v']}대(보유의 {pc(G['busy_max']['v'] / 698, 0)}) → 차량보다 운전 시간대가 제약"],
        ["단시간 운전원", "일 5시간, 07∼12·16∼21·17∼22시 편성, 2026년 175명", "오후 조 시작(16시)이 대기 증가 시점(14시 30분)보다 늦음"],
        ["바우처택시", "비휠체어 일반택시 연계(이용자는 장애인콜택시 요금), 2025.1∼8월 259억 원, 전용 임차택시 2025.12 종료",
         "콜센터 배차만 허용, 미터기 1,500원 표시로 기사 기피, 시간대별 유도 없음"],
        ["평균 대기 관리", "연·월 평균 대기 공표", f"분포·60분 초과율 미공표, 06시대 예약 {pc(R6['disp_after7'], 0)}가 07시 이후 배차"],
    ], dict(widths=[14, 36, 50], aligns=["CENTER", "LEFT", "LEFT"], src="자료: 서울시(2025.5), 바우처택시 운영규정(2024.8), 서울시설공단 채용공고(2025.1)·공지(2025.12), 서울신문(2025.11.7·2026.9.4), 응모자 분석")),
    ("sq", "목적"),
    ("o", "① 시간대·지역별 대기·포기 격차 측정 ② 원인 규명 ③ 포기 반영 배차 시뮬레이션으로 근무시간대 조정·택시 연계·라스트마일의 대기·비용·탄소 효과 비교"),
    ("o", "운영관리 관점에서 같은 자원으로 서비스 수준을 높이는 방안 검토. 장시간 대기는 통원·출근·통학 기회 손실이며, 택시·지하철 연계는 탄소 감축에도 기여", "참여 동기"),
]

DATA_HEAD = [
    ("o", "탑승내역(주요 변수: 접수·예정·배차·승차·하차·취소 시각, 출발·목적 행정동, 이용목적, 장애유형, 요금, 승차거리)으로 대기·포기를 직접 측정하고 공식 통계로 검증, 차고지·차량·연비로 시뮬레이션·탄소, 역 위치로 라스트마일 대상 산정", "선정 이유"),
]
DATA_ROWS = [
    ["장애인콜택시 탑승내역(2025)", "서울시설공단", "공공데이터포털", "data.go.kr/data/15115859/fileData.do"],
    ["시간대별 대기시간·탑승건수(2025)", "서울시설공단", "공공데이터포털", "data.go.kr/data/15147613, 15147614"],
    ["장애인콜택시 차고지 정보(2026.7)", "서울시설공단", "공공데이터포털", "data.go.kr/data/15144781/fileData.do"],
    ["장애인콜택시 차량정보(2026.8)", "서울시설공단", "공공데이터포털", "data.go.kr/data/15160788/fileData.do"],
    ["특별교통수단 운행현황(2024)", "한국교통안전공단", "공공데이터포털", "data.go.kr/data/15066774/fileData.do"],
    ["자동차 표시연비 정보(2026)", "한국에너지공단", "공공데이터포털", "data.go.kr/data/15083023/fileData.do"],
    ["장애인 현황(동별) 통계(2025)", "서울특별시", "서울 열린데이터광장", "data.seoul.go.kr(DT201004F040005)"],
    ["행정동 경계(2026.7)", "통계청 SGIS(가공)", "GitHub", "github.com/vuski/admdongkor"],
    ["지하철역 위치(2026.10)", "OpenStreetMap", "Overpass API", "overpass-api.de(ODbL)"],
    ["차고지 주소→좌표", "OpenStreetMap", "Nominatim", "nominatim.openstreetmap.org"],
]
DATA_TAIL = [("nk", "공개 파일·공개 API만 사용(크롤링·비공개 자료 없음, 수집 2026.10.17∼19, 개인식별정보 없음). 이용조건: 공공데이터포털 제한 없음, 서울 열린데이터광장 공공누리 제1유형, "
                     "행정동 경계 CC BY 4.0(vuski/admdongkor), 역·차고지 좌표 © OpenStreetMap contributors(ODbL)")]

CELLS["method"] = [
    ("sq", "수집·전처리"),
    ("o", f"특장차 {f0(N['sp'])}건 분석(임차택시 {f0(N['taxi'])}건은 비교에만 사용). 대기 = 승차시각 − 예정시각, 포기 = 승차 없이 취소, 격차 분석은 즉시 호출(전체의 {pc(N['imm_share'], 0)}) 중심"),
    ("o", f"날짜·시간대별 평균 대기가 공단 공식 통계(8,718개 시간칸)와 상관 {G['official_check']['corr']:.3f}, 탑승가중 연평균 {f1(LV['official_weighted'])}분 대 본 분석 {f1(LV['mine_all'])}분으로 일치. 행정동 이름은 2026.7 경계와 대응(97.1% 일치)", "검증"),
    ("sq", "분석 기법(해외 연구 방법 적용)"),
    ("tab", "분석 단계와 적용 방법", ["단계", "방법과 근거"], [
        ["형평성·요인", f"로렌츠·지니(Delbosc & Currie, 2011), 60분 기준(Lucas et al., 2016), Theil 분해(Theil, 1967), Gi* 핫스팟·OLS(n={f0(G['ols']['n'])}, Akcicek et al., 2024)"],
        ["포기·시뮬레이션", "Kaplan–Meier 인내시간(Brown et al., 2005). 실제 호출(11월 평일 7.9만 건, 배차 전 취소 포함) 재배차 이산사건 모형, 호출별 인내시간으로 포기 반영(Garnett et al., 2002), 우회계수 1.30(실측 1.302), 11월 보정·9월 검증"],
        ["근무 패키지", "단시간 편성(일 5시간) 기준 근무 이동·증원 배치·택시 분담 조합을 9월로 고르고 11월에 평가(07∼22시 어느 시간대도 1분 넘게 악화 금지)"],
        ["택시·탄소", "택시 분담·라스트마일(역 1㎞·5㎞ 기준, OSM) 전환, 택시 요금표로 1건당 보조금, 운행거리×표시연비×배출계수(IPCC, 2023년 전력계수)로 CO₂"],
    ], dict(widths=[16, 84], aligns=["CENTER", "LEFT"])),
]

CELLS["ai"] = [
    ("o", "사용 서비스: <b>Claude Code(Anthropic)</b> — 코드를 직접 작성·실행하는 AI 코딩 도구", "서비스"),
    ("o", "활용 범위: 데이터 내려받기, 분석·시뮬레이션 코드 작성·실행, 정책 자료·해외 사례·문헌 검색, 그림·보고서 초안. 주제 선정·결과 해석·정책 제안은 응모자가 검토해 확정", "범위"),
    ("box", ["<b>주요 프롬프트(응모자 요청의 요지, 시간순)</b>"] + A["prompts"]),
    ("o", "모든 수치는 공개 원자료에서 코드로 재계산(GitHub 공개), 대기 정의는 공단 공식 통계와 대조, 정책 자료·해외 사례는 원문 확인. 확인되지 않은 주장과 맞지 않은 AI 제안 방법(정상상태 근무 산정·출근 시각 국소탐색·대기 거점)은 제외", "검증"),
    ("o", f"AI에 입력한 자료는 공개 파일뿐(개인식별정보·위치정보·비공개 자료 없음). {A['ai_setting']}", "보호"),
]

ROWS = [
    ("현행(2025년 11월 추정 공급)", "−", S0),
    ("오후 단시간 20명 14∼19시로 이동", "0", P9["L20 오후 조 20명 14∼19시"]),
    ("단시간 25명 증원 – 16∼21시(현행 방식)", "25", P9["P2 증원 25명 16∼21시"]),
    ("단시간 25명 증원 – 07∼12시", "25", P9["P1 증원 25명 07∼12시"]),
    ("균등 증차 10%(비교)", "약 54", P9["S4 균등 증차 10%"]),
    ("<b>통합안</b>(15명 이동+증원 25명+아침 택시 분담 15%)", "25", PKG),
    ("통합안+도심·동남권 오후 호출 20% 택시 우선", "25", PR1),
]
def row(nm, add, r):
    return [nm, add, f1(r["mean"]), "−" if r is S0 else sg(chg(r)), f0(am(r)), f0(pm(r)), f"{hr(r, 20):.0f}·{hr(r, 21):.0f}", pc(r["over60"]), pc(r["ab"])]
RL = CD["nov"]["RL 예약 선배차 35분"]

CELLS["results"] = [
    ("sq", "① 시간대별 격차: 출근(07∼09시)·오후(14∼17시) 대기 집중"),
    ("o", f"평일 즉시 호출 대기 중앙값 07∼08시 {f0(H.wait_med[7])}∼{f0(H.wait_med[8])}분·16시 {f0(H.wait_med[16])}분으로 낮({f0(H.wait_med[13])}분)의 2배 이상, 16시 호출 {pc(H.cancel[16], 0)} 취소. "
          f"동시 운행은 최대 {G['busy_max']['v']}대, 07시 평균 {f0(H.busy_mean[7])}대 → <b>병목은 운전원 근무 시간대</b>(그림 1)"),
    ("o", f"06시대 예약의 {pc(R6['disp_after7'], 0)}가 07시 이후 배차(지연 중앙값 {f0(R6['late_med'])}분), 출근·통학 예약의 {pc(CR['over30'], 0)}가 30분 넘게 지연", "첫 근무·예약"),
    ("fig", str(FIG / "fig1_hour.png"), "평일 시간대별 호출·운행 중 차량·대기와 단시간 근무 편성(2025년)", "서울시설공단 탑승내역(2025), 공단 채용공고(2025.1) 응모자 분석", 116),
    ("sq", "② 지역별 격차: 도심·동남권 고대기 군집, 원인은 오후 귀가 흐름"),
    ("o", f"60분 초과 비율 행정동 하위 10% {pc(G['dong']['over60_q']['0.1'], 0)}·상위 10% {pc(G['dong']['over60_q']['0.9'], 0)}(지니 {L['gini']:.2f}), Gi* 고대기 {HS['hot']}개 동(도심·강남 서남부)·저대기 {HS['cold']}개 동(동북권)(그림 3 ②). "
          f"통제 회귀에서 도심권 +{f1(coef[LIFE.format('도심권')])}분·동남권 +{f1(coef[LIFE.format('동남권')])}분, 오후 도심권은 승차 {f0(bal['도심권']['pickup'])}건 대비 하차 {f0(bal['도심권']['dropoff'])}건으로 빈 차가 외곽에 쌓임"),
    ("o", f"Theil 분해 시 대기 불평등의 <b>시간대 간 몫 {pc(TH['시간대(24)']['share'], 0)}</b>, 생활권·자치구·행정동 간 {pc(TH['생활권(5)']['share'], 1)}·{pc(TH['자치구(25)']['share'], 1)}·{pc(TH['행정동']['share'], 1)} → 시간대 조정이 먼저, 지역은 보완", "분해"),
    ("sq", "③ 배차 시뮬레이션(포기 반영)과 통합안"),
    ("o", f"11월 보정 P90 {f0(CAL['best']['p90'])}분(실측 {f0(CAL['best']['obs_p90'])})·접근 {f1(CAL['best']['appr'])}분({f1(CAL['best']['obs_appr'])})·배차 전 포기 {pc(CAL['best']['ab'])}({pc(CAL['best']['obs_ab'])}), "
          f"9월 검증 P90 {f0(CAL['valid']['p90'])}분({f0(CAL['valid']['obs_p90'])}). 중앙값이 다소 커 효과는 변화율로 해석", "검증"),
    ("o", f"한 시간대만 손보면 다른 시간대가 남거나 나빠져(아래 표 3), <b>통합안</b>은 기존 오후 조 15명 14∼19시 이동(비용 0)+2026년 증원 25명 오후 15·저녁 10명+07∼09시 즉시 호출 15%(하루 약 {f0(PKG['diverted'])}건) 택시 분담. "
          f"평균 {f1(S0['mean'])}→{f1(PKG['mean'])}분({sg(chg(PKG))}, 9월 {sg(chg(SEP['PKG 통합안'], SEP['S0 현행']))}), 오전 {f0(am(S0))}→{f0(am(PKG))}·오후 {f0(pm(S0))}→{f0(pm(PKG))}·21시 {f0(hr(S0, 21))}→{f0(hr(PKG, 21))}분, "
          f"60분 초과 {pc(S0['over60'], 0)}→{pc(PKG['over60'], 0)}, 모든 시간대 악화 없음(그림 2)", "통합안"),
    ("tab", "시나리오별 즉시 호출 대기(11월 평일 재배차)", ["시나리오", "증원(명)", "평균", "변화율", "오전", "오후", "20·21시", "60분 초과", "포기율"],
     [row(*x) for x in ROWS], dict(widths=[34, 7, 7, 8, 6, 6, 9, 9, 8], aligns=["LEFT"] + ["CENTER"] * 8, rh=False, hl_rows=(5,), size=7.8, unit="분, %",
                                   src="오전 07∼09시·오후 14∼17시 평균, 포기율은 배차 전 취소 비율. 단시간 운전원 1명 = 근무 중 차량 1대 가정")),
    ("o", f"도심·동남권 오후 호출 20% 택시 우선 시 도심권 {f1(S0['life_mean']['도심권'])}→{f1(PR1['life_mean']['도심권'])}분, 동남권 {f1(S0['life_mean']['동남권'])}→{f1(PR1['life_mean']['동남권'])}분(다른 권역 유지)", "지역"),
    ("o", f"8개 매개변수 조건에서 {pc(max(sens))}∼{pc(min(sens))}. 예약 35분 선배차 시 아침 예약 30분 초과 지연 {pc(RL['res_late30_am_base'], 0)}→{pc(RL['res_late30_am'], 0)}", "민감도"),
    ("fig", str(FIG / "fig2_package.png"), "통합안의 시간대별 평균 대기와 수단별 1건당 CO₂", "응모자 시뮬레이션(코드: GitHub), 한국에너지공단 표시연비", 114),
    ("sq", "④ 택시 연계·라스트마일의 비용과 탄소"),
    ("o", f"바우처 1건 보조는 평균 약 {f0(CO['subsidy_mean'])}원(거리요금 기준 하한)으로 장애인콜택시 건당 운송비 59,700원(2024)의 1/6, 즉시 호출 20% 택시 분담 시 평균 {sg(chg(P9['D20 즉시 호출 20% 택시 분담']))}", "비용"),
    ("o", f"역 1㎞ 안·5㎞ 이상 호출이 즉시 호출의 {pc(LM['eligible']['share_calls'], 0)}·특장차 운행거리의 {pc(LM['eligible']['share_km'], 0)}, 30%가 지하철+양끝 택시로 바뀌면 {sg(chg(la30))}(양끝 특장차 {sg(chg(lb30))}), "
          f"{f1(CO['breakeven_km'])}㎞ 넘는 운행부터 전 구간 택시보다 저렴", "라스트마일"),
    ("o", f"1건당 CO₂ 특장차 {van:.1f}㎏·가족 동행 {fam:.1f}㎏·LPG 택시 {taxi:.1f}㎏·지하철+택시 {metro:.1f}㎏·전기 승합 {van_ev:.1f}㎏. 특장차 연 {f0(CB['base_t'])}톤(전기 전환 시 −{pc(CB['ev_cut'] / CB['base_t'], 0)}), "
          f"통합안은 빈 차 주행으로 {sg(TP / T0 - 1)} → 증원 차량부터 전기 승합", "탄소"),
]

CELLS["policy"] = [
    ("tab", "정책 제안(국내 실행 가능성 검토 후 선별)", ["제안", "내용", "실행 수단"], [
        ["① 근무시간대 통합안", f"오후 단시간 15명 16∼21→14∼19시(비용 0), 증원 25명 14∼19시 15·17∼22시 10명, 07∼09시 비휠체어 호출 15% 택시 분담 → 평균 {sg(chg(PKG), 0)}", "공단 근무 편성·채용"],
        ["② 휠체어 우선 특장차 + 앱 즉시 호출", "바우처를 앱(온다택시 등) 즉시 호출·결제로 확대, 일반 요금 표시 후 차액 정산(낙인 해소), 정점 인센티브, 미배차 시 특장차 대체, 보조 필요자는 특장차 유지(뉴욕 E-Hail 참고)", "바우처 운영규정 개정"],
        ["③ 휠체어 탑승 택시 확충", "법인특장·대형 가맹택시 휠체어형 개조비 보조·앱 배차 연동(조례 개정안 2030년 2배), 휠체어 승하차 수당 신설(시카고 $30·퀸즐랜드 $20 참고), 단체 배상책임보험·고정 교육", "서울시·국토부 보조"],
        ["④ 보호자 없는 이동", "보호자 동승 의무(운영규정 제3조③)를 활동지원사·동행매니저 동승으로 대체, 발달장애인 같은 기사 배정 허용, 탑승·도착 알림과 기관 인계 확인", "운영규정, 활동지원기관"],
        ["⑤ 라스트마일·지역·지표", f"{f1(CO['breakeven_km'])}㎞ 넘는 장거리는 지하철(전 역사 1동선)+양끝 택시, 도심·동남권 오후 택시 우선, 60·90분 초과율·최대 대기·예약 정시율 공표, 증원 차량 전기 승합", "서울시·교통공사·공단"],
    ], dict(widths=[20, 63, 17], aligns=["LEFT", "LEFT", "LEFT"], rh=False, size=7.8)),
    ("nk", "제외·중장기: 플랫폼 호출 부담금(「부담금관리기본법」상 법률 근거 필요), 기사 면책(근거 미확인), 개인 휠체어 차량 공유·돌봄 인력 자가용 운전(「여객자동차 운수사업법」 제81조), 저상버스(서울 71%)·계단 구간(자료 부족)"),
    ("o", f"통합안 평균 {sg(chg(PKG), 0)}, 60분 초과 {pc(S0['over60'], 0)}→{pc(PKG['over60'], 0)}, 연 약 {f0(recov)}건 포기→승차(지역 택시 우선 포함 {sg(chg(PR1), 0)}), 전기 승합 전환 시 연 최대 {f0(CB['ev_cut'])}톤 감축", "효과"),
    ("o", "같은 진단·시뮬레이션 코드로 타 시·도 특별교통수단, 수요응답형 교통(DRT)·고령자 이동지원의 근무표와 택시 연계 설계에 적용 가능", "파급"),
    ("o", f"오후 조 이동 0원, 증원 25명 연 약 {PT_YEAR * 25 / 1e8:.1f}억 원(시급 12,030원), 아침 택시 분담 연 약 {am_trips_yr * CO['subsidy_mean'] / 1e8:.1f}억 원(수당·보험료·호출료 제외). 택시 연계는 같은 예산으로 약 6배 많은 이동 처리", "비용"),
    ("o", "근무표·차량 위치 비공개로 근무 차량 수를 운행기록에서 추정(단시간 1명 = 차량 1대), 거리는 행정동 중심점 근사 → 공단 근무표로 재보정 필요", "한계"),
]

REFS = [
    "Akcicek, C., Shirgaokar, M., Misra, A., Marshall, W., & Wagner, M. (2024). Understanding Paratransit (MPC-677). Mountain-Plains Consortium.",
    "Brown, L. et al. (2005). Statistical analysis of a telephone call center. JASA, 100(469), 36–50.",
    "Delbosc, A., & Currie, G. (2011). Using Lorenz curves to assess public transport equity. J. Transport Geography, 19(6), 1252–1259.",
    "Garnett, O., Mandelbaum, A., & Reiman, M. (2002). Designing a call center with impatient customers. MSOM, 4(3), 208–227.",
    "Lucas, K., van Wee, B., & Maat, K. (2016). A method to evaluate equitable accessibility. Transportation, 43(3), 473–490.",
    "Theil, H. (1967). Economics and Information Theory. / IPCC (2006). GHG Inventory Guidelines, Vol. 2 Ch. 3.",
    "MTA (2024). Access-A-Ride On-Demand E-Hail Pilot Program. mta.info/ehail",
    "City of Chicago. Municipal Code 9-115-140(Accessibility fund, $0.10/ride); BACP (2020) TNP WAV increased incentives notice.",
    "NSW Point to Point Transport Commissioner (2024). WAV Safety obligations. / Queensland Taxi Subsidy Scheme(lifting fee).",
    "서울시설공단(2025.1). 계약직원 공개채용 공고(장애인콜택시 단시간 운전원 150명, 07∼12/16∼21/17∼22시, 시급 12,030원).",
    "서울시설공단(2025.12.22). 임차택시 서비스 종료 예정 안내. 서울특별시(2024.8.1). 장애인 바우처택시 운영규정.",
    "서울특별시(2025.5.15). 장애인콜택시 150% 확보 추진. 내 손안에 서울 / (2025.12.29). 전 역사 1역사 1동선 확보.",
    "서울신문(2025.11.7). 바우처 콜택시 259억 원 투입에도 장애인 기피승객 / (2026.9.4). 평균 대기 34분 뒤 ‘5시간 대기’.",
    "조달경제신문(2026.9.25). 서울 장애인콜택시는 왜 34분 기다리나(건당 운송비용 59,700원, 서울시의회 분석 인용).",
    "서울특별시 1인가구포털. 병원 안심동행 서비스.",
    "에너지법 시행규칙 [별표] 에너지열량 환산기준(2022.11.21) / 기후에너지환경부(2025.12) 2023년도 전력배출계수 0.4173 tCO₂eq/MWh / 한국가스안전공사(2015) 가스설계지침.",
    "「교통약자의 이동편의 증진법」, 「여객자동차 운수사업법」 제81조(자가용 자동차의 유상운송 금지), 「부담금관리기본법」 제3조·별표, 「장애인활동 지원에 관한 법률」, 국가법령정보센터.",
    "국토교통부(2025). 2024년도 교통약자 이동편의 실태조사(서울 시내버스 저상버스 보급률 71%, 칼럼 인용) / 경향신문(2026.10.1) 저상버스 전면 도입 목표 2032년.",
]
CELLS["refs"] = [
    ("o", "Python 3.12(pandas, geopandas, statsmodels, lifelines, esda, PuLP, scipy, matplotlib), python-hwpx, Playwright, Claude Code", "도구"),
    ("o", f"<b>{REPO}</b>(README에 재실행 순서, 원자료는 스크립트로 다시 내려받음)", "코드"),
    ("refs", REFS),
]
CELLS["images"] = [
    ("fig", str(FIG / "fig5_summary.png"), "서울 장애인콜택시 대기시간 격차 분석 결과와 정책 제안 요약", "응모자 분석(2025년 탑승내역 172만 건, 11월 평일 시뮬레이션)", 88),
]
