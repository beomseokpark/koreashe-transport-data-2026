"""참가신청서(붙임1) PDF — 양식 문구를 그대로 옮겨 조판, 이름·소속·지원형태를 미리 채움(서명·날짜·연락처는 응모자)
usage: build_forms.py → output/박범석_참가신청서.pdf"""
import asyncio, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "ops/templates/hwp-report"))
from hwp_report import FONTS
from common import ROOT, OUT

A = json.load(open(ROOT / "applicant.json", encoding="utf-8"))
txt = (ROOT / "reference/붙임1_참가신청서.txt").read_text(encoding="utf-8")
def between(a, b):
    i = txt.index(a) + len(a); j = txt.index(b, i); return txt[i:j].strip()
privacy = between("[개인정보 수집·이용]", "개인정보 수집·이용에 동의하십니까?")
rules = between("[공모전 규정 및 준수사항]", "[데이터 수집·활용 및 분석 시 준수사항]")
datarules = between("[데이터 수집·활용 및 분석 시 준수사항]", "위 [공모전 규정 및 준수사항]과")
pledge = between("[서약 및 서명]", "2026년")

def paras(s):
    out = []
    for line in s.splitlines():
        line = line.strip()
        if not line: continue
        cls = "h" if line.startswith("○") else ("i" if re.match(r"^(\d+\.|-)", line) else "")
        out.append(f'<p class="{cls}">{line}</p>')
    return "".join(out)

CHK, BOX = "■", "□"
ph = lambda v: f'<span class="ph">{v}</span>' if v.startswith("[") else v
html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{FONTS}
@page {{ size:210mm 297mm; margin:15mm 16mm 14mm; }}
html {{ font-family:'HB'; font-size:9.6pt; line-height:1.5; letter-spacing:-0.02em; word-break:keep-all; }}
body {{ margin:0; }} p {{ margin:0 0 0.8mm; text-align:justify; }}
.top {{ text-align:center; font-family:'HDo'; font-size:10.5pt; }}
h1 {{ text-align:center; font-family:'HL'; font-weight:800; font-size:20pt; letter-spacing:.5em; margin:1mm 0 5mm; }}
h2 {{ font-family:'HL'; font-weight:800; font-size:11.5pt; margin:4mm 0 1.6mm; }}
table {{ border-collapse:collapse; width:100%; font-family:'HDo'; font-size:10pt; border:1pt solid #000; }}
th, td {{ border:0.5pt solid #000; padding:1.8mm 2mm; text-align:center; }}
th {{ background:#dae3f3; font-weight:700; }}
.box {{ border:0.6pt solid #000; padding:2.2mm 3mm; font-size:8.9pt; line-height:1.45; }}
.box p.h {{ font-weight:700; margin-top:1.2mm; }} .box p.i {{ padding-left:3mm; text-indent:-3mm; }}
.q {{ text-align:right; font-family:'HDo'; font-weight:700; margin:1.4mm 0 0; font-size:10pt; }}
.sign {{ margin-top:5mm; font-family:'HDo'; font-size:10.5pt; }}
.sign .d {{ text-align:center; margin:3mm 0 4mm; letter-spacing:.1em; }}
.sign table td {{ height:11mm; }}
.ph {{ color:#c00000; }}
.pb {{ break-before:page; }}
</style></head><body>
<div class="top">- AI와 함께하는 교통문제 해결을 위한 데이터 분석 공모전 -</div>
<h1>참가신청서</h1>
<h2>[참가자 정보]</h2>
<table><colgroup><col style="width:22%"><col style="width:20%"><col style="width:20%"><col style="width:20%"><col style="width:18%"></colgroup>
<tr><th>지원형태</th><td colspan="4" style="text-align:left">{CHK} 개인 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {BOX} 팀</td></tr>
<tr><th>신청자명<br><span style="font-weight:400;font-size:8.5pt">※ 팀일 경우 팀명 기재</span></th><td colspan="4" style="text-align:left">{A['name']}</td></tr>
<tr><th>구분</th><th>이름</th><th>소속</th><th>이메일</th><th>연락처</th></tr>
<tr><th>대 표</th><td>{A['name']}</td><td>{A['affiliation']}</td><td style="font-size:8.6pt">{ph(A['email'])}</td><td style="font-size:8.6pt">{ph(A['phone'])}</td></tr>
<tr><th>팀원1</th><td></td><td></td><td></td><td></td></tr>
<tr><th>팀원2</th><td></td><td></td><td></td><td></td></tr></table>
<h2>[개인정보 수집·이용]</h2>
<div class="box">{paras(privacy)}</div>
<div class="q">개인정보 수집·이용에 동의하십니까? &nbsp;&nbsp; {CHK} 동의함 &nbsp;&nbsp; {BOX} 동의하지 않음</div>
<h2 class="pb">[공모전 규정 및 준수사항]</h2>
<div class="box">{paras(rules)}</div>
<h2>[데이터 수집·활용 및 분석 시 준수사항]</h2>
<div class="box">{paras(datarules)}</div>
<p style="margin-top:2mm;font-family:'HDo';font-weight:700">위 [공모전 규정 및 준수사항]과 [데이터 수집·활용 및 분석 시 준수사항]을 확인하였으며 이를 준수할 것을 서약하십니까?</p>
<div class="q">{CHK} 동의함 &nbsp;&nbsp; {BOX} 동의하지 않음</div>
<h2>[서약 및 서명]</h2>
<p>{pledge}</p>
<div class="sign"><div class="d">2026년 &nbsp;&nbsp;&nbsp;&nbsp; 월 &nbsp;&nbsp;&nbsp;&nbsp; 일</div>
<table><colgroup><col style="width:22%"><col style="width:33%"><col style="width:12%"><col style="width:33%"></colgroup>
<tr><th>이름(대 표)</th><td>{A['name']}</td><th>서명</th><td></td></tr>
<tr><th>이름(팀원1)</th><td></td><th>서명</th><td></td></tr>
<tr><th>이름(팀원2)</th><td></td><th>서명</th><td></td></tr></table></div>
</body></html>"""

async def main():
    from playwright.async_api import async_playwright
    p = OUT / "참가신청서.html"; p.write_text(html, encoding="utf-8")
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); pg = await b.new_page()
        await pg.goto(p.as_uri(), wait_until="networkidle"); await pg.wait_for_timeout(500)
        await pg.pdf(path=str(OUT / f"{A['name']}_참가신청서.pdf"), prefer_css_page_size=True, print_background=True); await b.close()
asyncio.run(main()); print("ok")
