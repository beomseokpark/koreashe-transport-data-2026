"""차고지 44곳 좌표: OSM Nominatim(1초 간격, 사용 정책 준수). 실패하면 '서울 + 차고지명' 검색.
usage: geocode_depots.py  →  data/processed/depots.csv"""
import csv, json, time, urllib.parse, urllib.request
from pathlib import Path
R = Path(__file__).resolve().parents[1] / "data"
UA = {"User-Agent": "koreashe-traffic-2026 contest analysis (https://github.com/beomseokpark/koreashe-transport-data-2026)"}
def q(s):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": s, "format": "json", "limit": 1, "countrycodes": "kr"})
    time.sleep(1.1)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        j = json.load(r)
    return (float(j[0]["lat"]), float(j[0]["lon"]), j[0]["display_name"]) if j else None
rows = list(csv.DictReader(open(next((R / "raw").glob("15144781_*.csv")), encoding="utf-8-sig")))
out = []
for r in rows:
    res, how = None, ""
    for s, h in [("서울특별시 " + r["상세주소"], "주소"), ("서울 " + r["차고지명"], "명칭")]:
        try:
            res = q(s)
        except Exception as e:
            print("err", s, e)
        if res: how = h; break
    print(r["차고지명"], how, res)
    out.append({**r, "lat": res[0] if res else "", "lon": res[1] if res else "", "geocode": how, "osm_name": res[2] if res else ""})
with open(R / "processed" / "depots.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
