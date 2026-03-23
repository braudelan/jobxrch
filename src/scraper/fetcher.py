# src/scraper/fetcher.py
"""
Fetches job descriptions and metadata from job posting URLs using Playwright.
Designed for LinkedIn job postings but can be adapted for others. Provides functions to extract job details and ingest them into the system, including
LLM-based metadata extraction as a fallback when selectors fail. Returns structured job data for storage and evaluation.
"""
import json
from playwright.sync_api import BrowserContext, Page


def _strip_fences(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    return s.strip()


def extract_metadata_from_text(description: str) -> dict:
    """Use LLM to extract job_title, company, location from a job description."""
    import importlib, os
    provider_name = os.environ.get("LLM_PROVIDER", "anthropic")
    complete = importlib.import_module(f"src.llm_utils.providers.{provider_name}").complete

    prompt = f"""Extract the job title, company name, and location from the following job posting text.

Return JSON only — no markdown wrapper, no text outside the JSON:
{{
  "job_title": "<job title or empty string if not found>",
  "company": "<company name or empty string if not found>",
  "location": "<location or empty string if not found>"
}}

Job posting text:
{description[:3000]}"""
    raw = complete(prompt)
    try:
        data = json.loads(_strip_fences(raw))
        return {
            "job_title": data.get("job_title", "") or "",
            "company": data.get("company", "") or "",
            "location": data.get("location", "") or "",
        }
    except (json.JSONDecodeError, KeyError):
        return {"job_title": "", "company": "", "location": ""}


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
    title = _extract_text(page, "h1.top-card-layout__title") or _extract_text(
        page, "h1"
    )
    company = _extract_text(page, "a.topcard__org-name-link") or _extract_text(
        page, ".topcard__org-name-link"
    )
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


def ingest_job_from_url(session_dir: str, url: str) -> int:
    """Given a job URL, fetch, save, and evaluate it. Returns the job ID."""
    from playwright.sync_api import sync_playwright
    from src.db.database import is_job_saved, save_job, get_job_by_link, save_evaluation
    from src.llm_utils.evaluate import evaluate_job

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            headless=False,
        )
        if not is_job_saved(url):
            details = fetch_job_details(context, url)
            save_job(
                {
                    "job_title": details["job_title"],
                    "company": details["company"],
                    "location": details["location"],
                    "link": url,
                    "description": details["description"],
                    "source": "manual",
                }
            )
        context.close()

    job = get_job_by_link(url)
    result, chash = evaluate_job(job)
    save_evaluation(job["id"], chash, result)
    return job["id"]


def fetch_job_details(context: BrowserContext, url: str) -> dict:
    page = _open_page(context, url)
    try:
        description = _extract_job_description(page)
        metadata = _extract_metadata_selectors(page)

        if not metadata["job_title"] or not metadata["company"]:
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
        return {
            "job_title": "Unknown",
            "company": "",
            "location": "",
            "description": "",
        }
    finally:
        page.close()
