"""Middleware system for Sparky.

This package provides a flexible middleware system for intercepting and
processing both tool calls and user messages.

Example:
    from sparky.middleware import (
        BaseMiddleware,
        CommandPromptMiddleware,
        MessageContext,
        MiddlewareType,
        ResourceFetchingMiddleware,
        SelfModificationGuard,
        ToolCallContext,
    )
    from sparky import AgentOrchestrator
    from sparky.providers import GeminiProvider, ProviderConfig

    # Create agent orchestrator with middlewares
    config = ProviderConfig(model_name="gemini-1.5-pro")
    provider = GeminiProvider(config)
    orchestrator = AgentOrchestrator(
        provider=provider,
        middlewares=[
            SelfModificationGuard(),
            CommandPromptMiddleware(),
            ResourceFetchingMiddleware(),
        ]
    )
"""

from .base import (
    BaseMiddleware,
    MessageContext,
    MiddlewareContext,
    MiddlewareType,
    NextMessageMiddleware,
    NextMiddleware,
    NextResponseMiddleware,
    NextToolMiddleware,
    ResponseContext,
    ToolCallContext,
)
from .message_middlewares import (
    CommandPromptMiddleware,
    FileAttachmentMiddleware,
    ResourceFetchingMiddleware,
)
from .registry import MiddlewareRegistry
from .response_middlewares import ResponseFormatterMiddleware
from .tool_middlewares import SelfModificationGuard

__all__ = [
    # Base classes and types
    "BaseMiddleware",
    "MessageContext",
    "MiddlewareContext",
    "MiddlewareType",
    "NextMessageMiddleware",
    "NextMiddleware",
    "NextResponseMiddleware",
    "NextToolMiddleware",
    "ResponseContext",
    "ToolCallContext",
    # Registry
    "MiddlewareRegistry",
    # Concrete middleware implementations
    "CommandPromptMiddleware",
    "FileAttachmentMiddleware",
    "ResourceFetchingMiddleware",
    "ResponseFormatterMiddleware",
    "SelfModificationGuard",
]
