"""이동지원 격차 실증 분석 (2025년 서울 장애인콜택시 특장차, 즉시 호출 중심)
1) 시간대 곡선  2) 자치구·행정동 격차, 로렌츠·지니(Delbosc·Currie 2011), 60분 초과 비율(충분성 기준, Lucas 외 2016)
3) Getis-Ord Gi* 핫스팟(Akcicek 외 2024의 핫스팟 분석 방식)  4) 대기 요인 OLS(HC1)
5) 생활권별 오후 승차(차가 필요)·하차(차가 생김) 수지 = 빈 차 쏠림
6) 인내시간 Kaplan–Meier(Brown 외 2005: 취소=포기, 승차=중도절단)"""
import json, numpy as np, pandas as pd, geopandas as gpd
import statsmodels.formula.api as smf
from lifelines import KaplanMeierFitter
from libpysal.weights import Queen
from esda.getisord import G_Local
from common import *

LIFE = {"도심권": "종로구 중구 용산구", "동북권": "성동구 광진구 동대문구 중랑구 성북구 강북구 도봉구 노원구",
        "서북권": "은평구 서대문구 마포구", "서남권": "양천구 강서구 구로구 금천구 영등포구 동작구 관악구",
        "동남권": "서초구 강남구 송파구 강동구"}
GU2L = {g: k for k, v in LIFE.items() for g in v.split()}
OUT_J = {}

t = pd.read_parquet(PROC / "trips.parquet")
s = t[t.차량구분 == "특장차"].copy()
s["life"] = s.출발구.map(GU2L)
imm = s[~s.reserved & s.life.notna()].copy()
done = imm[imm.done & imm.wait.notna()]
OUT_J["counts"] = dict(all=len(t), sp=len(s), sp_done=int(s.done.sum()), sp_cancel=int(s.cancel.sum()),
                       taxi=int((t.차량구분 == "임차택시").sum()), imm_share=float(1 - s.reserved.mean()),
                       imm_n=len(imm), imm_done=len(done))
OUT_J["overall"] = dict(med=float(done.wait.median()), mean=float(done.wait.mean()), p90=float(done.wait.quantile(.9)),
                        over60=float((done.wait > 60).mean()), cancel=float(imm.cancel.mean()),
                        reserved_med=float(s[s.reserved & s.done].wait.median()),
                        taxi_med=float(t[(t.차량구분 == "임차택시") & ~t.reserved & t.done].wait.median()))

# 0) 대기 정의 검증: 공단 공식 '시간대별 대기시간평균'(탑승 완료 기준)과 날짜·시간대별 평균 비교
off = pd.read_csv(next(RAW.glob("15147613_*.csv")), encoding="utf-8-sig"); off["hour"] = off.시간대.str[:2].astype(int)
off["date"] = pd.to_datetime(off.일자)
mine = s[s.done].groupby(["date", "hour"]).wait.mean().rename("mine").reset_index()
mm = off.merge(mine, on=["date", "hour"])
OUT_J["official_check"] = dict(n=len(mm), corr=float(np.corrcoef(mm.대기시간평균, mm.mine)[0, 1]),
                               diff_med=float((mm.mine - mm.대기시간평균).median()))

# 1) 시간대 (평일)
wk = imm[imm.dow < 5]; wd = wk[wk.done & wk.wait.notna()]
ndays = wk.date.nunique()
hour = pd.DataFrame({"calls_per_day": wk.groupby("hour").size() / ndays, "wait_med": wd.groupby("hour").wait.median(),
                     "wait_p90": wd.groupby("hour").wait.quantile(.9), "cancel": wk.groupby("hour").cancel.mean(),
                     "disp_med": wd.groupby("hour").wait_disp.median()})
