"""통합안(C6c) 확정 평가: 지역 처방 추가 효과(도심·동남권 오후 택시 우선 / 오후 조 도심·동남권 출근) + 시뮬레이터 v2 매개변수 민감도(8조건)"""
import json, numpy as np, pandas as pd
from sim import Sim
from p8_sim_ab import setup
from p9_package import evaluate, central_depots, A, C, TH, dep0
from p11_candidates import build, judge
from common import PROC

PKG = dict(k=15, add={(14, 19): 15, (17, 22): 10}, am_div=0.15)
out = {}
for tag, r_ in {"sep": ("2025-09-01", "2025-09-30"), "nov": ("2025-11-01", "2025-11-29")}.items():
    D = setup(*r_); D["N0"] = np.round(D["busy"] * (1 + A)).astype(int); b = evaluate(D, D["N0"])
    res = {"S0 현행": b}
    for name, spec, dep in [("PKG 통합안", PKG, False), ("PKG+R1 도심·동남권 오후 택시 우선 20%", dict(PKG, reg_div=0.20), False),
                            ("PKG+R2 오후 조 도심·동남권 출근", PKG, True)]:
        N, req, nd = build(D, spec)
        r = evaluate(D, N, req=req, dep=central_depots(N)[0] if dep else None)
        r.update(judge=judge(r, b), diverted=nd / len(D["days"])); res[name] = r
        print(tag, name, f"{r['mean']:.2f} ({r['mean']/b['mean']-1:+.1%}) over60 {r['over60']:.3f} ab {r['ab']:.4f} worst {r['judge']['max_worse']:+.1f} life {r['life_mean']} gap {r['gu_gap']:.1f}", flush=True)
    out[tag] = {k: {kk: vv for kk, vv in v.items() if kk != "veh_day_km"} for k, v in res.items()}
    if tag == "nov":
        out["ev_day_km"] = {k: dict(p50=float(np.percentile(v["veh_day_km"][v["veh_day_km"] > 0], 50)), p95=float(np.percentile(v["veh_day_km"][v["veh_day_km"] > 0], 95)),
                                    over371=float((v["veh_day_km"][v["veh_day_km"] > 0] > 371).mean())) for k, v in res.items() if k in ("S0 현행", "PKG 통합안")}
# 민감도(11월): 준비시간·우회계수·배차 규칙·가동률
D = setup("2025-11-01", "2025-11-29")
sens = {}
import p9_package as P9
for label, kw in [("기준", {}), ("준비시간 8분", dict(c=8)), ("준비시간 12분", dict(c=12)), ("우회계수 1.2", dict(detour=1.2)), ("우회계수 1.4", dict(detour=1.4)),
                  ("배차 θ 0.1", dict(theta=0.1)), ("배차 θ 0.5", dict(theta=0.5)), ("가동률 0.80", dict(a=-0.20)), ("가동률 0.90", dict(a=-0.10))]:
    a = kw.pop("a", A); D["N0"] = np.round(D["busy"] * (1 + a)).astype(int)
    def ev(N, req):
        o = Sim(req, np.tile(N, len(D["days"])), dep0, D["kmh"], c=kw.get("c", C), theta=kw.get("theta", TH), detour=kw.get("detour", 1.30), patience=req.patience.values).run()
        imm = ~req.reserved.values; return float(np.nanmean(o["wait"][imm])), float(o["aband"][imm].mean())
    m0, a0 = ev(D["N0"], D["req"]); N, req, nd = build(D, PKG); m1, a1 = ev(N, req)
    sens[label] = dict(base=m0, pkg=m1, chg=m1 / m0 - 1, ab0=a0, ab1=a1)
    print("민감도", label, round(m0, 1), round(m1, 1), f"{m1/m0-1:+.1%}", flush=True)
out["sensitivity"] = sens
json.dump(out, open(PROC / "final.json", "w"), ensure_ascii=False, indent=1, default=float)
