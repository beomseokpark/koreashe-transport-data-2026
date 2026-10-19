"""참가신청서(붙임1) — 원본 HWP 양식을 HWPX로 바꾼 뒤 칸·체크만 채움(표·문단·서식은 그대로)
채우는 것: 지원형태 ■개인, 신청자명, 대표 이름·소속(이메일·연락처는 applicant.json에 값이 있을 때만), 두 동의 ■, 날짜, 대표 이름
서명은 응모자가 직접. 출력: output/박범석_참가신청서.hwpx (한글에서 열어 서명 후 PDF로 저장)"""
import json
from pathlib import Path
from hwpx.hwp5.package import convert, to_hwpx_bytes
from hwpx import HwpxDocument
from common import ROOT, OUT

A = json.load(open(ROOT / "applicant.json", encoding="utf-8"))
HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
DATE = A.get("date", "2026년  10월  22일")
known = lambda v: bool(v) and not str(v).startswith("[")

def sub(el, old, new):
    """문단·칸 안 글자 조각(hp:t)에서 old → new. 조각 하나 안에 있어야 함(서식 보존)"""
    for t in el.iter(HP + "t"):
        if t.text and old in t.text:
            t.text = t.text.replace(old, new, 1); return
    raise SystemExit(f"못 찾음: {old!r}")

def put(table, r, c, text, like=None):
    """빈 칸 또는 안내문 칸에 글자를 넣음. 안내문(파란 글씨) 칸은 like 칸의 글자 서식(검정)으로 바꿈"""
    cell = table.cell(r, c)
    ts = list(cell.element.iter(HP + "t"))
    if ts:
        ts[0].text = text
        for t in ts[1:]: t.text = ""
    else:
        cell.set_text(text)
    if like is not None:
        cpr = next(like.element.iter(HP + "run")).get("charPrIDRef")
        for run in cell.element.iter(HP + "run"): run.set("charPrIDRef", cpr)

if __name__ == "__main__":
    src = ROOT / "reference/붙임1_참가신청서.hwp"
    doc = HwpxDocument.open(to_hwpx_bytes(convert(src.read_bytes()).files))
    ps = doc.paragraphs
    info = ps[1].tables[0]
    sub(info.cell(1, 1).element, "□ 개인", "■ 개인")
    put(info, 2, 1, A["name"], like=info.cell(1, 1))   # 안내문 "※ 팀일 경우 팀명 기재" 자리
    put(info, 4, 1, A["name"]); put(info, 4, 2, A["affiliation"])
    if known(A.get("email")): put(info, 4, 3, A["email"])
    if known(A.get("phone")): put(info, 4, 4, A["phone"])
    sub(ps[3].element, "□ 동의함", "■ 동의함")
    sub(ps[8].element, "□ 동의함", "■ 동의함")
    sub(ps[13].element, "2026년     월     일", DATE)
    sub(ps[15].element, "이름(대 표) :      서명:", f"이름(대 표) :  {A['name']}    서명:")
    out = OUT / f"{A['name']}_참가신청서.hwpx"
    doc.save_to_path(str(out))
    chk = HwpxDocument.open(str(out))
    print(out, "|", chk.paragraphs[1].tables[0].cell(4, 1).text, chk.paragraphs[3].text[-20:], chk.paragraphs[15].text)
