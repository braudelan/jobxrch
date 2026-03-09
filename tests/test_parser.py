import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scraper.parser import clean_job_card_data


def test_basic_extraction():
    raw_text = "Software Engineer\nAcme Corp\nSan Francisco, CA"
    raw_link = "https://www.linkedin.com/jobs/view/123456789/?refId=abc"
    result = clean_job_card_data(raw_text, raw_link)
    assert result["job_title"] == "Software Engineer"
    assert result["company"] == "Acme Corp"
    assert result["location"] == "San Francisco, CA"
    assert result["link"] == "https://www.linkedin.com/jobs/view/123456789/"


def test_noise_stripped():
    raw_text = "Software Engineer\nVerified\nAcme Corp\nPromoted\nSan Francisco, CA\nActively recruiting"
    result = clean_job_card_data(raw_text, "https://www.linkedin.com/jobs/view/123/")
    assert result["job_title"] == "Software Engineer"
    assert result["company"] == "Acme Corp"
    assert result["location"] == "San Francisco, CA"


def test_link_query_string_stripped():
    raw_link = "https://www.linkedin.com/jobs/view/999/?trackingId=xyz&refId=abc"
    result = clean_job_card_data("Title\nCompany\nLocation", raw_link)
    assert "?" not in result["link"]


def test_missing_link():
    result = clean_job_card_data("Title\nCompany\nLocation", None)
    assert result["link"] == "N/A"


def test_partial_card():
    result = clean_job_card_data("Only A Title", "https://www.linkedin.com/jobs/view/1/")
    assert result["job_title"] == "Only A Title"
    assert result["company"] == "N/A"
    assert result["location"] == "N/A"


def test_empty_card():
    result = clean_job_card_data("", None)
    assert result["job_title"] == "N/A"
    assert result["company"] == "N/A"
    assert result["location"] == "N/A"
    assert result["link"] == "N/A"