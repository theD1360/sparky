from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from models import MCPResponse


# Initialize the MCP server
mcp = FastMCP("criminal-ip-tools")

load_dotenv()


def _get_api_key() -> tuple[str | None, str | None]:
    """Get API key from environment. Returns (api_key, error_message)."""
    api_key = os.getenv("CRIMINAL_IP_KEY")
    if not api_key:
        return (
            None,
            "CRIMINAL_IP_KEY environment variable is required. Get your API key from https://www.criminalip.io/",
        )
    return api_key, None


async def _make_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Helper function to make HTTP requests with httpx."""
    try:
        response = await client.request(
            method, url, headers=headers, params=params, json=data, timeout=30
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise ValueError(f"HTTP error: {e.response.status_code} - {e.response.text}")
    except httpx.TimeoutException:
        raise TimeoutError("Request timed out")
    except Exception as e:
        raise RuntimeError(f"Request failed: {e}")


@mcp.tool()
async def criminal_ip_lookup(ip: str) -> dict:
    """Get comprehensive threat intelligence data for an IP address."""
    try:
        api_key, error = _get_api_key()
        if error:
            return MCPResponse.error(error).to_dict()

        headers = {"x-api-key": api_key}
        base_url = "https://api.criminalip.io/v1"
        url = f"{base_url}/ip/data?ip={ip}"

        async with httpx.AsyncClient() as client:
            result = await _make_request(client, "GET", url, headers=headers)

        return MCPResponse.success(result=result).to_dict()

    except ValueError as e:
        return MCPResponse.error(str(e)).to_dict()
    except TimeoutError:
        return MCPResponse.error("Request timed out. Please try again.").to_dict()
    except Exception as e:
        return MCPResponse.error(f"An unexpected error occurred: {e}").to_dict()


@mcp.tool()
async def criminal_ip_domain_scan(domain: str) -> dict:
    """Get domain information including DNS records, hosting info, and security assessment."""
    retries = 3
    for attempt in range(retries):
        try:
            api_key, error = _get_api_key()
            if error:
                return MCPResponse.error(error).to_dict()

            headers = {"x-api-key": api_key}
            base_url = "https://api.criminalip.io/v1"
            url = f"{base_url}/domain/scan"

            async with httpx.AsyncClient() as client:
                result = await _make_request(
                    client, "POST", url, headers=headers, data={"query": domain}
                )
                return MCPResponse.success(result=result).to_dict()

        except ValueError as e:
            error_detail = str(e)
            if "HTTP error: 502" in error_detail or "HTTP error: 503" in error_detail or "HTTP error: 504" in error_detail:
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue  # Retry on temporary errors
            return MCPResponse.error(error_detail).to_dict()
        except TimeoutError:
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue  # Retry on timeout
            return MCPResponse.error("Request timed out after multiple retries.").to_dict()
        except Exception as e:
            return MCPResponse.error(f"An unexpected error occurred: {e}").to_dict()

    return MCPResponse.error("Failed to complete request after multiple retries.").to_dict()


@mcp.tool()
async def criminal_ip_banner_search(query: str, offset: int = 0) -> dict:
    """Search for banners (service information) across the internet."""
    try:
        api_key, error = _get_api_key()
        if error:
            return MCPResponse.error(error).to_dict()

        headers = {"x-api-key": api_key}
        base_url = "https://api.criminalip.io/v1"
        url = f"{base_url}/banner/search?query={query}&offset={offset}"

        async with httpx.AsyncClient() as client:
            result = await _make_request(client, "GET", url, headers=headers)
        return MCPResponse.success(result=result).to_dict()

    except ValueError as e:
        return MCPResponse.error(str(e)).to_dict()
    except TimeoutError:
        return MCPResponse.error("Request timed out. Please try again.").to_dict()
    except Exception as e:
        return MCPResponse.error(f"An unexpected error occurred: {e}").to_dict()


@mcp.tool()
async def criminal_ip_asset_search(query: str, offset: int = 0) -> dict:
    """Search for assets (domains, IPs) by organization, ASN, or other criteria."""
    try:
        api_key, error = _get_api_key()
        if error:
            return MCPResponse.error(error).to_dict()

        headers = {"x-api-key": api_key}
        base_url = "https://api.criminalip.io/v1"
        url = f"{base_url}/asset/search?query={query}&offset={offset}"

        async with httpx.AsyncClient() as client:
            result = await _make_request(client, "GET", url, headers=headers)
        return MCPResponse.success(result=result).to_dict()

    except ValueError as e:
        return MCPResponse.error(str(e)).to_dict()
    except TimeoutError:
        return MCPResponse.error("Request timed out. Please try again.").to_dict()
    except Exception as e:
        return MCPResponse.error(f"An unexpected error occurred: {e}").to_dict()


@mcp.tool()
async def criminal_ip_exploit_search(query: str, offset: int = 0) -> dict:
    """Search for known exploits and vulnerabilities associated with services or technologies."""
    try:
        api_key, error = _get_api_key()
        if error:
            return MCPResponse.error(error).to_dict()

        headers = {"x-api-key": api_key}
        base_url = "https://api.criminalip.io/v1"
        url = f"{base_url}/exploit/search?query={query}&offset={offset}"

        async with httpx.AsyncClient() as client:
            result = await _make_request(client, "GET", url, headers=headers)
        return MCPResponse.success(result=result).to_dict()

    except ValueError as e:
        return MCPResponse.error(str(e)).to_dict()
    except TimeoutError:
        return MCPResponse.error("Request timed out. Please try again.").to_dict()
    except Exception as e:
        return MCPResponse.error(f"An unexpected error occurred: {e}").to_dict()


@mcp.tool()
async def criminal_ip_user_info() -> dict:
    """Get information about the current API user including plan details and usage statistics."""
    try:
        api_key, error = _get_api_key()
        if error:
            return MCPResponse.error(error).to_dict()

        headers = {"x-api-key": api_key}
        base_url = "https://api.criminalip.io/v1"
        url = f"{base_url}/user/me"

        async with httpx.AsyncClient() as client:
            result = await _make_request(client, "POST", url, headers=headers)
        return MCPResponse.success(result=result).to_dict()

    except ValueError as e:
        return MCPResponse.error(str(e)).to_dict()
    except TimeoutError:
        return MCPResponse.error("Request timed out. Please try again.").to_dict()
    except Exception as e:
        return MCPResponse.error(f"An unexpected error occurred: {e}").to_dict()


def main():
    mcp.run()


if __name__ == "__main__":
    main()
