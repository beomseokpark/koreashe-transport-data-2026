"""서울 열린데이터광장 통계표(장애인 현황 장애유형별/동별, 기본 화면 = 2025 자치구) CSV 내려받기 (Playwright)
usage: seoul_stat_down.py URL OUT.csv
화면 좌표 클릭(다운로드 버튼 → CSV → 다운로드)이라 화면 배치가 바뀌면 고쳐야 함"""
import asyncio, re, sys
from playwright.async_api import async_playwright
async def main(url, out):
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium")
        ctx = await b.new_context(accept_downloads=True, locale="ko-KR", viewport={"width":1600,"height":1000})
        pg = await ctx.new_page()
        await pg.goto(url, wait_until="networkidle", timeout=90000)
        await pg.wait_for_timeout(2000)
        await pg.click("a.staBtn.down, button.staBtn.down, .staBtn.down")
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path="/tmp/stat_dl.png")
        html = await pg.content()
        for m in re.findall(r'<input[^>]*(?:radio|checkbox)[^>]*>', html)[:40]: print(m[:200])
        try:
            await pg.mouse.click(607,399)
        except Exception as e: print("csv radio", e)
        async with pg.expect_download(timeout=60000) as d:
            await pg.mouse.click(800,663)
        dl = await d.value; await dl.save_as(out); print("saved", out)
        await b.close()
asyncio.run(main(sys.argv[1], sys.argv[2]))
