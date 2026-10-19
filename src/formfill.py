"""원본 HWPX 양식의 표 칸에 블록(문단·표·그림)을 채우는 도구 — 표·칸·테두리·문단 서식은 건드리지 않음
블록: ("sq", 글) □ 소제목 / ("o", 글, 키) ○ / ("d", 글) - / ("nk", 글) ※ 작은 글 / ("p", 글, dict) 일반 문단
      ("tab", 제목, 머리, 행들, dict(widths, aligns, rh, src, unit, size)) 칸 안 표 / ("fig", 경로, 제목, 자료, 폭mm)
      ("box", [줄들]) 회색 상자(프롬프트) / ("refs", [항목]) 번호 목록
글 안에서 <b>굵게</b>, <u>밑줄</u>, <x>파랑</x>, <r>빨강</r>"""
import re, sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path.home() / "ops/templates/hwp-report"))
from hwpx_report import hwpify, HEAD_FILL, ROW_FILL, BLUE, RED
from hwpx._document.media import add_image

HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
MM = 7200 / 25.4


class CellWriter:
    def __init__(self, doc, body="함초롬바탕", head="함초롬돋움", base=10, small=8.5, line=150, cell_w_mm=122):
        self.doc, self.bf, self.hf, self.base, self.small, self.line, self.w = doc, body, head, base, small, line, cell_w_mm
        hdr = doc.parts.headers[0]
        for f in (body, head):
            hdr.ensure_font(f, font_type="TTF")
        self._cp, self._pp = {}, {}
        self.fno = self.tno = 0
        self.cell = None

    # 서식
    def cp(self, font=None, size=None, bold=False, color=None, underline=False):
        k = (font or self.bf, size or self.base, bold, color, underline)
        if k not in self._cp:
            self._cp[k] = self.doc.ensure_run_style(font=k[0], size=k[1], bold=bold, color=color or "#000000", underline=underline)
        return self._cp[k]

    def pp(self, key, fmt):
        if key not in self._pp:
            p = self.doc.add_paragraph("", include_run=False, inherit_style=False)
            i = len(self.doc.paragraphs) - 1
            self.doc.set_paragraph_format(paragraph_index=i, **fmt)
            self._pp[key] = self.doc.paragraphs[i].para_pr_id_ref
            self.doc.remove_paragraph(self.doc.paragraphs[i])
        return self._pp[key]

    def fmt(self, left=0, first=0, before=0, after=2, align="JUSTIFY", line=None, keep=False):
        return dict(alignment=align, line_spacing_percent=line or self.line, indent_left_mm=left, first_line_indent_mm=first,
                    spacing_before_pt=before, spacing_after_pt=after, keep_with_next=keep or None)

    def segs(self, text, font=None, size=None, bold=False, color=None):
        out = []
        for part in re.split(r"(<[buxr]>.*?</[buxr]>)", hwpify(text)):
            if not part:
                continue
            m = re.match(r"<([buxr])>(.*?)</\1>", part)
            if m:
                k, t = m.groups()
                out.append((t, self.cp(font, size, bold or k in "bu", {"x": BLUE, "r": RED}.get(k, color), k == "u")))
            else:
                out.append((part, self.cp(font, size, bold, color)))
        return out

    def para(self, key, fmt, segs, cell=None):
        cell = cell or self.cell
        p = cell.add_paragraph("", para_pr_id_ref=self.pp(key, fmt))
        for r in list(p.element.findall(HP + "run")):
            p.element.remove(r)
        for t, c in segs:
            if t:
                p.add_run(t, char_pr_id_ref=c)
        return p

    # 블록
    def sq(self, t):
        self.para("sq", self.fmt(4.5, -4.5, before=5, after=2, align="LEFT", keep=True),
                  [("□ ", self.cp(self.hf, self.base + 1))] + self.segs(t, self.hf, self.base + 1, True))

    def o(self, t, key=None):
        s = [("○ ", self.cp())] + ([(f"({key}) ", self.cp(bold=True))] if key else [])
        self.para("o", self.fmt(7, -3.8, before=1, after=1.5), s + self.segs(t))

    def d(self, t):
        self.para("d", self.fmt(10, -2.6, after=1), [("- ", self.cp())] + self.segs(t))

    def nk(self, t):
        self.para("nk", self.fmt(7, -3.4, after=1, line=140), [("※ ", self.cp(self.hf, self.small))] + self.segs(t, self.hf, self.small))

    def p(self, t, opt=None):
        opt = opt or {}
        self.para(("p", opt.get("align", "LEFT"), opt.get("size")), self.fmt(align=opt.get("align", "LEFT"), after=opt.get("after", 1)),
                  self.segs(t, opt.get("font"), opt.get("size"), opt.get("bold", False)))

    def _cell_text(self, cell, text, size, bold, align, color=None):
        for i, ln in enumerate(str(text).split("\n")):
            self.para(("tc", align), dict(alignment=align, line_spacing_percent=115, spacing_before_pt=0, spacing_after_pt=0),
                      self.segs(ln, self.hf, size, bold, color), cell=cell)

    def _drop(self, old):
        for p in old:
            p.remove()

    def tab(self, title, head, rows, opt=None):
        opt = opt or {}
        size = opt.get("size", self.small)
        host = self.cell.add_paragraph("", para_pr_id_ref=self.pp("thost", dict(alignment="CENTER", line_spacing_percent=100, spacing_before_pt=3, spacing_after_pt=0)))
        bf = self.doc.ensure_border_fill(border_color="#000000", border_width="0.12 mm")
        t = host.add_table(len(rows) + 1, len(head), width=int((self.w - 2) * MM), border_fill_id_ref=bf)
        if opt.get("widths"):
            t.set_column_widths(opt["widths"])
        aligns = opt.get("aligns") or ["CENTER"] * len(head)
        for c, h in enumerate(head):
            cell = t.cell(0, c); old = list(cell.paragraphs); self._cell_text(cell, h, size, True, "CENTER"); self._drop(old); t.set_cell_shading(0, c, HEAD_FILL)
        for r, row in enumerate(rows, 1):
            for c, v in enumerate(row):
                cell = t.cell(r, c); old = list(cell.paragraphs)
                first = opt.get("rh", True) and c == 0
                hl = r - 1 in opt.get("hl_rows", ())
                self._cell_text(cell, v, size, first or hl, aligns[c]); self._drop(old)
                if first:
                    t.set_cell_shading(r, c, ROW_FILL)
                elif hl:
                    t.set_cell_shading(r, c, "#EAF1FB")
        if title:   # 한글 표 캡션(표 객체에 붙어 쪽이 바뀌어도 표와 함께 움직임)
            self.tno += 1
            unit = f" (단위: {opt['unit']})" if opt.get("unit") else ""
            t.set_caption(f"【표 {self.tno}】 {hwpify(title)}{unit}", side="TOP", gap=280, char_pr_id_ref=self.cp(self.hf, self.base - 0.5, True))
            cpp = self.pp("tcap", dict(alignment="CENTER", line_spacing_percent=130, spacing_before_pt=0, spacing_after_pt=0))
            for cp_ in t.element.find(HP + "caption").iter(HP + "p"):
                cp_.set("paraPrIDRef", str(cpp))
        if opt.get("src"):
            self.para("tsrc", self.fmt(2.5, -2.5, before=1, after=3, line=130, align="LEFT"),
                      [("* ", self.cp(self.hf, self.small - 0.5))] + self.segs(opt["src"], self.hf, self.small - 0.5))
        return t

    def box(self, lines):
        host = self.cell.add_paragraph("", para_pr_id_ref=self.pp("thost", dict(alignment="CENTER", line_spacing_percent=100, spacing_after_pt=0)))
        bf = self.doc.ensure_border_fill(border_color="#8AA4D6", border_width="0.12 mm")
        t = host.add_table(1, 1, width=int((self.w - 6) * MM), border_fill_id_ref=bf)
        cell = t.cell(0, 0); old = list(cell.paragraphs)
        for ln in lines:
            self.para("boxp", dict(alignment="LEFT", line_spacing_percent=135, indent_left_mm=3.5, first_line_indent_mm=-3.5,
                                   spacing_before_pt=0.5, spacing_after_pt=0.5), self.segs(ln, self.hf, self.small), cell=cell)
        self._drop(old)
        t.set_cell_shading(0, 0, "#F4F4F2")
        self.para("gap", dict(alignment="LEFT", line_spacing_percent=100, spacing_after_pt=0), [(" ", self.cp(size=3))])

    def fig(self, path, title, src=None, width_mm=None):
        self.fno += 1
        width_mm = width_mm or (self.w - 4)
        data = Path(path).read_bytes()
        with Image.open(path) as im:
            w, h = im.size
        bid = str(add_image(self.doc, data, "png"))
        host = self.cell.add_paragraph("", para_pr_id_ref=self.pp("fhost", dict(alignment="CENTER", line_spacing_percent=100, spacing_before_pt=3, spacing_after_pt=1)))
        host.add_picture(bid, width=int(width_mm * MM), height=int(width_mm * h / w * MM), align="CENTER")
        self.para("fcap", dict(alignment="CENTER", line_spacing_percent=130, spacing_after_pt=0),
                  [(f"[그림 {self.fno}] ", self.cp(self.hf, self.base - 0.5, True))] + self.segs(title, self.hf, self.base - 0.5, True))
        if src:
            self.para("fsrc", dict(alignment="CENTER", line_spacing_percent=125, spacing_after_pt=4), self.segs(f"자료: {src}", self.hf, self.small - 0.5))

    def refs(self, items):
        for i, x in enumerate(items, 1):
            self.para("ref", dict(alignment="LEFT", line_spacing_percent=130, indent_left_mm=5, first_line_indent_mm=-5, spacing_after_pt=1),
                      [(f"{i}. ", self.cp(self.hf, self.small - 0.3))] + self.segs(x, self.hf, self.small - 0.3))

    def render(self, cell, blocks):
        self.cell = cell
        for b in blocks:
            getattr(self, b[0])(*b[1:])
