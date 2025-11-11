import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch



class TestAdvancedNetworkingServer(unittest.IsolatedAsyncioTestCase):
    """Test suite for advanced_networking tool"""

    async def test_whois_info_success(self):
        """Test successful WHOIS lookup"""
        from src.tools.advanced_networking.server import mcp

        whois_info = mcp._tool_manager.get_tool("whois_info")

        mock_whois_output = """Registrar: Example Registrar, Inc.
Creation Date: 2020-01-15T10:00:00Z
Expiration Date: 2025-01-15T10:00:00Z
Name Server: ns1.example.com
Name Server: ns2.example.com
Email: admin@example.com
"""

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(mock_whois_output.encode(), b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await whois_info.run({"domain": "example.com"})

        # New format returns raw key-value pairs
        self.assertIn("registrar", result.result)
        self.assertEqual(result.result["registrar"], "Example Registrar, Inc.")
        self.assertIn("creation_date", result.result)
        self.assertIn("expiration_date", result.result)
        self.assertIn("email", result.result)

    async def test_whois_info_failure(self):
        """Test WHOIS lookup with error"""
        from src.tools.advanced_networking.server import mcp

        whois_info = mcp._tool_manager.get_tool("whois_info")

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"Domain not found"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await whois_info.run({"domain": "invalid-domain.com"})

        # Should return empty result when returncode is not 0
        self.assertEqual(result.result, None)

    async def test_whois_info_exception(self):
        """Test WHOIS lookup with exception"""
        from src.tools.advanced_networking.server import mcp

        whois_info = mcp._tool_manager.get_tool("whois_info")

        with patch(
            "asyncio.create_subprocess_exec", side_effect=Exception("Command failed")
        ):
            result = await whois_info.run({"domain": "example.com"})

        self.assertEqual(result.status, "error")
        self.assertIn("Command failed", result.message)

    async def test_dns_records_success(self):
        """Test successful DNS record lookup"""
        from src.tools.advanced_networking.server import mcp

        dns_records = mcp._tool_manager.get_tool("dns_records")

        # Mock A records
        mock_a_record = MagicMock()
        mock_a_record.address = "93.184.216.34"

        # Mock MX records
        mock_mx_record = MagicMock()
        mock_mx_record.exchange = "mail.example.com"

        # Mock TXT records
        mock_txt_record = MagicMock()
        mock_txt_record.strings = [b"v=spf1 include:example.com ~all"]

        # Mock NS records
        mock_ns_record = MagicMock()
        mock_ns_record.target = "ns1.example.com"

        def mock_resolve(
            domain, rtype, raise_on_no_answer=False
        ):  # pylint: disable=unused-argument
            if rtype == "A":
                return [mock_a_record]
            elif rtype == "MX":
                return [mock_mx_record]
            elif rtype == "TXT":
                return [mock_txt_record]
            elif rtype == "NS":
                return [mock_ns_record]
            return []

        with patch("dns.resolver.resolve", side_effect=mock_resolve):
            result = await dns_records.run({"domain": "example.com"})

        self.assertEqual(result.result["A"], ["93.184.216.34"])
        self.assertEqual(result.result["MX"], ["mail.example.com"])
        self.assertIn("v=spf1", result.result["TXT"][0])
        self.assertEqual(result.result["NS"], ["ns1.example.com"])

    async def test_dns_records_dnspython_not_installed(self):
        """Test DNS records when dnspython is not installed"""
        from src.tools.advanced_networking.server import mcp

        dns_records = mcp._tool_manager.get_tool("dns_records")

        with patch("builtins.__import__", side_effect=ImportError):
            result = await dns_records.run({"domain": "example.com"})

        self.assertEqual(result.status, "error")
        self.assertIn("dnspython library is not installed", result.message)

    async def test_dns_records_partial_failure(self):
        """Test DNS records with some records failing"""
        from src.tools.advanced_networking.server import mcp

        dns_records = mcp._tool_manager.get_tool("dns_records")

        mock_a_record = MagicMock()
        mock_a_record.address = "93.184.216.34"

        def mock_resolve(
            domain, rtype, raise_on_no_answer=False
        ):  # pylint: disable=unused-argument
            if rtype == "A":
                return [mock_a_record]
            else:
                raise Exception(
                    "DNS query failed"
                )  # pylint: disable=broad-exception-raised

        with patch("dns.resolver.resolve", side_effect=mock_resolve):
            result = await dns_records.run({"domain": "example.com"})

        self.assertEqual(result.status, "error")
        self.assertIn("Error resolving", result.message)

    async def test_enumerate_subdomains_success(self):
        """Test successful subdomain enumeration"""
        from src.tools.advanced_networking.server import mcp

        enumerate_subdomains = mcp._tool_manager.get_tool("enumerate_subdomains")

        def mock_resolve(fqdn, rtype):  # pylint: disable=unused-argument
            # Only www and mail subdomains exist
            if fqdn in ["www.example.com", "mail.example.com"]:
                return [MagicMock()]
            raise Exception("NXDOMAIN")  # pylint: disable=broad-exception-raised

        with patch("dns.resolver.resolve", side_effect=mock_resolve):
            result = await enumerate_subdomains.run({"domain": "example.com"})

        self.assertIn("www.example.com", result.result)
        self.assertIn("mail.example.com", result.result)
        self.assertNotIn("nonexistent.example.com", result.result)

    async def test_enumerate_subdomains_dnspython_not_installed(self):
        """Test subdomain enumeration when dnspython is not installed"""
        from src.tools.advanced_networking.server import mcp

        enumerate_subdomains = mcp._tool_manager.get_tool("enumerate_subdomains")

        with patch("builtins.__import__", side_effect=ImportError):
            result = await enumerate_subdomains.run({"domain": "example.com"})

        self.assertEqual(result.status, "error")
        self.assertIn("dnspython library is not installed", result.message)

    async def test_ip_info_success(self):
        """Test successful IP info lookup"""
        from src.tools.advanced_networking.server import mcp

        ip_info = mcp._tool_manager.get_tool("ip_info")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ip": "93.184.216.34",
            "city": "Norwell",
            "country": "US",
            "org": "AS15133 Edgecast Inc.",
            "hostname": "example.com",
        }

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await ip_info.run({"ip": "example.com"})

        self.assertEqual(result.result["ip"], "93.184.216.34")
        self.assertEqual(result.result["city"], "Norwell")
        self.assertEqual(result.result["country"], "US")
        self.assertEqual(result.result["org"], "AS15133 Edgecast Inc.")
        self.assertEqual(result.result["hostname"], "example.com")

    async def test_ip_info_httpx_exception(self):
        """Test IP info when httpx raises exception"""
        from src.tools.advanced_networking.server import mcp

        ip_info = mcp._tool_manager.get_tool("ip_info")

        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            with patch("httpx.AsyncClient", side_effect=Exception("Connection failed")):
                result = await ip_info.run({"ip": "example.com"})

        self.assertEqual(result.status, "error")
        self.assertIn("Connection failed", result.message)

    async def test_ip_info_socket_exception(self):
        """Test IP info with socket exception"""
        from mcp.server.fastmcp.exceptions import ToolError

        from src.tools.advanced_networking.server import mcp

        ip_info = mcp._tool_manager.get_tool("ip_info")

        with self.assertRaises(ToolError):
            with patch("socket.gethostbyname", side_effect=Exception("Host not found")):
                await ip_info.run({"ip": "invalid-domain.com"})

    async def test_web_stack_success(self):
        """Test successful web stack detection"""
        from src.tools.advanced_networking.server import mcp

        web_stack = mcp._tool_manager.get_tool("web_stack")

        mock_response = MagicMock()
        mock_response.headers = {
            "Server": "nginx/1.18.0",
            "X-Powered-By": "PHP/7.4.3",
        }
        mock_response.text = """
        <html>
        <head>
            <script src="/wp-content/themes/example/script.js"></script>
            <script src="https://cdn.example.com/jquery-3.6.0.min.js"></script>
            <script src="https://cdn.example.com/bootstrap.min.js"></script>
        </head>
        <body>Some content</body>
        </html>
        """

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await web_stack.run({"domain": "example.com"})

        self.assertEqual(result.result["headers"]["Server"], "nginx/1.18.0")
        self.assertEqual(result.result["headers"]["X-Powered-By"], "PHP/7.4.3")
        self.assertIn("WordPress", result.result["detected_technologies"])
        self.assertIn("jQuery", result.result["detected_technologies"])

    async def test_web_stack_httpx_exception(self):
        """Test web stack when httpx raises exception"""
        from src.tools.advanced_networking.server import mcp

        web_stack = mcp._tool_manager.get_tool("web_stack")

        with patch("httpx.AsyncClient", side_effect=Exception("Connection failed")):
            result = await web_stack.run({"domain": "example.com"})

        self.assertEqual(result.status, "error")
        self.assertIn("An error occurred", result.message)

    async def test_web_stack_http_error_status(self):
        """Test web stack with HTTP error status"""
        from src.tools.advanced_networking.server import mcp

        web_stack = mcp._tool_manager.get_tool("web_stack")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.headers = {}

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await web_stack.run({"domain": "nonexistent-domain.com"})

        # Should still return result with empty/None values
        self.assertIn("headers", result.result)

    async def test_call_tool_domain_investigate_success(self):
        """Test domain_investigate tool call success"""
        from src.tools.advanced_networking.server import mcp

        call_tool = mcp.call_tool

        from models import MCPResponse

        # Mock all the individual functions
        mock_whois = MCPResponse.success({"registrar": "Example Registrar"})
        mock_dns = MCPResponse.success({"A": ["93.184.216.34"]})
        mock_subdomains = MCPResponse.success(["www.example.com"])
        mock_ipinfo = MCPResponse.success({"ip": "93.184.216.34"})
        mock_webstack = MCPResponse.success({"server_header": "nginx"})

        with patch(
            "src.tools.advanced_networking.server.whois_info",
            return_value=mock_whois,
        ):
            with patch(
                "src.tools.advanced_networking.server.dns_records",
                return_value=mock_dns,
            ):
                with patch(
                    "src.tools.advanced_networking.server.enumerate_subdomains",
                    return_value=mock_subdomains,
                ):
                    with patch(
                        "src.tools.advanced_networking.server.ip_info",
                        return_value=mock_ipinfo,
                    ):
                        with patch(
                            "src.tools.advanced_networking.server.web_stack",
                            return_value=mock_webstack,
                        ):
                            result = await call_tool(
                                "domain_investigate", {"domain": "example.com"}
                            )

        result_data = json.loads(result[0].text)
        self.assertEqual(result_data["status"], "success")
        self.assertEqual(result_data["result"]["whois"], mock_whois.result)
        self.assertEqual(result_data["result"]["dns_records"], mock_dns.result)
        self.assertEqual(result_data["result"]["subdomains"], mock_subdomains.result)
        self.assertEqual(result_data["result"]["ip_info"], mock_ipinfo.result)
        self.assertEqual(
            result_data["result"]["technology_stack"], mock_webstack.result
        )

    async def test_call_tool_domain_investigate_missing_domain(self):
        """Test domain_investigate tool call with missing domain"""
        from src.tools.advanced_networking.server import mcp

        call_tool = mcp.call_tool

        with self.assertRaises(Exception):
            await call_tool("domain_investigate", {})

    async def test_call_tool_unknown_tool(self):
        """Test call_tool with unknown tool name"""
        from src.tools.advanced_networking.server import mcp

        call_tool = mcp.call_tool

        with self.assertRaises(Exception):
            await call_tool("unknown_tool", {})

    async def test_list_tools(self):
        """Test list_tools returns correct tool definitions"""
        from src.tools.advanced_networking.server import mcp

        list_tools = mcp.list_tools

        tools = await list_tools()

        # Now has 7 tools: domain_investigate, dns_records, enumerate_subdomains, ip_info, web_stack, whois_info, whatsmyip
        self.assertEqual(len(tools), 7)

        tool_names = [tool.name for tool in tools]
        self.assertIn("domain_investigate", tool_names)
        self.assertIn("dns_records", tool_names)
        self.assertIn("enumerate_subdomains", tool_names)
        self.assertIn("ip_info", tool_names)
        self.assertIn("web_stack", tool_names)
        self.assertIn("whois_info", tool_names)
        self.assertIn("whatsmyip", tool_names)


if __name__ == "__main__":
    unittest.main()
