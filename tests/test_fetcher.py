import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from playwright.sync_api import sync_playwright
from src.fetcher.fetcher import fetch_job_description

SESSION_DIR = os.path.join(os.path.dirname(__file__), "..", ".session")

JOB_URL = "https://www.linkedin.com/jobs/view/4334046024/"


@pytest.fixture(scope="module")
def browser_context():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
        )
        yield context
        context.close()


def test_fetch_job_description(browser_context):
    result = fetch_job_description(browser_context, JOB_URL)
    print(f"\n--- JD Preview ---\n")
    print(f"{result[:500]}")
    assert result != "", "Job description should not be empty"
    assert "About the job" not in result, "Should return body text, not the heading"
