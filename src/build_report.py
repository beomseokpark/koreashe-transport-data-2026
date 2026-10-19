"""분석보고서(분석 기획서) PDF 조판 — 공모전 양식(붙임2) 항목 순서 그대로, 공문서 개조식 문체
표지 → 본문(이름/팀명·주제 표, Ⅰ 배경·목적, Ⅱ 활용 데이터, Ⅲ 분석과정·방법, Ⅳ AI 기술 활용, Ⅴ 분석 내용·결과, Ⅵ 정책제안·기대효과)
→ Ⅶ 분석도구·참고문헌 → Ⅷ 분석결과 이미지. 숫자는 data/processed/*.json·csv에서 읽어 채운다.
usage: build_report.py  → output/박범석_분석기획서.pdf"""
import asyncio, json, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path.home() / "ops/templates/hwp-report"))
from hwp_report import FONTS, CSS, hwpify
from common import PROC, FIG, OUT, ROOT

A = json.load(open(ROOT / "applicant.json", encoding="utf-8"))
G = json.load(open(PROC / "gap.json")); C = json.load(open(PROC / "sim_calib.json"))
P = json.load(open(PROC / "policies.json")); CB = json.load(open(PROC / "carbon.json"))
IJ = json.load(open(PROC / "isa.json")); TH = json.load(open(PROC / "theil.json"))
SH = json.load(open(PROC / "shift.json")); EX = json.load(open(PROC / "extra.json"))
SC = pd.read_csv(PROC / "scenarios.csv").set_index("name")
H = pd.read_csv(PROC / "hour_profile.csv", index_col=0)
GU = pd.read_csv(PROC / "gu.csv", index_col=0)
REPO = A.get("repo", "https://github.com/beomseokpark/koreashe-transport-data-2026")

f0 = lambda x: f"{x:,.0f}"; f1 = lambda x: f"{x:,.1f}"; pc = lambda x, d=1: f"{x * 100:.{d}f}%".replace("-", "−")
sg = lambda x: f"{x * 100:+.1f}%".replace("-", "−")
O = G["overall"]; N = G["counts"]; L = G["lorenz"]; HS = G["hotspot"]; PT = G["patience"]
nat = {r["구분"]: r for r in G["national"]}
coef = {r["index"]: r for r in G["ols"]["coef"]}
cf = lambda k: coef[k]["b"]
BAND = "C(band, Treatment('10-14시'))[T.{}]"; LIFE = "C(life, Treatment('동북권'))[T.{}]"
bal = {r["life"]: r for r in G["balance_pm"]["table"]}
dl = {r["life"]: r for r in G["depot_life"]}

# ── 근무시간대·증원·수요 분담 시나리오(p7_shift.py)
SN, SS, SENS = SH["nov"]["scen"], SH["sep"]["scen"], SH["sensitivity"]
k0 = "S0 현행"
def key(pre): return [k for k in SN if k.startswith(pre)][0]
KL20, KL30, KP1, KP2, KP3, KS4, KS6, KH1, KD = (key(p) for p in ("L20", "L30", "P1", "P2", "P3", "S4", "S6", "H1", "D10"))
chg = lambda k, S=SN: S[k]["mean"] / S[k0]["mean"] - 1
hm = lambda k, h: SN[k]["hour_mean"][h - 6]                      # h시 평균 대기(11월 평일)
pm = lambda k: np.mean([hm(k, h) for h in (14, 15, 16, 17)])    # 14~17시 평균
recov = lambda k: (SN[k0]["aband"] - SN[k]["aband"]) * N["imm_n"]  # 연간 포기→승차 전환 추정(2025 즉시 호출 수 기준)
VH = lambda k: SN[k]["vh"] - SN[k0]["vh"]
sens_l30 = [v[KL30]["chg"] for v in SENS.values()]
sens_order = all(v[KS6]["chg"] < v[KS4]["chg"] and v[KP3]["chg"] < v[KP2]["chg"] and v[KL30]["chg"] < v[KP2]["chg"] for v in SENS.values())
H1_SEP = IJ["train"]["same"]["hybrid_train_mean"] / IJ["train"]["same"]["train_base"] - 1
WAGE = 12030; PT_YEAR = WAGE * 5 * 250                          # 단시간 운전원 기본시급×5시간×평일 250일(수당·보험료 제외)
S6_PT = VH(KS6) / 5                                             # 정점 보강 추가 근무량을 5시간 단시간 근무로 환산한 인원
t_of = lambda k: CB["pass_km_obs"] * (1 + SN[k]["empty"]) * CB["fleet_kgkm"] / 1000
EVK = IJ["ev"]
FIT = IJ["fits"]
TX = EX["taxi_share"]; R6 = EX["res6"]; CR = EX["commute_res"]; LV = EX["level"]

# ───────────────────────── 조판 도구
parts, fno, tno = [], [0], [0]
def add(h): parts.append(h)
def sec(t, first=False): add(f'<div class="sec{" first" if first else ""}">{t}</div>')
def sq(t): add(f'<div class="sq">{t}</div>')
def o(t, key=None): add(f'<p class="o">{f"<b>({key})</b> " if key else ""}{t}</p>')
def d(t): add(f'<p class="d">{t}</p>')
def nk(t): add(f'<p class="nk">{t}</p>')
def fig(path, title, src, mh=None, w=None):
    fno[0] += 1
    st = (f"max-height:{mh}mm;" if mh else "") + (f"max-width:{w}mm;" if w else "")
    add(f'<div class="fig"><img src="{(FIG / path).as_uri()}" style="{st}"><div class="fcap">[그림 {fno[0]}] {title}</div><div class="fsrc">자료: {src}</div></div>')
