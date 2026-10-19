"""시뮬레이션 입력 만들기: 기간 내 평일 특장차 완료 호출, 관측 근무차량 곡선, 시간대별 속도, 차고지 배정"""
import numpy as np, pandas as pd
from common import *

SLOT = 30
def load(start, end, weekdays_only=True):
    t = pd.read_parquet(PROC / "trips.parquet")
    s = t[(t.차량구분 == "특장차")]
    s = s[(s.예정일시 >= start) & (s.예정일시 < end)]
    if weekdays_only: s = s[s.dow < 5]
    return s

def requests(s):
    """완료 건 중 출발·목적 좌표가 있는 서울 내 운행 → 시뮬레이션 호출표(분 단위, 날짜를 이어 붙임)"""
    d = s[s.done & s.하차일시.notna() & s.o_x.notna() & s.d_x.notna() & s.ride_min.between(1, 300)].copy()
    days = sorted(d.date.unique()); di = {k: i for i, k in enumerate(days)}
    base = d.date.map(di).values * 1440
    d["t"] = base + (d.예정일시 - d.date).dt.total_seconds().values / 60
    out = pd.DataFrame({"t": d.t.values, "reserved": d.reserved.values, "ox": d.o_x.values, "oy": d.o_y.values,
                        "dx": d.d_x.values, "dy": d.d_y.values, "ride": d.ride_min.values,
                        "obs_wait": d.wait.values, "obs_appr": ((d.승차일시 - d.배차일시).dt.total_seconds() / 60).values,
                        "hour": d.hour.values, "o_adm": d.o_adm.values, "o_gu": d.출발구.values})
    return out.sort_values("t").reset_index(drop=True), days, len(s[s.done]), len(d)

def busy_curve(s, days):
    """관측 '운행 중'(배차~하차) 차량 수의 30분 칸별 최댓값 → 근무 차량 수의 하한"""
    d = s[s.done & s.배차일시.notna() & s.하차일시.notna()]
    out = np.zeros((len(days), 1440 // SLOT))
    for i, day in enumerate(days):
        t0 = pd.Timestamp(day)
        a = ((d.배차일시 - t0).dt.total_seconds() // 60).values
        b = ((d.하차일시 - t0).dt.total_seconds() // 60).values
        m = (b > 0) & (a < 1440) & (b > a)
        diff = np.zeros(1442)
        np.add.at(diff, np.clip(a[m], 0, 1440).astype(int), 1)
        np.add.at(diff, np.clip(b[m], 0, 1440).astype(int), -1)
        busy = np.cumsum(diff)[:1440]
        out[i] = busy.reshape(-1, SLOT).max(1)
    return out

def speeds(s):
    v = s[s.done & (s.ride_min > 3) & (s.승차거리 > 500)]
    return (v.승차거리 / 1000 / (v.ride_min / 60)).groupby(v.hour).median().reindex(range(24)).ffill().bfill().values

def depots_for(V, seed=0):
    """차량 순위 → 차고지 좌표: 주차대수 비례로 섞어 배정(근무 차량 수가 적을 때도 고르게 퍼지게)"""
    import geopandas as gpd
    dp = pd.read_csv(PROC / "depots.csv")
    pts = gpd.GeoSeries(gpd.points_from_xy(dp.lon, dp.lat), crs=4326).to_crs(5179)
    dp["x"], dp["y"] = pts.x, pts.y
    w = dp.주차대수.values / dp.주차대수.sum()
    # 비례 라운드로빈: 각 순위마다 '받아야 할 몫 - 받은 몫'이 가장 큰 차고지
    got = np.zeros(len(dp)); xy = np.zeros((V, 2))
    for v in range(V):
        j = int(np.argmax(w * (v + 1) - got)); got[j] += 1; xy[v] = dp.loc[j, ["x", "y"]].values
    return xy, dp

def requests_ab(s, kmh, detour=1.30, seed=0):
    """포기 반영 호출표: 완료 건 + 배차 전에 취소된 즉시 호출(목적지 좌표 있는 건)과 호출별 인내시간(분)
    - 배차 전 취소: 실제 취소까지 걸린 시간 = 인내시간(그보다 빨리 태우면 승차)
    - 완료된 즉시 호출: 관측 대기 w보다 오래 참는다는 조건부 Kaplan–Meier 분포에서 추출(S(t)/S(w))
    - 예약 호출: 포기 없음(∞). 배차 뒤 취소는 대기와 무관한 사유가 섞여 제외(이전과 같음)
    - 취소 건의 승차시간 = 우회계수×직선거리 ÷ 시간대별 속도, 완료 건의 실측/추정 비로 보정"""
    req, days, ndone, nreq = requests(s)
    di = {k: i for i, k in enumerate(days)}
    c = s[s.cancel & ~s.reserved & s.배차일시.isna() & s.o_x.notna() & s.d_x.notna() & s.date.isin(days) & (s.t_cancel > 0)].copy()
    est = lambda d: np.maximum(np.hypot(d.dx - d.ox, d.dy - d.oy) / 1000 * detour, 0.5) / kmh[d.hour.values % 24] * 60
    r_obs = pd.DataFrame({"ox": req.ox, "oy": req.oy, "dx": req.dx, "dy": req.dy, "hour": req.hour})
    scale = float(np.median(req.ride.values / np.maximum(est(r_obs), 1)))
    cc = pd.DataFrame({"t": c.date.map(di).values * 1440 + (c.예정일시 - c.date).dt.total_seconds().values / 60,
                       "reserved": False, "ox": c.o_x.values, "oy": c.o_y.values, "dx": c.d_x.values, "dy": c.d_y.values,
                       "obs_wait": np.nan, "obs_appr": np.nan, "hour": c.hour.values, "o_adm": c.o_adm.values, "o_gu": c.출발구.values})
    cc["ride"] = np.maximum(est(cc) * scale, 1.0)
    cc["patience"] = c.t_cancel.values; cc["cancelled"] = True
    req = req.copy(); req["cancelled"] = False
    km = pd.read_csv(PROC / "km_patience.csv", index_col=0).iloc[:, 0]
    tg, S = km.index.values, km.values
    Sat = lambda w: np.interp(w, tg, S)
    rng = np.random.default_rng(seed)
    w = np.clip(np.nan_to_num(req.obs_wait.values, nan=0.0), 0, None)
    target = rng.random(len(req)) * Sat(w)                  # S(τ) = u·S(w)
    # S는 감소함수: S(τ)=target인 τ를 역보간, 관측 범위 밖(target < S(끝))이면 ∞
    tau = np.interp(-target, -S, tg); tau[target < S[-1]] = np.inf
    req["patience"] = np.where(req.reserved.values, np.inf, np.maximum(tau, w))
    out = pd.concat([req, cc], ignore_index=True).sort_values("t").reset_index(drop=True)
    return out, days, dict(scale=scale, n_done=len(req), n_cancel=len(cc))
