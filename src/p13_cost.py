"""택시 연계 1건당 보조금 추정(거리요금 기준 하한) — 서울 중형택시 요금(2023.2.1~: 기본 4,800원/1.6㎞, 131m당 100원),
이용자 부담 = 장애인콜택시 요금(바우처 운영규정 2024.8: 5㎞ 1,500원, 5~10㎞ 280원/㎞, 10㎞ 초과 70원/㎞, 30㎞ 초과 750원/㎞),
기사 봉사비 2,000원(서울신문 2025.11.7). 호출료·시간요금·단거리 보상은 제외 → 실제보다 낮게 잡힌 값"""
import json, numpy as np, pandas as pd
from common import PROC

def meter(d): return 4800 + np.maximum(d - 1.6, 0) / 0.131 * 100
def fare(d):
    return 1500 + np.clip(d - 5, 0, 5) * 280 + np.clip(d - 10, 0, 20) * 70 + np.maximum(d - 30, 0) * 750
t = pd.read_parquet(PROC / "trips.parquet", columns=["차량구분", "done", "reserved", "승차거리"])
d = t[(t.차량구분 == "특장차") & t.done & ~t.reserved & (t.승차거리 > 0)].승차거리.values / 1000
sub = meter(d) - fare(d) + 2000
lm = json.load(open(PROC / "lastmile.json"))
leg = 2 * (meter(1.5) - 1500 + 2000)
dd = np.arange(1, 40, 0.1); be = float(dd[np.argmax(meter(dd) - fare(dd) + 2000 >= leg)])
out = dict(mean_km=float(d.mean()), subsidy_mean=float(sub.mean()), subsidy_median=float(np.median(sub)), user_fare_mean=float(fare(d).mean()),
           meter_mean=float(meter(d).mean()), lastmile_two_legs=float(leg), breakeven_km=be,
           wav_bonus_chicago_usd=30, calltaxi_cost_per_trip_2024=59700, pt_wage=12030, pt_year=12030 * 5 * 250)
print(out)
json.dump(out, open(PROC / "cost.json", "w"), ensure_ascii=False, indent=1, default=float)
