"""보고서 그림 1~3 (격차 실증)"""
import json, numpy as np, pandas as pd, geopandas as gpd
from style import *
from common import PROC
J = json.load(open(PROC / "gap.json"))
H = pd.read_csv(PROC / "hour_profile.csv", index_col=0)
hrs = H.index.values

# 그림 1: 평일 시간대별 호출·운행 차량·대기 (가로 3칸, 같은 x축) + 단시간 근무 편성(서울시설공단 2025년 채용공고)
with plt.rc_context({"font.size": 10, "axes.titlesize": 10.5, "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 8.5}):
    fig, ax = plt.subplots(1, 3, figsize=(8.8, 2.75), gridspec_kw=dict(wspace=0.28))
    ax[0].bar(hrs, H.calls_per_day, color=BLUE, width=0.8)
    ax[0].set_title("① 즉시 호출(평일 하루 평균, 건)")
    ax[1].plot(hrs, H.busy_mean, color=BLUE, marker="o", ms=2.5)
    ax[1].fill_between(hrs, 0, H.busy_mean, color=BLUE, alpha=.08)
    ax[1].axhline(J["fleet"], color=GRAY, lw=1); ax[1].text(-0.4, J["fleet"] - 15, f"보유 차량 {J['fleet']}대", ha="left", va="top", color=INK2, fontsize=8)
    ax[1].set_ylim(0, 720); ax[1].set_title("② 운행 중 차량(배차~하차, 대)")
    ax[1].annotate(f"07시 {H.busy_mean[7]:.0f}대", (7, H.busy_mean[7]), (0.2, 300), fontsize=8, color=INK, arrowprops=dict(arrowstyle="-", color=GRAY, lw=.8))
    ax[1].annotate(f"16시 {H.busy_mean[16]:.0f}대", (16, H.busy_mean[16]), (16.6, 300), fontsize=8, color=INK, arrowprops=dict(arrowstyle="-", color=GRAY, lw=.8))
    for (a_, b_), y in zip([(7, 12), (16, 21), (17, 22)], [545, 545, 480]):
        ax[1].plot([a_ - 0.5, b_ - 0.5], [y, y], color=AQUA, lw=4, solid_capstyle="butt")
    ax[1].text(6.2, 545, "단시간", ha="right", va="center", fontsize=7.5, color=AQUA)
    ax[1].text(9, 575, "07∼12시", ha="center", va="bottom", fontsize=7.5, color=AQUA)
    ax[1].text(18, 575, "16∼21시", ha="center", va="bottom", fontsize=7.5, color=AQUA)
    ax[1].text(19, 450, "17∼22시", ha="center", va="top", fontsize=7.5, color=AQUA)
    ax[2].plot(hrs, H.wait_med, color=BLUE, marker="o", ms=2.5, label="중앙값")
    ax[2].plot(hrs, H.wait_p90, color=ORANGE, marker="o", ms=2.5, label="상위 10%")
    ax[2].set_title("③ 호출~승차 대기(분)"); ax[2].legend(loc="upper left", ncol=2, fontsize=8, bbox_to_anchor=(0, 1.0))
    ax[2].set_ylim(0, 150)
    for a_, b_ in ((6.5, 8.5), (13.5, 16.5)): ax[2].axvspan(a_, b_, color=ORANGE, alpha=.08, lw=0)
    for a in ax:
        a.set_xticks(range(0, 24, 4)); a.set_xticklabels([f"{h}시" for h in range(0, 24, 4)]); a.set_xlim(-0.6, 23.6)
    save(fig, "fig1_hour")

# 그림 2: 행정동 지도 (60분 초과 비율 / Gi* 핫스팟)
g = gpd.read_parquet(PROC / "dong_gap.parquet")
dg = gpd.read_parquet(PROC / "dongs.parquet")
dp = pd.read_csv(PROC / "depots.csv"); dpg = gpd.GeoDataFrame(dp, geometry=gpd.points_from_xy(dp.lon, dp.lat), crs=4326).to_crs(5179)
gu = dg.dissolve("sggnm")
fig, ax = plt.subplots(1, 2, figsize=(7.4, 4.0))
bins = [0, .10, .15, .20, .25, .30, 1.01]
from matplotlib.colors import BoundaryNorm, ListedColormap
cm = ListedColormap(SEQ[:6]); nm = BoundaryNorm(bins, cm.N)
dg.plot(ax=ax[0], color="#f0efec", lw=0)
g.plot(ax=ax[0], column="over60", cmap=cm, norm=nm, lw=0.15, edgecolor="white")
gu.boundary.plot(ax=ax[0], color=INK2, lw=0.5)
from matplotlib.patches import Patch
lab = ["10% 미만", "10~15%", "15~20%", "20~25%", "25~30%", "30% 이상"]
ax[0].legend([Patch(color=c) for c in SEQ[:6]], lab, loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=3, fontsize=7, title="60분 넘게 기다린 호출 비율", title_fontsize=7.5)
ax[0].set_title("① 행정동별 60분 초과 대기 비율")
col = {"hot": RED, "cold": BLUE, "ns": "#e6e5e1"}
dg.plot(ax=ax[1], color="#f7f7f5", lw=0)
g.plot(ax=ax[1], color=g.hot.map(col), lw=0.15, edgecolor="white")
gu.boundary.plot(ax=ax[1], color=INK2, lw=0.5)
dpg.plot(ax=ax[1], color=INK, markersize=7, marker="^")
ax[1].legend([Patch(color=RED), Patch(color=BLUE), Patch(color="#e6e5e1"), plt.Line2D([], [], color=INK, marker="^", ls="", ms=4)],
             [f"고대기 군집 {J['hotspot']['hot']}개 동", f"저대기 군집 {J['hotspot']['cold']}개 동", "유의하지 않음", "차고지 44곳"],
             loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=2, fontsize=7)
ax[1].set_title("② 평균 대기 Gi* 핫스팟 (p<0.05)")
for a in ax: a.set_axis_off()
save(fig, "fig2_map")

# 그림 3: 로렌츠 곡선 + 인내시간(Kaplan–Meier)
fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw=dict(wspace=0.32))
L = J["lorenz"]
ax[0].plot([0, 1], [0, 1], color=GRAY, lw=1)
ax[0].plot(L["x"], L["y"], color=BLUE)
ax[0].fill_between(L["x"], L["y"], L["x"], color=BLUE, alpha=.1)
ax[0].set_xlabel("호출 누적 비율 (긴 대기 비율이 낮은 동부터)"); ax[0].set_ylabel("60분 초과 대기 누적 비율")
ax[0].text(0.05, 0.85, f"지니계수 {L['gini']:.2f}\n상위 20% 호출이 긴 대기의 {L['top20']*100:.0f}%", fontsize=8, color=INK, va="top")
ax[0].set_title("① 긴 대기의 불평등 (로렌츠 곡선)"); ax[0].set_xlim(0, 1); ax[0].set_ylim(0, 1)
P = J["patience"]
ax[1].plot(P["grid"], [1 - s for s in P["S"]], color=ORANGE)
for w in (30, 60, 90):
    v = 1 - P[f"S{w}"]; ax[1].plot(w, v, "o", color=ORANGE, ms=4)
    ax[1].text(w + 3, v - 0.02, f"{w}분 {v*100:.0f}%", fontsize=8, color=INK, va="top")
ax[1].set_xlabel("호출 후 경과 시간 (분)"); ax[1].set_ylabel("그때까지 포기(취소)할 확률")
ax[1].set_title("② 대기 시간별 누적 포기 확률 (Kaplan–Meier)"); ax[1].set_xlim(0, 180); ax[1].set_ylim(0, 0.35)
save(fig, "fig3_equity")
print("ok")
