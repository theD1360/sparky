"""Base classes and types for the middleware system.

This module provides the core middleware infrastructure including base classes,
context objects, and type definitions used throughout the middleware system.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, Union

logger = logging.getLogger(__name__)


class MiddlewareType(Enum):
    """Type of middleware for automatic routing."""

    TOOL = "tool"
    MESSAGE = "message"
    RESPONSE = "response"


# ============================================================================
# CONTEXT OBJECTS
# ============================================================================


@dataclass
class ToolCallContext:
    """Context object passed through the tool call middleware chain."""

    tool_name: str
    tool_args: dict
    result: Any = None  # Will be set to ToolResult after execution
    bot_instance: Optional[Any] = None  # Reference to bot for accessing toolchain


@dataclass
class MessageContext:
    """Context object passed through the message middleware chain."""

    message: str  # The original user message
    modified_message: Optional[str] = None  # Modified message to send to model
    skip_model: bool = False  # If True, skip sending to model entirely
    response: Optional[str] = None  # Direct response (if skip_model is True)
    bot_instance: Optional[Any] = None  # Reference to bot for accessing methods


@dataclass
class ResponseContext:
    """Context object passed through the response middleware chain."""

    response: str  # The original model response
    modified_response: Optional[str] = None  # Modified response to return to user
    user_message: Optional[str] = None  # The original user message (for context)
    metadata: Optional[dict] = None  # Additional metadata about the response
    bot_instance: Optional[Any] = None  # Reference to bot for accessing methods


# ============================================================================
# TYPE ALIASES
# ============================================================================

# Context can be any of these types
MiddlewareContext = Union[ToolCallContext, MessageContext, ResponseContext]

# The "next" function signatures for the middleware chain
NextToolMiddleware = Callable[[ToolCallContext], Awaitable[ToolCallContext]]
NextMessageMiddleware = Callable[[MessageContext], Awaitable[MessageContext]]
NextResponseMiddleware = Callable[[ResponseContext], Awaitable[ResponseContext]]
NextMiddleware = Union[
    NextToolMiddleware, NextMessageMiddleware, NextResponseMiddleware
]


# ============================================================================
# BASE MIDDLEWARE CLASS
# ============================================================================


class BaseMiddleware:
    """Base class for all middleware implementations.

    Subclasses must:
    1. Set the `middleware_type` class attribute to indicate their type
    2. Implement the `__call__` method to process requests

    Example:
        class MyToolMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.TOOL

            async def __call__(self, context: ToolCallContext, next_call):
                # Process tool call
                return await next_call(context)
    """

    middleware_type: MiddlewareType  # Must be set by subclasses

    async def __call__(
        self, context: MiddlewareContext, next_call: NextMiddleware
    ) -> MiddlewareContext:
        """Process a request through the middleware.

        Args:
            context: The context object (ToolCallContext or MessageContext)
            next_call: The next middleware or final action in the chain

        Returns:
            The modified context after processing

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement __call__ method"
        )
