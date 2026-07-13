"""Tests for MCPConfig persistence helpers."""

import json
from pathlib import Path

from badmcp.config import MCPConfig


def test_upsert_and_delete_server(tmp_path: Path):
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    config = MCPConfig(str(path))
    saved = config.upsert_server(
        "demo",
        {
            "command": "python",
            "args": ["src/tools/demo/server.py"],
            "description": "Demo",
            "env": {"PYTHONPATH": "/app/agent/src"},
        },
    )
    assert saved["command"] == "python"
    assert "demo" in config.list_servers()

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "demo" in raw["mcpServers"]
    assert raw["mcpServers"]["demo"]["args"] == ["src/tools/demo/server.py"]

    listed = config.list_server_definitions(mask_secrets=True)
    assert listed[0]["name"] == "demo"

    assert config.delete_server("demo") is True
    assert "demo" not in config.list_servers()


def test_masked_bearer_token_preserved(tmp_path: Path):
    path = tmp_path / "mcp.json"
    path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "remote": {
                        "url": "http://example/mcp",
                        "type": "sse",
                        "bearerToken": "supersecrettoken",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    config = MCPConfig(str(path))
    listed = config.list_server_definitions(mask_secrets=True)
    assert listed[0]["bearerToken"].startswith("***")

    config.upsert_server(
        "remote",
        {
            "url": "http://example/mcp",
            "type": "sse",
            "bearerToken": listed[0]["bearerToken"],
        },
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["mcpServers"]["remote"]["bearerToken"] == "supersecrettoken"
