# src/pipeline.py
import os
from playwright.sync_api import sync_playwright
from src.scraper.crawler import scrape_all_saved_jobs
from src.fetcher.fetcher import fetch_job_description
from src.db.database import init_db, is_job_saved, save_job, get_job_id, save_evaluation
from src.llm_utils.evaluate import evaluate_job

SESSION_DIR = os.path.join(os.path.dirname(__file__), "..", ".session")


def run():
    init_db()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
        )
        page = context.new_page()

        page.goto("https://www.linkedin.com/my-items/saved-jobs/")
        if "login" in page.url or "authwall" in page.url:
            print("Not logged in. Please log in the browser window, then press Enter...")
            input()

        print("Initialization complete. Starting crawler...")
        jobs = scrape_all_saved_jobs(page)
        print(f"Found {len(jobs)} saved jobs.")

        new_jobs = [job for job in jobs if not is_job_saved(job["link"])]
        print(f"{len(new_jobs)} new jobs to fetch. {len(jobs) - len(new_jobs)} already in DB, skipping.")

        for i, job in enumerate(new_jobs, 1):
            print(f"[{i}/{len(new_jobs)}] Fetching: {job['job_title']} at {job['company']}")
            job["description"] = fetch_job_description(context, job["link"])
            save_job(job)

            print(f"[{i}/{len(new_jobs)}] Evaluating...")
            result, chash = evaluate_job(job)
            save_evaluation(get_job_id(job["link"]), chash, result)
            print(f"[{i}/{len(new_jobs)}] Done.\n")

        context.close()

    print("All done.")
