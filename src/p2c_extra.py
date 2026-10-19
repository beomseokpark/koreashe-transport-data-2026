"""보조 진단: 예약 호출 지연(특히 06시대·출근/통학), 임차택시 시간대 분포, 공단 공식 대기 통계와 수준 대조
- 예약 지연 = 승차시각 − 예정시각(예약 호출). 06시대 예약은 첫 배차 시각 분포로 '근무 시작 전 공백'을 확인
- 임차택시(개인택시 임차, 비휠체어 이용자용) 시간대별 운행 건수와 특장차 대기를 나란히 비교
- 공단 '시간대별 대기시간'×'시간대별 탑승건수'의 탑승가중 연평균 vs 탑승내역(특장차+임차택시) 평균"""
import json, numpy as np, pandas as pd
from common import *

t = pd.read_parquet(PROC / "trips.parquet")
sp = t[t.차량구분 == "특장차"]; tx = t[t.차량구분 == "임차택시"]
out = {}

# 1) 예약 호출 지연
r = sp[sp.reserved & sp.done & sp.wait.notna()]
rw = r[r.dow < 5]
out["res"] = dict(n=len(r), med=float(r.wait.median()), over30=float((r.wait > 30).mean()), over60=float((r.wait > 60).mean()),
                  hour_med=rw.groupby("hour").wait.median().round(1).to_dict(), hour_over30=rw.groupby("hour").wait.apply(lambda x: float((x > 30).mean())).round(3).to_dict())
r6 = rw[rw.hour == 6]
mins = lambda c: (r6[c].dt.hour * 60 + r6[c].dt.minute)
out["res6"] = dict(n=len(r6), per_day=len(r6) / rw.date.nunique(), sched_med=float(mins("예정일시").median()),
                   disp_med=float(mins("배차일시").median()), pick_med=float(mins("승차일시").median()),
                   late_med=float(r6.wait.median()), over30=float((r6.wait > 30).mean()),
                   disp_after7=float((mins("배차일시") >= 420).mean()))
i6 = sp[~sp.reserved & (sp.dow < 5) & (sp.hour == 6)]
out["imm6"] = dict(per_day=len(i6) / i6.date.nunique(), med=float(i6[i6.done].wait.median()))
c = r[r.이용목적.str.contains("통학")]
out["commute_res"] = dict(n=len(c), share_reserved=float(sp[sp.이용목적.str.contains("통학")].reserved.mean()), med=float(c.wait.median()),
                          over30=float((c.wait > 30).mean()), over60=float((c.wait > 60).mean()))
ci = sp[~sp.reserved & sp.이용목적.str.contains("통학")]
out["commute_imm"] = dict(n=len(ci), cancel=float(ci.cancel.mean()), over60=float((ci[ci.done].wait > 60).mean()))

# 2) 임차택시 시간대 분포(평일 하루 평균 건수)와 대기
wd = lambda d: d[d.dow < 5]
nd = wd(t).date.nunique()
out["taxi_hour"] = (wd(tx).groupby("hour").size() / nd).round(1).reindex(range(24), fill_value=0).to_dict()
out["sp_hour"] = (wd(sp).groupby("hour").size() / nd).round(1).reindex(range(24), fill_value=0).to_dict()
txi = wd(tx[tx.done & ~tx.reserved])
out["taxi_wait_hour"] = txi.groupby("hour").wait.median().round(1).to_dict()
tsum = wd(tx).groupby("hour").size()
out["taxi_share"] = dict(day_10_15=float(tsum.loc[10:14].sum() / tsum.sum()), after18=float(tsum.loc[18:].sum() / tsum.sum()),
                         peak_7_9=float(tsum.loc[7:8].sum() / tsum.sum()), peak_15_18=float(tsum.loc[15:17].sum() / tsum.sum()))

# 3) 공식 통계 수준 대조
off = pd.read_csv(next(RAW.glob("15147613_*.csv")), encoding="utf-8-sig")
tb = pd.read_csv(next(RAW.glob("15147614_*.csv")), encoding="utf-8-sig")
m = off.merge(tb, on=["시설명", "일자", "시간대"])
d = t[t.done & t.wait.notna()]
out["level"] = dict(official_weighted=float((m.대기시간평균 * m.탑승건수).sum() / m.탑승건수.sum()), official_rides=int(m.탑승건수.sum()),
                    mine_all=float(d.wait.mean()), mine_rides=len(d), mine_sp=float(d[d.차량구분 == "특장차"].wait.mean()),
                    mine_taxi=float(d[d.차량구분 == "임차택시"].wait.mean()))
json.dump(out, open(PROC / "extra.json", "w"), ensure_ascii=False, indent=1, default=float)
print(json.dumps({k: v for k, v in out.items() if k not in ("taxi_hour", "sp_hour", "taxi_wait_hour")}, ensure_ascii=False, indent=1, default=float))
