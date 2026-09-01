# src/scraper/crawler.py
"""
Crawls LinkedIn's jobs-tracker page using Playwright, collecting saved jobs
and paginating through all results.
"""

import re
import time
import random
from playwright.sync_api import Page

LINK_SELECTOR = 'a[href*="/jobs/view/"]'


def _go_to_next_page(page: Page) -> bool:
    next_button = page.locator('button[aria-label*="Next"]').first
    if next_button.is_visible() and next_button.is_enabled():
        next_button.click()
        return True
    return False


def _parse_card(title: str, card_text: str, href: str) -> dict:
    # card_text = "TitleCompany · LocationReposted 2d ago" (flex layout, no newlines)
    remaining = card_text[len(title):].strip() if card_text.startswith(title) else card_text.strip()

    company, location = "N/A", "N/A"
    if " · " in remaining:
        company_raw, rest = remaining.split(" · ", 1)
        company = company_raw.strip()
        location = re.split(r"\s*(?:Reposted|Posted|Easy Apply)\b", rest)[0].strip()

    return {
        "job_title": title,
        "company": company,
        "location": location,
        "link": href,
    }


def scrape_all_saved_jobs(page: Page) -> list:
    all_jobs = []
    page_num = 1

    while True:
        print(f"--- Crawling Page {page_num} ---")

        time.sleep(6)
        links_found = page.locator(LINK_SELECTOR).all()
        print(f"  [debug] {len(links_found)} job links found on page {page_num}")
        if not links_found:
            print("No more job cards found.")
            break

        seen_hrefs: set[str] = set()
        # one-shot diagnostic: inspect first title link's inner structure
        for lnk in links_found:
            t = lnk.inner_text().strip()
            if t.lower() == "apply":
                continue
            aria = lnk.get_attribute("aria-label")
            children = lnk.evaluate("""el => [...el.children].map(c => ({
                tag: c.tagName, cls: c.className, text: c.innerText.trim().slice(0,80)
            }))""")
            print(f"  [debug] aria-label: {aria!r}")
            print(f"  [debug] link children: {children}")
            break

        for link in links_found:
            title = link.inner_text().strip()
            if title.lower() == "apply":
                continue

            href = link.get_attribute("href")
            if not href:
                continue
            href = href.split("?")[0]
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            card_text = link.locator("xpath=..").inner_text().strip()
            job = _parse_card(title, card_text, href)
            job["source"] = "linkedin"
            all_jobs.append(job)

        if not _go_to_next_page(page):
            break

        page_num += 1
        time.sleep(random.uniform(4, 7))

    return all_jobs
