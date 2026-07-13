"""DuckDuckGo Instant Answer helpers."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

DUCKDUCKGO_API_URL = "https://api.duckduckgo.com/"
RATE_LIMIT_SECONDS = 1.0
_last_search_time = 0.0


def search(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Search DuckDuckGo Instant Answer API. Returns title/url dicts."""
    global _last_search_time
    elapsed = time.time() - _last_search_time
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)
    _last_search_time = time.time()

    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
    )
    url = f"{DUCKDUCKGO_API_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "SparkyBadRobot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload: Dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return [{"error": str(exc)}]

    results: List[Dict[str, str]] = []

    def _walk(items: List[Any]) -> None:
        for item in items:
            if len(results) >= max_results:
                return
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("Topics"), list):
                _walk(item["Topics"])
                continue
            title = str(item.get("Text") or "").strip()
            link = str(item.get("FirstURL") or "").strip()
            if title and link:
                results.append({"title": title, "url": link})

    _walk(list(payload.get("RelatedTopics") or []))
    return results
