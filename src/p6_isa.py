"""시간 안정(time-stable) 근무 곡선: 무한서버 제공부하 방식(Jennings et al. 1996; Feldman et al. 2008이 ISA와 일치함을 보임) + 전기차 주행거리 점검
- 원 ISA(Feldman et al. 2008): 칸별 '시스템 안 호출 수' L(t) 분포로 s(t) = min{s: P(L(t) ≥ s) ≤ α}를 반복 갱신.
  그러나 이 시뮬레이터에는 포기가 없어(완료 호출만 재배차) 과부하 시간대에 대기열이 줄지 않고, 반복할수록 평균 대기가 38.7→49분으로 발산(isa() 기록).
- 그래서 차량을 넉넉히(698대 전부) 둔 '무한서버' 시뮬레이션에서 칸별 동시 사용 차량 수 L∞(t)의 분포를 얻고,
  모든 칸에 같은 분위수 q를 적용한 s(t) = ⌈Q_q(L∞(t))⌉를 쓴다(같은 q = 시간대별 부족 확률이 같음).
- 총 근무 차량·시간을 예산 B(현행 또는 +10%)로 고정: Σ s(t) = B가 되는 q를 이분법으로 찾음
- 결과: 같은 예산이면 낮 정점은 크게 좋아지나 18시 이후 차량이 너무 줄어 저녁 대기가 무너짐(호출이 드문 시간대의 '공간 커버' 필요를 무한서버 근사가 과소평가)
  → 혼합안: 낮(05~18시) 근무량만 시간안정 곡선으로 재배분하고 18시 이후는 현행 유지
- 학습 2025-09 평일 → 평가 2025-11 평일(곡선 모양만 옮기고 11월 예산에 맞춰 비례 조정), 근무조(4~10시간)로 근사한 실행판도 평가
- 전기차: 차량별·날짜별 주행거리(빈 차 포함) 분포를 스타리아 EV 11인 1회 충전 주행거리(한국에너지공단 표시연비)와 비교"""
import json, numpy as np, pandas as pd
import simdata as sd
from sim import Sim
from p4_policies import fit_shifts, cover, W0, W1, C, A, summarize
from common import PROC, RAW

SL = sd.SLOT; NS = 1440 // SL; WIN = slice(W0, W1); EV0 = 36   # 18:00
dep, _ = sd.depots_for(698)

def setup(a, b):
    s = sd.load(a, b); req, days, *_ = sd.requests(s)
    Nb = np.round(sd.busy_curve(s, days).mean(0) * (1 + A)).astype(int)
    return req, days, sd.speeds(s), Nb

def run(req, days, kmh, N, **kw):
    return Sim(req, np.tile(N, len(days)), dep, kmh, c=C, theta=0.3, sample_min=5, **kw).run()

