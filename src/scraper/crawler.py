# src/scraper/crawler.py
import time
import random
from playwright.sync_api import Page
from .parser import LinkedInParser

class LinkedInCrawler:
    def __init__(self, page: Page):
        self.page = page
        self.card_selector = 'div[data-view-name="search-entity-result-universal-template"]'

    def scrape_all_saved_jobs(self):
        all_jobs = []
        page_num = 1

        while True:
            print(f"--- Crawling Page {page_num} ---")
            
            try:
                self.page.wait_for_selector(self.card_selector, timeout=10000)
            except Exception:
                print("No more job cards found.")
                break

            # Orchestration: Find elements, then pass to Parser
            cards = self.page.locator(self.card_selector).all()
            for card in cards:
                # Extract raw data from browser
                raw_text = card.inner_text()
                raw_link = card.locator('a[href*="/jobs/view/"]').first.get_attribute("href")
                
                # Use the Parser to structure it
                job_data = LinkedInParser.clean_metadata(raw_text, raw_link)
                all_jobs.append(job_data)

            # Pagination Logic
            if not self._go_to_next_page():
                break
            
            page_num += 1
            time.sleep(random.uniform(4, 7))

        return all_jobs

    def _go_to_next_page(self) -> bool:
        next_button = self.page.locator('button[aria-label*="Next"]').first
        if next_button.is_visible() and next_button.is_enabled():
            next_button.click()
            return True
        return False