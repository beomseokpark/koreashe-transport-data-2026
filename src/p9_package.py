"""근무시간대 패키지 탐색(시뮬레이터 v2: 포기 반영, p8_sim_ab.py 보정값)
- 1단계(추가 인력 없음): 오후 단시간 조(16~21시) k명을 다른 시간대(14~19 / 14:30~19:30 / 15~20시)로 이동
- 2단계(2026년 증원 25명): 06:30~11:30 / 07~12 / 14~19 / 17~22시 칸에 5명 단위로 배분(56가지) + 1단계 이동 k
- 제약: 07~22시 모든 시간대 평균 대기가 현행보다 1분 넘게 나빠지지 않고, 포기율도 늘지 않을 것(9월로 선택)
- 선택한 안을 11월에 평가(표본 밖). 지역 처방: 오후에만 근무하는 차량(오후 조)을 도심·동남권 차고지에서 출근시키는 안
- 수요 분담: 즉시 호출 일부를 바우처·온디맨드 택시로(무작위 10·20%)"""
import itertools, json, numpy as np, pandas as pd
import simdata as sd
from sim import Sim
from p8_sim_ab import setup
from p7_shift import divert
from common import PROC

CAL = json.load(open(PROC / "sim_ab_calib.json"))["best"]; C, TH, A = CAL["c"], CAL["theta"], CAL["a"]
dep0, dpt = sd.depots_for(698)
sl = lambda h: int(round(h * 2))
LIFE = {"도심권": "종로구 중구 용산구", "동북권": "성동구 광진구 동대문구 중랑구 성북구 강북구 도봉구 노원구", "서북권": "은평구 서대문구 마포구",
        "서남권": "양천구 강서구 구로구 금천구 영등포구 동작구 관악구", "동남권": "서초구 강남구 송파구 강동구"}
G2L = {g: k for k, v in LIFE.items() for g in v.split()}
SLOTS = {"06:30∼11:30": (6.5, 11.5), "07∼12": (7, 12), "14∼19": (14, 19), "17∼22": (17, 22)}

def move(N, k, b=(14, 19), a=(16, 21)):
    M = N.copy(); M[sl(a[0]):sl(a[1])] -= k; M[sl(b[0]):sl(b[1])] += k; return np.maximum(M, 0)

def add(N, k, b):
    M = N.copy(); M[sl(b[0]):sl(b[1])] += k; return M

def central_depots(N):
    """오후(13:30 이후)에만 근무를 시작하는 순위의 차량을 도심·동남권 차고지(주차면 비례)에 배정"""
    dp = dpt.copy(); dp["gu"] = dp.상세주소.str.split().str[0]
    cen = dp[dp.gu.map(G2L).isin(["도심권", "동남권"])].reset_index(drop=True)
    r0, r1 = int(N[sl(13.5)]), int(N[sl(14):sl(19)].max())
    dep = dep0.copy(); w = cen.주차대수.values / cen.주차대수.sum(); got = np.zeros(len(cen))
    for j, r in enumerate(range(r0, min(r1, len(dep)))):
        i = int(np.argmax(w * (j + 1) - got)); got[i] += 1; dep[r] = cen.loc[i, ["x", "y"]].values
    return dep, (r0, r1)

def evaluate(D, N, req=None, dep=None):
    req = D["req"] if req is None else req
    o = Sim(req, np.tile(N, len(D["days"])), dep0 if dep is None else dep, D["kmh"], c=C, theta=TH, patience=req.patience.values).run()
    imm = ~req.reserved.values; w = o["wait"][imm]; hr = req.hour.values[imm]
    g = pd.Series(w).groupby(hr)
    life = pd.Series(req.o_gu.values[imm]).map(G2L)
    return dict(mean=float(np.nanmean(w)), med=float(np.nanmedian(w)), p90=float(np.nanpercentile(w, 90)), over60=float(np.nanmean(w > 60)),
                ab=float(o["aband"][imm].mean()), served=int((~np.isnan(o["wait"])).sum()),
                hour_mean=g.mean().reindex(range(6, 23)).round(1).tolist(),
                hour_ab=pd.Series(o["aband"][imm]).groupby(hr).mean().reindex(range(6, 23)).round(3).tolist(),
                life_mean=pd.Series(w).groupby(life.values).mean().round(1).to_dict(),
                gu_gap=float(pd.Series(w).groupby(req.o_gu.values[imm]).median().pipe(lambda x: x[x.index.map(G2L).notna()]).pipe(lambda x: x.max() - x.min())),
                vh=float(N.sum() / 2), empty=float((o["dead_km"] + o["ret_km"]) / o["pass_km"]), veh_day_km=o["veh_day_km"])

def ok(r, b, tol=1.0):
    return all(x <= y + tol for x, y in zip(r["hour_mean"][1:17], b["hour_mean"][1:17])) and r["ab"] <= b["ab"] + 1e-4

