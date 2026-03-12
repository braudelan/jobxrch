# src/fetcher/fetcher.py
from playwright.sync_api import BrowserContext, Page


def _expand_job_description(page: Page) -> None:
    try:
        button = page.locator('[data-testid="expandable-text-button"]')
        if button.is_visible(timeout=2000):
            button.click()
    except Exception:
        pass


def _extract_job_description(page: Page) -> str:
    try:
        box = page.locator('[data-testid="expandable-text-box"]').first
        box.wait_for(timeout=10000)
        return box.inner_text().removesuffix("\n…\nmore").strip()
    except Exception as e:
        print(f"Could not extract JD: {e}")
        return ""


def fetch_job_description(context: BrowserContext, url: str) -> str:
    page = context.new_page()
    try:
        page.goto(url, timeout=15000)
        page.wait_for_selector("h2:has-text('About the job')", timeout=10000)
        print(f"\nPage loaded for {url}")
        print("Expanding description if needed...")
        _expand_job_description(page)
        print("JD expanded (if applicable). Extracting text...")
        return _extract_job_description(page)
    except Exception as e:
        print(f"Failed to fetch JD for {url}: {e}")
        return ""
    finally:
        page.close()
