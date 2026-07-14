"""
상품 링크 1개를 받아 리뷰를 크롤링해서 JSON으로 저장하는 프로토타입 스크립트.
Scrapy 없이 Playwright만 직접 써서 빠르게 확인용으로 돌리기 위한 용도.

사용법:
    python quick_extract.py "https://store.kakao.com/kakaofriends/products/..."
"""
import asyncio
import json
import re
import sys

from playwright.async_api import async_playwright

REVIEW_TAB_SELECTORS = [
    "a[data-tiara-layer='review']",
    "[data-tiara-action-name='리뷰 탭 클릭']",
    "a.link_tab:has-text('리뷰')",
    "text=리뷰",
    "a:has-text('리뷰')",
    "button:has-text('리뷰')",
]
MORE_BTN_SELECTOR = "a[data-tiara-layer='btn_review_list_more']"
MAX_MORE_CLICKS = 200


async def extract_reviews(product_url: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )
        await page.goto(product_url, wait_until="domcontentloaded")

        viewport_height = await page.evaluate("window.innerHeight")
        step = max(int(viewport_height * 0.6), 300)

        tab_clicked = False
        for i in range(15):
            for sel in REVIEW_TAB_SELECTORS:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        await el.scroll_into_view_if_needed()
                        await el.click()
                        tab_clicked = True
                        print(f"리뷰 탭 클릭 성공(스크롤 {i + 1}회차): {sel}")
                        await page.wait_for_timeout(2000)
                        break
                except Exception as e:
                    print(f"리뷰 탭 클릭 시도 실패({sel}): {e}")
            if tab_clicked:
                break
            await page.evaluate(f"window.scrollBy(0, {step})")
            await page.wait_for_timeout(800)

        if not tab_clicked:
            print(f"리뷰 탭을 찾지 못했습니다: {product_url}")

        click_count = 0
        while click_count < MAX_MORE_CLICKS:
            more_btn = await page.query_selector(MORE_BTN_SELECTOR)
            if not more_btn:
                print(f"'더보기' 버튼 없음 - 로딩 완료 (클릭 {click_count}회)")
                break
            try:
                await more_btn.scroll_into_view_if_needed()
                await more_btn.click()
                click_count += 1
                await page.wait_for_timeout(1000)
                current_count = len(await page.query_selector_all("p.txt_review"))
                print(f"'더보기' 클릭 {click_count}회차 - 누적 리뷰 수: {current_count}")
            except Exception as e:
                print(f"'더보기' 클릭 중 오류, 중단: {e}")
                break

        product_name = await page.evaluate(
            """
            () => {
                const nameEl = document.querySelector('.txt_name');
                if (!nameEl) return null;
                const clone = nameEl.cloneNode(true);
                const screenOut = clone.querySelector('.screen_out');
                if (screenOut) screenOut.remove();
                return clone.textContent.trim();
            }
            """
        )
        print(f"상품명: {product_name}")

        reviews_data = await page.evaluate(
            """
            () => {
                const items = document.querySelectorAll('li.box_review, li.item-container.box_review');
                const results = [];
                items.forEach(item => {
                    const textEl = item.querySelector('p.txt_review');
                    if (!textEl) return;
                    const text = textEl.textContent.trim();
                    if (!text) return;

                    let rating = null;
                    const scoreEl = item.querySelector('.area_score em.img_shop');
                    if (scoreEl) {
                        const m = scoreEl.textContent.match(/(\\d+)/);
                        if (m) rating = parseInt(m[1], 10);
                    }

                    let date = null;
                    const infoItems = item.querySelectorAll('.list_reviewinfo li');
                    infoItems.forEach(li => {
                        const label = li.querySelector('strong.screen_out');
                        if (label && label.textContent.trim() === '작성일') {
                            const span = li.querySelector('span.txt_reviewinfo');
                            if (span) date = span.textContent.trim();
                        }
                    });

                    results.push({ text, rating, date });
                });
                return results;
            }
            """
        )
        print(f"최종 추출된 리뷰 개수: {len(reviews_data)}")

        await browser.close()

        reviews = [
            {
                "product_url": product_url,
                "product_name": product_name,
                "review_index": idx,
                "review_text": item.get("text"),
                "rating": item.get("rating"),
                "date": item.get("date"),
            }
            for idx, item in enumerate(reviews_data)
        ]
        return {"product_url": product_url, "product_name": product_name, "reviews": reviews}


def slugify(url: str) -> str:
    tail = url.rstrip("/").split("/")[-1]
    return re.sub(r"[^0-9A-Za-z_-]", "_", tail) or "product"


async def main():
    if len(sys.argv) < 2:
        print('사용법: python quick_extract.py "https://store.kakao.com/kakaofriends/products/319124464?docId=319124464"')
        sys.exit(1)

    product_url = sys.argv[1]
    result = await extract_reviews(product_url)

    out_path = f"quick_review_{slugify(product_url)}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {out_path} (리뷰 {len(result['reviews'])}개)")


if __name__ == "__main__":
    asyncio.run(main())