def strip(r): return {k: v for k, v in r.items() if k != "veh_day_km"}

if __name__ == "__main__":
    sep, nov = setup("2025-09-01", "2025-09-30"), setup("2025-11-01", "2025-11-29")
    out = {"calib": CAL}
    for D in (sep, nov): D["N0"] = np.round(D["busy"] * (1 + A)).astype(int)
    b9 = evaluate(sep, sep["N0"]); print("9월 현행", round(b9["mean"], 2), round(b9["ab"], 4), flush=True)
    # 1단계: 이동 대상 시간대·인원
    st1 = []
    for tgt in [(14, 19), (14.5, 19.5), (15, 20)]:
        for k in (10, 15, 20, 25, 30):
            r = evaluate(sep, move(sep["N0"], k, tgt)); st1.append(dict(tgt=tgt, k=k, mean=r["mean"], ab=r["ab"], ok=ok(r, b9), hour=r["hour_mean"]))
            print("1단계", tgt, k, round(r["mean"], 2), round(r["ab"], 4), "OK" if st1[-1]["ok"] else "", flush=True)
    feas1 = [x for x in st1 if x["ok"]]
    best1 = min(feas1, key=lambda x: x["mean"]) if feas1 else None
    # 2단계: 증원 25명 배분 × 1단계 이동
    st2 = []
    for k in (0, 20, 30):
        for comb in itertools.product(range(6), repeat=4):
            if sum(comb) != 5: continue
            N = move(sep["N0"], k) if k else sep["N0"].copy()
            for (nm, sl_), u in zip(SLOTS.items(), comb): N = add(N, 5 * u, sl_)
            r = evaluate(sep, N); st2.append(dict(k=k, comb=dict(zip(SLOTS, [5 * u for u in comb])), mean=r["mean"], ab=r["ab"], ok=ok(r, b9), hour=r["hour_mean"]))
        print("2단계 k", k, "완료", flush=True)
    feas2 = [x for x in st2 if x["ok"]]
    best2 = min(feas2, key=lambda x: x["mean"]) if feas2 else None
    print("BEST1", best1 and {k: v for k, v in best1.items() if k != "hour"}, "\nBEST2", best2 and {k: v for k, v in best2.items() if k != "hour"}, flush=True)
    out["stage1"], out["stage2"] = st1, st2
    out["best1"], out["best2"] = best1, best2
    # 11월 평가
    N0 = nov["N0"]; res = {}
    def put(name, N, **kw):
        r = evaluate(nov, N, **kw); res[name] = r; print("11월", name, round(r["mean"], 2), round(r["over60"], 3), round(r["ab"], 4), flush=True)
    put("S0 현행", N0)
    put("L20 오후 조 20명 14∼19시", move(N0, 20)); put("L30 오후 조 30명 14∼19시", move(N0, 30))
    if best1: put("B1 1단계 선택안", move(N0, best1["k"], best1["tgt"]))
    put("P2 증원 25명 16∼21시", add(N0, 25, (16, 21))); put("P1 증원 25명 07∼12시", add(N0, 25, (7, 12))); put("P3 증원 25명 14∼19시", add(N0, 25, (14, 19)))
    if best2:
        N2 = move(N0, best2["k"]) if best2["k"] else N0.copy()
        for nm, v in best2["comb"].items(): N2 = add(N2, v, SLOTS[nm])
        put("B2 2단계 선택안", N2)
        depc, band = central_depots(N2); out["central_band"] = band
        put("B2R 2단계 + 오후 조 도심·동남권 출근", N2, dep=depc)
    put("S4 균등 증차 10%", np.round(N0 * 1.1).astype(int))
    for sh in (0.10, 0.20):
        rq, nd = divert(nov["req"], share=sh, hours=(0, 24)); put(f"D{int(sh * 100)} 즉시 호출 {int(sh * 100)}% 택시 분담", N0, req=rq); res[f"D{int(sh * 100)} 즉시 호출 {int(sh * 100)}% 택시 분담"]["diverted_per_day"] = nd / len(nov["days"])
    if best2:
        rq, nd = divert(nov["req"], share=0.10, hours=(0, 24)); put("B2D 2단계 + 즉시 호출 10% 분담", N2, req=rq)
    out["nov"] = {k: strip(v) for k, v in res.items()}
    out["ev_day_km"] = {k: dict(p50=float(np.percentile(v["veh_day_km"][v["veh_day_km"] > 0], 50)), p95=float(np.percentile(v["veh_day_km"][v["veh_day_km"] > 0], 95))) for k, v in res.items() if k in ("S0 현행",) or k.startswith("B2")}
    json.dump(out, open(PROC / "package.json", "w"), ensure_ascii=False, indent=1, default=float)
