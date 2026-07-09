"""LangChain callback handlers for event dispatching."""

import logging
from typing import Any, Dict, List, Optional

from events import BotEvents
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class LangChainEventCallbackHandler(AsyncCallbackHandler):
    """Callback handler that dispatches events for tool calls and thoughts."""

    def __init__(self, events: Any, executed_tool_calls: List[Dict[str, Any]]):
        """Initialize the callback handler.

        Args:
            events: Events system for dispatching events
            executed_tool_calls: List to append executed tool calls to
        """
        super().__init__()
        self.events = events
        self.executed_tool_calls = executed_tool_calls

    async def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Called when the LLM starts running."""
        # Extract thinking text from prompts if available
        if prompts:
            thinking_text = (
                prompts[0] if isinstance(prompts[0], str) else str(prompts[0])
            )
            if thinking_text and thinking_text.strip():
                await self.events.async_dispatch(BotEvents.THOUGHT, thinking_text)

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Called when a new token is generated."""
        # Could dispatch streaming events here if needed
        pass

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when the LLM finishes running."""
        # Extract thinking text from response if available
        # LLMResult contains generations which may have thinking text
        if response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    if hasattr(gen, "message") and hasattr(gen.message, "content"):
                        content = str(gen.message.content)
                        # If there are tool calls, the content is the thinking text
                        if (
                            hasattr(gen.message, "tool_calls")
                            and gen.message.tool_calls
                        ):
                            if content and content.strip():
                                await self.events.async_dispatch(
                                    BotEvents.THOUGHT, content
                                )

    async def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """Called when a tool starts running.

        Args:
            serialized: Serialized tool information
            input_str: Input string to the tool (can be dict or string)
        """
        tool_name = serialized.get("name", "")
        # Parse input_str to get tool args
        # input_str might be a dict already or a JSON string
        if isinstance(input_str, dict):
            tool_args = input_str
        else:
            try:
                import json

                tool_args = json.loads(input_str) if input_str else {}
            except (json.JSONDecodeError, TypeError):
                tool_args = {"input": input_str} if input_str else {}

        # Log the tool call
        self.executed_tool_calls.append({"name": tool_name, "arguments": tool_args})

        # Dispatch tool use event
        await self.events.async_dispatch(BotEvents.TOOL_USE, tool_name, tool_args)

    async def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Called when a tool finishes running.

        Args:
            output: Output from the tool
        """
        # Get tool name from kwargs if available
        tool_name = kwargs.get("name", "")
        if not tool_name and "serialized" in kwargs:
            tool_name = kwargs["serialized"].get("name", "")

        # Dispatch tool result event
        await self.events.async_dispatch(
            BotEvents.TOOL_RESULT, tool_name, output, "success"
        )

    async def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        """Called when a tool encounters an error.

        Args:
            error: The error that occurred
        """
        tool_name = kwargs.get("name", "")
        if not tool_name and "serialized" in kwargs:
            tool_name = kwargs["serialized"].get("name", "")

        error_msg = str(error)
        await self.events.async_dispatch(
            BotEvents.TOOL_RESULT, tool_name, error_msg, "error"
        )
