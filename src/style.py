"""그림 공통 스타일: 맑은 고딕 대용 Noto Sans CJK KR, 얇은 선·옅은 격자, 검증된 3색(파랑·주황·청록)"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
BLUE, ORANGE, AQUA, GRAY, INK, INK2, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#9a9993", "#0b0b0b", "#52514e", "#e6e5e1"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
RED = "#e34948"
plt.rcParams.update({
    "font.family": ["Noto Sans CJK KR", "DejaVu Sans"], "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.labelsize": 9, "axes.edgecolor": GRAY, "axes.linewidth": 0.6, "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "legend.fontsize": 8.5, "figure.dpi": 110, "savefig.dpi": 220, "savefig.bbox": "tight", "axes.axisbelow": True,
    "axes.unicode_minus": False, "lines.linewidth": 2, "axes.titlelocation": "left"})
def save(fig, name):
    from common import FIG
    fig.savefig(FIG / f"{name}.png", facecolor="white"); plt.close(fig)
