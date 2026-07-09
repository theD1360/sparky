"""Wrapper for LangChain tools to route through middleware."""

import logging
from typing import Any, Dict, Optional

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class MiddlewareToolWrapper(BaseTool):
    """Wraps a LangChain tool to route calls through middleware."""

    def __init__(
        self,
        original_tool: BaseTool,
        execute_tool_callback: Any,
    ):
        """Initialize the middleware wrapper.

        Args:
            original_tool: The original LangChain tool to wrap
            execute_tool_callback: Callback function that routes through middleware
        """
        super().__init__(
            name=original_tool.name,
            description=original_tool.description,
            args_schema=original_tool.args_schema,
        )
        self.original_tool = original_tool
        self.execute_tool_callback = execute_tool_callback

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Async execution that routes through middleware."""
        # Call the middleware callback which will execute the tool
        # The middleware will eventually call the original tool
        tool_result = await self.execute_tool_callback(self.name, kwargs)

        # Return the result (middleware already handled execution)
        # If middleware returned an error, raise it
        if tool_result.status == "error":
            raise Exception(tool_result.message)
        return tool_result.result

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Sync execution - not used but required by BaseTool."""
        raise NotImplementedError("Use async execution (_arun) instead")
