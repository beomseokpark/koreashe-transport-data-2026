"""정책 시나리오 시뮬레이션 (평가: 2025-11 평일, 거점·수요 학습: 2025-09~10 평일)
S0 현행(빈 차는 하차 지점 대기)            S1 근무 시각 재배치(같은 차량·시간 총량, SIPP+제곱근 규칙 ILP)
S2 MEXCLP 대기 거점                        S3 S1+S2
S4·S5 현행 근무 모양 그대로 차량 +10%·+20%(비교 기준: 증차)
S6 S4와 같은 추가 차량·시간을 정점(07:00~09:30, 14:30~17:30)에만 투입   S7 S1+S6"""
import json, numpy as np, pandas as pd, pulp
import simdata as sd
from sim import Sim
from common import PROC, FIG

SL = sd.SLOT; NS = 1440 // SL
cal = json.load(open(PROC / "sim_calib.json"))["best"]; C, A = cal["c"], cal["a"]

def offered_load(req, ndays, service_extra):
    """무한서버 제공부하 m(t): 각 호출이 [예정, 예정+접근+승차] 동안 차 1대를 쓴다고 보고 30분 칸별 평균 동시 사용 대수
    (Green·Kolesar·Whitt 2007의 lagged/modified-offered-load 방식: 서비스 시간만큼 늦게 반영)"""
    m = np.zeros(NS)
    a = (req.t.values % 1440); dur = service_extra + req.ride.values
    for s0, d in zip(a, dur):
        e = s0 + d; k = int(s0 // SL)
        while k * SL < e and k < 3 * NS:
            lo, hi = max(s0, k * SL), min(e, (k + 1) * SL)
            m[k % NS] += max(0, hi - lo) / SL; k += 1
    return m / ndays

LENS = [8, 12, 16, 18, 20]     # 근무 길이 4·6·8·9·10시간(30분 칸)
W0, W1 = 10, 48                # 근무 창 05:00~24:00 (그 밖 심야는 현행 유지)
TPL = [(k, L) for L in LENS for k in range(W0, W1 - L + 1)]

def cover(x, base):
    N = base.copy(); N[W0:W1] = 0
    for (k, L), n in zip(TPL, x): N[k:k + L] += n
    return N

def fit_shifts(Nb):
    """현행 근무 곡선(05~24시)을 근무조(시작 시각×길이) 조합으로 근사: Σ|cov−N| 최소, 총 차량·시간 ≤ 현행
    (Dantzig 1954 이래의 근무표 선형계획)"""
    pr = pulp.LpProblem("fit", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x{i}", 0, None, cat="Integer") for i in range(len(TPL))]
    e = {t: pulp.LpVariable(f"e{t}", 0) for t in range(W0, W1)}
    pr += pulp.lpSum(e.values()) + 0.01 * pulp.lpSum(x)
    for t in range(W0, W1):
        cov = pulp.lpSum(x[i] for i, (k, L) in enumerate(TPL) if k <= t < k + L)
        pr += cov - int(Nb[t]) <= e[t]; pr += int(Nb[t]) - cov <= e[t]
    pr += pulp.lpSum(x[i] * L for i, (k, L) in enumerate(TPL)) <= int(Nb[W0:W1].sum())
    pr.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=120))
    return np.array([int(round(v.value())) for v in x])

def late_shift(x, d=-1):
    """18시 이후에 끝나는 근무조의 출근을 d칸(30분) 당김"""
    pos = {tp: i for i, tp in enumerate(TPL)}; y = np.zeros_like(x)
    for i, (k, L) in enumerate(TPL):
        j = pos.get((k + d, L)) if k + L > 36 else i
        y[j if j is not None else i] += x[i]
    return y

