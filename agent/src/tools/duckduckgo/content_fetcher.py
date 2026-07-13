"""Fetch and extract readable text from a web page."""

from __future__ import annotations

import urllib.error
import urllib.request


def fetch_content(url: str) -> str:
    """Fetch a webpage and return cleaned plain text."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        BeautifulSoup = None  # type: ignore

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SparkyBadRobot/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        return f"Error fetching URL: {exc}"

    if BeautifulSoup is None:
        return html

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)
