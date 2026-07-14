# Network Tools MCP Server

Consolidated networking tools server providing comprehensive HTTP and network reconnaissance capabilities.

## Available Tools

### HTTP Operations
- **http_get** - Perform HTTP GET requests with custom headers and query parameters
- **http_post** - Perform HTTP POST requests with JSON or form data

Page content as markdown is provided by the third-party **fetch** MCP server (`mcp-server-fetch`), not this server.

### Network Reconnaissance
- **whois_info** - Get WHOIS information for domains
- **dns_records** - Retrieve DNS records (A, MX, TXT, NS)
- **enumerate_subdomains** - Discover common subdomains
- **ip_info** - Get geolocation and ASN information for IP addresses
- **web_stack** - Detect web technologies (server, CMS, frameworks)
- **whatsmyip** - Get your public or local IP address
- **domain_investigate** - Comprehensive domain investigation (combines all reconnaissance tools)

## Dependencies

- **httpx** - Modern async HTTP client
- **dnspython** (optional) - Required for DNS-related tools
- **whois** command-line tool (optional) - Required for WHOIS lookups

Markdown page fetching lives in the separate **fetch** MCP server (`uvx mcp-server-fetch`).

## History

This server was consolidated from two separate servers:
- `network/server.py` - Basic HTTP operations
- `advanced_networking/server.py` - Network reconnaissance tools

Consolidation completed: November 12, 2025

