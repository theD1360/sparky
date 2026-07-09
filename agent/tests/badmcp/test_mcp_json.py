"""Tests for badmcp.mcp_json connection parsing."""

import pytest

from badmcp.mcp_json import parse_mcp_json_to_connections, server_entry_to_connection


class TestServerEntryToConnection:
    def test_stdio_server(self):
        conn = server_entry_to_connection(
            "knowledge",
            {"command": "python", "args": ["server.py"], "env": {"FOO": "bar"}},
        )
        assert conn == {
            "transport": "stdio",
            "command": "python",
            "args": ["server.py"],
            "env": {"FOO": "bar"},
        }

    def test_sse_server(self):
        conn = server_entry_to_connection(
            "meta",
            {"url": "http://localhost/mcp/sse", "type": "sse"},
        )
        assert conn == {"transport": "sse", "url": "http://localhost/mcp/sse"}

    def test_streamable_http_server(self):
        conn = server_entry_to_connection(
            "sparky",
            {
                "url": "http://localhost:8000/mcp",
                "transport": "streamable_http",
                "headers": {"X-Key": "secret"},
            },
        )
        assert conn == {
            "transport": "streamable_http",
            "url": "http://localhost:8000/mcp",
            "headers": {"X-Key": "secret"},
        }

    def test_bearer_token_becomes_header(self):
        conn = server_entry_to_connection(
            "meta",
            {"url": "http://localhost/mcp", "bearerToken": "tok123"},
        )
        assert conn["headers"]["Authorization"] == "Bearer tok123"

    def test_disabled_server_returns_none(self):
        assert server_entry_to_connection("x", {"disabled": True, "command": "python"}) is None


class TestParseMcpJsonToConnections:
    def test_claude_desktop_format(self):
        data = {
            "mcpServers": {
                "shell": {"command": "python", "args": ["shell.py"]},
                "remote": {"url": "http://host/mcp", "type": "sse"},
            }
        }
        connections = parse_mcp_json_to_connections(data)
        assert set(connections.keys()) == {"shell", "remote"}
        assert connections["shell"]["transport"] == "stdio"
        assert connections["remote"]["transport"] == "sse"

    def test_invalid_root_raises(self):
        with pytest.raises(ValueError, match="mcpServers"):
            parse_mcp_json_to_connections({"mcpServers": "bad"})
