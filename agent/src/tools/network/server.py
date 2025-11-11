from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from models import MCPResponse

mcp = FastMCP("badmcp-network-server")


def _make_headers(headers: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Convert dict to headers with string values."""
    out: Dict[str, str] = {}
    if headers:
        for k, v in headers.items():
            out[str(k)] = str(v)
    return out


@mcp.tool()
async def http_get(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, Any]] = None,
    timeout: float = 20,
) -> dict:
    """Perform an HTTP GET request."""
    try:
        headers_dict = _make_headers(headers)

        # Add query parameters to URL if provided
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            sep = "&" if urllib.parse.urlparse(url).query else "?"
            url = f"{url}{sep}{query}"

        req = urllib.request.Request(url, headers=headers_dict or {})
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body_bytes = resp.read()
            elapsed_ms = int((time.time() - start) * 1000)
            content_type = resp.headers.get("Content-Type", "")
            try:
                if "application/json" in content_type:
                    body: Any = json.loads(body_bytes.decode("utf-8", errors="replace"))
                else:
                    body = body_bytes.decode("utf-8", errors="replace")
            except Exception:
                body = body_bytes.decode("utf-8", errors="replace")

            result = {
                "url": url,
                "status": resp.status,
                "headers": dict(resp.headers.items()),
                "body": body,
                "elapsed_ms": elapsed_ms,
            }
            return MCPResponse.success(result=result).to_dict()

    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


@mcp.tool()
async def http_post(
    url: str,
    data: Optional[Any] = None,
    json: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, Any]] = None,
    timeout: float = 20,
) -> dict:
    """Perform an HTTP POST request with optional JSON or form data."""
    try:
        headers_dict = _make_headers(headers)

        body_bytes: Optional[bytes] = None
        if json is not None:
            import json as json_module

            body_bytes = json_module.dumps(json).encode("utf-8")
            headers_dict.setdefault("Content-Type", "application/json")
        elif isinstance(data, dict):
            body_bytes = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
            headers_dict.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif isinstance(data, str):
            body_bytes = data.encode("utf-8")
            headers_dict.setdefault("Content-Type", "text/plain; charset=utf-8")
        elif data is None:
            body_bytes = None
        else:
            return MCPResponse.error("'data' must be dict, string, or null").to_dict()

        req = urllib.request.Request(
            url, data=body_bytes, headers=headers_dict or {}, method="POST"
        )
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body_bytes = resp.read()
            elapsed_ms = int((time.time() - start) * 1000)
            content_type = resp.headers.get("Content-Type", "")
            try:
                if "application/json" in content_type:
                    import json as json_module

                    resp_body: Any = json_module.loads(
                        resp_body_bytes.decode("utf-8", errors="replace")
                    )
                else:
                    resp_body = resp_body_bytes.decode("utf-8", errors="replace")
            except Exception:
                resp_body = resp_body_bytes.decode("utf-8", errors="replace")

            result = {
                "url": url,
                "status": resp.status,
                "headers": dict(resp.headers.items()),
                "body": resp_body,
                "elapsed_ms": elapsed_ms,
            }
            return MCPResponse.success(result=result).to_dict()

    except Exception as e:
        return MCPResponse.error(str(e)).to_dict()


def main():
    mcp.run()


if __name__ == "__main__":
    main()
