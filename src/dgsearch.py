"""data.go.kr 데이터 검색 (Playwright 렌더링).
usage: dgsearch.py TYPE "키워드" [...]   TYPE: FILE|STD|API
출력: pk | 제목 | 제공기관 | 수정일 | 형식"""
import sys, asyncio, re
from urllib.parse import quote
from playwright.async_api import async_playwright

async def main(dtype, kws):
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium")
        pg = await (await b.new_context(locale="ko-KR")).new_page()
        for kw in kws:
            for page in range(1, 8):
                url = (f"https://www.data.go.kr/tcs/dss/selectDataSetList.do?dType={dtype}"
                       f"&keyword={quote(kw)}&perPage=40&currentPage={page}")
                await pg.goto(url, wait_until="networkidle", timeout=60000)
                await pg.wait_for_timeout(800)
                rows = await pg.eval_on_selector_all("div.apply-result-item", """els => els.map(e => {
                    const a = e.querySelector('.apply-result-link a');
                    const exts = [...e.querySelectorAll('.apply-result-link .krds-badge')].map(x => x.innerText.trim()).join('/');
                    const lis = [...e.querySelectorAll('ul li')].map(x => x.innerText.replace(/\\s+/g,' ').trim());
                    return [a ? a.getAttribute('href') : '', a ? a.innerText.replace(/\\s+/g,' ').trim() : '', exts, lis.join(' ; ')];
                })""")
                if page == 1:
                    print(f"== [{dtype}] {kw}")
                for href, title, exts, meta in rows:
                    m = re.search(r'/data/(\d+)/', href or '')
                    org = re.search(r'제공기관 ([^;]+)', meta); upd = re.search(r'수정일 ([\d-]+)', meta)
                    print(f"   {m.group(1) if m else '?'} | {title[:60]} | {org.group(1).strip() if org else ''} | {upd.group(1) if upd else ''} | {exts}")
                if len(rows) < 40:
                    break
        await b.close()

asyncio.run(main(sys.argv[1], sys.argv[2:]))
