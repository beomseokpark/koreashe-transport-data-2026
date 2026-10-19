"""탑승내역 2025(172만 건) 정리 → data/processed/trips.parquet, dongs.parquet
- 요청시각 t0 = 예정일시(즉시 호출은 접수와 같음), 대기 = 승차-예정, 배차지연 = 배차-예정
- 출발·목적 행정동 → 2026.7 행정동 경계(adm_cd2) 중심점(EPSG:5179, m)"""
import pandas as pd, numpy as np, geopandas as gpd
from common import *

g = gpd.read_file(GEO)
g = g[g.sidonm == "서울특별시"].to_crs(5179)
g["dong"] = g.adm_nm.str.split().str[-1]
g["key"] = g.sggnm + "|" + g.dong.map(norm_dong)
g["base"] = g.dong.map(dong_base)
c = g.geometry.representative_point()
g["x"], g["y"] = c.x, c.y
g["area_km2"] = g.geometry.area / 1e6
g[["adm_cd2", "sggnm", "dong", "key", "x", "y", "area_km2", "geometry"]].to_parquet(PROC / "dongs.parquet")
key2 = g.set_index("key")
OLD = {("종로구", "명륜3가동"): "혜화동"}   # 옛 법정동 이름 → 현행 행정동

def resolve(gu, dg):
    """(구, 동) → (adm_cd2, x, y). 표기 변형 → 옛 동(같은 구에서 이름이 같은 현행 동들의 평균 중심) 순"""
    dg = OLD.get((gu, norm_dong(dg)), dg)
    for v in dong_variants(dg):
        k = f"{gu}|{v}"
        if k in key2.index:
            r = key2.loc[k]; return r.adm_cd2, r.x, r.y, "exact"
    c = g[(g.sggnm == gu) & (g.base == dong_base(dg))]
    if len(c):
        r = c.sort_values("area_km2").iloc[-1]
        return r.adm_cd2, c.x.mean(), c.y.mean(), "base"
    return None, np.nan, np.nan, "none"

cols = ["접수일시", "예정일시", "배차일시", "승차일시", "하차일시", "취소일시"]
df = pd.read_csv(TRIPS, parse_dates=cols, encoding="utf-8-sig")
n0 = len(df)
mins = lambda a, b: (df[a] - df[b]).dt.total_seconds() / 60
df["lead"] = mins("예정일시", "접수일시")
df["wait"] = mins("승차일시", "예정일시")
df["wait_disp"] = mins("배차일시", "예정일시")
df["t_cancel"] = mins("취소일시", "예정일시")
df["ride_min"] = mins("하차일시", "승차일시")
df["done"] = df.승차일시.notna()
df["cancel"] = df.취소일시.notna() & ~df.done
df["reserved"] = (df.lead > 10) | df.이용목적.str.startswith("예약")
df["hour"] = df.예정일시.dt.hour
df["dow"] = df.예정일시.dt.dayofweek
df["date"] = df.예정일시.dt.date

for side, gu, dg in [("o", "출발구", "출발동"), ("d", "목적구", "목적동")]:
    pairs = df[[gu, dg]].drop_duplicates()
    lut = {(a, b): resolve(a, b) for a, b in pairs.itertuples(index=False)}
    res = pd.DataFrame([lut[t] for t in zip(df[gu], df[dg])], columns=["adm", "x", "y", "how"], index=df.index)
    df[f"{side}_adm"], df[f"{side}_x"], df[f"{side}_y"] = res.adm, res.x, res.y
    seoul = df[gu].isin(g.sggnm.unique())
    print(side, "서울 내 매칭", res[seoul].how.value_counts(normalize=True).round(4).to_dict(),
          "옛 동 묶음:", sorted({f"{a} {b}" for (a, b), v in lut.items() if v[3] == "base"}),
          "미매칭:", df.loc[seoul & res.adm.isna(), dg].value_counts().head(5).to_dict())

# 이상치: 대기 −30분 미만·300분 초과는 기록 오류로 보고 대기 지표에서 제외(건수 보고)
bad = df.done & ~df.wait.between(-30, 300)
print("총", n0, "완료", int(df.done.sum()), "취소", int(df.cancel.sum()), "대기 이상치", int(bad.sum()))
df.loc[bad, "wait"] = np.nan
keep = ["접수일시", "예정일시", "배차일시", "승차일시", "하차일시", "취소일시", "출발구", "출발동", "목적구", "목적동",
        "이용목적", "요금", "승차거리", "차량구분", "장애유형", "lead", "wait", "wait_disp", "t_cancel", "ride_min",
        "done", "cancel", "reserved", "hour", "dow", "date", "o_adm", "o_x", "o_y", "d_adm", "d_x", "d_y"]
df["date"] = pd.to_datetime(df.date)
df[keep].to_parquet(PROC / "trips.parquet")
print(df.groupby("차량구분")[["done", "cancel", "reserved"]].mean().round(3))
