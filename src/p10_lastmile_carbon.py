"""라스트마일 연계(지하철 엘리베이터 동선 + 단거리 택시)와 수단별 탄소 비교
A. 연계 가능 호출: 출발·목적 행정동 중심점이 모두 지하철역 1㎞ 안이고 직선거리 5㎞ 이상인 특장차 즉시 호출(2025)
   - 역 좌표: OpenStreetMap railway=station(지하철·경전철·광역철도, Overpass 2026-10-19 수집, ODbL)
   - 서울 지하철은 2025.12 전 역사 '1역사 1동선'(엘리베이터) 확보(서울교통공사 구간). 코레일 구간 일부 미확보는 한계로 기재
B. 시뮬레이션(v2, 11월 평일): 연계 가능 호출 중 u%가 전환
   - A안: 역↔집 구간을 민간 택시(바우처·WAV)가 맡음 → 특장차 수요에서 제외
   - B안: 역↔집 구간도 특장차가 맡음 → 긴 운행 1건을 짧은 운행 2건(출발지→출발역, 도착역→목적지)으로 대체.
     둘째 구간은 첫 구간 도착 + 지하철 이동(직선거리÷30㎞/h + 환승·승강 10분) 시각에 사전 예약
C. 수단별 1건당 CO₂(평균 특장차 운행거리 기준): 특장차(LPG·전기, 빈 차 주행 포함), 바우처 일반택시(LPG·전기, 호출 접근 2㎞ 가정),
   지하철+양끝 1㎞ 택시(지하철 한계 배출 0으로 가정), 가족 차량 동행(왕복 운전 가정)
   연비: 한국에너지공단 표시연비(도심), 배출계수: p5_carbon.py와 같음"""
import json, numpy as np, pandas as pd, geopandas as gpd
import simdata as sd
from p8_sim_ab import setup
from p9_package import evaluate, C, TH, A
from common import PROC, RAW

ST = RAW / "osm_subway_stations.json"
if not ST.exists():   # OpenStreetMap Overpass API에서 서울 일대 railway=station 노드 받기(ODbL)
    import urllib.parse, urllib.request
    q = '[out:json][timeout:90];(node["railway"="station"](37.42,126.76,37.71,127.19);node["public_transport"="station"]["subway"="yes"](37.42,126.76,37.71,127.19););out body;'
    req = urllib.request.Request("https://overpass-api.de/api/interpreter?" + urllib.parse.urlencode({"data": q}), headers={"User-Agent": "koreashe-transport-data-2026-analysis/1.0"})
    ST.write_bytes(urllib.request.urlopen(req, timeout=120).read())
st = json.load(open(ST))["elements"]
sg = gpd.GeoSeries(gpd.points_from_xy([e["lon"] for e in st], [e["lat"] for e in st]), crs=4326).to_crs(5179)
SX, SY = sg.x.values, sg.y.values
dg = pd.read_parquet(PROC / "dongs.parquet")
D = np.hypot(dg.x.values[:, None] - SX[None, :], dg.y.values[:, None] - SY[None, :])
dg["st_km"] = D.min(1) / 1000; dg["st_x"] = SX[D.argmin(1)]; dg["st_y"] = SY[D.argmin(1)]
DG = dg.set_index("adm_cd2")

def eligible(df, r_km=1.0, min_km=5.0):
    o = DG.reindex(df.o_adm.astype(str)); d = DG.reindex(df.d_adm.astype(str)) if "d_adm" in df else None
    od = np.hypot(df.dx.values - df.ox.values, df.dy.values - df.oy.values) / 1000
    return (o.st_km.values <= r_km) & (d.st_km.values <= r_km) & (od >= min_km), o, d, od