def per_slot_L(o):
    a = np.array(o["samples"]); slot = ((a[:, 0] % 1440) // SL).astype(int)
    return [a[slot == k, 1] + a[slot == k, 2] for k in range(NS)]

def quant_curve(Ls, B, a=W0, b=W1):
    """칸 a~b 안 Σ ceil(q-분위수) = B 가 되는 공통 분위수 q (이분법)"""
    lo, hi = 0.0, 1.0
    f = lambda q: np.array([np.ceil(np.quantile(Ls[k], q)) if len(Ls[k]) else 0 for k in range(a, b)])
    for _ in range(40):
        mid = (lo + hi) / 2
        if f(mid).sum() > B: hi = mid
        else: lo = mid
    return f(lo).astype(int), lo

def isa(req, days, kmh, Nb, B, iters=8):
    s = Nb.copy(); hist = []
    for it in range(iters):
        o = run(req, days, kmh, s); Ls = per_slot_L(o)
        new, q = quant_curve(Ls, B)
        cand = s.copy(); cand[WIN] = np.round(0.5 * s[WIN] + 0.5 * new).astype(int)   # 진동 방지(반씩 갱신)
        imm = ~req.reserved.values
        hist.append(dict(it=it, mean=float(np.nanmean(o["wait"][imm])), q=float(q), change=int(np.abs(cand - s)[WIN].sum())))
        print("  ISA", hist[-1], flush=True)
        s = cand
    o = run(req, days, kmh, s); hist.append(dict(it=iters, mean=float(np.nanmean(o["wait"][~req.reserved.values])), q=None, change=0))
    return s, hist

def to_month(s_tr, Nb_tr, Nb_ev, B_ev):
    """학습월 곡선 모양을 평가월 예산 B_ev에 맞춰 비례 조정(창 밖은 평가월 현행)"""
    N = Nb_ev.copy(); shape = s_tr[WIN] / s_tr[WIN].sum()
    v = np.floor(shape * B_ev).astype(int); v[np.argsort(-(shape * B_ev - v))[:B_ev - v.sum()]] += 1
    N[WIN] = v; return N

def fit_exact(N, lens):
    """목표 곡선 N(05~24시)을 근무조(시작×길이 lens, 30분 칸)로 근사: Σ|cov−N| 최소, 총 근무량 = 목표와 같게(Dantzig 1954식 근무표 정수계획)"""
    import pulp
    TPL = [(k, L) for L in lens for k in range(W0, W1 - L + 1)]
    pr = pulp.LpProblem("fit", pulp.LpMinimize); x = [pulp.LpVariable(f"x{i}", 0, None, cat="Integer") for i in range(len(TPL))]
    e = {t: pulp.LpVariable(f"e{t}", 0) for t in range(W0, W1)}
    pr += pulp.lpSum(e.values())
    for t in range(W0, W1):
        cov = pulp.lpSum(x[i] for i, (k, L) in enumerate(TPL) if k <= t < k + L)
        pr += cov - int(N[t]) <= e[t]; pr += int(N[t]) - cov <= e[t]
    pr += pulp.lpSum(x[i] * L for i, (k, L) in enumerate(TPL)) == int(N[W0:W1].sum())
    pr.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=120))
    M = np.array(N).copy(); M[W0:W1] = 0; heads = 0; byL = {}
    for (k, L), v in zip(TPL, x):
        n = int(round(v.value())); M[k:k + L] += n; heads += n; byL[L / 2] = byL.get(L / 2, 0) + n
    return M, dict(heads=heads, by_hours=byL, err=float(np.abs(M - N)[W0:W1].mean()))

FULL = [8, 12, 16, 18, 20]; PART = [4, 6] + FULL       # 4~10시간 / 2·3시간 시간제 포함

def hour_stability(req, w):
    """시간대(07~20시)별 60분 초과 비율의 표준편차: 작을수록 시간대 간 서비스가 고름"""
    imm = ~req.reserved.values
    g = pd.Series(w[imm] > 60).groupby(req.hour.values[imm]).mean().reindex(range(7, 21))
    return float(g.std()), g.round(3).to_dict()

