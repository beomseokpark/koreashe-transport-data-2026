"""원자료 다시 내려받기 (data/raw/). 공공데이터포털 파일은 Playwright로 상세페이지 '다운로드' 버튼을 누름(dgdown.py)
usage: p0_fetch.py   (실행 후 p1_prepare.py부터 README 순서대로)"""
import subprocess, sys, urllib.request
from common import RAW, ROOT
PY = sys.executable
PKS = ["15115859", "15147613", "15147614", "15144781", "15160788", "15066774", "15083023"]
subprocess.run([PY, str(ROOT / "src/dgdown.py"), str(RAW), *PKS], check=True)
subprocess.run([PY, str(ROOT / "src/seoul_stat_down.py"),
                "https://stat.eseoul.go.kr/statHtml/statHtml.do?orgId=201&tblId=DT_201004_F040005&conn_path=I2",
                str(RAW / "seoul_disabled_by_gu_2025.csv")], check=True)
url = "https://raw.githubusercontent.com/vuski/admdongkor/master/ver20260701/HangJeongDong_ver20260701.geojson"
urllib.request.urlretrieve(url, RAW / "HangJeongDong_ver20260701.geojson")
print("done → 다음: geocode_depots.py, geocode_fix.py (차고지 좌표, Nominatim) 또는 data/processed/depots.csv 사용")