def peak_boost(Nb, extra, wins=((14, 19), (29, 35))):
    """추가 차량·시간(칸) extra를 정점 창(07:00~09:30, 14:30~17:30)에만 균등 배분"""
    N = Nb.copy(); slots = [t for a, b in wins for t in range(a, b)]
    add = np.full(len(slots), extra // len(slots)); add[:extra - add.sum()] += 1
    for t, v in zip(slots, add): N[t] += v
    return N

def local_search(x0, base, evalf, step=4, iters=12, log=None, max_evals=10**9):
    """시뮬레이션 기반 국소탐색: 같은 길이 근무조 step명의 출근 시각을 ±30분·±1시간·±2시간 옮겨 평균 대기가 줄면 채택.
    인원·근무 길이·차량·시간 총량은 그대로. 정상상태 근사(SIPP)가 과부하 구간에서 맞지 않아 시뮬레이션으로 직접 평가."""
    x = x0.copy(); best = evalf(cover(x, base)); hist = [best]; ne = 0
    pos = {tp: i for i, tp in enumerate(TPL)}
    for it in range(iters):
        improved = False
        for j in np.random.default_rng(it).permutation(len(TPL)):
            if x[j] < step: continue
            kj, L = TPL[j]
            for d in (1, -1, 2, -2, 4, -4):
                k = pos.get((kj + d, L))
                if k is None: continue
                y = x.copy(); y[j] -= step; y[k] += step
                f = evalf(cover(y, base)); ne += 1
                if ne >= max_evals: return x, best, hist
                if f < best - 0.05:
                    x, best, improved = y, f, True
                    if log: log(it, TPL[j], TPL[k], best)
                    break
        hist.append(best)
        if not improved:
            if step > 2: step //= 2; continue
            break
    return x, best, hist

def hm(k): return f"{k // 2:02d}:{30 * (k % 2):02d}"

def mexclp(hw, X, Y, p, q, rad_km):
    """Daskin(1983) MEXCLP 탐욕 해법: p대를 거점에 하나씩 추가, 한계 기대커버 Σ h_i (1-q) q^{y_i} 최대"""
    D = np.hypot(X[:, None] - X[None, :], Y[:, None] - Y[None, :]) / 1000
    a = D <= rad_km; y = np.zeros(len(X)); x = np.zeros(len(X), int)
    for _ in range(int(p)):
        g = (a * (hw * (1 - q) * q ** y)[:, None]).sum(0)
        j = int(g.argmax()); x[j] += 1; y += a[:, j]
    cov = float((hw * (1 - q ** y)).sum() / hw.sum())
    return x, cov

def summarize(req, o, name):
    w = o["wait"]; imm = ~req.reserved.values; wi = w[imm]
    g = pd.Series(wi).groupby(req.o_gu.values[imm]).median()
    return dict(name=name, med=np.nanmedian(wi), mean=np.nanmean(wi), p90=np.nanpercentile(wi, 90),
                over60=np.nanmean(wi > 60), gu_max_min=float(g.max() - g.min()), gu_sd=float(g.std()),
                dead_km=o["dead_km"], reloc_km=o["reloc_km"], ret_km=o["ret_km"], pass_km=o["pass_km"])

if __name__ == "__main__":
    dep, _ = sd.depots_for(698)
    ev = sd.load("2025-11-01", "2025-11-29"); req, days, *_ = sd.requests(ev)
    kmh = sd.speeds(ev); B = sd.busy_curve(ev, days)
    Nb = np.round(B.mean(0) * (1 + A)).astype(int)
    tile = lambda n: np.tile(n, len(days))
    # 제공부하(무한서버) m(t): 관측 접근시간 중앙값(약 18분)+승차시간. 현행 공급과 비교해 과부하 구간 확인용
    m = offered_load(req, len(days), float(np.nanmedian(req.obs_appr))) * (1 + A)
    # 근무 재배치: 학습월(9월)에서 시뮬레이션 기반 국소탐색 → 평가월(11월)에 같은 시작 시각 비율 적용
    tr9 = sd.load("2025-09-01", "2025-09-30"); rq9, d9, *_ = sd.requests(tr9)
    k9 = sd.speeds(tr9); Nb9 = np.round(sd.busy_curve(tr9, d9).mean(0) * (1 + A)).astype(int)
    ev9 = lambda N: float(np.nanmean(Sim(rq9, np.tile(N, len(d9)), dep, k9, c=C, theta=0.3).run()["wait"]))
    x9 = fit_shifts(Nb9)
    print("9월 현행", ev9(Nb9), "근무조 근사", ev9(cover(x9, Nb9)), "근사 오차(칸 평균)", np.abs(cover(x9, Nb9) - Nb9)[W0:W1].mean(), flush=True)
    f9fit = ev9(cover(x9, Nb9))
    # 구조적 재배치(18시 이후 끝나는 조 30분 당김)에서 시작해 국소탐색 120회로 다듬음
    x9s = late_shift(x9, -1); f9s = ev9(cover(x9s, Nb9)); print("구조적 재배치", f9s, flush=True)
    x9o, f9, hist = local_search(x9s, Nb9, ev9, max_evals=120, log=lambda it, a, b, f: print(f"  iter{it} {hm(a[0])}({a[1]/2:g}h)→{hm(b[0])} 평균대기 {f:.2f}", flush=True))
    xb = fit_shifts(Nb)                                   # 11월 현행을 근무조로 근사
    # 11월 적용: 길이별 인원은 11월 근사값 그대로, 길이 안에서 출근 시각 분포만 9월 최적해를 따름
    xr = np.zeros_like(xb)
    for L in LENS:
        ii = [i for i, (k, l) in enumerate(TPL) if l == L]; n = int(xb[ii].sum())
        if n == 0: continue
        sh = x9o[ii] / x9o[ii].sum() if x9o[ii].sum() else xb[ii] / n
        v = np.floor(sh * n).astype(int); v[np.argsort(-(sh * n - v))[:n - v.sum()]] += 1; xr[ii] = v
    n = int(xb.sum())
    Nfit, Nr = cover(xb, Nb), cover(xr, Nb)
    info = dict(train_base=f9fit, train_struct=f9s, train_opt=f9, hist=hist, drivers=n,
                starts_base={f"{hm(k)}/{L/2:g}h": int(v) for (k, L), v in zip(TPL, xb) if v}, starts_opt={f"{hm(k)}/{L/2:g}h": int(v) for (k, L), v in zip(TPL, xr) if v},
                fit_err=float(np.abs(Nfit - Nb)[W0:W1].mean()))
    print("재배치", info)
    # 학습 기간(9~10월 평일) 출발 수요로 시간대별 MEXCLP 거점
    tr = sd.load("2025-09-01", "2025-10-31"); tr = tr[tr.o_x.notna() & ~tr.date.isin(pd.to_datetime(
        ["2025-10-03", "2025-10-06", "2025-10-07", "2025-10-08", "2025-10-09"]))]
    dg = pd.read_parquet(PROC / "dongs.parquet")
    X, Y = dg.x.values, dg.y.values
    idx = {a: i for i, a in enumerate(dg.adm_cd2)}
    o0 = Sim(req, tile(Nb), dep, kmh, c=C, theta=0.3).run()
    il = pd.DataFrame(o0["idle_log"], columns=["t", "idle", "on"]); il["h"] = (il.t % 1440 // 60).astype(int)
    ih = il.groupby("h")[["idle", "on"]].mean()
    stages, st_info = {}, {}
    for h in range(24):
        sub = tr[tr.hour == h]
        hw = np.bincount(sub.o_adm.map(idx).dropna().astype(int), minlength=len(dg)).astype(float)
        p = int(round(ih.idle.get(h, 0)));
        if p < 1 or hw.sum() == 0: continue
        q = float(np.clip(1 - ih.idle[h] / max(ih.on[h], 1), 0.05, 0.95))
        rad = 10 / 60 * kmh[h] / 1.30         # 10분 안에 닿는 직선거리
        x, cov = mexclp(hw, X, Y, p, q, rad)
        sel = np.flatnonzero(x)
        stages[h] = (np.c_[X[sel], Y[sel]], x[sel]); st_info[h] = dict(p=p, q=round(q, 3), rad_km=round(rad, 2), sites=len(sel), cov=round(cov, 3))
    print("거점", st_info)
    sc = {"S0 현행": (Nb, "stay"), "S0' 현행(근무조 근사)": (Nfit, "stay"), "S1 근무 재배치": (Nr, "stay"), "S2 대기 거점": (Nb, "stage"), "S3 재배치+거점": (Nr, "stage"),
          "S4 증차 10%": (np.round(Nb * 1.1).astype(int), "stay"), "S5 증차 20%": (np.round(Nb * 1.2).astype(int), "stay"),
          "S6 정점 집중 보강": (peak_boost(Nb, int(np.round(Nb * 1.1).astype(int).sum() - Nb.sum())), "stay"),
          "S7 재배치+정점 보강": (peak_boost(Nr, int(np.round(Nb * 1.1).astype(int).sum() - Nb.sum())), "stay")}
    rows, waits = [], {}
    for name, (N, pol) in sc.items():
        o = o0 if name == "S0 현행" else Sim(req, tile(N), dep, kmh, c=C, theta=0.3, policy=pol, stages=stages).run()
        rows.append(summarize(req, o, name)); waits[name] = o["wait"]; print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in rows[-1].items()})
    pd.DataFrame(rows).to_csv(PROC / "scenarios.csv", index=False)
    np.savez(PROC / "scenario_waits.npz", **{k: v for k, v in waits.items()}, reserved=req.reserved.values,
             hour=req.hour.values, gu=req.o_gu.values.astype(str), adm=req.o_adm.values.astype(str))
    json.dump(dict(retime=info, Nb=Nb.tolist(), Nr=Nr.tolist(), Nfit=Nfit.tolist(),
                   Npeak=peak_boost(Nb, int(np.round(Nb * 1.1).astype(int).sum() - Nb.sum())).tolist(), m=m.round(2).tolist(), stages=st_info,
                   stage_sites={h: dict(x=v[0][:, 0].tolist(), y=v[0][:, 1].tolist(), n=v[1].tolist()) for h, v in stages.items()},
                   days=len(days), nreq=len(req)),
              open(PROC / "policies.json", "w"), ensure_ascii=False, indent=1)