# 운행 중 차량(배차~하차) 평일 시간대 평균: 분 단위 누적
d = s[s.done & s.배차일시.notna() & s.하차일시.notna()]
t0 = pd.Timestamp("2025-01-01"); NM = 365 * 1440
a = ((d.배차일시 - t0).dt.total_seconds() // 60).astype(int).values; b = ((d.하차일시 - t0).dt.total_seconds() // 60).astype(int).values
ok = (b > a) & (b - a < 600) & (a >= 0) & (b < NM)
df_ = np.zeros(NM + 1); np.add.at(df_, a[ok], 1); np.add.at(df_, b[ok], -1)
busy = pd.Series(np.cumsum(df_)[:NM], pd.date_range(t0, periods=NM, freq="min"))
bw = busy[busy.index.dayofweek < 5]
hour["busy_mean"] = bw.groupby(bw.index.hour).mean()
hour["busy_p95"] = bw.groupby(bw.index.hour).quantile(.95)
hour.to_csv(PROC / "hour_profile.csv")
OUT_J["busy_max"] = dict(v=int(busy.max()), at=str(busy.idxmax())); OUT_J["fleet"] = 698
OUT_J["hour"] = {k: hour[k].round(2).to_dict() for k in hour}

# 2) 자치구 / 행정동
dis = pd.read_csv(RAW / "seoul_disabled_by_gu_2025.csv", encoding="utf-8-sig", header=None, skiprows=4)
dis = dis[[1, 2]].rename(columns={1: "gu", 2: "disabled"}); dis = dis[dis.gu != "소계"]
dis["disabled"] = pd.to_numeric(dis.disabled, errors="coerce")
gu = imm.groupby("출발구").agg(calls=("done", "size"), cancel=("cancel", "mean"))
gu = gu.join(done.groupby("출발구").agg(wait_med=("wait", "median"), over60=("wait", lambda x: (x > 60).mean())))
gu = gu.join(done[done.hour.between(14, 17)].groupby("출발구").wait.median().rename("pm_med"))
gu = gu.join(imm.groupby("출발구").승차거리.median().div(1000).rename("km_med"))
gu = gu.join(dis.set_index("gu").disabled); gu["calls_per_1k"] = gu.calls / gu.disabled * 1000
gu["life"] = gu.index.map(GU2L); gu.to_csv(PROC / "gu.csv")
OUT_J["gu"] = gu.round(4).reset_index().to_dict("records")

dg = gpd.read_parquet(PROC / "dongs.parquet")
# 7) 차고지 접근성: 행정동 중심 → 가장 가까운 차고지 직선거리, 생활권별 주차면 vs 호출 몫
dp = pd.read_csv(PROC / "depots.csv")
dpp = gpd.GeoSeries(gpd.points_from_xy(dp.lon, dp.lat), crs=4326).to_crs(5179)
dp["x"], dp["y"] = dpp.x.values, dpp.y.values
dg["depot_km"] = np.hypot(dg.x.values[:, None] - dp.x.values[None, :], dg.y.values[:, None] - dp.y.values[None, :]).min(1) / 1000
dp["life"] = dp.상세주소.str.split().str[0].map(GU2L)
park = dp.groupby("life").주차대수.sum()
share = pd.DataFrame({"park_share": park / park.sum(), "call_share": imm.groupby("life").size() / len(imm),
                      "depots": dp.groupby("life").size()})
OUT_J["depot_life"] = share.round(3).reset_index().rename(columns={"index": "life"}).to_dict("records")
dn = imm.groupby("o_adm").agg(calls=("done", "size"), cancel=("cancel", "mean"))
dn = dn.join(done.groupby("o_adm").agg(wait_mean=("wait", "mean"), wait_med=("wait", "median"), over60=("wait", lambda x: (x > 60).mean()), nd=("wait", "size")))
dn = dn.join(done[done.hour.between(14, 17)].groupby("o_adm").wait.median().rename("pm_med"))
g = dg.merge(dn, left_on="adm_cd2", right_index=True, how="left")
g["long_n"] = g.over60 * g.nd

def lorenz(x, w):
    """x: 지역별 '긴 대기' 비율, w: 지역별 호출 수 → 호출 누적비 vs 긴 대기 누적비, 지니"""
    o = np.argsort(x); x, w = np.asarray(x)[o], np.asarray(w)[o]
    cw = np.r_[0, np.cumsum(w)] / w.sum(); cl = np.r_[0, np.cumsum(x * w)] / (x * w).sum()
    gini = 1 - np.sum((cw[1:] - cw[:-1]) * (cl[1:] + cl[:-1]))
    return cw, cl, gini
v = g[g.nd >= 200]
cw, cl, gini = lorenz(v.over60.values, v.nd.values)
OUT_J["lorenz"] = dict(gini=float(gini), n_dong=len(v), x=cw.tolist(), y=cl.tolist())
# 하위 20% 동이 차지하는 긴 대기 몫 / 상위 20%
top = 1 - np.interp(0.8, cw, cl); bot = np.interp(0.2, cw, cl)
OUT_J["lorenz"].update(top20=float(top), bottom20=float(bot))
vp = g[g.pm_med.notna() & (g.nd >= 200)]
OUT_J["dong"] = dict(n=len(v), over60_q=v.over60.quantile([.1, .5, .9]).round(3).to_dict(),
                     over25pct=int((v.over60 > .25).sum()), worst=v.sort_values("over60", ascending=False)[["sggnm", "dong", "over60", "wait_med", "nd"]].head(10).round(3).to_dict("records"),
                     best=v.sort_values("over60")[["sggnm", "dong", "over60", "wait_med", "nd"]].head(5).round(3).to_dict("records"))

# 3) Gi* 핫스팟 (행정동 평균 대기, 200건 이상)
gg = g[g.nd >= 200].reset_index(drop=True)
W = Queen.from_dataframe(gg, use_index=False, silence_warnings=True); W.transform = "r"
G = G_Local(gg.wait_mean.values, W, star=True, permutations=999, seed=1)
gg["gi_z"] = G.Zs; gg["gi_p"] = G.p_sim
gg["hot"] = np.where((gg.gi_p < .05) & (gg.gi_z > 0), "hot", np.where((gg.gi_p < .05) & (gg.gi_z < 0), "cold", "ns"))
OUT_J["hotspot_depot_km"] = dict(hot=float(gg[gg.hot == "hot"].depot_km.mean()), cold=float(gg[gg.hot == "cold"].depot_km.mean()),
                                 corr_wait=float(np.corrcoef(gg.depot_km, gg.wait_mean)[0, 1]))
gg[["adm_cd2", "sggnm", "dong", "calls", "depot_km", "wait_mean", "wait_med", "over60", "cancel", "pm_med", "gi_z", "gi_p", "hot", "geometry"]].to_parquet(PROC / "dong_gap.parquet")
OUT_J["hotspot"] = dict(hot=int((gg.hot == "hot").sum()), cold=int((gg.hot == "cold").sum()),
                        hot_gu=gg[gg.hot == "hot"].sggnm.value_counts().head(8).to_dict(),
                        cold_gu=gg[gg.hot == "cold"].sggnm.value_counts().head(8).to_dict(),
                        hot_wait=float(gg[gg.hot == "hot"].wait_mean.mean()), cold_wait=float(gg[gg.hot == "cold"].wait_mean.mean()))

# 4) 대기 요인 OLS (즉시·완료, 서울 출발)
r = done[done.d_x.notna()].copy()
r["band"] = pd.cut(r.hour, [0, 7, 10, 14, 18, 24], right=False, labels=["0-7시", "7-10시", "10-14시", "14-18시", "18-24시"]).astype(str)
r["weekend"] = (r.dow >= 5).astype(int); r["km"] = (r.승차거리 / 1000).clip(0, 60)
r["same_gu"] = (r.출발구 == r.목적구).astype(int)
r["purpose"] = np.where(r.이용목적.str.contains("치료|재활"), "치료·재활", np.where(r.이용목적 == "귀가", "귀가", "기타"))
r["dtype"] = np.where(r.장애유형.isin(["뇌병", "지체"]), "뇌병변·지체", np.where(r.장애유형.isin(["자폐", "지적"]), "발달", "기타"))
r["month"] = r.예정일시.dt.month.astype(str)
r["depot_km"] = r.o_adm.map(dg.set_index("adm_cd2").depot_km)
mdl = smf.ols("wait ~ C(band, Treatment('10-14시')) + weekend + km + same_gu + C(purpose, Treatment('기타')) + C(dtype, Treatment('뇌병변·지체')) + depot_km + C(life, Treatment('동북권')) + C(month)",
              data=r).fit(cov_type="HC1")
coef = pd.DataFrame({"b": mdl.params, "lo": mdl.conf_int()[0], "hi": mdl.conf_int()[1], "p": mdl.pvalues})
coef = coef[~coef.index.str.contains("month")]
coef.to_csv(PROC / "ols_coef.csv")
OUT_J["ols"] = dict(n=int(mdl.nobs), r2=float(mdl.rsquared), coef=coef.round(3).reset_index().to_dict("records"))

# 5) 생활권 빈 차 쏠림: 평일 14~18시 승차(차가 필요) vs 하차(차가 생김)
pm = s[(s.dow < 5) & s.done & s.hour.between(14, 17)]
need = pm.groupby(pm.출발구.map(GU2L)).size(); supply = pm.groupby(pm.목적구.map(GU2L)).size()
nd_ = s[s.dow < 5].date.nunique()
bal = pd.DataFrame({"pickup": need, "dropoff": supply}).fillna(0) / nd_
bal["net"] = bal.dropoff - bal.pickup
bal.to_csv(PROC / "life_balance_pm.csv")
OUT_J["balance_pm"] = dict(table=bal.round(1).reset_index().rename(columns={"index": "life"}).to_dict("records"))

# 6) 인내시간 KM (즉시 호출: 취소=사건, 승차=중도절단)
k = imm[(imm.cancel & imm.t_cancel.between(0, 300)) | (imm.done & imm.wait.between(0, 300))].copy()
k["dur"] = np.where(k.cancel, k.t_cancel, k.wait); k["ev"] = k.cancel.astype(int)
km = KaplanMeierFitter().fit(k.dur, k.ev)
sf = km.survival_function_.iloc[:, 0]
S = lambda w: float(np.interp(w, sf.index.values, sf.values))
OUT_J["patience"] = dict(n=len(k), events=int(k.ev.sum()), S30=S(30), S60=S(60), S90=S(90), S120=S(120),
                         median=float(km.median_survival_time_), grid=list(range(0, 181, 5)),
                         S=[S(w) for w in range(0, 181, 5)])
# 사건 중 배차 전 취소 비율(=차가 정해지기도 전에 포기)
c = imm[imm.cancel]; OUT_J["patience"]["cancel_before_dispatch"] = float(c.배차일시.isna().mean())
OUT_J["patience"]["cancel_t_med"] = float(c.t_cancel.median())
sf.to_csv(PROC / "km_patience.csv")

# 전국 맥락: 특별교통수단 법정대수 대비 운행대수(2024)
nat = pd.read_csv(next(RAW.glob("15066774_*.csv")), encoding="cp949")
nat["ratio"] = nat.운행대수 / nat.법정기준대수; nat["per_vehicle"] = nat.장애인수 / nat.운행대수
OUT_J["national"] = nat.round(3).to_dict("records")
json.dump(OUT_J, open(PROC / "gap.json", "w"), ensure_ascii=False, indent=1, default=float)
print(json.dumps({k: OUT_J[k] for k in ["counts", "overall", "busy_max", "hotspot", "balance_pm"]}, ensure_ascii=False, indent=1, default=float))
print("lorenz", OUT_J["lorenz"]["gini"], OUT_J["lorenz"]["top20"], OUT_J["lorenz"]["bottom20"]); print("dong", OUT_J["dong"]["over60_q"], OUT_J["dong"]["over25pct"])
print(coef.round(2).to_string()); print("patience", {k: v for k, v in OUT_J["patience"].items() if k not in ("grid", "S")})
