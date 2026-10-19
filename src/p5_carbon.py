"""특장차 운행 탄소배출(연간)과 감축 시나리오
- 운행거리: 2025년 실제 승차거리 합계(특장차 완료 운행) + 빈 차 거리(시뮬레이션의 빈차/승차 거리 비율로 추정)
- 차량 구성: 서울시설공단 차량정보(유종별 대수) / 대표 차종 도심 연비: 한국에너지공단 표시연비
- 배출계수: 순발열량(에너지법 시행규칙 별표, 2022.11.21 개정) × IPCC 2006 기본 CO2 계수(휘발유 69,300·경유 74,100·LPG 63,100 kg/TJ)
  부탄 액비중 0.59(한국가스안전공사 가스설계지침의 i-부탄 0.59·n-부탄 0.60), 전력 0.4173 tCO2eq/MWh(2023년도, 기후에너지환경부 2025.12)"""
import json, re, numpy as np, pandas as pd
from common import RAW, PROC

fe = pd.read_csv(next(RAW.glob("15083023_*.csv")), encoding="utf-8-sig")
def city(pat):
    r = fe[fe.모델명.str.contains(pat, regex=True)].iloc[0]; return float(r.도심_연비), r.모델명
REP = {"LPG": city(r"^스타리아\(US4\) PE 3\.5LPI 8AT 11인 .*빌트인캠 On"),
       "경유": city(r"^카니발 2\.2디젤 11인 18인치\(22\)"),
       "휘발유": city(r"^카니발 3\.5GDI 11인 18인치타이어$"),
       "전기": city(r"^스타리아\(US4\) EV 11인"),
       "하이브리드": city(r"^스타리아\(US4\) PE 1\.6T-GDI HEV 6AT 11인 17인치")}
NCV = {"휘발유": 30.1, "경유": 35.3, "LPG": 45.5 * 0.59, "하이브리드": 30.1}      # MJ/L
EF = {"휘발유": 69.3, "경유": 74.1, "LPG": 63.1, "하이브리드": 69.3}             # gCO2/MJ (IPCC 2006)
kg_per_l = {k: NCV[k] * EF[k] / 1000 for k in NCV}
GRID = 0.4173                                                                     # kgCO2eq/kWh
kg_km = {k: kg_per_l[k] / REP[k][0] for k in kg_per_l}; kg_km["전기"] = GRID / REP["전기"][0]

veh = pd.read_csv(next(RAW.glob("15160788_*.csv")), encoding="cp949")
mix = veh.유종.value_counts(); mix = mix[mix.index.isin(["LPG", "경유", "휘발유"])]
fleet_kgkm = float(sum(kg_km[f] * n for f, n in mix.items()) / mix.sum())

t = pd.read_parquet(PROC / "trips.parquet", columns=["차량구분", "done", "승차거리"])
pass_km_obs = float(t[(t.차량구분 == "특장차") & t.done].승차거리.sum() / 1000)
sc = pd.read_csv(PROC / "scenarios.csv").set_index("name")
isa = PROC / "isa_scenarios.csv"          # p6_isa.py 결과(낮 재배분 등)도 함께 환산
if isa.exists():
    extra = pd.read_csv(isa).set_index("name"); sc = pd.concat([sc, extra.loc[~extra.index.isin(sc.index), sc.columns]])
base = sc.loc["S0 현행"]
empty_ratio = float((base.dead_km + base.ret_km + base.reloc_km) / base.pass_km)   # 승차 1km당 빈 차 km
rows = []
for name, r in sc.iterrows():
    ratio = (r.dead_km + r.ret_km + r.reloc_km) / base.pass_km
    km = pass_km_obs * (1 + ratio)
    rows.append(dict(name=name, empty_ratio=ratio, km=km, t_co2=km * fleet_kgkm / 1000))
out = pd.DataFrame(rows).set_index("name")
b = out.loc["S0 현행"]
ev = dict(t_co2=b.km * kg_km["전기"] / 1000, hev=b.km * kg_km["하이브리드"] / 1000)
lpg_lo, lpg_hi = (45.5 * d * 63.1 / 1000 / REP["LPG"][0] for d in (0.55, 0.60))
res = dict(rep_models={k: dict(model=v[1], city_kmpl=v[0]) for k, v in REP.items()}, kg_per_l=kg_per_l, kg_km=kg_km,
           fleet_mix=mix.to_dict(), fleet_kgkm=fleet_kgkm, pass_km_obs=pass_km_obs, empty_ratio=empty_ratio,
           scen=out.round(3).reset_index().to_dict("records"), base_t=float(b.t_co2), ev_t=float(ev["t_co2"]),
           hev_t=float(ev["hev"]), ev_cut=float(b.t_co2 - ev["t_co2"]), lpg_kgkm_range=[lpg_lo, lpg_hi],
           per_vehicle_km=float(b.km / 698))
json.dump(res, open(PROC / "carbon.json", "w"), ensure_ascii=False, indent=1, default=float)
print(json.dumps(res, ensure_ascii=False, indent=1, default=float)[:2500])
