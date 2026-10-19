"""Nominatim에서 못 찾은 차고지 3곳: 지번을 법정동 단위로 낮춰 다시 찾기(동 중심 정도의 정밀도)"""
import csv, json, time, urllib.parse, urllib.request
from common import PROC
UA = {"User-Agent": "koreashe-traffic-2026 contest analysis (https://github.com/beomseokpark/koreashe-transport-data-2026)"}
ALT = {"신림공영주차장": ["서울특별시 관악구 신림동 1456-3", "서울특별시 관악구 신림동"],
       "신방화차고지": ["서울특별시 강서구 마곡동 731-123", "서울특별시 강서구 마곡동"],
       "아현역차고지": ["서울특별시 마포구 신촌로28길 29", "아현역, 서울", "서울특별시 마포구 아현동"]}
rows = list(csv.DictReader(open(PROC / "depots.csv", encoding="utf-8")))
for r in rows:
    if r["lat"] or r["차고지명"] not in ALT: continue
    for s in ALT[r["차고지명"]]:
        time.sleep(1.1)
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": s, "format": "json", "limit": 1})
        j = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))
        if j:
            r.update(lat=j[0]["lat"], lon=j[0]["lon"], geocode="대체:" + s, osm_name=j[0]["display_name"]); break
    print(r["차고지명"], r["geocode"], r["osm_name"])
with open(PROC / "depots.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
