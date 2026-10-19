"""공통 경로·상수"""
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, FIG, OUT = ROOT / "data/raw", ROOT / "data/processed", ROOT / "figures", ROOT / "output"
for p in (PROC, FIG, OUT):
    p.mkdir(parents=True, exist_ok=True)
TRIPS = next(RAW.glob("15115859_*.csv"))
GEO = RAW / "HangJeongDong_ver20260701.geojson"

def norm_dong(s: str) -> str:
    """가운뎃점 통일, 공백 제거"""
    return str(s).strip().replace(" ", "").replace(".", "·").replace("ㆍ", "·")

def dong_variants(s: str):
    """'수유제2동'↔'수유2동' 두 표기를 모두 시도"""
    s = norm_dong(s)
    return [s, re.sub(r"제(\d)", r"\1", s), re.sub(r"(?<!제)(\d)", r"제\1", s, count=1)]

def dong_base(s: str) -> str:
    """'신당제6동'→'신당', '공릉1·3동'→'공릉' (옛 동 이름을 현행 동들로 묶을 때)"""
    s = norm_dong(s)
    s = re.sub(r"(제)?[\d·]+(가)?동$", "", s)
    return re.sub(r"(본)?동$", "", s)