if __name__ == "__main__":
    rq9, d9, k9, Nb9 = setup("2025-09-01", "2025-09-30")
    rq11, d11, k11, Nb11 = setup("2025-11-01", "2025-11-29")
    out = dict(train={}, eval={})
    B9 = {"same": int(Nb9[WIN].sum()), "plus10": int(np.round(Nb9 * 1.1).astype(int)[WIN].sum())}
    B11 = {"same": int(Nb11[WIN].sum()), "plus10": int(np.round(Nb11 * 1.1).astype(int)[WIN].sum())}
    curves = {}
    full = Nb9.copy(); full[WIN] = 698
    Linf = per_slot_L(run(rq9, d9, k9, full))           # 무한서버(차량 넉넉) 동시 사용 차량 분포
    for key in ["same", "plus10"]:
        cur, q = quant_curve(Linf, B9[key]); s9 = Nb9.copy(); s9[WIN] = cur
        imm = ~rq9.reserved.values
        f9 = float(np.nanmean(run(rq9, d9, k9, s9)["wait"][imm])); f9b = float(np.nanmean(run(rq9, d9, k9, Nb9 if key == "same" else np.round(Nb9 * 1.1).astype(int))["wait"][imm]))
        out["train"][key] = dict(q=float(q), curve=s9.tolist(), train_mean=f9, train_base=f9b,
                                 Linf_mean=[float(np.mean(Linf[k])) if len(Linf[k]) else 0 for k in range(NS)])
        print("== 예산", key, B9[key], "q", round(q, 3), "9월 평균대기", round(f9b, 2), "→", round(f9, 2), flush=True)
        curves[key] = to_month(s9, Nb9, Nb11, B11[key])
        # 혼합안: 낮(05~18시)만 시간안정 곡선으로 재배분, 18시 이후는 각 예산의 현행 모양 유지
        base9 = Nb9 if key == "same" else np.round(Nb9 * 1.1).astype(int)
        base11 = Nb11 if key == "same" else np.round(Nb11 * 1.1).astype(int)
        cur, qd = quant_curve(Linf, int(base9[W0:EV0].sum()), W0, EV0); h9 = base9.copy(); h9[W0:EV0] = cur
        fh = float(np.nanmean(run(rq9, d9, k9, h9)["wait"][imm]))
        h11 = base11.copy(); day = int(base11[W0:EV0].sum()); shp = h9[W0:EV0] / h9[W0:EV0].sum()
        v = np.floor(shp * day).astype(int); v[np.argsort(-(shp * day - v))[:day - v.sum()]] += 1; h11[W0:EV0] = v
        out["train"][key].update(hybrid_q=float(qd), hybrid_train_mean=fh, hybrid_curve=h9.tolist())
        print("   혼합안 9월 평균대기", round(fh, 2), flush=True)
        curves["h_" + key] = h11
    sc = {"S0 현행": Nb11, "S4 증차 10%": np.round(Nb11 * 1.1).astype(int),
          "I1 시간안정(현행 예산)": curves["same"], "I2 시간안정(+10% 예산)": curves["plus10"],
          "H1 낮 재배분(현행 예산)": curves["h_same"], "H2 낮 재배분(+10% 예산)": curves["h_plus10"],
}
    fits = {}
    for key, cname in [("H1", "h_same"), ("H2", "h_plus10")]:
        for tag, lens in [("f", FULL), ("p", PART)]:
            M, info = fit_exact(curves[cname], lens); fits[f"{key}{tag}"] = info
            sc[f"{key}{tag} 낮 재배분({'현행' if key == 'H1' else '+10%'}, {'4∼10시간 근무조' if tag == 'f' else '시간제 포함 근무조'})"] = M
    _, fits["S0"] = fit_exact(Nb11, FULL)
    out["fits"] = fits; print("근무조 근사", fits, flush=True)
    rows, waits, vk = [], {}, {}
    for name, N in sc.items():
        o = run(rq11, d11, k11, N)
        r = summarize(rq11, o, name); r["hour_sd"], r["hour_over60"] = hour_stability(rq11, o["wait"])
        r["vh"] = float(N.sum() / 2)
        rows.append(r); waits[name] = o["wait"]
        km = o["veh_day_km"]; vk[name] = km[km > 0]
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k != "hour_over60"}, flush=True)
    pd.DataFrame(rows).drop(columns=["hour_over60"]).to_csv(PROC / "isa_scenarios.csv", index=False)
    np.savez(PROC / "isa_waits.npz", **waits, reserved=rq11.reserved.values, hour=rq11.hour.values)
    out["eval"] = {r["name"]: {k: v for k, v in r.items() if k != "name"} for r in rows}
    out["curves"] = {k: v.tolist() for k, v in sc.items()}
    # 전기차: 차량·일 주행거리(빈 차 포함) vs 스타리아 EV 11인 1회 충전 주행거리
    fe = pd.read_csv(next(RAW.glob("15083023_*.csv")), encoding="utf-8-sig")
    ev_range = float(fe[fe.모델명.str.contains(r"^스타리아\(US4\) EV 11인", regex=True)].iloc[0]["1회충전주행거리"])
    # 시뮬레이션 거리(직선×1.30)를 실측 승차거리 기준으로 보정: 실측 승차거리/시뮬 승차거리
    t = pd.read_parquet(PROC / "trips.parquet", columns=["차량구분", "done", "승차거리", "예정일시", "dow", "o_x", "d_x"])
    m = t[(t.차량구분 == "특장차") & t.done & (t.예정일시 >= "2025-11-01") & (t.예정일시 < "2025-11-29") & (t.dow < 5) & t.o_x.notna() & t.d_x.notna()]
    s0 = [r for r in rows if r["name"] == "S0 현행"][0]
    scale = float(m.승차거리.sum() / 1000 / s0["pass_km"])
    out["ev"] = dict(range_km=ev_range, km_scale=scale, **{
        name: dict(p50=float(np.percentile(v * scale, 50)), p95=float(np.percentile(v * scale, 95)), max=float(v.max() * scale),
                   share_over_range=float((v * scale > ev_range).mean()), share_over_70pct=float((v * scale > 0.7 * ev_range).mean()))
        for name, v in vk.items() if name in ("S0 현행", "H2 낮 재배분(+10% 예산)", "S4 증차 10%")})
    print("EV", out["ev"])
    json.dump(out, open(PROC / "isa.json", "w"), ensure_ascii=False, indent=1, default=float)
