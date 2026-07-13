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
        # Do not treat prompts as thoughts — they include the full chat transcript
        # (e.g. "Human: ...") and were being saved as thought bubbles.
        return

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Called when a new token is generated."""
        # Could dispatch streaming events here if needed
        pass

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when the LLM finishes running."""
        # Only emit thoughts when the model produced reasoning ahead of tool calls.
        if not response.generations:
            return
        for gen_list in response.generations:
            for gen in gen_list:
                message = getattr(gen, "message", None)
                if message is None:
                    continue
                tool_calls = getattr(message, "tool_calls", None)
                if not tool_calls:
                    continue
                content = getattr(message, "content", None)
                text = _normalize_llm_content(content)
                if text and text.strip():
                    await self.events.async_dispatch(BotEvents.THOUGHT, text.strip())


def _normalize_llm_content(content: Any) -> str:
    """Flatten structured LLM content into plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text") or part.get("thinking")
                if text:
                    parts.append(str(text))
            else:
                text = getattr(part, "text", None)
                if text:
                    parts.append(str(text))
        return "\n".join(p for p in parts if p).strip()
    return str(content)

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
