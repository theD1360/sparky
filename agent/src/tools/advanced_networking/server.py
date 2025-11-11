from __future__ import annotations

import asyncio
import socket

import httpx
from mcp.server.fastmcp import FastMCP

from models import MCPResponse

mcp = FastMCP("advanced-networking")


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
            return MCPResponse.error("whois command failed or returned no output.")

        result_text = stdout.decode(errors="ignore")
        if result_text.startswith("No match for"):
            return MCPResponse.error("No WHOIS record found for the domain.")

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
        return MCPResponse.success(whois_data)
    except FileNotFoundError:
        return MCPResponse.error(
            "The 'whois' command is not installed or not in the system's PATH."
        )
    except Exception as e:
        return MCPResponse.error(f"An unexpected error occurred: {e}")


@mcp.tool()
async def dns_records(domain: str) -> dict:
    """Get DNS records (A, MX, TXT, NS) for a given domain."""
    try:
        import dns.resolver
    except ImportError:
        return MCPResponse.error(
            "dnspython library is not installed. Please install it with 'pip install dnspython'."
        )

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
            return MCPResponse.error(f"Error resolving {rtype} records: {e}")
    return MCPResponse.success(records)


@mcp.tool()
async def enumerate_subdomains(domain: str) -> dict:
    """Enumerate common subdomains for a given domain."""
    try:
        import dns.resolver
    except ImportError:
        return MCPResponse.error(
            "dnspython library is not installed. Please install it with 'pip install dnspython'."
        )

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

    return MCPResponse.success(found_subdomains)


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
            return MCPResponse.error(f"Could not resolve host: {ip}")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://ipinfo.io/{ip}/json")
            r.raise_for_status()
            return MCPResponse.success(r.json())
    except httpx.HTTPStatusError as e:
        return MCPResponse.error(
            f"ipinfo.io API error: {e.response.status_code} - {e.response.text}"
        )
    except Exception as e:
        return MCPResponse.error(f"An unexpected error occurred: {e}")


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
            return MCPResponse.success(result)
    except httpx.RequestError as e:
        return MCPResponse.error(f"Could not connect to {domain}: {e}")
    except Exception as e:
        return MCPResponse.error(f"An error occurred: {e}")


@mcp.tool()
async def whatsmyip(public: bool = True) -> dict:
    """Get your public or local IP address."""
    if public:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get("https://api.ipify.org")
                r.raise_for_status()
                return MCPResponse.success({"public_ip": r.text.strip()})
        except httpx.RequestError as e:
            return MCPResponse.error(f"Failed to get public IP: {e}")
    else:
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return MCPResponse.success({"local_ip": local_ip})
        except Exception as e:
            return MCPResponse.error(f"Failed to get local IP: {e}")


@mcp.tool()
async def domain_investigate(domain: str) -> dict:
    """
    Perform comprehensive domain/network reconnaissance for a given domain.
    Returns WHOIS info, DNS records, enumerated subdomains, IP info, and web stack.
    """
    # We call the underlying functions directly, not as tools
    tasks = {
        "whois": whois_info(domain),
        "dns_records": dns_records(domain),
        "subdomains": enumerate_subdomains(domain),
        "ip_info": ip_info(domain),
        "technology_stack": web_stack(domain),
    }

    results = await asyncio.gather(*tasks.values())

    # Process results, extracting the 'result' from successful MCPResponses
    processed_results = {}
    for i, key in enumerate(tasks.keys()):
        response = results[i]
        if response.status == "success":
            processed_results[key] = response.result
        else:
            processed_results[key] = {"error": response.message}

    return MCPResponse.success(processed_results)


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
