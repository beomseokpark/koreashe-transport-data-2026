"""단시간 운전원 근무 시간대 조정·증원 배치·수요 분담 시나리오 + 시뮬레이터 매개변수 민감도
- 근거: 서울시설공단 2025년 계약직원 공개채용 공고 — 장애인콜택시 단시간 운전원 150명, 일 5시간,
  근무시간 07:00~12:00 / 16:00~21:00 / 17:00~22:00 등(reference/policy/2025_단시간운전원_공고.pdf)
- 공급은 시뮬레이터와 같은 '유효 근무 차량' 곡선(30분 칸). 단시간 운전원 1명 = 근무 시간 동안 차량 1대로 둔다.
- L 시나리오: 오후 조(16~21시) k명을 14~19시로 2시간 당김(총 근무시간 같음). 9월·11월 평일에 각각 적용(학습 없이 구조만 바꾸므로 과적합 없음)
- P 시나리오: 2026년 증원분(25명, 150→175명)을 어느 시간대에 둘지 비교
- D 시나리오: 14~18시 즉시 호출의 10%를 바우처택시 등으로 분담(무작위, 시드 고정)
- 민감도: 준비시간 c, 우회계수, 배차 규칙 θ, 가동률 a를 하나씩 바꿔 주요 시나리오의 '현행 대비 변화율'이 유지되는지 확인"""
import json, numpy as np, pandas as pd
import simdata as sd
from sim import Sim
from p4_policies import summarize, peak_boost, C, A
from common import PROC

dep, _ = sd.depots_for(698)
sl = lambda h: int(round(h * 2))
km = pd.read_csv(PROC / "km_patience.csv", index_col=0).iloc[:, 0]

def aband(w):
    w = np.clip(w[~np.isnan(w)], 0, None)
    return float(np.mean(1 - np.interp(w, km.index.values, km.values)))

def setup(a, b):
    s = sd.load(a, b); req, days, *_ = sd.requests(s)
    return req, days, sd.speeds(s), sd.busy_curve(s, days).mean(0)

def move(N, k, a=(16, 21), b=(14, 19)):
    M = N.copy(); M[sl(a[0]):sl(a[1])] -= k; M[sl(b[0]):sl(b[1])] += k
    return np.maximum(M, 0)

def add(N, k, b):
    M = N.copy(); M[sl(b[0]):sl(b[1])] += k; return M

def scenarios(Nb, hybrid=None):
    sc = {"S0 현행": Nb,
          "L20 오후 단시간 20명 16~21→14~19시": move(Nb, 20), "L30 오후 단시간 30명 16~21→14~19시": move(Nb, 30),
          "P1 증원 25명 07~12시": add(Nb, 25, (7, 12)), "P2 증원 25명 16~21시": add(Nb, 25, (16, 21)),
          "P3 증원 25명 14~19시": add(Nb, 25, (14, 19)), "P4 오후 30명 이동+증원 25명 16~21시": add(move(Nb, 30), 25, (16, 21)),
          "S4 균등 증차 10%": np.round(Nb * 1.1).astype(int),
          "S6 정점 집중 보강 +10%": peak_boost(Nb, int(np.round(Nb * 1.1).astype(int).sum() - Nb.sum()))}
    if hybrid is not None: sc["H1 낮 재배분(같은 근무시간)"] = hybrid
    return sc

def divert(req, share=0.10, hours=(14, 18), seed=0):
    """14~18시 즉시 호출 중 share를 무작위로 빼서(바우처택시 등 분담) 남은 호출만 재배차"""
    rng = np.random.default_rng(seed)
    cand = (~req.reserved.values) & (req.hour.values >= hours[0]) & (req.hour.values < hours[1])
    drop = cand & (rng.random(len(req)) < share)
    return req[~drop].reset_index(drop=True), int(drop.sum())

