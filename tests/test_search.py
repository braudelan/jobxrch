import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.llm_utils.search import tavily_search, get_search_fn


# --- get_search_fn (no network, just env logic) ---

def test_get_search_fn_none_without_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert get_search_fn() is None


def test_get_search_fn_returns_tavily(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "dummy")
    assert get_search_fn() is tavily_search


# --- tavily_search (real HTTP, skipped if no key) ---

@pytest.mark.skipif(not os.environ.get("TAVILY_API_KEY"), reason="TAVILY_API_KEY not set")
def test_tavily_search_returns_results():
    result = tavily_search("Stripe fintech company")
    assert isinstance(result, str)
    assert len(result) > 0
    assert "No results found." not in result


@pytest.mark.skipif(not os.environ.get("TAVILY_API_KEY"), reason="TAVILY_API_KEY not set")
def test_tavily_search_includes_url():
    result = tavily_search("Stripe fintech company")
    assert "https://" in result
