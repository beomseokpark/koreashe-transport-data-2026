"""보고서 그림(시뮬레이터 v2·통합안): fig2_package(통합안 시간대별 대기 + 수단별 1건당 CO₂), fig5_summary(한 장 요약)"""
import json, numpy as np, pandas as pd, geopandas as gpd
from matplotlib.patches import FancyBboxPatch
from style import *
from common import PROC

F = json.load(open(PROC / "final.json")); PK = json.load(open(PROC / "package.json")); LM = json.load(open(PROC / "lastmile.json"))
G = json.load(open(PROC / "gap.json")); CB = json.load(open(PROC / "carbon.json"))
N = F["nov"]; P = PK["nov"]
k0, kP, kR = "S0 현행", "PKG 통합안", "PKG+R1 도심·동남권 오후 택시 우선 20%"
P2 = "P2 증원 25명 16∼21시"
hrs = np.arange(6, 23)
CO2 = LM["carbon"]["per_trip_kg"]
CO2_LAB = {"특장차(현행 차량 구성, 빈 차 포함)": "특장차(현행 LPG·경유 등)", "가족 차량 동행(휘발유, 왕복)": "가족 차량 동행(왕복)",
           "바우처 일반택시(LPG)": "바우처 일반택시(LPG)", "지하철+양끝 택시(LPG, 각 1㎞)": "지하철+양끝 택시", "특장차 전기 승합": "특장차 전기 승합",
           "바우처 일반택시(전기)": "바우처 일반택시(전기)"}

# 그림 2: ① 시간대별 평균 대기(현행·증원 16~21시·통합안) ② 수단별 1건당 CO2
fig, ax = plt.subplots(1, 2, figsize=(8.6, 3.0), gridspec_kw=dict(wspace=0.55, width_ratios=[1.25, 1]))
for k, c, ls, lw, nm in [(None, GRAY, "-", 2.6, "현행"), ("P2", AQUA, "--", 1.6, "증원 25명 16∼21시(현행 방식)"), ("PKG", BLUE, "-", 2.0, "통합안")]:
    y = N[k0]["hour_mean"] if k is None else (P[P2]["hour_mean"] if k == "P2" else N[kP]["hour_mean"])
    ax[0].plot(hrs, y, color=c, ls=ls, lw=lw, marker="o", ms=2.3, label=nm)
for a_, b_, t_ in ((6.5, 9.5, "오전"), (13.5, 17.5, "오후"), (19.5, 21.5, "저녁")):
    ax[0].axvspan(a_, b_, color=ORANGE, alpha=.07, lw=0); ax[0].text((a_ + b_) / 2, 68, t_, ha="center", fontsize=7.5, color=INK2)
ax[0].set_xlim(6, 22.5); ax[0].set_ylim(15, 72); ax[0].set_xticks(range(6, 23, 3)); ax[0].set_xticklabels([f"{h}시" for h in range(6, 23, 3)])
ax[0].set_title("① 시간대별 평균 대기(분, 11월 평일)"); ax[0].legend(loc="lower left", fontsize=7.3, ncol=1, bbox_to_anchor=(0, -0.02))
order = sorted(CO2, key=lambda k: -CO2[k])
cols = [ORANGE if "특장차(" in k else (BLUE if ("지하철" in k or "전기" in k) else "#9ec5f4" if "택시" in k else GRAY) for k in order]
ax[1].barh(range(len(order))[::-1], [CO2[k] for k in order], color=cols, height=0.62)
for i, k in enumerate(order):
    ax[1].text(CO2[k] + 0.05, len(order) - 1 - i, f"{CO2[k]:.1f}", va="center", fontsize=7.5)
ax[1].set_yticks(range(len(order))[::-1]); ax[1].set_yticklabels([CO2_LAB[k] for k in order], fontsize=7.5)
ax[1].set_xlim(0, max(CO2.values()) * 1.2); ax[1].grid(axis="y", visible=False)
ax[1].set_title("② 수단별 1건당 CO₂(kg)")
save(fig, "fig2_package")

# 그림 3(분석결과 이미지): 한 장 요약
H = pd.read_csv(PROC / "hour_profile.csv", index_col=0)
fig = plt.figure(figsize=(7.4, 9.4))
fig.text(0.02, 0.975, "서울 장애인콜택시 대기시간 격차 분석 요약", fontsize=15, fontweight="bold", color=INK, va="top")
fig.text(0.02, 0.948, "2025년 탑승기록 172만 건 · 특장차 즉시 호출 · 시뮬레이션은 2025년 11월 평일", fontsize=9, color=INK2, va="top")
O = G["overall"]
tiles = [(f"{O['med']:.0f}분", "승차까지 대기 중앙값"), (f"{O['over60'] * 100:.0f}%", "60분 넘게 기다린 호출"),
         (f"{G['busy_max']['v']}/698", "동시 운행 최대/보유 차량"), (f"−{(1 - N[kP]['mean'] / N[k0]['mean']) * 100:.0f}%", "통합안 평균 대기 변화")]
for i, (v, s) in enumerate(tiles):
    x0 = 0.02 + i * 0.245
    fig.patches.append(FancyBboxPatch((x0, 0.845), 0.225, 0.08, boxstyle="round,pad=0,rounding_size=0.008", transform=fig.transFigure, facecolor="#f3f6fb", edgecolor="none"))
    fig.text(x0 + 0.012, 0.905, v, fontsize=17, fontweight="bold", color=BLUE if i < 3 else ORANGE, va="top")
    fig.text(x0 + 0.012, 0.86, s, fontsize=8.2, color=INK2, va="bottom")
