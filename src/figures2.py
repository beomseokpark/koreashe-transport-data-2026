"""보고서 그림 4(정책 시뮬레이션)·5(한 장 요약)"""
import json, numpy as np, pandas as pd, geopandas as gpd
from matplotlib.patches import FancyBboxPatch
from style import *
from common import PROC

P = json.load(open(PROC / "policies.json")); G = json.load(open(PROC / "gap.json")); CB = json.load(open(PROC / "carbon.json"))
SC = pd.read_csv(PROC / "scenarios.csv").set_index("name")
W = np.load(PROC / "scenario_waits.npz", allow_pickle=True)
imm = ~W["reserved"]; hour = W["hour"]
t = np.arange(48) / 2
lab = lambda k: k.split(" ", 1)[1]

# 그림 4: 단시간 운전원 근무시간대 조정·증원 배치 시나리오(p7_shift.py) ① 근무 차량 곡선 ② 시간대별 평균 대기
SH = json.load(open(PROC / "shift.json")); SN = SH["nov"]["scen"]; N0 = np.array(SH["nov"]["N0"])
sl = lambda h: int(round(h * 2))
def move(N, k, a=(16, 21), b=(14, 19)):
    M = N.copy(); M[sl(a[0]):sl(a[1])] -= k; M[sl(b[0]):sl(b[1])] += k; return np.maximum(M, 0)
def addk(N, k, b):
    M = N.copy(); M[sl(b[0]):sl(b[1])] += k; return M
kk = lambda pre: [k for k in SN if k.startswith(pre)][0]
SERIES = [("S0 현행", N0, GRAY, "-", 2.6, "현행"),
          (kk("L30"), move(N0, 30), BLUE, "-", 1.9, "오후 단시간 30명 14∼19시로 이동(같은 근무시간)"),
          (kk("P2"), addk(N0, 25, (16, 21)), AQUA, "--", 1.5, "단시간 25명 증원 16∼21시 배치"),
          (kk("P3"), addk(N0, 25, (14, 19)), ORANGE, "-", 1.7, "단시간 25명 증원 14∼19시 배치")]
fig, ax = plt.subplots(1, 2, figsize=(7.4, 3.0), gridspec_kw=dict(wspace=0.26))
for k, N, c, ls, lw, nm in SERIES:
    ax[0].step(t, N, where="post", color=c, ls=ls, lw=lw, label=nm)
ax[0].set_xlim(6, 23); ax[0].set_xticks(range(6, 24, 3)); ax[0].set_xticklabels([f"{h}시" for h in range(6, 24, 3)])
ax[0].axvspan(14, 16, color=ORANGE, alpha=.08, lw=0); ax[0].text(15, 20, "14∼16시\n공백 보강", ha="center", fontsize=7, color=INK2)
ax[0].set_title("① 근무 차량 수(시뮬레이션 입력, 대)")
hrs = np.arange(6, 23)
for k, N, c, ls, lw, nm in SERIES:
    ax[1].plot(hrs, SN[k]["hour_mean"], color=c, ls=ls, lw=lw, marker="o", ms=2.3, label=nm)
ax[1].set_xlim(6, 22.5); ax[1].set_xticks(range(6, 23, 3)); ax[1].set_xticklabels([f"{h}시" for h in range(6, 23, 3)])
ax[1].set_title("② 시간대별 평균 대기(분, 11월 평일)")
h_, l_ = ax[1].get_legend_handles_labels()
fig.legend(h_, l_, loc="lower center", ncol=2, fontsize=7.8, bbox_to_anchor=(0.5, -0.12))
save(fig, "fig4_policy")

# 그림 5: 한 장 요약
H = pd.read_csv(PROC / "hour_profile.csv", index_col=0)
fig = plt.figure(figsize=(7.4, 9.6))
fig.text(0.02, 0.975, "서울 장애인콜택시 대기시간 격차 분석 요약", fontsize=15, fontweight="bold", color=INK, va="top")
fig.text(0.02, 0.948, "2025년 탑승기록 172만 건 · 특장차 즉시 호출 기준", fontsize=9, color=INK2, va="top")
O = G["overall"]; PT = G["patience"]
tiles = [(f"{O['med']:.0f}분", "승차까지 대기 중앙값"), (f"{O['over60'] * 100:.0f}%", "60분 넘게 기다린 호출"),
         (f"{O['cancel'] * 100:.0f}%", "접수 후 취소(포기)"), (f"{G['busy_max']['v']}/698", "동시 운행 최대/보유 차량")]
for i, (v, s) in enumerate(tiles):
    x0 = 0.02 + i * 0.245
    fig.patches.append(FancyBboxPatch((x0, 0.845), 0.225, 0.08, boxstyle="round,pad=0,rounding_size=0.008", transform=fig.transFigure,
                                      facecolor="#f3f6fb", edgecolor="none"))
    fig.text(x0 + 0.012, 0.905, v, fontsize=17, fontweight="bold", color=BLUE, va="top")
    fig.text(x0 + 0.012, 0.86, s, fontsize=8.2, color=INK2, va="bottom")
