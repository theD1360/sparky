"""Wrapper for LangChain tools to route through middleware."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import ConfigDict, PrivateAttr

logger = logging.getLogger(__name__)


class MiddlewareToolWrapper(BaseTool):
    """Wraps a LangChain tool to route calls through middleware.

    Uses PrivateAttr so Pydantic BaseTool does not reject custom fields.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _original_tool: BaseTool = PrivateAttr()
    _execute_tool_callback: Any = PrivateAttr()

    def __init__(
        self,
        original_tool: BaseTool,
        execute_tool_callback: Any,
    ):
        super().__init__(
            name=original_tool.name,
            description=original_tool.description,
            args_schema=original_tool.args_schema,
        )
        self._original_tool = original_tool
        self._execute_tool_callback = execute_tool_callback

    @property
    def original_tool(self) -> BaseTool:
        return self._original_tool

    @property
    def execute_tool_callback(self) -> Any:
        return self._execute_tool_callback

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Async execution that routes through middleware."""
        tool_result = await self._execute_tool_callback(self.name, kwargs)
        if tool_result.status == "error":
            raise Exception(tool_result.message)
        return tool_result.result

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync execution - not used but required by BaseTool."""
        raise NotImplementedError("Use async execution (_arun) instead")
