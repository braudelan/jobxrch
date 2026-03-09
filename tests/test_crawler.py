import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scraper.crawler import scrape_all_saved_jobs, _go_to_next_page


def test_crawler_functions_importable():
    assert callable(scrape_all_saved_jobs)
    assert callable(_go_to_next_page)
