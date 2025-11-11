"""Tool registry and result types for the middleware system."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ToolResult:
    """Result of a tool execution."""

    status: str  # "success" or "error"
    result: Any = None
    message: Optional[str] = None
