"""대기 불평등의 Theil T 분해: 전체 불평등 중 '집단 간' 몫(시간대·생활권·자치구·행정동·시간대×생활권)
T = mean((w/μ)·ln(w/μ)),  T = Σ_g s_g·T_g (집단 안) + Σ_g s_g·ln(μ_g/μ) (집단 간),  s_g = 집단 g의 대기 총량 몫
대상: 2025년 특장차 즉시 호출 완료 건(서울 출발), 대기 1분 미만은 1분으로(로그 정의)
지니(Delbosc & Currie 2011; 서울 대중교통 적용 Jang et al. 2017)는 분해가 안 되어, 원인 구분에는 Theil을 함께 씀"""
import json, numpy as np, pandas as pd
from common import PROC

LIFE = {"도심권": "종로구 중구 용산구", "동북권": "성동구 광진구 동대문구 중랑구 성북구 강북구 도봉구 노원구",
        "서북권": "은평구 서대문구 마포구", "서남권": "양천구 강서구 구로구 금천구 영등포구 동작구 관악구",
        "동남권": "서초구 강남구 송파구 강동구"}
GU2L = {g: k for k, v in LIFE.items() for g in v.split()}
t = pd.read_parquet(PROC / "trips.parquet", columns=["차량구분", "reserved", "done", "wait", "hour", "dow", "출발구", "o_adm"])
d = t[(t.차량구분 == "특장차") & ~t.reserved & t.done & t.wait.notna() & t.출발구.isin(GU2L)].copy()
d["w"] = d.wait.clip(lower=1); d["life"] = d.출발구.map(GU2L)
d["hl"] = d.hour.astype(str) + "|" + d.life

def theil(w):
    r = w / w.mean(); return float(np.mean(r * np.log(r)))
T = theil(d.w.values); mu = d.w.mean()
def between(col):
    g = d.groupby(col).w.agg(["sum", "mean"]); s = g["sum"] / g["sum"].sum()
    return float((s * np.log(g["mean"] / mu)).sum())
res = dict(T=T, n=len(d))
for col, nm in [("hour", "시간대(24)"), ("life", "생활권(5)"), ("출발구", "자치구(25)"), ("o_adm", "행정동"), ("hl", "시간대×생활권")]:
    b = between(col); res[nm] = dict(between=b, share=b / T, groups=int(d[col].nunique()))
# 60분 초과 여부(0/1)의 분산 분해(설명 비율 = 집단 간 분산 / 전체 분산)도 함께
y = (d.wait > 60).astype(float); V = y.var(ddof=0)
for col, nm in [("hour", "시간대(24)"), ("life", "생활권(5)"), ("출발구", "자치구(25)"), ("o_adm", "행정동"), ("hl", "시간대×생활권")]:
    m = y.groupby(d[col]).transform("mean"); res[nm]["over60_between_share"] = float(m.var(ddof=0) / V)
json.dump(res, open(PROC / "theil.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
