"""MCP (Model Context Protocol) integration module.

To avoid circular import issues during debugging or different entry points,
we use lazy imports (PEP 562) for re-exported symbols instead of importing
submodules at package import time.
"""

__all__ = [
    "MCPConfig",
    "MCPServerConfig",
    "MultiMCPBot",
    "run_chat_with_mcp_config",
]


def __getattr__(name: str):
    if name in ("MCPConfig", "MCPServerConfig"):
        from .config import MCPConfig, MCPServerConfig

        mapping = {
            "MCPConfig": MCPConfig,
            "MCPServerConfig": MCPServerConfig,
        }
        return mapping[name]
    if name in ("MultiMCPBot", "run_chat_with_mcp_config"):
        from .multi_client import MultiMCPBot, run_chat_with_mcp_config

        mapping = {
            "MultiMCPBot": MultiMCPBot,
            "run_chat_with_mcp_config": run_chat_with_mcp_config,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)
