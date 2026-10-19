"""시뮬레이터 v2(포기 반영) 보정·검증
- 수요: 완료 호출 + 배차 전 취소된 즉시 호출, 호출별 인내시간(simdata.requests_ab)
- 보정(2025-11 평일): 준비시간 c, 가동률 a, 배차 규칙 θ(0=가까운 호출 우선, 클수록 먼저 온 호출 우선)
  목표: 완료 호출 대기 중앙값·P90, 접근시간, 시간대별 중앙값 RMSE, 배차 전 포기율
- 검증: 2025-09 평일 표본 밖
- 우회계수 1.30은 실측 승차거리/행정동 중심점 직선거리 중앙값(1.302)으로 확인"""
import json, numpy as np, pandas as pd
import simdata as sd
from sim import Sim
from common import PROC

dep, _ = sd.depots_for(698)

def setup(a, b, seed=0):
    s = sd.load(a, b); kmh = sd.speeds(s)
    req, days, info = sd.requests_ab(s, kmh, seed=seed)
    return dict(req=req, days=days, kmh=kmh, busy=sd.busy_curve(s, days).mean(0), info=info)

def run(D, N, c, theta, **kw):
    return Sim(D["req"], np.tile(N, len(D["days"])), dep, D["kmh"], c=c, theta=theta, patience=D["req"].patience.values, **kw).run()

def metrics(D, o):
    r = D["req"]; imm = ~r.reserved.values; done = imm & ~r.cancelled.values
    w = o["wait"]; hh = list(range(7, 21))
    sh = pd.Series(w[imm]).groupby(r.hour.values[imm]).median()
    ob = pd.Series(r.obs_wait.values[done]).groupby(r.hour.values[done]).median()
    return dict(med=float(np.nanmedian(w[imm])), p90=float(np.nanpercentile(w[imm], 90)), appr=float(np.nanmedian(o["appr"])),
                ab=float(o["aband"][imm].mean()), rmse=float(np.sqrt(((sh[hh] - ob[hh]) ** 2).mean())),
                obs_med=float(np.nanmedian(r.obs_wait[done])), obs_p90=float(np.nanpercentile(r.obs_wait[done], 90)),
                obs_appr=float(np.nanmedian(r.obs_appr)), obs_ab=float(r.cancelled[imm].mean()))

def loss(m):
    return m["rmse"] + abs(m["med"] - m["obs_med"]) + 0.5 * abs(m["p90"] - m["obs_p90"]) + abs(m["appr"] - m["obs_appr"]) + 100 * abs(m["ab"] - m["obs_ab"])

if __name__ == "__main__":
    cal = setup("2025-11-01", "2025-11-29")
    grid = []
    for th in (0.0, 0.1, 0.3):
        for c in (8, 10, 12):
            for a in (-0.20, -0.15, -0.10, -0.05, 0.0):
                N = np.round(cal["busy"] * (1 + a)).astype(int)
                m = metrics(cal, run(cal, N, c, th)); m.update(theta=th, c=c, a=a, loss=loss(m)); grid.append(m)
                print({k: round(v, 3) for k, v in m.items()}, flush=True)
    best = min(grid, key=lambda g: g["loss"]); print("BEST", best)
    val = setup("2025-09-01", "2025-09-30")
    mv = metrics(val, run(val, np.round(val["busy"] * (1 + best["a"])).astype(int), best["c"], best["theta"]))
    print("VALID", mv)
    json.dump(dict(best=best, valid=mv, grid=grid, info=dict(nov=cal["info"], sep=val["info"]), detour_check=1.302),
              open(PROC / "sim_ab_calib.json", "w"), ensure_ascii=False, indent=1, default=float)
