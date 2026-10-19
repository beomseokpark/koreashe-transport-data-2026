"""시뮬레이터 보정(2025-11 평일)과 표본 밖 검증(2025-09 평일).
보정 대상: 즉시 호출 대기 중앙값·P90, 접근시간(배차→승차) 중앙값, 시간대별 대기 중앙값(07~20시) RMSE
매개변수: c(승하차 준비 등 고정시간, 분), α(근무 차량 = 관측 '운행 중' 하한 × (1+α))"""
import json, numpy as np, pandas as pd, simdata as sd
from sim import Sim
from common import PROC

def setup(a, b):
    s = sd.load(a, b); req, days, ndone, nreq = sd.requests(s)
    return dict(s=s, req=req, days=days, B=sd.busy_curve(s, days), kmh=sd.speeds(s), ndone=ndone, nreq=nreq)

def metrics(req, w, appr):
    imm = ~req.reserved.values; hh = list(range(7, 21))
    sh = pd.Series(w[imm]).groupby(req.hour.values[imm]).median()
    ob = pd.Series(req.obs_wait.values[imm]).groupby(req.hour.values[imm]).median()
    return dict(med=float(np.nanmedian(w[imm])), p90=float(np.nanpercentile(w[imm], 90)), appr=float(np.nanmedian(appr)),
                rmse=float(np.sqrt(((sh[hh] - ob[hh]) ** 2).mean())), obs_med=float(np.nanmedian(req.obs_wait[imm])),
                obs_p90=float(np.nanpercentile(req.obs_wait[imm], 90)), obs_appr=float(np.nanmedian(req.obs_appr)),
                sim_hour=sh.round(2).to_dict(), obs_hour=ob.round(2).to_dict())

def run(D, c, a, dep, **kw):
    N = np.tile(np.round(D["B"].mean(0) * (1 + a)).astype(int), len(D["days"]))
    return Sim(D["req"], N, dep, D["kmh"], c=c, theta=0.3, **kw).run(), N

if __name__ == "__main__":
    dep, _ = sd.depots_for(698)
    cal = setup("2025-11-01", "2025-11-29")
    grid = []
    for c in [8, 10, 12]:
        for a in [-0.05, -0.10, -0.15, -0.20]:
            o, _ = run(cal, c, a, dep); m = metrics(cal["req"], o["wait"], o["appr"])
            # 손실: 시간대 RMSE + 중앙값·P90·접근 오차(분)
            loss = m["rmse"] + abs(m["med"] - m["obs_med"]) + 0.5 * abs(m["p90"] - m["obs_p90"]) + abs(m["appr"] - m["obs_appr"])
            grid.append(dict(c=c, a=a, loss=loss, **{k: v for k, v in m.items() if not k.endswith("hour")}))
            print(grid[-1])
    best = min(grid, key=lambda g: g["loss"]); print("BEST", best)
    val = setup("2025-09-01", "2025-09-30")
    o, _ = run(val, best["c"], best["a"], dep); mv = metrics(val["req"], o["wait"], o["appr"])
    oc, _ = run(cal, best["c"], best["a"], dep); mc = metrics(cal["req"], oc["wait"], oc["appr"])
    print("VALID(9월)", {k: v for k, v in mv.items() if not k.endswith("hour")})
    json.dump(dict(grid=grid, best=best, calib=mc, valid=mv, kmh=list(map(float, cal["kmh"])),
                   n=dict(cal_done=cal["ndone"], cal_sim=cal["nreq"], cal_days=len(cal["days"]),
                          val_done=val["ndone"], val_sim=val["nreq"], val_days=len(val["days"]))),
              open(PROC / "sim_calib.json", "w"), ensure_ascii=False, indent=1)
