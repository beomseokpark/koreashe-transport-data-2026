"""data.go.kr 파일데이터 다운로드. usage: dgdown.py OUTDIR PK [PK ...]
상세페이지의 '다운로드' 버튼을 눌러 받은 파일을 OUTDIR/PK_원래이름 으로 저장하고, 상세 메타(제공기관·수정일·URL)를 출력."""
import sys, asyncio, os, re
from playwright.async_api import async_playwright

async def main(outdir, pks):
    os.makedirs(outdir, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium")
        ctx = await b.new_context(locale="ko-KR", accept_downloads=True)
        pg = await ctx.new_page()
        for pk in pks:
            url = f"https://www.data.go.kr/data/{pk}/fileData.do"
            try:
                await pg.goto(url, wait_until="networkidle", timeout=60000)
            except Exception as e:
                print("ERR goto", pk, e); continue
            title = (await pg.title()).split('|')[0].strip()
            body = await pg.inner_text("body")
            meta = {}
            for k in ["제공기관", "수정일", "업데이트 주기", "차기 등록 예정일", "이용허락범위", "데이터 한계", "기타 유의사항"]:
                m = re.search(k + r'\s*\n?\s*([^\n]+)', body)
                if m: meta[k] = m.group(1).strip()[:80]
            print(f"== {pk} {title} {meta}")
            btns = pg.locator("a:has-text('다운로드'), button:has-text('다운로드')")
            n = await btns.count()
            got = False
            for i in range(n):
                el = btns.nth(i)
                if not await el.is_visible():
                    continue
                try:
                    async with pg.expect_download(timeout=60000) as dl_info:
                        await el.click()
                    dl = await dl_info.value
                    fn = os.path.join(outdir, f"{pk}_{dl.suggested_filename}")
                    await dl.save_as(fn)
                    print("   saved", fn, os.path.getsize(fn))
                    got = True
                    break
                except Exception as e:
                    print("   try", i, "no download:", str(e)[:80])
            if not got:
                print("   !! no file downloaded")
        await b.close()

asyncio.run(main(sys.argv[1], sys.argv[2:]))