a1 = fig.add_axes([0.07, 0.6, 0.4, 0.2])
a1.plot(H.index, H.wait_med, color=BLUE, marker="o", ms=2.5); a1.set_title("① 시간대별 대기 중앙값(분, 평일)", fontsize=9)
a1.set_xticks(range(0, 24, 4)); a1.set_xticklabels([f"{h}시" for h in range(0, 24, 4)], fontsize=7.5); a1.tick_params(labelsize=7.5)
a2 = fig.add_axes([0.53, 0.555, 0.45, 0.235])
g = gpd.read_parquet(PROC / "dong_gap.parquet"); dg = gpd.read_parquet(PROC / "dongs.parquet")
dg.plot(ax=a2, color="#f7f7f5", lw=0); g.plot(ax=a2, color=g.hot.map({"hot": RED, "cold": BLUE, "ns": "#e6e5e1"}), lw=0.1, edgecolor="white")
dg.dissolve("sggnm").boundary.plot(ax=a2, color=INK2, lw=0.35); a2.set_axis_off()
a2.set_title("② 평균 대기 핫스팟(Gi*, p<0.05)", fontsize=9)
a2.text(0.02, 0.02, f"■ 고대기 {G['hotspot']['hot']}개 동", color=RED, transform=a2.transAxes, fontsize=7.5)
a2.text(0.35, 0.02, f"■ 저대기 {G['hotspot']['cold']}개 동", color=BLUE, transform=a2.transAxes, fontsize=7.5)
a3 = fig.add_axes([0.07, 0.33, 0.4, 0.2])
a3.plot(PT["grid"], [1 - s for s in PT["S"]], color=ORANGE); a3.set_xlim(0, 150); a3.set_ylim(0, .35)
a3.plot(60, 1 - PT["S60"], "o", color=ORANGE, ms=4); a3.text(64, 1 - PT["S60"] - .03, f"60분 → {(1 - PT['S60']) * 100:.0f}% 포기", fontsize=7.5)
a3.set_title("③ 대기 시간별 누적 포기 확률", fontsize=9); a3.tick_params(labelsize=7.5); a3.set_xlabel("대기(분)", fontsize=7.5)
a4 = fig.add_axes([0.6, 0.33, 0.36, 0.2])
order = ["S0 현행", kk("L20"), kk("L30"), kk("P2"), kk("P3"), kk("S6")]
NAMES = {"S0 현행": "현행", kk("L20"): "오후 조 20명 이동", kk("L30"): "오후 조 30명 이동", kk("P2"): "증원 25명 16∼21시",
         kk("P3"): "증원 25명 14∼19시", kk("S6"): "정점 보강 10%"}
vals = [SN[k]["mean"] for k in order]
a4.barh(range(len(order))[::-1], vals, color=[GRAY, "#9ec5f4", BLUE, "#c3c2b7", ORANGE, "#c3c2b7"], height=0.62)
for i, (k, v) in enumerate(zip(order, vals)):
    a4.text(v + 0.5, len(order) - 1 - i, f"{v:.1f}분", va="center", fontsize=7.5)
a4.set_yticks(range(len(order))[::-1]); a4.set_yticklabels([NAMES[k] for k in order], fontsize=7.5)
a4.set_xlim(0, max(vals) * 1.25); a4.tick_params(labelsize=7.5); a4.grid(axis="y", visible=False)
a4.set_title("④ 시나리오별 평균 대기(11월 평일)", fontsize=9)
fig.text(0.02, 0.25, "정책 제안", fontsize=11, fontweight="bold", color=INK)
pcg = lambda k: f"{(1 - SN[k]['mean'] / SN['S0 현행']['mean']) * 100:.0f}%"
RX = [f"① 단시간 운전원 오후 조 일부(20∼30명) 근무시간을 16∼21시에서 14∼19시로 조정: 추가 비용 없이 평균 대기 {pcg(kk('L20'))[:-1]}∼{pcg(kk('L30'))} 단축",
      f"② 증원 인력은 정점(14∼19시·07∼12시)에 배치: 25명 증원 시 16∼21시 배치 {pcg(kk('P2'))} 단축, 14∼19시 배치 {pcg(kk('P3'))} 단축",
      "③ 60분·90분 초과율, 최대 대기, 예약 정시율, 행정동 지니계수를 매월 공표",
      f"④ 바우처택시 정점 배차에 시간대별 인센티브 가산, 증원 차량부터 전기 승합 전환(전량 전환 시 −{CB['ev_cut'] / CB['base_t'] * 100:.0f}%)"]
for i, r in enumerate(RX):
    fig.text(0.03, 0.22 - i * 0.035, r, fontsize=8.6, color=INK, va="top")
fig.text(0.02, 0.06, "자료: 서울시설공단 장애인콜택시 탑승내역·차고지·차량정보(공공데이터포털), 통계청 행정동 경계, 한국에너지공단 표시연비. 응모자 분석.",
         fontsize=7, color=INK2)
save(fig, "fig5_summary")
print("ok")