def evaluate(req, days, kmh, N, c=C, theta=0.3, detour=1.30):
    o = Sim(req, np.tile(N, len(days)), dep, kmh, c=c, theta=theta, detour=detour).run()
    r = summarize(req, o, ""); imm = ~req.reserved.values; w = o["wait"][imm]; hr = req.hour.values[imm]
    g = pd.Series(w).groupby(hr)
    r.update(aband=aband(w), hour_mean=g.mean().reindex(range(6, 23)).round(1).tolist(),
             hour_over60=g.apply(lambda x: float((x > 60).mean())).reindex(range(6, 23)).round(3).tolist(),
             vh=float(N.sum() / 2), empty=float((o["dead_km"] + o["ret_km"]) / o["pass_km"]))
    return r, o["wait"]

if __name__ == "__main__":
    IJ = json.load(open(PROC / "isa.json"))
    out = {"source": "서울시설공단 2025년 계약직원 공개채용 공고(단시간 운전원 150명, 07~12/16~21/17~22시, 시급 12,030원)"}
    waits = {}
    for tag, (a, b) in {"sep": ("2025-09-01", "2025-09-30"), "nov": ("2025-11-01", "2025-11-29")}.items():
        req, days, kmh, busy = setup(a, b)
        Nb = np.round(busy * (1 + A)).astype(int)
        hyb = np.array(IJ["curves"]["H1 낮 재배분(현행 예산)"]) if tag == "nov" else None
        res = {}
        for name, N in scenarios(Nb, hyb).items():
            r, w = evaluate(req, days, kmh, N); r.pop("name"); res[name] = r
            if tag == "nov": waits[name] = w
            print(tag, f"{name:34s} mean {r['mean']:.2f} over60 {r['over60']:.3f} vh {r['vh'] - Nb.sum() / 2:+.0f}", flush=True)
        rq_d, nd = divert(req)
        r, _ = evaluate(rq_d, days, kmh, Nb); r.pop("name"); r["diverted_per_day"] = nd / len(days); res["D10 14~18시 호출 10% 바우처 분담"] = r
        print(tag, "D10", round(r["mean"], 2), round(r["over60"], 3), "분담", round(nd / len(days), 1), "건/일", flush=True)
        out[tag] = dict(days=len(days), nreq=len(req), N0=Nb.tolist(), scen=res)
    np.savez(PROC / "shift_waits.npz", **waits)
    # 민감도(11월): 매개변수 하나씩 바꿔 현행 대비 변화율
    req, days, kmh, busy = setup("2025-11-01", "2025-11-29")
    hyb = np.array(IJ["curves"]["H1 낮 재배분(현행 예산)"]); Nb0 = np.round(busy * (1 + A)).astype(int)
    grid = [("기준", {}), ("준비시간 8분", dict(c=8)), ("준비시간 12분", dict(c=12)), ("우회계수 1.2", dict(detour=1.2)), ("우회계수 1.4", dict(detour=1.4)),
            ("배차 θ 0.1", dict(theta=0.1)), ("배차 θ 0.5", dict(theta=0.5)), ("가동률 0.80", dict(a=-0.20)), ("가동률 0.90", dict(a=-0.10))]
    keys = ["L30 오후 단시간 30명 16~21→14~19시", "P3 증원 25명 14~19시", "P2 증원 25명 16~21시", "S6 정점 집중 보강 +10%", "S4 균등 증차 10%", "H1 낮 재배분(같은 근무시간)"]
    sens = {}
    for label, kw in grid:
        a = kw.pop("a", A); scale = (1 + a) / (1 + A)
        Nb = np.round(busy * (1 + a)).astype(int)
        sc = scenarios(Nb, np.round(hyb * scale).astype(int))
        base, _ = evaluate(req, days, kmh, Nb, **kw)
        row = dict(base_mean=base["mean"], base_over60=base["over60"])
        for k in keys:
            r, _ = evaluate(req, days, kmh, sc[k], **kw); row[k] = dict(mean=r["mean"], chg=r["mean"] / base["mean"] - 1, over60=r["over60"])
        sens[label] = row
        print("민감도", label, round(base["mean"], 1), {k[:3]: round(v["chg"] * 100, 1) for k, v in row.items() if isinstance(v, dict)}, flush=True)
    out["sensitivity"] = sens
    json.dump(out, open(PROC / "shift.json", "w"), ensure_ascii=False, indent=1, default=float)
