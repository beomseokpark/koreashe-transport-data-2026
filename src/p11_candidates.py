"""통합 패키지 후보 비교(시뮬레이터 v2) — 오전 정점·저녁 악화·지역 격차를 함께 고려
후보: 오후 조 이동 k명 + 증원 인원 배분(07~12·14~19·17~22시) + 아침(07~09시) 즉시 호출의 택시 분담 + 예약 선배차
지역 처방: 도심·동남권 오후(14~18시) 출발 즉시 호출의 택시 우선 배정, 오후 조 도심·동남권 출근
판정(9월·11월 각각): 07~22시 모든 시간대 평균 대기가 현행보다 1분 넘게 나빠지지 않을 것, 오전(07~09시) −10% 이상"""
import json, numpy as np, pandas as pd
from sim import Sim
from p8_sim_ab import setup
from p9_package import evaluate, move, add, central_depots, G2L, C, TH, A, dep0
from common import PROC

def divert_sel(req, mask, share, seed=1):
    rng = np.random.default_rng(seed)
    drop = mask & (rng.random(len(req)) < share)
    return req[~drop].reset_index(drop=True), int(drop.sum())

CANDS = {
    "C1 이동20+증원25(오후15·저녁10)": dict(k=20, add={(14, 19): 15, (17, 22): 10}),
    "C2 C1+오전 증원20(총45)": dict(k=20, add={(14, 19): 15, (17, 22): 10, (7, 12): 20}),
    "C3 이동30+증원35(저녁15·오전20)": dict(k=30, add={(17, 22): 15, (7, 12): 20}),
    "C4 이동30+증원25(저녁10·오전15)": dict(k=30, add={(17, 22): 10, (7, 12): 15}),
    "C5 이동20+증원25(저녁10·오전15)": dict(k=20, add={(17, 22): 10, (7, 12): 15}),
    "C6 C1+아침 택시 분담15%": dict(k=20, add={(14, 19): 15, (17, 22): 10}, am_div=0.15),
    "C7 C4+아침 택시 분담10%": dict(k=30, add={(17, 22): 10, (7, 12): 15}, am_div=0.10),
    "C8 이동30+증원25(저녁15·오전10)": dict(k=30, add={(17, 22): 15, (7, 12): 10}),
    "C9 C8+아침 택시 분담10%": dict(k=30, add={(17, 22): 15, (7, 12): 10}, am_div=0.10),
}

def build(D, spec):
    N = move(D["N0"], spec["k"]) if spec.get("k") else D["N0"].copy()
    for slot, v in spec.get("add", {}).items(): N = add(N, v, slot)
    req = D["req"]; nd = 0
    if spec.get("am_div"):
        imm = ~req.reserved.values
        req, nd = divert_sel(req, imm & (req.hour.values >= 7) & (req.hour.values < 9), spec["am_div"])
    if spec.get("reg_div"):
        imm = ~req.reserved.values; life = pd.Series(req.o_gu.values).map(G2L).values
        m = imm & (req.hour.values >= 14) & (req.hour.values < 18) & np.isin(life, ["도심권", "동남권"])
        req, nd2 = divert_sel(req, m, spec["reg_div"], seed=2); nd += nd2
    return N, req, nd

def judge(r, b):
    worse = max(x - y for x, y in zip(r["hour_mean"][1:17], b["hour_mean"][1:17]))
    am = np.mean(r["hour_mean"][1:4]) / np.mean(b["hour_mean"][1:4]) - 1
    pm = np.mean(r["hour_mean"][8:12]) / np.mean(b["hour_mean"][8:12]) - 1
    ev = np.mean(r["hour_mean"][14:16]) - np.mean(b["hour_mean"][14:16])
    return dict(max_worse=float(worse), am=float(am), pm=float(pm), ev_diff=float(ev), all_ok=bool(worse <= 1.0), am_ok=bool(am <= -0.10))

if __name__ == "__main__":
    out = {}
    for tag, rng_ in {"sep": ("2025-09-01", "2025-09-30"), "nov": ("2025-11-01", "2025-11-29")}.items():
        D = setup(*rng_); D["N0"] = np.round(D["busy"] * (1 + A)).astype(int)
        b = evaluate(D, D["N0"]); res = {"S0 현행": dict(b, judge=judge(b, b), added=0, diverted=0)}
        specs = dict(CANDS)
        specs["R1 지역: 도심·동남권 오후 호출 20% 택시 우선"] = dict(k=0, add={}, reg_div=0.20)
        specs["R2 지역: C1+오후 조 도심·동남권 출근"] = dict(k=20, add={(14, 19): 15, (17, 22): 10}, depots=True)
        for name, spec in specs.items():
            N, req, nd = build(D, spec)
            dep = central_depots(N)[0] if spec.get("depots") else None
            r = evaluate(D, N, req=req, dep=dep)
            r.update(judge=judge(r, b), added=int(sum(spec.get("add", {}).values())), diverted=nd / len(D["days"]))
            res[name] = r
            j = r["judge"]
            print(tag, f"{name:34s} mean {r['mean']:.2f} ({r['mean'] / b['mean'] - 1:+.1%}) AM {j['am']:+.1%} PM {j['pm']:+.1%} EVΔ {j['ev_diff']:+.1f} worst {j['max_worse']:+.1f} "
                  f"{'ALL' if j['all_ok'] else ''} {'AM' if j['am_ok'] else ''} life {r['life_mean']}", flush=True)
        # 예약 선배차(아침 정시성): 예약 호출을 예정 35분 전부터 배차
        o = Sim(D["req"], np.tile(D["N0"], len(D["days"])), dep0, D["kmh"], c=C, theta=TH, patience=D["req"].patience.values, res_lead=35).run()
        rv = D["req"].reserved.values; w = o["wait"]
        h = D["req"].hour.values
        o0 = Sim(D["req"], np.tile(D["N0"], len(D["days"])), dep0, D["kmh"], c=C, theta=TH, patience=D["req"].patience.values).run()
        def late(oo, sel): return float(np.nanmean(oo["wait"][sel] > 30))
        am_res = rv & (h >= 6) & (h < 9)
        res["RL 예약 선배차 35분"] = dict(res_late30_am=late(o, am_res), res_late30_am_base=late(o0, am_res),
                                         imm_mean=float(np.nanmean(w[~rv])), imm_mean_base=float(np.nanmean(o0["wait"][~rv])))
        print(tag, "예약 선배차", res["RL 예약 선배차 35분"], flush=True)
        out[tag] = {k: {kk: vv for kk, vv in v.items() if kk != "veh_day_km"} for k, v in res.items()}
    json.dump(out, open(PROC / "candidates.json", "w"), ensure_ascii=False, indent=1, default=float)
