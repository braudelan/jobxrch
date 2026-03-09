# main.py
import os
from playwright.sync_api import sync_playwright
from src.scraper.crawler import scrape_all_saved_jobs
from src.fetcher.fetcher import fetch_job_description

SESSION_DIR = os.path.join(os.path.dirname(__file__), ".session")


def run_pipeline():
    with sync_playwright() as p:
        # 1. Launch persistent context (saves session to disk)
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
        )
        page = context.new_page()

        # 2. If not logged in, wait for user to log in manually
        page.goto("https://www.linkedin.com/my-items/saved-jobs/")
        if "login" in page.url or "authwall" in page.url:
            print("Not logged in. Please log into LinkedIn in the browser window, then press Enter here...")
            input()

        print("Initialization complete. Starting Crawler...")

        # 3. Crawl saved jobs
        results = scrape_all_saved_jobs(page)
        print(f"Found {len(results)} jobs. Fetching first job description as smoke test...")

        # 4. Fetch JD for first 5 jobs as a smoke test
        if results:
            for job in results[:5]:
                print(f"Fetching: {job['job_title']} at {job['company']}")
                job["description"] = fetch_job_description(context, job["link"])
                print(f"--- Description preview ---\n{job['description'][:500]}")

        context.close()


if __name__ == "__main__":
    run_pipeline()