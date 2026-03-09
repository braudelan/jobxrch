# src/scraper/crawler.py
import time
import random
from playwright.sync_api import Page
from .parser import clean_job_card_data

CARD_SELECTOR = 'div[data-view-name="search-entity-result-universal-template"]'


def _go_to_next_page(page: Page) -> bool:
    next_button = page.locator('button[aria-label*="Next"]').first
    if next_button.is_visible() and next_button.is_enabled():
        next_button.click()
        return True
    return False


def scrape_all_saved_jobs(page: Page) -> list:
    all_jobs = []
    page_num = 1

    while True:
        print(f"--- Crawling Page {page_num} ---")

        try:
            page.wait_for_selector(CARD_SELECTOR, timeout=10000)
        except Exception:
            print("No more job cards found.")
            break

        cards = page.locator(CARD_SELECTOR).all()
        for card in cards:
            raw_text = card.inner_text()
            raw_link = card.locator('a[href*="/jobs/view/"]').first.get_attribute("href")
            all_jobs.append(clean_job_card_data(raw_text, raw_link))

        if not _go_to_next_page(page):
            break

        page_num += 1
        time.sleep(random.uniform(4, 7))

    return all_jobs