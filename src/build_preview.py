"""미리보기 PDF(근사): 원본 양식 모양(여백 30·20·15㎜, 항목 칸 22㎜ 회색, 내용 칸 128㎜)을 HTML로 흉내 내 같은 원고(report_content)를 조판
한글과 줄바꿈·쪽 나눔이 조금 다를 수 있음. 출력: output/미리보기_분석보고서.pdf"""
import asyncio, html, re, sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "ops/templates/hwp-report"))
from hwp_report import FONTS
from hwpx_report import hwpify
import report_content as RC
from common import ROOT, OUT

LOGO = ROOT / "forms/x2/BinData/image1.png"
fno = [0]; tno = [0]

def mk(t):
    t = hwpify(t)
    t = re.sub(r"<x>(.*?)</x>", r'<span style="color:#2F5BB7">\1</span>', t)
    return re.sub(r"<r>(.*?)</r>", r'<span style="color:#C00000">\1</span>', t)

def block(b):
    k = b[0]
    if k == "sq": return f'<p class="sq">□ <b>{mk(b[1])}</b></p>'
    if k == "o": return f'<p class="o">○ {"<b>(" + b[2] + ")</b> " if len(b) > 2 and b[2] else ""}{mk(b[1])}</p>'
    if k == "d": return f'<p class="d">- {mk(b[1])}</p>'
    if k == "nk": return f'<p class="nk">※ {mk(b[1])}</p>'
    if k == "p": return f'<p class="pp">{mk(b[1])}</p>'
    if k == "box": return '<div class="box">' + "".join(f"<p>{mk(x)}</p>" for x in b[1]) + "</div>"
    if k == "refs": return '<ol class="refs">' + "".join(f"<li>{mk(x)}</li>" for x in b[1]) + "</ol>"
    if k == "fig":
        fno[0] += 1
        return (f'<div class="fig"><img src="{Path(b[1]).as_uri()}" style="width:{b[4] if len(b) > 4 and b[4] else 120}mm"><div class="fc">[그림 {fno[0]}] {mk(b[2])}</div>'
                + (f'<div class="fs">자료: {mk(b[3])}</div>' if len(b) > 3 and b[3] else "") + "</div>")
    if k == "tab":
        _, title, head, rows, opt = b
        tno[0] += 1
        ws = opt.get("widths"); al = opt.get("aligns") or ["CENTER"] * len(head); rh = opt.get("rh", True); hl = set(opt.get("hl_rows", ()))
        cg = "".join(f'<col style="width:{w / sum(ws) * 100:.1f}%">' for w in ws) if ws else ""
        th = "".join(f"<th>{mk(h)}</th>" for h in head)
        trs = ""
        for i, r in enumerate(rows):
            tds = ""
            for c, v in enumerate(r):
                cls = ("rh " if (rh and c == 0) else "") + ("hl " if i in hl else "") + ("l" if al[c] == "LEFT" else "")
                tds += f'<td class="{cls}">{mk(str(v))}</td>'
            trs += f"<tr>{tds}</tr>"
        unit = f' (단위: {opt["unit"]})' if opt.get("unit") else ""
        cap = f'<div class="tc">【표 {tno[0]}】 {mk(title)}{unit}</div>' if title else ""
        src = f'<p class="ts">* {mk(opt["src"])}</p>' if opt.get("src") else ""
        return f'<div class="tblk">{cap}<table class="in" style="font-size:{opt.get("size", 8)}pt"><colgroup>{cg}</colgroup><tr>{th}</tr>{trs}</table></div>{src}'
    raise ValueError(k)

def cell(blocks): return "".join(block(b) for b in blocks)

def data_cell():
    rows = "".join("<tr>" + "".join(f'<td class="dl">{html.escape(v)}</td>' for v in r) + "</tr>" for r in RC.DATA_ROWS)
    t = ('<table class="dt"><colgroup><col style="width:26%"><col style="width:21%"><col style="width:18%"><col style="width:35%"></colgroup>'
         '<tr><th rowspan="2">활용 데이터(명)</th><th rowspan="2">제공기관(명)</th><th colspan="2">출처</th></tr><tr><th>플랫폼(명)</th><th>URL</th></tr>' + rows + "</table>")
    return cell(RC.DATA_HEAD) + t + cell(RC.DATA_TAIL)

LABELS = [("이름/팀명", "name"), ("주제", "topic"), ("분석 배경 및 목적", "background"), ("활용 데이터", "data"), ("분석과정 및 방법", "method"),
          ("AI 기술 활용", "ai"), ("분석 내용 및 결과", "results"), ("정책제안<br>및 기대효과", "policy"), ("분석도구 및 참고문헌", "refs"), ("분석결과 이미지<br>(필수)", "images")]
NOTE = """<p class="nt">※ 분석보고서 작성 시 유의사항</p><p class="nt">- 본문 5장 내외로 작성(표지, 참고문헌 제외)하되, 위 필수항목은 분석보고서에 반드시 명시하여 작성</p>
<p class="nt">- 제시한 항목 외 추가 내용이 있을 경우 별도 제목을 기재하여 작성</p><p class="nt">- 분석 결과 이미지(시각화, 인포그래픽 등)는 문서 내 포함 필수</p>
<p class="nt">- 프로그래밍 언어를 이용한 분석 사례의 경우, 분석 코드를 Github/클라우드 링크를 분석보고서에 기재, 결선 진출 시 실행 가능한 전체 코드를 별도 안내에 따라 제출하며, 결선 발표 평가 시 코드 실행을 확인함.</p>
<p class="nt">- 제출 형식 : PDF / 파일명: 팀명(또는 이름)_분석보고서.pdf / 이메일 접수: yaerumjung@koreashe.org</p>"""