def tab(title, head, rows, src=None, unit=None, widths=None, rh=True, cls=""):
    tno[0] += 1
    cg = "".join(f'<col style="width:{w}">' for w in widths) if widths else ""
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(c if str(c).startswith("<td") else f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    u = f'<span class="u">(단위: {unit})</span>' if unit else ""
    s = f'<div class="tsrc">{src}</div>' if src else ""
    add(f'<div class="tw {cls}"><div class="tcap"><span class="t">【표 {tno[0]}】 {title}</span>{u}</div>'
        f'<table class="{"rh" if rh else ""}"><colgroup>{cg}</colgroup><tr>{th}</tr>{tr}</table>{s}</div>')
Lc = lambda x: f'<td class="l">{x}</td>'
xf = lambda k=1: f'<span class="xr">(그림 {fno[0] + k})</span>'
xt = lambda k=1: f'<span class="xr">(표 {tno[0] + k})</span>'

EXTRA = """
html { font-size:11pt; line-height:1.55; }
.sec { font-size:13.5pt; margin:5mm 0 3mm; break-before:auto; padding:1.1mm 2mm 0.9mm; }
.sec.pg { break-before:page; }
.sq { font-size:12pt; margin:3.4mm 0 1.4mm; padding-left:5mm; text-indent:-5mm; }
.sq::before { width:5mm; }
.o { padding-left:8.4mm; text-indent:-4.6mm; margin:0 0 1.1mm; }
.o::before { width:4.6mm; }
.d { font-size:10.6pt; padding-left:12mm; text-indent:-3mm; margin:0 0 0.9mm; }
.d::before { width:3mm; }
.nk { font-size:9.2pt; margin:0 0 1mm; line-height:1.45; padding-left:8.4mm; text-indent:-4.2mm; } .nk::before { width:4.2mm; }
.fig { margin:2.4mm 0 3mm; } .fig img { max-width:168mm; max-height:105mm; }
.fcap { font-size:9.8pt; margin-top:1mm; } .fsrc { font-size:8.6pt; }
.tw { margin:2.4mm 0 3mm; } .tcap { break-after:avoid; } .sq { break-after:avoid; }
.tcap { font-size:10pt; margin-bottom:0.8mm; } .tcap .u { font-size:8.6pt; }
table { font-size:8.9pt; line-height:1.32; }
th { padding:0.8mm 1mm; } td { padding:0.7mm 1mm; }
.tsrc { font-size:8.4pt; }
.small table { font-size:8.3pt; }
.brk { break-inside:auto; } .brk table { table-layout:fixed; } .brk tr { break-inside:avoid; }
.url { font-size:7.4pt; word-break:break-all; }
.head table { font-size:10.4pt; border:1.1pt solid #000; } .head td { padding:1.6mm 2.2mm; }
.head td:first-child { background:#dae3f3; width:28mm; font-weight:700; text-align:center; }
.formt { text-align:center; font-family:'HDo'; font-size:10.5pt; margin:0 0 1mm; }
.formh { text-align:center; font-family:'HL'; font-weight:800; font-size:19pt; letter-spacing:.35em; margin:0 0 4mm; }
.refs { font-size:8.6pt; line-height:1.36; } .refs li { margin-bottom:0.7mm; }
.prompt { font-family:'HDo'; font-size:9.3pt; background:#f4f4f2; border-left:2.2pt solid #8aa4d6; padding:1.2mm 2.4mm; margin:0.6mm 0 1.2mm 8.4mm; line-height:1.45; }
.cv2 { height:255mm; position:relative; }
.cv2 .top { position:absolute; top:6mm; left:0; right:0; text-align:center; font-family:'HDo'; font-size:12pt; }
.cv2 .kind { position:absolute; top:24mm; left:0; right:0; text-align:center; font-family:'HL'; font-weight:800; font-size:16pt; letter-spacing:.4em; }
.cv2 .box { position:absolute; left:4mm; right:4mm; top:58mm; border:2.8pt double #3d5a99; background:#e8eef9; padding:11mm 6mm; text-align:center; font-family:'HL'; font-weight:800; font-size:22pt; line-height:1.42; letter-spacing:-0.03em; }
.cv2 .box small { display:block; font-family:'HB'; font-size:12.5pt; font-weight:400; margin-top:4mm; letter-spacing:-0.02em; line-height:1.5; }
.cv2 .key { position:absolute; left:14mm; right:14mm; top:150mm; font-family:'HDo'; font-size:10.5pt; line-height:1.7; border-top:0.8pt solid #888; border-bottom:0.8pt solid #888; padding:3mm 2mm; }
.cv2 .date { position:absolute; top:205mm; left:0; right:0; text-align:center; font-family:'HL'; font-weight:800; font-size:16pt; letter-spacing:.12em; }
.cv2 .who { position:absolute; bottom:12mm; left:0; right:0; text-align:center; font-family:'HL'; font-weight:800; font-size:17pt; letter-spacing:.12em; line-height:1.6; }
.cv2 .who small { display:block; font-size:12pt; font-weight:500; letter-spacing:.02em; }
"""
BODY_PAGE = "@page { size:210mm 297mm; margin:17mm 17mm 16mm; @bottom-center { content:'- ' counter(page) ' -'; font-family:'HB'; font-size:10pt; } }"
FRONT_PAGE = "@page { size:210mm 297mm; margin:17mm 17mm 16mm; }"
doc = lambda body, page: f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><style>{FONTS}{page}{CSS}{EXTRA}</style></head><body>{body}</body></html>"

TITLE = "서울 장애인콜택시 대기시간 격차 분석 및 운전원 근무시간대 개선 방안"
SUB = "2025년 탑승기록 172만 건 진단, 배차 시뮬레이션 및 전기차 전환 효과 분석"

# ───────────────────────── 표지
cover = f"""<div class="cv2"><div class="top">- AI와 함께하는 교통문제 해결을 위한 데이터 분석 공모전 -</div>
<div class="kind">분석보고서</div>
<div class="box">{TITLE}<small>{SUB}</small></div>
<div class="key">○ 데이터: 서울시설공단 장애인콜택시 탑승내역 2025년 {f0(N['all'])}건(공공데이터포털) 외 8종<br>
○ 방법: 형평성 지표(로렌츠·지니·Theil 분해), Gi* 핫스팟, 회귀, 생존분석(포기), 이산사건 배차 시뮬레이션(근무시간대 조정·증원 배치·수요 분담), 탄소 배출 산정<br>
○ 분석 코드: {REPO}</div>
<div class="date">2026.  10.</div>
<div class="who">{A['name']}<small>{A['affiliation']}</small></div></div>"""

# ───────────────────────── 본문
add('<div class="formt">- AI와 함께하는 교통문제 해결을 위한 데이터 분석 공모전 -</div><div class="formh">분석보고서</div>')
add(f"""<div class="tw head"><table><tr><td>이름/팀명</td><td class="l">{A['name']} (개인 참가, {A['affiliation']})</td></tr>
<tr><td>주제</td><td class="l"><b>{TITLE}</b><br>- {SUB}</td></tr></table></div>""")

sec("Ⅰ. 분석 배경 및 목적", first=True)
sq("현황: 차량 확충 이후에도 출퇴근 시간대 장시간 대기 지속")
o("장애인콜택시를 2021년 632대에서 2025년 854대(법정 기준 569대의 151%)로 늘리는 계획 추진, 평균 대기는 2023년 47분에서 2025년 3월 32분으로 단축(서울시, 2025.5)", key="확충")
o("그러나 출근 시간대 평균 48분·퇴근 시간대 50분·최장 301분 대기가 확인되어 60분·90분 초과 대기율과 최대 대기를 관리지표로 삼자는 요구 제기(서울신문, 2026.9.4)", key="한계")
o(f"2025년 탑승기록(특장차 {f0(N['sp'])}건) 분석 결과 즉시 호출 대기 중앙값 {f1(O['med'])}분, "
  f"<b>60분 초과 대기 {pc(O['over60'])}</b>, 접수 후 취소 {pc(O['cancel'])} → 평균에 가려진 장시간 대기 상당", key="실태")
sq("기존 대책과 분석으로 확인한 공백")
POLGAP = [
    ("차량 확충", "2025년 854대 계획(법정 기준 151%)",
     f"동시 운행 차량은 연중 최대 {G['busy_max']['v']}대로 보유 698대의 {pc(G['busy_max']['v'] / 698, 0)} → 차량보다 운전 시간대가 제약"),
    ("단시간 운전원", "일 5시간, 2025년 150명(07∼12·16∼21·17∼22시 편성), 2026년 175명",
     f"오후 조 시작(16시)이 오후 대기 증가 시점(14시 30분)보다 늦어 14∼16시 공급 공백"),
    ("비휠체어 택시 연계", "바우처택시(일반택시, 이용자는 장애인콜택시 요금, 차액·호출료 시 부담), 전용 임차택시는 2025.12.31 종료",
     f"2025년 임차택시 운행의 {pc(TX['day_10_15'], 0)}가 대기가 가장 짧은 10∼15시, 18시 이후 {pc(TX['after18'], 0)} → 정점 분담 미흡, 시간대별 배차 유도 장치 없음"),
    ("평균 대기 관리", "연·월 평균 대기시간 공표",
     f"시간대·지역 분포와 60분 초과율 미공표, 06시대 예약의 {pc(R6['disp_after7'], 0)}가 07시 이후 배차"),
]
tab("기존 대책과 분석으로 확인한 공백", ["구분", "기존 대책", "분석으로 확인한 공백"], [[f"<b>{a}</b>", Lc(b), Lc(c)] for a, b, c in POLGAP],
    src="자료: 서울시(2025.5), 서울시 장애인 바우처택시 운영규정(2024.8), 서울시설공단 채용공고(2025.1)·임차택시 종료 안내(2025.12), 서울신문(2026.9.4), 응모자 분석", widths=["15%", "35%", "50%"], cls="small brk")
sq("목적")
o("① 시간대·지역별 대기·포기 격차 측정 ② 원인(운전원 근무 시간대·오후 운행 흐름) 규명 ③ 배차 시뮬레이션으로 근무시간대 조정·증원 배치·수요 분담·전기차 전환 효과 비교")
o("경영학 운영관리 관점에서 같은 자원으로 서비스 수준을 높이는 방안 검토. 장시간 대기는 통원·출근·통학 기회 손실로 이어지고, 대기 단축은 가족 차량 의존 완화로 탄소 감축에도 기여", key="참여 동기")

sec("Ⅱ. 활용 데이터")
DATA = [
    ("장애인콜택시 탑승내역(2025.1.1∼12.31)", "서울시설공단", "공공데이터포털", "data.go.kr/data/15115859/fileData.do", f"{f0(N['all'])}건(접수·배차·승차·하차·취소 시각, 출발·목적 행정동, 이용목적, 장애유형), 개인식별정보 없음"),
    ("장애인콜택시 시간대별 대기시간·탑승건수(2025)", "서울시설공단", "공공데이터포털", "data.go.kr/data/15147613/fileData.do<br>data.go.kr/data/15147614/fileData.do", "대기시간 정의·수준 검증"),
    ("장애인콜택시 차고지 정보(2026.7.14)", "서울시설공단", "공공데이터포털", "data.go.kr/data/15144781/fileData.do", "차고지 44곳·주차면 → 시뮬레이션 출발점"),
    ("장애인콜택시 차량정보(2026.8.6)", "서울시설공단", "공공데이터포털", "data.go.kr/data/15160788/fileData.do", "698대 차종·유종 → 배출량"),
    ("전국 대중교통 특별교통수단 운행현황(2024)", "한국교통안전공단", "공공데이터포털", "data.go.kr/data/15066774/fileData.do", "시·도별 법정기준대수 대비 운행대수"),
    ("장애인 현황(장애유형별/동별) 통계(2025)", "서울특별시", "서울 열린데이터광장", "data.seoul.go.kr/dataList/DT201004F040005/S/2/datasetView.do", "자치구별 등록장애인"),
    ("행정동 경계(2026.7.1)", "통계청(SGIS) 원자료", "GitHub", "github.com/vuski/admdongkor", "행정동 중심점·지도(CC BY 4.0)"),
    ("자동차 표시연비 정보(2026)", "한국에너지공단", "공공데이터포털", "data.go.kr/data/15083023/fileData.do", "대표 차종 도심 연비"),
    ("OpenStreetMap Nominatim 주소검색", "OSM 재단(오픈 데이터)", "OSM Nominatim", "nominatim.openstreetmap.org", "차고지 주소→좌표(ODbL, 1초 간격 준수)"),
]
tab("활용 데이터 목록", ["활용 데이터(명)", "제공기관(명)", "출처 플랫폼(명)", "URL", "규모·선정 이유"],
    [[Lc(a), b, c, Lc(f'<span class="url">{u}</span>'), Lc(e)] for a, b, c, u, e in DATA],
    src="모두 공개 파일을 내려받아 사용(크롤링·비공개 자료 없음). 정책 자료(단시간 근무 편성 등)와 배출계수는 Ⅶ 참고문헌에 출처 표기. 수집일 2026.10.17.",
    widths=["23%", "15%", "12%", "21%", "29%"], rh=True, cls="small brk")

sec("Ⅲ. 분석과정 및 방법")
sq("수집·전처리")
o(f"탑승내역 {f0(N['all'])}건 중 특장차 {f0(N['sp'])}건 분석(비휠체어 전용 임차택시 {f0(N['taxi'])}건은 비교에만 사용, 2025.12.31 운영 종료). "
  f"대기 = 승차시각 − 예정시각(즉시 호출은 접수시각과 같음), 포기 = 승차 없이 취소. 예약 호출({pc(1 - N['imm_share'], 0)})은 정해진 시각에 배차되므로 격차 분석은 즉시 호출 중심")
o(f"날짜·시간대별 평균 대기가 공단 공식 ‘시간대별 대기시간’({f0(G['official_check']['n'])}개 시간칸)과 상관 {G['official_check']['corr']:.3f}. "
  f"공식 자료의 탑승가중 연평균 {f1(LV['official_weighted'])}분과 본 분석(특장차+임차택시) {f1(LV['mine_all'])}분이 일치하여 같은 지표임을 확인", key="검증")
o("출발·목적 행정동 이름을 2026.7 경계와 대응(97.1% 일치, 옛 동명 2.9%는 같은 구 현행 동들로 묶어 중심점 부여)")
sq("분석 기법(해외 연구 방법 적용)")
METH = [
    ("형평성·분해", "로렌츠 곡선·지니계수(Delbosc & Currie, 2011; Jang et al., 2017), 60분 기준 미달 비율(Lucas et al., 2016), Theil T 분해(시간대·생활권·자치구·행정동 간 몫, Theil, 1967)"),
    ("핫스팟·요인", f"행정동 평균 대기의 Getis-Ord Gi*(퀸 인접, 999회 순열)와 OLS(강건 표준오차, n={f0(G['ols']['n'])}) — 덴버 장애인 교통 분석 틀(Akcicek et al., 2024) 적용"),
    ("포기 분석", "Kaplan–Meier 인내시간(취소=인내 소진, 승차=중도절단; Brown et al., 2005), 시나리오 대기를 기대 포기율로 환산(Garnett et al., 2002)"),
    ("배차 시뮬레이션", f"실제 호출 7만여 건(11월 평일) 재배차(최근접 빈 차 배차, 이동시간 = 준비시간 + 1.30×직선거리 ÷ 시간대별 실측 속도, 근무 차량 = 관측 운행 차량 곡선), "
                   f"11월 보정(준비 {C['best']['c']}분, 가동률 {1 + C['best']['a']:.2f})·9월 표본 밖 검증"),
    ("근무 시나리오", "공단 채용공고의 단시간 근무 편성(일 5시간) 기준 근무시간대 이동·증원 배치 비교, 시간 안정 근무 곡선(Jennings et al., 1996; Feldman et al., 2008)으로 재배분 상한 산정, 매개변수 민감도 분석"),
    ("탄소·전기차", "운행거리(실측 승차거리+시뮬레이션 빈 차 비율)×대표 차종 도심 연비×배출계수(순발열량×IPCC 기본값, 전력 2023년 계수), 차량·일 주행거리와 1회 충전 주행거리 비교(CALSTART, 2023)"),
]
tab("분석 단계와 적용 방법", ["단계", "방법과 근거"], [[b, Lc(t)] for b, t in METH], widths=["15%", "85%"], cls="small brk")

sec("Ⅳ. AI 기술 활용")
o("사용 서비스: <b>Claude Code(Anthropic)</b> — 코드를 직접 작성·실행하는 AI 코딩 도구", key="서비스")
o("활용 범위: 데이터 탐색·내려받기, 전처리·분석·시뮬레이션 코드 작성·실행, 정책 자료·해외 문헌 검색, 그림·보고서 초안 조판. 주제 선정·결과 해석·정책 제안은 응모자가 검토해 확정", key="범위")
o("주요 프롬프트(응모자 요청의 요지, 시간순):", key="프롬프트")
for p in A["prompts"]:
    add(f'<div class="prompt">{p}</div>')
o("검증: 모든 수치는 공개 원자료에서 코드로 재계산(GitHub 공개), 대기 정의·수준은 공단 공식 통계와 대조, 문헌·정책 자료는 원문 확인. "
  "맞지 않은 AI 제안 방법(정상상태 근무 산정(Green et al., 2007)·출근 시각 국소탐색·대기 거점)은 결과 확인 후 제외하고 본문에 기재", key="검증")
o(f"자료 보호: AI에 입력한 자료는 공공데이터포털·서울 열린데이터광장의 공개 파일뿐(개인식별정보·위치정보·비공개 자료 없음). {A['ai_setting']}", key="보호")

sec("Ⅴ. 분석 내용 및 결과")
sq("① 시간대별 격차: 출근(07∼09시)·오후(14∼17시) 시간대 대기 집중")
o(f"평일 즉시 호출 대기 중앙값은 07∼08시 {f0(H.wait_med[7])}∼{f0(H.wait_med[8])}분, 16시 {f0(H.wait_med[16])}분으로 낮 시간({f0(H.wait_med[13])}분)의 2배 이상이며, "
  f"16시 호출의 {pc(H.cancel[16], 0)}가 취소됨{xf()}")
o(f"보유 차량 698대 중 동시 운행 차량은 연중 최대 {G['busy_max']['v']}대. 07시 평균 {f0(H.busy_mean[7])}대만 운행하고, 15시 이후에는 호출이 많은데도 운행 차량이 감소 "
  f"→ <b>병목은 차량 대수보다 운전원 근무 시간대와 수요의 불일치</b>", key="공급")
fig("fig1_hour.png", "평일 시간대별 호출·운행 중 차량·대기와 단시간 근무 편성(2025년, 특장차 즉시 호출)", "서울시설공단 장애인콜택시 탑승내역(2025), 공단 채용공고(2025.1) 응모자 분석", mh=46)
o(f"06시대 예약 호출(평일 하루 {f0(R6['per_day'])}건)은 {pc(R6['disp_after7'], 0)}가 07시 이후 배차되어 예정 대비 지연 중앙값 {f0(R6['late_med'])}분. "
  f"출근·통학 호출은 {pc(CR['share_reserved'], 0)}가 예약을 이용하나 <b>예약의 {pc(CR['over30'], 0)}가 예정보다 30분 넘게 늦게 승차</b>(60분 초과 {pc(CR['over60'], 0)}) → 정시성 문제", key="첫 근무·예약")
sq("② 지역별 격차: 도심·동남권 고대기 군집, 원인은 오후 귀가 흐름")
o(f"60분 초과 대기 비율은 행정동 하위 10% {pc(G['dong']['over60_q']['0.1'], 0)}, 상위 10% {pc(G['dong']['over60_q']['0.9'], 0)}. 로렌츠 곡선 지니계수 {L['gini']:.2f}, "
  f"대기가 긴 동의 호출 20%가 전체 긴 대기의 {pc(L['top20'], 0)} 차지. Gi* 고대기 군집 {HS['hot']}개 동(서초·강남·중구·용산·관악·동작·종로), 저대기 군집 {HS['cold']}개 동(노원·중랑·도봉·강동){xf()}")
o(f"시간대·거리·목적을 통제한 회귀에서 도심권 출발은 동북권보다 {f1(cf(LIFE.format('도심권')))}분, 동남권 {f1(cf(LIFE.format('동남권')))}분 더 대기(장애유형 차이 0.2분 이내, R²={G['ols']['r2']:.2f}). "
  f"오후 도심권은 승차 {f0(bal['도심권']['pickup'])}건 대비 하차 {f0(bal['도심권']['dropoff'])}건(하루 평균)으로 빈 차가 외곽에 쌓이며, 차고지 주차면 비중({pc(dl['도심권']['park_share'], 0)})은 호출 비중({pc(dl['도심권']['call_share'], 0)})보다 커 차고지보다 오후 귀가 흐름이 원인", key="요인")
o(f"Theil 분해 결과 대기 불평등 중 <b>시간대 간 몫 {pc(TH['시간대(24)']['share'], 0)}</b>, 생활권 간 {pc(TH['생활권(5)']['share'], 1)}, 자치구 간 {pc(TH['자치구(25)']['share'], 1)}, "
  f"행정동 간 {pc(TH['행정동']['share'], 1)} → 지역 격차보다 <b>시간대 공급 조정이 우선 과제</b>", key="분해")
fig("fig2_map.png", "행정동별 60분 초과 대기 비율과 평균 대기 핫스팟(즉시 호출, 200건 이상 동)", "서울시설공단 탑승내역·차고지 정보, 통계청 행정동 경계 응모자 분석", mh=60)
sq("③ 대기와 포기: 60분 대기 시 5건 중 1건 취소")
o(f"Kaplan–Meier 추정 결과 호출 후 30분 안에 {pc(1 - PT['S30'], 0)}, 60분 {pc(1 - PT['S60'], 0)}, 90분 {pc(1 - PT['S90'], 0)}가 취소하며 취소의 {pc(PT['cancel_before_dispatch'], 0)}는 배차 전에 발생 "
  f"→ 대기 단축이 숨은 이동 포기 감소로 직결(그림 4 ③)")
sq("④ 배차 시뮬레이션: 단시간 운전원 근무시간대 조정과 증원 배치 효과")
cal, val = C["calib"], C["valid"]
o(f"시뮬레이터는 보정월(11월) P90 {f0(cal['p90'])}분(실측 {f0(cal['obs_p90'])}), 접근시간 {f1(cal['appr'])}분(실측 {f1(cal['obs_appr'])}), 표본 밖 9월 P90 {f0(val['p90'])}분(실측 {f0(val['obs_p90'])})을 재현. "
  f"중앙값은 다소 크게 나와({f1(cal['med'])}분, 실측 {f1(cal['obs_med'])}) 정책 효과는 현행 대비 변화로 해석", key="검증")
ROWS = [(k0, "현행(2025년 11월 추정 공급)", "−"),
        (KL20, "오후 단시간 20명 근무시간 이동(16∼21시→14∼19시)", "0"),
        (KL30, "<b>오후 단시간 30명 근무시간 이동(16∼21시→14∼19시)</b>", "0"),
        (KH1, "낮 근무 재배분(시간 안정 곡선, 2∼3시간 블록 필요)", "0"),
        (KP2, "단시간 25명 증원 – 16∼21시 배치(현행 편성)", f"+{f0(VH(KP2))}"),
        (KP3, "<b>단시간 25명 증원 – 14∼19시 배치</b>", f"+{f0(VH(KP3))}"),
        (KS4, "균등 증차 10%", f"+{f0(VH(KS4))}"),
        (KS6, "정점 집중 보강 10%(07:00∼09:30·14:30∼17:30)", f"+{f0(VH(KS6))}"),
        (KD, f"14∼18시 호출 10% 바우처택시 분담(하루 {f0(SN[KD]['diverted_per_day'])}건)", "0")]
def sep_chg(k):
    if k == k0: return "−"
    if k == KH1: return sg(H1_SEP) + "*"
    return sg(chg(k, SS))
tab("시나리오별 즉시 호출 대기(평일 재배차, 11월 평가·9월 재현)", ["시나리오", "추가 근무<br>(대·시간/일)", "평균", "변화율<br>(11월)", "변화율<br>(9월)", "P90", "60분 초과", "기대<br>포기율**"],
    [[Lc(nm), vh, f1(SN[k]['mean']), ("−" if k == k0 else sg(chg(k))), sep_chg(k), f0(SN[k]['p90']), pc(SN[k]['over60']), pc(SN[k]['aband'])] for k, nm, vh in ROWS],
    src="변화율(9월)의 *는 9월로 곡선을 만든 학습월 값. 기대 포기율(**)은 시나리오 대기에 Kaplan–Meier 포기 확률을 적용한 값(실제 취소 건은 재배차에서 제외되어 변화폭이 의미 있음). 단시간 운전원 1명 = 근무 중 차량 1대로 가정",
    unit="분, %", widths=["37%", "10%", "7%", "9%", "9%", "6%", "10%", "12%"], cls="small")
o(f"오후 단시간 조 30명의 근무를 2시간 앞당기면 <b>총 근무시간 변화 없이</b> 평균 대기 {f1(SN[k0]['mean'])}→{f1(SN[KL30]['mean'])}분({pc(chg(KL30))}, 9월 {pc(chg(KL30, SS))}), "
  f"14∼17시 평균 {f0(pm(k0))}→{f0(pm(KL30))}분, 60분 초과 {pc(SN[k0]['over60'], 0)}→{pc(SN[KL30]['over60'], 0)}. 다만 20∼21시 평균은 {f0(hm(k0, 20))}·{f0(hm(k0, 21))}분→{f0(hm(KL30, 20))}·{f0(hm(KL30, 21))}분으로 늘어 "
  f"저녁 최소 차량 기준 병행 필요(20명 이동 시 {pc(chg(KL20))}, 저녁 {f0(hm(KL20, 20))}·{f0(hm(KL20, 21))}분){xf()}", key="재배치")
o(f"2026년 증원분 25명을 현행처럼 16∼21시에 두면 {pc(chg(KP2))}, 14∼19시에 두면 {pc(chg(KP3))}로 같은 인건비에 효과 {chg(KP3) / chg(KP2):.1f}배. "
  f"<b>기존 30명의 근무시간 이동(추가 비용 없음, {pc(chg(KL30))})이 16∼21시 증원 25명({pc(chg(KP2))})보다 큰 효과</b>", key="증원 배치")
o(f"같은 추가 근무량(평일 하루 {f0(VH(KS6))}대·시간)은 균등 증차 시 {pc(chg(KS4))}, 정점 집중 시 {pc(chg(KS6))}. 낮 근무 시간 안정 재배분은 {pc(chg(KH1))}이나 2∼3시간 근무 블록 필요(4시간 이상 근무조로는 효과 소멸). "
  f"14∼18시 호출 10% 바우처 분담 시 {pc(chg(KD))}", key="증원·분담")
o(f"준비시간(8∼12분)·우회계수(1.2∼1.4)·배차 규칙(θ 0.1∼0.5)·가동률(0.80∼0.90)을 바꾼 8개 조건에서 오후 조 이동 효과 {pc(max(sens_l30))}∼{pc(min(sens_l30))}"
  f"{'로 시나리오 순서 유지' if sens_order else ''}. 출근 시각 국소탐색(9월 학습 효과가 11월에 소멸)·MEXCLP 대기 거점(Daskin, 1983; 낮 빈 차 부족)은 효과 없음", key="민감도")
fig("fig4_policy.png", "단시간 운전원 근무시간대 조정·증원 배치 시나리오의 근무 차량과 시간대별 평균 대기(11월 평일 재배차)", "응모자 시뮬레이션(코드: GitHub)", mh=52)
sq(f"⑤ 탄소: 연간 약 {f0(CB['base_t'])}톤, 전기 승합 전환 시 {pc(CB['ev_cut'] / CB['base_t'], 0)} 감축")
o(f"특장차 2025년 실측 승차거리 {f0(CB['pass_km_obs'] / 1e4)}만㎞에 빈 차 주행(승차 1㎞당 {CB['empty_ratio']:.2f}㎞)을 더하면 연간 약 {f0(CB['pass_km_obs'] * (1 + CB['empty_ratio']) / 1e4)}만㎞, "
  f"차량 구성(LPG {CB['fleet_mix'].get('LPG', 0)}·휘발유 {CB['fleet_mix'].get('휘발유', 0)}·경유 {CB['fleet_mix'].get('경유', 0)}대) 기준 약 {f0(CB['base_t'])}tCO₂. "
  f"전량 전기 승합(도심 {CB['rep_models']['전기']['city_kmpl']}㎞/kWh)으로 전환하면 {f0(CB['ev_t'])}tCO₂eq로 {f0(CB['ev_cut'])}톤({pc(CB['ev_cut'] / CB['base_t'], 0)}) 감축")
o(f"빈 차 주행 증가로 배출은 오후 조 이동 시 {pc(t_of(KL30) / t_of(k0) - 1)}(연 {f0(t_of(KL30))}톤), 균등 증차 {pc(t_of(KS4) / t_of(k0) - 1)}·정점 보강 {pc(t_of(KS6) / t_of(k0) - 1)} 늘어 증원 차량부터 전기 승합 도입 필요. "
  f"차량·일 주행거리는 상위 5% {f0(EVK['S0 현행']['p95'])}㎞로 1회 충전 {f0(EVK['range_km'])}㎞ 초과일 {pc(EVK['S0 현행']['share_over_range'])} → 차고지 야간 충전으로 운행 가능(CALSTART, 2023 방식)", key="시나리오")

sec("Ⅵ. 정책제안 및 기대효과")
POL = [
    ("① 단시간 운전원 오후 조 근무시간 조정",
     f"16∼21시 편성 중 20∼30명을 14∼19시로 2시간 앞당김 → 추가 인건비 없이 평균 대기 {pc(chg(KL20), 0)}∼{pc(chg(KL30), 0)}, 14∼17시 평균 {f0(pm(k0))}→{f0(pm(KL30))}분. 저녁 대기는 17∼22시 편성 유지·최소 차량 기준으로 관리",
     "서울시설공단(단시간 근무 편성)"),
    ("② 증원 인력의 정점 배치",
     f"신규 단시간 운전원은 14∼19시·07∼12시 우선 배치(25명 기준 효과 {chg(KP3) / chg(KP2):.1f}배). 중기적으로 2∼3시간 정점 블록(시간제·연장근무) 도입 시 같은 근무시간으로 {pc(chg(KH1), 0)}",
     "서울시·공단(채용·근무 계획, 노사 협의)"),
    ("③ 대기시간 분포 성과지표 공표",
     "60분·90분 초과 대기율, 최대 대기, 예약 정시율(예정 30분 이내 승차), 행정동 지니계수, 시간대별 P90 매월 공표. 공개 탑승기록으로 추가 비용 없이 산출(본 분석 코드 재사용)",
     "서울시·공단, 국토교통부 이동편의 실태조사"),
    ("④ 바우처택시 정점 배차 유도",
     f"정점(07∼09시·14∼18시) 바우처택시 배차에 시간대별 인센티브를 가산해 비휠체어 정점 호출 분담 유도(10% 분담 시 {pc(chg(KD), 0)}). 2025년 임차택시는 운행의 {pc(TX['day_10_15'], 0)}가 10∼15시에 몰려 정점 분담이 약했음. "
     "보스턴 MBTA 택시 연계 사례(보조금 $31→$9, 이용 +28%)처럼 이용 상한(현행 월 60회)·대상 기준 병행",
     "서울시 택시정책과·공단"),
    ("⑤ 교체 주기에 맞춘 전기 승합 전환",
     f"증원 차량과 내구연한 도래 LPG·경유 차량부터 전기 휠체어탑승차로 교체, 차고지 44곳(주차면 {f0(pd.read_csv(PROC / 'depots.csv').주차대수.sum())}면) 야간 충전 → 전량 전환 시 연 {f0(CB['ev_cut'])}톤 감축. 탑승기록 표준 공개를 타 시·도로 확산",
     "서울시 기후환경본부·공단, 국토교통부"),
]
tab("정책 제안과 적용 대상", ["제안", "내용", "적용 대상"], [[Lc(f"<b>{a}</b>"), Lc(b), Lc(c)] for a, b, c in POL], widths=["19%", "63%", "18%"], rh=False, cls="small brk")
o(f"1단계(오후 조 30명 이동) 평균 대기 {pc(chg(KL30), 0)}, 60분 초과 대기 {pc(SN[k0]['over60'], 0)}→{pc(SN[KL30]['over60'], 0)}, 연간 약 {f0(recov(KL30))}건의 포기가 승차로 전환(2025년 즉시 호출 {f0(N['imm_n'])}건 기준). "
  f"2단계(정점 집중 보강 10%) {pc(chg(KS6), 0)}, 60분 초과 {pc(SN[KS6]['over60'], 0)}, 포기 전환 연 {f0(recov(KS6))}건. 전기 승합 전환으로 연 약 {f0(CB['ev_cut'])}톤 CO₂ 감축", key="효과")
o(f"1단계는 근무 편성 변경으로 추가 예산 없음. 단시간 운전원 기본시급 {f0(WAGE)}원(2025년 공고) 기준 25명 증원은 연 약 {PT_YEAR * 25 / 1e8:.1f}억 원, "
  f"정점 집중 보강 10%(단시간 {f0(S6_PT)}명 상당)는 연 약 {PT_YEAR * S6_PT / 1e8:.1f}억 원(수당·보험료 제외)으로 같은 비용이라도 배치 시간대에 따라 효과가 2배 이상 차이", key="비용")
o("이동 시간 예측 가능성이 높아지면 가족 돌봄 운전·일반 택시 이용이 줄어 형평성 개선과 배출 감축이 함께 나타나며, 수요응답형 교통(DRT)·고령자 이동지원에도 적용 가능", key="파급")
o("실제 근무표·차량 위치가 비공개라 근무 차량 수를 운행기록으로 추정(단시간 운전원 1명 = 차량 1대 가정), 거리는 행정동 중심점 기준 근사 → 공단 근무표로 재보정 필요", key="한계")

add('<div class="sec pg">Ⅶ. 분석도구 및 참고문헌</div>')
o("도구: Python 3.12(pandas, geopandas, statsmodels, lifelines, esda·libpysal, PuLP·CBC, matplotlib), Playwright(공공데이터포털 파일 내려받기), Claude Code", key="도구")
o(f"분석 코드: <b>{REPO}</b> (README에 재실행 순서, 원자료는 공공데이터포털에서 스크립트로 다시 내려받음)", key="코드")
REFS = [
    "Akcicek, C., Shirgaokar, M., Misra, A., Marshall, W., & Wagner, M. (2024). <i>Understanding Paratransit: Examining Time Inefficiencies and the Efficacy of Alternative Modes for Persons with Disability</i> (MPC-677). Mountain-Plains Consortium. https://rosap.ntl.bts.gov/view/dot/78935",
    "Brown, L., Gans, N., Mandelbaum, A., Sakov, A., Shen, H., Zeltyn, S., & Zhao, L. (2005). Statistical analysis of a telephone call center: A queueing-science perspective. <i>Journal of the American Statistical Association</i>, 100(469), 36–50. https://doi.org/10.1198/016214504000001808",
    "CALSTART (2023). <i>Clovis Transit Fleet Electrification Feasibility Study</i> (Final, 2023.2.24). City of Clovis, CA.",
    "Daskin, M. S. (1983). A maximum expected covering location model: Formulation, properties and heuristic solution. <i>Transportation Science</i>, 17(1), 48–70. https://doi.org/10.1287/trsc.17.1.48",
    "Delbosc, A., & Currie, G. (2011). Using Lorenz curves to assess public transport equity. <i>Journal of Transport Geography</i>, 19(6), 1252–1259. https://doi.org/10.1016/j.jtrangeo.2011.02.008",
    "Feldman, Z., Mandelbaum, A., Massey, W. A., & Whitt, W. (2008). Staffing of time-varying queues to achieve time-stable performance. <i>Management Science</i>, 54(2), 324–338. https://doi.org/10.1287/mnsc.1070.0821",
    "Garnett, O., Mandelbaum, A., & Reiman, M. (2002). Designing a call center with impatient customers. <i>Manufacturing & Service Operations Management</i>, 4(3), 208–227. https://doi.org/10.1287/msom.4.3.208.7753",
    "Green, L. V., Kolesar, P. J., & Whitt, W. (2007). Coping with time-varying demand when setting staffing requirements for a service system. <i>Production and Operations Management</i>, 16(1), 13–39. https://doi.org/10.1111/j.1937-5956.2007.tb00164.x",
    "Jang, S., An, Y., Yi, C., & Lee, S. (2017). Assessing the spatial equity of Seoul's public transportation using the Gini coefficient based on its accessibility. <i>International Journal of Urban Sciences</i>, 21(1), 91–107.",
    "Jennings, O. B., Mandelbaum, A., Massey, W. A., & Whitt, W. (1996). Server staffing to meet time-varying demand. <i>Management Science</i>, 42(10), 1383–1394. https://doi.org/10.1287/mnsc.42.10.1383",
    "Lucas, K., van Wee, B., & Maat, K. (2016). A method to evaluate equitable accessibility: Combining ethical theories and accessibility-based approaches. <i>Transportation</i>, 43(3), 473–490. https://doi.org/10.1007/s11116-015-9585-2",
    "MBTA (2017.2.28). Governor Baker, MBTA celebrate expansion of The RIDE's on-demand paratransit service (보도자료). https://www.mbta.com/news/2017-02-28/governor-baker-mbta-celebrate-expansion-the-rides-demand-paratransit-service",
    "Theil, H. (1967). <i>Economics and Information Theory</i>. North-Holland.",
    "IPCC (2006). <i>2006 IPCC Guidelines for National Greenhouse Gas Inventories</i>, Vol. 2 Energy, Ch. 3 Mobile Combustion(도로 수송 CO₂ 기본 배출계수).",
    "서울시설공단(2025.1). 2025년 서울시설공단 계약직원 공개채용 공고(장애인콜택시 운전원(단시간) 150명, 일 5시간, 07:00∼12:00/16:00∼21:00/17:00∼22:00 등 편성, 시급 12,030원).",
    "서울특별시(2025.5.15). 장애인콜택시 150% 확보 추진…약자를 위한 서울 택시의 변화. 내 손안에 서울. https://mediahub.seoul.go.kr/archives/2014386",
    "서울특별시(2024.8.1). 장애인 바우처택시 운영규정(이용요금·월 60회·보조금·인센티브). https://news.seoul.go.kr/traffic/archives/512540",
    "서울시설공단(2025.12.22). 임차택시 서비스 종료 예정 안내(장애인 전용 임차택시 2025.12.31 운영 종료). 장애인콜택시 공지사항, sisul.or.kr",
    "서울신문(2026.9.4). 유기훈 서울시의원 “장애인콜택시 평균 대기 34분 뒤에 가려진 ‘5시간 대기’ 살펴야”. https://go.seoul.co.kr/news/newsView.php?id=20260904500192",
    "에너지법 시행규칙 [별표] 에너지열량 환산기준(개정 2022.11.21.), 국가법령정보센터 law.go.kr",
    "기후에너지환경부(2025.12). 전력배출계수 갱신 주기 3년에서 1년으로 단축(2023년도 전력배출계수 0.4173 tCO₂eq/MWh) 보도자료, mcee.go.kr",
    "한국가스안전공사(2015). 가스설계지침(가스 물성정보: 부탄 액비중). koreascience.kr/article/JAKO201647740042930",
    "「교통약자의 이동편의 증진법」 및 같은 법 시행규칙(특별교통수단 법정 운행대수 기준), 국가법령정보센터",
]
add('<ol class="refs">' + "".join(f"<li>{r}</li>" for r in REFS) + "</ol>")

add('<div class="sec pg">Ⅷ. 분석결과 이미지</div>')
o("본문 [그림 1](시간대별 호출·운행 차량·대기와 단시간 근무 편성), [그림 2](행정동 지도·핫스팟), [그림 3](근무시간대 조정 시뮬레이션)이 분석결과 이미지이며, "
  "핵심 결과와 정책 제안의 요약은 [그림 4]와 같음. 그림은 모두 공개 원자료에서 GitHub 코드(figures.py, figures2.py)로 다시 그릴 수 있음")
fig("fig5_summary.png", "서울 장애인콜택시 대기시간 격차 분석 결과와 정책 제안 요약", "응모자 분석(2025년 탑승내역 172만 건)", mh=215)


async def pdf(html, out):
    from playwright.async_api import async_playwright
    p = Path(out).with_suffix(".html"); p.write_text(html, encoding="utf-8")
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); pg = await b.new_page()
        await pg.goto(p.as_uri(), wait_until="networkidle"); await pg.wait_for_timeout(800)
        await pg.pdf(path=str(out), prefer_css_page_size=True, print_background=True); await b.close()

if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="rep_"))
    asyncio.run(pdf(doc(hwpify(cover), FRONT_PAGE), tmp / "cover.pdf"))
    asyncio.run(pdf(doc(hwpify("".join(parts)), BODY_PAGE), tmp / "body.pdf"))
    out = OUT / f"{A['name']}_분석기획서.pdf"
    subprocess.run(["pdfunite", str(tmp / "cover.pdf"), str(tmp / "body.pdf"), str(out)], check=True)
    np_ = re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(tmp / "body.pdf")], capture_output=True, text=True).stdout).group(1)
    # 참고문헌이 시작하는 쪽 = 본문 분량 끝
    for i in range(1, int(np_) + 1):
        t = subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), str(tmp / "body.pdf"), "-"], capture_output=True, text=True).stdout
        if "Ⅶ. 분석도구" in t: print("참고문헌 시작 쪽:", i)
    print("본문 PDF 쪽수:", np_, "→", out)