a1 = fig.add_axes([0.07, 0.6, 0.4, 0.2])
a1.plot(H.index, H.wait_med, color=BLUE, marker="o", ms=2.5); a1.set_title("① 시간대별 대기 중앙값(분, 평일)", fontsize=9)
for a_, b_ in ((6.5, 8.5), (13.5, 16.5)): a1.axvspan(a_, b_, color=ORANGE, alpha=.08, lw=0)
a1.set_xticks(range(0, 24, 4)); a1.set_xticklabels([f"{h}시" for h in range(0, 24, 4)], fontsize=7.5); a1.tick_params(labelsize=7.5)
a2 = fig.add_axes([0.53, 0.555, 0.45, 0.235])
g = gpd.read_parquet(PROC / "dong_gap.parquet"); dg = gpd.read_parquet(PROC / "dongs.parquet")
dg.plot(ax=a2, color="#f7f7f5", lw=0); g.plot(ax=a2, color=g.hot.map({"hot": RED, "cold": BLUE, "ns": "#e6e5e1"}), lw=0.1, edgecolor="white")
dg.dissolve("sggnm").boundary.plot(ax=a2, color=INK2, lw=0.35); a2.set_axis_off()
a2.set_title("② 평균 대기 핫스팟(Gi*, p<0.05)", fontsize=9)
a2.text(0.02, 0.02, f"■ 고대기 {G['hotspot']['hot']}개 동", color=RED, transform=a2.transAxes, fontsize=7.5)
a2.text(0.35, 0.02, f"■ 저대기 {G['hotspot']['cold']}개 동", color=BLUE, transform=a2.transAxes, fontsize=7.5)
a3 = fig.add_axes([0.26, 0.33, 0.25, 0.2])
bars = [("현행", N[k0]["mean"], GRAY), ("증원 25명 16∼21시", P[P2]["mean"], "#c3c2b7"), ("균등 증차 10%", P["S4 균등 증차 10%"]["mean"], "#c3c2b7"),
        ("통합안", N[kP]["mean"], BLUE), ("통합안+지역 택시 우선", N[kR]["mean"], ORANGE)]
a3.barh(range(len(bars))[::-1], [b[1] for b in bars], color=[b[2] for b in bars], height=0.62)
for i, b in enumerate(bars): a3.text(b[1] + 0.5, len(bars) - 1 - i, f"{b[1]:.1f}분", va="center", fontsize=7.3)
a3.set_yticks(range(len(bars))[::-1]); a3.set_yticklabels([b[0] for b in bars], fontsize=7.3); a3.set_xlim(0, 60); a3.tick_params(labelsize=7.3); a3.grid(axis="y", visible=False)
a3.set_title("③ 시나리오별 평균 대기", fontsize=9)
a4 = fig.add_axes([0.76, 0.33, 0.21, 0.2])
order2 = sorted(CO2, key=lambda k: -CO2[k])
a4.barh(range(len(order2))[::-1], [CO2[k] for k in order2], color=[ORANGE if "특장차(" in k else (BLUE if ("지하철" in k or "전기" in k) else "#9ec5f4" if "택시" in k else GRAY) for k in order2], height=0.62)
a4.set_yticks(range(len(order2))[::-1]); a4.set_yticklabels([CO2_LAB[k] for k in order2], fontsize=7); a4.tick_params(labelsize=7); a4.grid(axis="y", visible=False)
for i, k in enumerate(order2): a4.text(CO2[k] + 0.05, len(order2) - 1 - i, f"{CO2[k]:.1f}", va="center", fontsize=7)
a4.set_xlim(0, max(CO2.values()) * 1.3); a4.set_title("④ 수단별 1건당 CO₂(kg)", fontsize=9)
fig.text(0.02, 0.25, "정책 제안", fontsize=11, fontweight="bold", color=INK)
RX = ["① 근무시간대 통합안: 오후 단시간 조 15명 14∼19시 이동 + 증원 25명 오후·저녁 배치 + 아침 정점 택시 분담",
      "② 휠체어 이용자는 특장차 우선, 비휠체어는 앱 즉시 호출 택시(일반 요금 표시·사후 정산, 미배차 시 특장차 대체)",
      "③ 휠체어 탑승 택시 확충: 법인특장·대형 가맹택시 개조비 보조, 휠체어 승하차 수당, 단체 배상책임보험·교육",
      "④ 보호자 대신 활동지원사·동행매니저 동승 인정, 발달장애인 같은 기사 배정, 탑승·도착 실시간 알림",
      "⑤ 10.5㎞ 넘는 장거리는 지하철+양끝 택시, 도심·동남권 오후 택시 우선, 장시간 대기 지표 공표, 전기 승합"]
for i, r in enumerate(RX):
    fig.text(0.03, 0.22 - i * 0.033, r, fontsize=8.3, color=INK, va="top")
fig.text(0.02, 0.04, "자료: 서울시설공단 장애인콜택시 탑승내역·차고지·차량정보(공공데이터포털), 통계청 행정동 경계, 한국에너지공단 표시연비, OpenStreetMap 역 위치. 응모자 분석.",
         fontsize=6.8, color=INK2)
save(fig, "fig5_summary")
print("ok")