CSS = """
@page { size:210mm 297mm; margin:35mm 30mm 30mm 30mm; }   /* 한글: 위 20+머리말 15, 아래 15+꼬리말 15 */
body { font-family:'HB'; font-size:10pt; line-height:1.4; color:#000; margin:0; }
.title { width:150mm; border:none; margin-bottom:2mm; position:relative; } .title .a { font-family:'HL'; font-weight:700; font-size:13pt; text-align:center; margin-top:12mm; }
.title .b { font-family:'HL'; font-weight:700; font-size:16pt; text-align:center; margin:1mm 0 4mm; } .title img { position:absolute; right:0; top:0; width:45mm; }
table.main { width:150mm; border-collapse:collapse; table-layout:fixed; } table.main > tbody > tr > td { border:0.12mm solid #000; padding:0.5mm 1.8mm; vertical-align:middle; }
table.main td.lab { width:22mm; background:#F2F2F2; text-align:center; font-family:'HL'; font-size:11pt; line-height:1.6; }
table.main tr { break-inside:auto; }
p { margin:0; text-align:justify; } .pp { margin:0.5mm 0; }
.sq { font-family:'HDo'; font-size:11pt; margin:2.4mm 0 0.8mm; padding-left:4.5mm; text-indent:-4.5mm; break-after:avoid; }
.o { padding-left:7mm; text-indent:-3.8mm; margin:0.4mm 0 0.6mm; } .d { padding-left:10mm; text-indent:-2.6mm; }
.nk { font-family:'HDo'; font-size:8pt; padding-left:7mm; text-indent:-3.4mm; line-height:1.4; margin:0.5mm 0; }
.tc { font-family:'HDo'; font-weight:700; font-size:9.5pt; text-align:center; margin:1.6mm 0 0.4mm; break-after:avoid; } .tu { font-family:'HDo'; font-size:8pt; text-align:right; }
table.in, table.dt { width:100%; border-collapse:collapse; font-family:'HDo'; line-height:1.15; margin:0.5mm 0; } table.in td, table.in th, table.dt td, table.dt th { border:0.12mm solid #000; padding:0.5mm 0.8mm; text-align:center; }
table.in th, table.dt th { background:#DAE3F3; font-weight:700; } td.l { text-align:left !important; } td.rh { background:#FFF2CC; font-weight:700; } td.hl { background:#EAF1FB; font-weight:700; }
table.dt { font-size:8pt; break-inside:avoid; } td.dl { text-align:left !important; word-break:break-all; }
.tblk { break-inside:avoid; } .ts { font-family:'HDo'; font-size:8pt; line-height:1.3; margin:0.4mm 0 1.2mm; }
.fig { text-align:center; margin:1.6mm 0 1.2mm; break-inside:avoid; } .fig img { display:block; margin:0 auto; } .fc { font-family:'HDo'; font-weight:700; font-size:9.5pt; margin-top:0.6mm; } .fs { font-family:'HDo'; font-size:8pt; }
.box { break-inside:avoid; border:0.12mm solid #8AA4D6; background:#F4F4F2; padding:0.8mm 2mm; margin:0.6mm 0 1mm 3mm; font-family:'HDo'; font-size:8pt; line-height:1.35; } .box p { padding-left:3.5mm; text-indent:-3.5mm; }
.r.fs { font-family:'HDo'; font-size:8.2pt; line-height:1.3; padding-left:5mm; margin:0.5mm 0; } .refs li { margin-bottom:0.3mm; }
.nt { font-family:'HL'; font-size:11pt; line-height:1.6; margin-top:0.5mm; }
"""

def build():
    rows = "".join(f'<tr><td class="lab">{lab}</td><td>{data_cell() if key == "data" else cell(RC.CELLS[key])}</td></tr>' for lab, key in LABELS)
    body = (f'<div class="title"><img src="{LOGO.as_uri()}"><div class="a">- AI와 함께하는 교통문제 해결을 위한 데이터 분석 공모전 -</div><div class="b">분석보고서</div></div>'
            f'<table class="main"><tbody>{rows}</tbody></table><br>{NOTE}')
    return f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><style>{FONTS}{CSS}</style></head><body>{body}</body></html>"

async def pdf(html_, out):
    from playwright.async_api import async_playwright
    p = Path(out).with_suffix(".html"); p.write_text(html_, encoding="utf-8")
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); pg = await b.new_page()
        await pg.goto(p.as_uri(), wait_until="networkidle"); await pg.wait_for_timeout(600)
        await pg.pdf(path=str(out), prefer_css_page_size=True, print_background=True); await b.close()

if __name__ == "__main__":
    out = OUT / "미리보기_분석보고서.pdf"
    asyncio.run(pdf(build(), out))
    import subprocess
    print(out, subprocess.run(["pdfinfo", str(out)], capture_output=True, text=True).stdout.split("Pages:")[1].split()[0], "쪽")
    for i in range(1, 12):
        t = subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), str(out), "-"], capture_output=True, text=True).stdout
        if "분석도구 및 참고문헌" in t.replace("\n", " ") or "Akcicek" in t: print("참고문헌 칸 시작 쪽:", i); break
