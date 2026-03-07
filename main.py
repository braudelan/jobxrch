# main.py
import os
import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from src.scraper.crawler import LinkedInCrawler

# 1. Load configuration
load_dotenv() 
LI_AT_COOKIE = os.getenv("LI_AT_COOKIE")

def run_pipeline():
    if not LI_AT_COOKIE:
        print("Error: LI_AT_COOKIE not found in .env file.")
        return

    with sync_playwright() as p:
        # 2. Setup Browser
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        context.add_cookies([{
            "name": "li_at",
            "value": LI_AT_COOKIE,
            "domain": ".linkedin.com",
            "path": "/"
        }])
        
        page = context.new_page()
        print("Initialization complete. Starting Crawler...")

        # 3. Execute Scrape
        crawler = LinkedInCrawler(page)
        page.goto("https://www.linkedin.com/my-items/saved-jobs/")
        
        results = crawler.scrape_all_saved_jobs()
        
        # 4. Save Data
        if results:
            df = pd.DataFrame(results)
            os.makedirs("data", exist_ok=True)
            df.to_csv("data/linkedin_saved_jobs.csv", index=False)
            print(f"Pipeline finished. {len(df)} jobs saved to data/linkedin_saved_jobs.csv")
        
        browser.close()

if __name__ == "__main__":
    run_pipeline()