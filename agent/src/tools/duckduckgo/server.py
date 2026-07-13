"""DuckDuckGo search MCP server (FastMCP)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("duckduckgo")

DUCKDUCKGO_API_URL = "https://api.duckduckgo.com/"
RATE_LIMIT_SECONDS = 1.0
_last_search_time = 0.0


def _rate_limit() -> None:
    global _last_search_time
    elapsed = time.time() - _last_search_time
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)
    _last_search_time = time.time()


def _flatten_topics(items: List[Any], limit: int) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    for item in items:
        if len(results) >= limit:
            break
        if not isinstance(item, dict):
            continue
        if "Topics" in item and isinstance(item["Topics"], list):
            results.extend(_flatten_topics(item["Topics"], limit - len(results)))
            continue
        title = str(item.get("Text") or "").strip()
        url = str(item.get("FirstURL") or "").strip()
        if title and url:
            results.append({"title": title, "url": url})
    return results


@mcp.tool()
def duckduckgo_search(query: str, max_results: int = 10) -> dict:
    """Search DuckDuckGo Instant Answer API for the given query."""
    if not query or not query.strip():
        return {"error": "query is required", "results": []}

    max_results = max(1, min(int(max_results or 10), 25))
    _rate_limit()

    params = urllib.parse.urlencode(
        {
            "q": query.strip(),
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
    )
    url = f"{DUCKDUCKGO_API_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SparkyBadRobot/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"error": str(exc), "results": []}

    results = _flatten_topics(list(payload.get("RelatedTopics") or []), max_results)
    abstract = str(payload.get("AbstractText") or "").strip()
    abstract_url = str(payload.get("AbstractURL") or "").strip()
    if abstract and abstract_url and len(results) < max_results:
        results.insert(0, {"title": abstract, "url": abstract_url})
        results = results[:max_results]

    return {
        "query": query.strip(),
        "heading": payload.get("Heading") or "",
        "results": results,
    }


@mcp.tool()
def fetch_page_content(url: str, max_chars: int = 8000) -> dict:
    """Fetch a web page and return truncated plain text content."""
    if not url or not url.strip():
        return {"error": "url is required", "content": ""}

    max_chars = max(500, min(int(max_chars or 8000), 50000))
    try:
        from tools.duckduckgo.content_fetcher import fetch_content

        text = fetch_content(url.strip())
    except Exception as exc:
        return {"error": str(exc), "content": ""}

    if text.startswith("Error fetching URL:"):
        return {"error": text, "content": ""}

    truncated = text[:max_chars]
    return {
        "url": url.strip(),
        "content": truncated,
        "truncated": len(text) > max_chars,
    }


if __name__ == "__main__":
    mcp.run()
