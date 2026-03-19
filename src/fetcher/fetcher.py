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


def _extract_text(page, selector: str, fallback: str = "") -> str:
    try:
        el = page.locator(selector).first
        el.wait_for(timeout=3000)
        return el.inner_text().strip()
    except Exception:
        return fallback


def _open_page(context: BrowserContext, url: str) -> Page:
    page = context.new_page()
    page.goto(url, timeout=15000)
    page.wait_for_selector("h2:has-text('About the job')", timeout=10000)
    _expand_job_description(page)
    return page


def _extract_metadata_selectors(page: Page) -> dict:
    title = _extract_text(page, "h1.top-card-layout__title") or _extract_text(page, "h1")
    company = _extract_text(page, "a.topcard__org-name-link") or _extract_text(page, ".topcard__org-name-link")
    location = _extract_text(page, ".topcard__flavor--bullet")
    return {
        "job_title": title or "",
        "company": company or "",
        "location": location or "",
    }


def fetch_job_description(context: BrowserContext, url: str) -> str:
    page = _open_page(context, url)
    try:
        print(f"\nPage loaded for {url}")
        print("Extracting description...")
        return _extract_job_description(page)
    except Exception as e:
        print(f"Failed to fetch JD for {url}: {e}")
        return ""
    finally:
        page.close()


def fetch_job_details(context: BrowserContext, url: str) -> dict:
    page = _open_page(context, url)
    try:
        description = _extract_job_description(page)
        metadata = _extract_metadata_selectors(page)

        if not metadata["job_title"] or not metadata["company"]:
            from src.llm_utils.evaluate import extract_metadata_from_text
            llm_meta = extract_metadata_from_text(description)
            if not metadata["job_title"]:
                metadata["job_title"] = llm_meta.get("job_title", "Unknown")
            if not metadata["company"]:
                metadata["company"] = llm_meta.get("company", "")
            if not metadata["location"]:
                metadata["location"] = llm_meta.get("location", "")

        if not metadata["job_title"]:
            metadata["job_title"] = "Unknown"

        metadata["description"] = description
        return metadata
    except Exception as e:
        print(f"Failed to fetch job details for {url}: {e}")
        return {"job_title": "Unknown", "company": "", "location": "", "description": ""}
    finally:
        page.close()
