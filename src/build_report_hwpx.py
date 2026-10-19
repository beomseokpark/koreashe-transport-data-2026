"""분석보고서(붙임2) — 원본 HWP 양식(reference/붙임2_분석보고서_양식.hwp)을 HWPX로 바꿔 표·칸·서식은 그대로 두고 오른쪽 칸만 채움
- 각 칸의 파란 작성요령(※) 문단은 지우고 그 자리에 내용(문단·칸 안 표·그림)을 넣음(사용자 결정 2026-10-19)
- 활용 데이터 칸의 원본 목록 표(머리 2행 + 빈 4행)는 같은 서식의 행을 복사해 늘린 뒤 채움
- 표 아래 '※ 분석보고서 작성 시 유의사항'(검정 글씨)과 맨 위 제목 표는 그대로 둠, 표지 없음
출력: output/박범석_분석보고서.hwpx (한글에서 열어 PDF로 저장)"""
import copy, sys
from hwpx.hwp5.package import convert, to_hwpx_bytes
from hwpx import HwpxDocument
from hwpx.layout.pages import estimate_pages
from formfill import CellWriter, HP
import report_content as RC
from common import ROOT, OUT

ROW = dict(name=0, topic=1, background=2, data=3, method=4, ai=5, results=6, policy=7, refs=8, images=9)

def strip_lineseg(el):
    for ls in list(el.iter(HP + "linesegarray")):
        ls.getparent().remove(ls)

def fill_list_table(t, rows, cpr):
    """원본 목록 표: 머리 2행 아래 빈 행에 채우고, 모자라면 첫 데이터 행을 복사해 늘림.
    원본 빈 칸에 숨어 있던 글자 서식(회색 기울임·이중 취소선) 대신 검정 함초롬돋움(cpr)으로 씀"""
    tbl = t.element
    trs = tbl.findall(HP + "tr")
    need = 2 + len(rows) - len(trs)
    last = trs[-1]
    tmpl = trs[2]   # 첫 데이터 행: 원본 마지막 빈 행에는 보이지 않는 이중 취소선 서식(charPr 32)이 있어 복사·사용하지 않음
    for _ in range(max(need, 0)):
        new = copy.deepcopy(tmpl)
        r = len(tbl.findall(HP + "tr"))
        for tc in new.findall(HP + "tc"):
            tc.find(HP + "cellAddr").set("rowAddr", str(r))
        tbl.insert(list(tbl).index(last) + 1, new)
        last = new
    tbl.set("rowCnt", str(len(tbl.findall(HP + "tr"))))
    for i, vals in enumerate(rows):
        tr = tbl.findall(HP + "tr")[2 + i]
        for tc, v in zip(tr.findall(HP + "tc"), vals):
            ps = tc.find(HP + "subList").findall(HP + "p")
            for p in ps[1:]:
                p.getparent().remove(p)
            p = ps[0]; strip_lineseg(p)
            runs = p.findall(HP + "run")
            run = runs[0]
            for r_ in runs[1:]:
                p.remove(r_)
            ts = run.findall(HP + "t")
            for t_ in ts[1:]:
                run.remove(t_)
            run.set("charPrIDRef", str(cpr))
            if ts:
                ts[0].text = v
            else:
                import lxml.etree as LET
                LET.SubElement(run, HP + "t").text = v

def build():
    src = ROOT / "reference/붙임2_분석보고서_양식.hwp"
    doc = HwpxDocument.open(to_hwpx_bytes(convert(src.read_bytes()).files))
    main = doc.paragraphs[1].tables[0]
    w = CellWriter(doc, base=10, small=8, line=140, cell_w_mm=121)
    for key, r in ROW.items():
        cell = main.cell(r, 1)
        old = [p for p in cell.paragraphs if not (key == "data" and p.tables)]
        keep = next((p for p in cell.paragraphs if p.tables), None) if key == "data" else None
        if key == "data":
            w.render(cell, RC.DATA_HEAD)
            sub = keep.element.getparent()
            sub.remove(keep.element); sub.append(keep.element)          # 목록 표를 머리 블록 뒤로
            fill_list_table(keep.tables[0], RC.DATA_ROWS, w.cp(w.hf, 8.5))
            w.render(cell, RC.DATA_TAIL)
        else:
            w.render(cell, RC.CELLS[key])
        for p in old:                      # 파란 작성요령 문단 삭제(새 내용을 넣은 뒤)
            p.remove()
        strip_lineseg(cell.element)
    out = OUT / f"{RC.A['name']}_분석보고서.hwpx"
    doc.save_to_path(str(out))
    return out

if __name__ == "__main__":
    out = build()
    est = estimate_pages(HwpxDocument.open(str(out)))
    print(out, "추정 쪽수", est.pages)
