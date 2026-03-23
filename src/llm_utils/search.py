# src/llm_utils/search.py
"""
Pluggable web search backends for the chat tool.

Each provider is a callable: (query: str) -> str
Pass one to chat_reply() as the `search_fn` argument, or let it
auto-select based on environment variables.

To add a new provider:
  1. Write a function with signature (query: str) -> str
  2. Add it here and wire it up in `get_search_fn` if desired
"""

import json
import os
import urllib.request


def tavily_search(query: str, count: int = 5) -> str:
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return "Web search is not configured (missing TAVILY_API_KEY)."

    payload = json.dumps({"api_key": api_key, "query": query, "max_results": count}).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read())

    results = data.get("results", [])
    if not results:
        return "No results found."

    lines = []
    for r in results:
        lines.append(f"**{r.get('title', '')}**")
        lines.append(r.get("url", ""))
        if r.get("content"):
            lines.append(r["content"])
        lines.append("")
    return "\n".join(lines).strip()


def get_search_fn():
    """Return the configured search provider, or None if no key is set."""
    if os.environ.get("TAVILY_API_KEY"):
        return tavily_search
    return None
