"""Middleware dispatchers for processing requests through middleware chains.

This module contains the dispatcher classes that handle execution of middleware
chains for different types of requests (tool calls, messages, responses).
"""

import functools

from .base import MessageContext, ResponseContext, ToolCallContext
from ..tool_registry import ToolResult


class MessageDispatcher:
    """Dispatcher for message middleware."""

    def __init__(self, bot_instance):
        self._middlewares: list = []
        self._bot = bot_instance

    def add_middleware(self, mw):
        self._middlewares.append(mw)

    async def dispatch(self, message: str) -> MessageContext:
        """Process a message through the middleware chain.
        
        Args:
            message: The user message string
            
        Returns:
            MessageContext with potentially modified message
        """
        # Create context from message string
        context = MessageContext(message=message, bot_instance=self._bot)

        # The final action in the chain is to just return the context
        async def final_action(ctx: MessageContext) -> MessageContext:
            return ctx

        # Build the chain of calls, starting from the end
        chain = final_action
        for mw in reversed(self._middlewares):
            # Each 'next' call becomes the previously wrapped part of the chain
            chain = functools.partial(mw, next_call=chain)

        return await chain(context)


class ResponseDispatcher:
    """Dispatcher for response middleware."""

    def __init__(self, bot_instance):
        self._middlewares: list = []
        self._bot = bot_instance

    def add_middleware(self, mw):
        self._middlewares.append(mw)

    async def dispatch(self, context: ResponseContext) -> ResponseContext:
        """Process a response through the middleware chain."""

        # The final action in the chain is to just return the context
        async def final_action(ctx: ResponseContext) -> ResponseContext:
            return ctx

        # Build the chain of calls, starting from the end
        chain = final_action
        for mw in reversed(self._middlewares):
            # Each 'next' call becomes the previously wrapped part of the chain
            chain = functools.partial(mw, next_call=chain)

        return await chain(context)


class ToolDispatcher:
    """Dispatcher for tool call middleware."""

    def __init__(self, bot_instance):
        self._middlewares: list = []
        self._bot = bot_instance

    def add_middleware(self, mw):
        self._middlewares.append(mw)

    async def dispatch(self, context: ToolCallContext) -> ToolResult:
        """Process a tool call through the middleware chain."""

        # The final action in the chain is the actual tool execution
        async def final_action(ctx: ToolCallContext) -> ToolCallContext:
            try:
                tool_result = await self._bot.toolchain.call(
                    ctx.tool_name, ctx.tool_args
                )
                ctx.result = ToolResult(status="success", result=tool_result)
            except Exception as e:
                ctx.result = ToolResult(status="error", message=str(e))
            return ctx

        # Build the chain of calls, starting from the end
        chain = final_action
        for mw in reversed(self._middlewares):
            # Each 'next' call becomes the previously wrapped part of the chain
            chain = functools.partial(mw, next_call=chain)

        final_context = await chain(context)
        return final_context.result

