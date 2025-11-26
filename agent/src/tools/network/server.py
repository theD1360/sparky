from __future__ import annotations

import asyncio
import json
import socket
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

import html2text
import httpx
from mcp.server.fastmcp import FastMCP
from models import MCPResponse

mcp = FastMCP("network-tools")


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


@mcp.tool()
async def fetch_as_markdown(url: str) -> dict:
    """Fetch content from a URL and convert it to Markdown."""
    try:
        response = await http_get(url)
        if response["status"] != "success":
            return MCPResponse.error(
                f"Failed to fetch URL: {response['message']}"
            ).to_dict()

        html_content = response["result"]["body"]

        # Attempt to convert HTML to Markdown using html2text
        try:
            markdown_content = html2text.html2text(html_content)
            return MCPResponse.success(markdown_content).to_dict()
        except Exception as e:
            return MCPResponse.error(
                f"Failed to convert HTML to Markdown: {e}"
            ).to_dict()
    except Exception as e:
        return MCPResponse.error(f"An unexpected error occurred: {e}").to_dict()


# ============================================================================
# ADVANCED NETWORKING TOOLS (Domain/Network Reconnaissance)
# ============================================================================


@mcp.tool()
async def whois_info(domain: str) -> dict:
    """Get WHOIS information for a given domain."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "whois",
            domain,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0 or not stdout:
            return MCPResponse.error(
                "whois command failed or returned no output."
            ).to_dict()

        result_text = stdout.decode(errors="ignore")
        if result_text.startswith("No match for"):
            return MCPResponse.error("No WHOIS record found for the domain.").to_dict()

        # Process the raw whois text into a structured dictionary
        whois_data = {}
        for line in result_text.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                cleaned_key = key.strip().lower().replace(" ", "_")
                if cleaned_key in whois_data:
                    # Append if key already exists
                    if not isinstance(whois_data[cleaned_key], list):
                        whois_data[cleaned_key] = [whois_data[cleaned_key]]
                    whois_data[cleaned_key].append(value.strip())
                else:
                    whois_data[cleaned_key] = value.strip()
        return MCPResponse.success(whois_data).to_dict()
    except FileNotFoundError:
        return MCPResponse.error(
            "The 'whois' command is not installed or not in the system's PATH."
        ).to_dict()
    except Exception as e:
        return MCPResponse.error(f"An unexpected error occurred: {e}").to_dict()


@mcp.tool()
async def dns_records(domain: str) -> dict:
    """Get DNS records (A, MX, TXT, NS) for a given domain."""
    try:
        import dns.resolver
    except ImportError:
        return MCPResponse.error(
            "dnspython library is not installed. Please install it with 'pip install dnspython'."
        ).to_dict()

    records = {}
    for rtype in ("A", "MX", "TXT", "NS"):
        try:
            ans = dns.resolver.resolve(domain, rtype, raise_on_no_answer=False)
            if rtype == "A":
                records[rtype] = [r.address for r in ans]
            elif rtype == "MX":
                records[rtype] = sorted([str(r.exchange) for r in ans])
            elif rtype == "TXT":
                records[rtype] = [
                    b"".join(r.strings).decode(errors="replace") for r in ans
                ]
            elif rtype == "NS":
                records[rtype] = sorted([str(r.target) for r in ans])
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            records[rtype] = []
        except Exception as e:
            return MCPResponse.error(f"Error resolving {rtype} records: {e}").to_dict()
    return MCPResponse.success(records).to_dict()


@mcp.tool()
async def enumerate_subdomains(domain: str) -> dict:
    """Enumerate common subdomains for a given domain."""
    try:
        import dns.resolver
    except ImportError:
        return MCPResponse.error(
            "dnspython library is not installed. Please install it with 'pip install dnspython'."
        ).to_dict()

    common_subdomains = [
        "www",
        "mail",
        "api",
        "blog",
        "dev",
        "test",
        "staging",
        "admin",
    ]

    async def resolve_subdomain(sub):
        try:
            fqdn = f"{sub}.{domain}"
            await asyncio.to_thread(dns.resolver.resolve, fqdn, "A")
            return fqdn
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            return None
        except Exception:
            return None

    tasks = [resolve_subdomain(s) for s in common_subdomains]
    results = await asyncio.gather(*tasks)
    found_subdomains = [res for res in results if res]

    return MCPResponse.success(found_subdomains).to_dict()


@mcp.tool()
async def ip_info(ip: str) -> dict:
    """Get geolocation and ASN information for a given IP address."""
    try:
        # Validate if the input is an IP address
        socket.inet_aton(ip)
    except socket.error:
        # If not, try to resolve it as a domain
        try:
            ip = socket.gethostbyname(ip)
        except socket.gaierror:
            return MCPResponse.error(f"Could not resolve host: {ip}").to_dict()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://ipinfo.io/{ip}/json")
            r.raise_for_status()
            return MCPResponse.success(r.json()).to_dict()
    except httpx.HTTPStatusError as e:
        return MCPResponse.error(
            f"ipinfo.io API error: {e.response.status_code} - {e.response.text}"
        ).to_dict()
    except Exception as e:
        return MCPResponse.error(f"An unexpected error occurred: {e}").to_dict()


@mcp.tool()
async def web_stack(domain: str) -> dict:
    """Get basic web stack information for a given domain."""
    try:
        url = f"http://{domain}"
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url)

            techs = set()
            # Check headers
            server = r.headers.get("Server", "").lower()
            if "nginx" in server:
                techs.add("Nginx")
            if "apache" in server:
                techs.add("Apache")
            if "cloudflare" in server:
                techs.add("Cloudflare")

            # Check body content
            html = r.text
            if "wp-content" in html:
                techs.add("WordPress")
            if "Drupal" in html:
                techs.add("Drupal")
            if "jquery" in html:
                techs.add("jQuery")

            result = {
                "headers": {
                    "Server": r.headers.get("Server"),
                    "X-Powered-By": r.headers.get("X-Powered-By"),
                },
                "detected_technologies": sorted(list(techs)),
            }
            return MCPResponse.success(result).to_dict()
    except httpx.RequestError as e:
        return MCPResponse.error(f"Could not connect to {domain}: {e}").to_dict()
    except Exception as e:
        return MCPResponse.error(f"An error occurred: {e}").to_dict()


@mcp.tool()
async def whatsmyip(public: bool = True) -> dict:
    """Get your public or local IP address."""
    if public:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get("https://api.ipify.org")
                r.raise_for_status()
                return MCPResponse.success({"public_ip": r.text.strip()}).to_dict()
        except httpx.RequestError as e:
            return MCPResponse.error(f"Failed to get public IP: {e}").to_dict()
    else:
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return MCPResponse.success({"local_ip": local_ip}).to_dict()
        except Exception as e:
            return MCPResponse.error(f"Failed to get local IP: {e}").to_dict()


@mcp.tool()
async def domain_investigate(domain: str) -> dict:
    """
    Perform comprehensive domain/network reconnaissance for a given domain.
    Returns WHOIS info, DNS records, enumerated subdomains, IP info, and web stack.
    """
    # Resolve domain to IP
    try:
        ip_address = socket.gethostbyname(domain)
    except socket.gaierror as e:
        return MCPResponse.error(
            f"Could not resolve domain {domain} to an IP address: {e}"
        ).to_dict()
    except Exception as e:
        return MCPResponse.error(
            f"An error occurred during IP resolution: {e}"
        ).to_dict()

    # Helper functions to call tools and extract results
    async def call_tool(tool_func, *args):
        result = await tool_func(*args)
        if result.get("status") == "success":
            return result.get("result")
        else:
            return {"error": result.get("message", "Unknown error")}

    # Gather all reconnaissance data
    tasks = {
        "whois": call_tool(whois_info, domain),
        "dns_records": call_tool(dns_records, domain),
        "subdomains": call_tool(enumerate_subdomains, domain),
        "ip_info": call_tool(ip_info, domain),
        "technology_stack": call_tool(web_stack, domain),
    }

    results = await asyncio.gather(*tasks.values())

    # Combine results
    processed_results = {}
    for i, key in enumerate(tasks.keys()):
        processed_results[key] = results[i]

    return MCPResponse.success(processed_results).to_dict()


def main():
    mcp.run()


if __name__ == "__main__":
    main()


@mcp.tool()
async def fetch_as_markdown(url: str) -> dict:
    """Fetch content from a URL and convert it to Markdown."""
    try:
        response = await http_get(url)
        if response["status"] != "success":
            return MCPResponse.error(
                f"Failed to fetch URL: {response['message']}"
            ).to_dict()

        html_content = response["result"]["body"]

        # Attempt to convert HTML to Markdown using html2text
        try:
            markdown_result = await execute(
                code=f"import html2text; h = html2text.HTML2Text(); print(h.handle('{html_content}'))",
                language="python",
                use_sandbox=True,  # Use sandbox for security
            )
            markdown_content = markdown_result["result"]["stdout"]

        except Exception as e:
            return MCPResponse.error(
                f"Failed to convert HTML to Markdown: {e}"
            ).to_dict()

        result = {"url": url, "markdown": markdown_content}
        return MCPResponse.success(result=result).to_dict()

    except Exception as e:
        return MCPResponse.error(f"An unexpected error occurred: {e}").to_dict()