if __name__ == "__main__":
    out = {"stations": len(st)}
    t = pd.read_parquet(PROC / "trips.parquet")
    s = t[(t.차량구분 == "특장차") & ~t.reserved & t.o_x.notna() & t.d_x.notna()].copy()
    s = s.rename(columns={"o_x": "ox", "o_y": "oy", "d_x": "dx", "d_y": "dy"})
    el, o, d, od = eligible(s)
    km = s.승차거리.values / 1000
    out["eligible"] = dict(share_calls=float(el.mean()), share_km=float(km[el & s.done.values].sum() / km[s.done.values].sum()),
                           n=int(el.sum()), mean_km=float(km[el & s.done.values].mean()), od_share_5km=float((od >= 5).mean()),
                           both_near=float(((o.st_km.values <= 1) & (d.st_km.values <= 1)).mean()))
    print("연계 가능", out["eligible"], flush=True)
    # 시뮬레이션
    nov = setup("2025-11-01", "2025-11-29"); N0 = np.round(nov["busy"] * (1 + A)).astype(int)
    req = nov["req"].copy()
    # requests_ab에는 목적 행정동이 없어 좌표로 가장 가까운 행정동 중심점을 찾음
    from scipy.spatial import cKDTree
    tree = cKDTree(np.c_[dg.x.values, dg.y.values])
    req["d_adm"] = dg.adm_cd2.values[tree.query(np.c_[req.dx.values, req.dy.values])[1]]
    req["o_adm"] = req.o_adm.astype(str)
    imm = ~req.reserved.values
    elr, o2, d2, od2 = eligible(req)
    elr &= imm
    base = evaluate(nov, N0); res = {"S0 현행": base}
    rng = np.random.default_rng(0)
    kmh = nov["kmh"]
    for u in (0.1, 0.3):
        pick = elr & (rng.random(len(req)) < u)
        # A안: 특장차 수요에서 제외
        rA = evaluate(nov, N0, req=req[~pick].reset_index(drop=True)); rA["moved_per_day"] = float(pick.sum() / len(nov["days"]))
        res[f"LA{int(u * 100)} 라스트마일 {int(u * 100)}% 전환(양끝 민간 택시)"] = rA
        # B안: 특장차가 양끝 구간 운행
        p = req[pick]; o_ = DG.reindex(p.o_adm.values); d_ = DG.reindex(p.d_adm.values)
        def leg(t0, ox, oy, dx, dy, hour, reserved, pat):
            kmv = np.maximum(np.hypot(dx - ox, dy - oy) / 1000 * 1.30, 0.5)
            return pd.DataFrame({"t": t0, "reserved": reserved, "ox": ox, "oy": oy, "dx": dx, "dy": dy,
                                 "ride": np.maximum(kmv / kmh[hour % 24] * 60 * nov["info"]["scale"], 1.0), "obs_wait": np.nan, "obs_appr": np.nan,
                                 "hour": hour, "o_adm": p.o_adm.values, "o_gu": p.o_gu.values, "cancelled": False, "patience": pat})
        l1 = leg(p.t.values, p.ox.values, p.oy.values, o_.st_x.values, o_.st_y.values, p.hour.values, False, p.patience.values)
        metro = od2[pick] / 30 * 60 + 10
        t2 = p.t.values + 20 + l1.ride.values + metro
        l2 = leg(t2, d_.st_x.values, d_.st_y.values, p.dx.values, p.dy.values, ((t2 % 1440) // 60).astype(int), True, np.inf)
        reqB = pd.concat([req[~pick], l1, l2], ignore_index=True).sort_values("t").reset_index(drop=True)
        rB = evaluate(nov, N0, req=reqB)
        res[f"LB{int(u * 100)} 라스트마일 {int(u * 100)}% 전환(양끝 특장차)"] = rB
        print(u, "A", round(rA["mean"], 2), round(rA["ab"], 4), "B", round(rB["mean"], 2), round(rB["ab"], 4), flush=True)
    out["sim"] = {k: {kk: vv for kk, vv in v.items() if kk != "veh_day_km"} for k, v in res.items()}
    # C. 수단별 1건당 CO2
    CB = json.load(open(PROC / "carbon.json"))
    fe = pd.read_csv(next(RAW.glob("15083023_*.csv")), encoding="utf-8-sig")
    city = lambda pat: float(fe[fe.모델명.str.contains(pat, regex=True)].iloc[0]["도심_연비"])
    kgL = CB["kg_per_l"]; grid = 0.4173
    f = dict(van_lpg=CB["kg_km"]["LPG"], van_fleet=CB["fleet_kgkm"], van_ev=CB["kg_km"]["전기"],
             taxi_lpg=kgL["LPG"] / city(r"^쏘나타\(DN8c\) 2\.0 LPI 택시"), taxi_ev=grid / city(r"^니로 EV 17인치"),
             car_gas=kgL["휘발유"] / city(r"^쏘나타\(DN8\) 2\.0CVVL_17인치타이어$"))
    L = float(km[s.done.values].mean()); e = CB["empty_ratio"]; appr = 2.0
    per = {"특장차(현행 차량 구성, 빈 차 포함)": L * (1 + e) * f["van_fleet"], "특장차 전기 승합": L * (1 + e) * f["van_ev"],
           "바우처 일반택시(LPG)": (L + appr) * f["taxi_lpg"], "바우처 일반택시(전기)": (L + appr) * f["taxi_ev"],
           "지하철+양끝 택시(LPG, 각 1㎞)": 2 * (1 + appr) * f["taxi_lpg"], "가족 차량 동행(휘발유, 왕복)": 2 * L * f["car_gas"]}
    out["carbon"] = dict(factors=f, trip_km=L, empty_ratio=e, approach_km=appr, per_trip_kg=per)
    print(json.dumps(out["carbon"], ensure_ascii=False, indent=1))
    json.dump(out, open(PROC / "lastmile.json", "w"), ensure_ascii=False, indent=1, default=float)
