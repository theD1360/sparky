"""Middleware registry for centralized middleware management.

This module provides the MiddlewareRegistry class which handles registration
and routing of middleware to the appropriate dispatchers.
"""

import logging
from typing import List, Optional

from .base import BaseMiddleware, MiddlewareType

logger = logging.getLogger(__name__)


class MiddlewareRegistry:
    """Central registry for managing middleware and their dispatchers.

    The registry handles:
    - Registration of middleware
    - Automatic routing to appropriate dispatchers based on type
    - Management of all three dispatcher instances
    - Validation of middleware configuration

    Example:
        registry = MiddlewareRegistry(bot_instance)
        registry.register(SelfModificationGuard())
        registry.register(CommandPromptMiddleware())
        registry.register(ResourceFetchingMiddleware())
        registry.register(ResponseFormatterMiddleware())

        # All middlewares automatically routed to correct dispatchers
    """

    def __init__(self, bot_instance):
        """Initialize the registry with dispatcher instances.

        Args:
            bot_instance: Reference to the Bot instance
        """
        from .dispatchers import MessageDispatcher, ResponseDispatcher, ToolDispatcher

        self.bot = bot_instance

        # Initialize all dispatchers
        self.tool_dispatcher = ToolDispatcher(bot_instance)
        self.message_dispatcher = MessageDispatcher(bot_instance)
        self.response_dispatcher = ResponseDispatcher(bot_instance)

        # Track registered middleware for inspection
        self._registered_middleware = {
            MiddlewareType.TOOL: [],
            MiddlewareType.MESSAGE: [],
            MiddlewareType.RESPONSE: [],
        }

        logger.debug("MiddlewareRegistry initialized with all dispatchers")

    def register(self, middleware: BaseMiddleware) -> None:
        """Register a single middleware and route it to the appropriate dispatcher.

        Args:
            middleware: The middleware instance to register

        Raises:
            ValueError: If middleware doesn't have a middleware_type attribute
                       or has an unknown type
        """
        # Validate middleware has required type attribute
        if not hasattr(middleware, "middleware_type"):
            raise ValueError(
                f"Middleware {middleware.__class__.__name__} must have a "
                "'middleware_type' attribute"
            )

        middleware_type = middleware.middleware_type
        middleware_name = middleware.__class__.__name__

        # Route to appropriate dispatcher
        if middleware_type == MiddlewareType.TOOL:
            self.tool_dispatcher.add_middleware(middleware)
            self._registered_middleware[MiddlewareType.TOOL].append(middleware)
            logger.info(f"Registered tool middleware: {middleware_name}")

        elif middleware_type == MiddlewareType.MESSAGE:
            self.message_dispatcher.add_middleware(middleware)
            self._registered_middleware[MiddlewareType.MESSAGE].append(middleware)
            logger.info(f"Registered message middleware: {middleware_name}")

        elif middleware_type == MiddlewareType.RESPONSE:
            self.response_dispatcher.add_middleware(middleware)
            self._registered_middleware[MiddlewareType.RESPONSE].append(middleware)
            logger.info(f"Registered response middleware: {middleware_name}")

        else:
            raise ValueError(
                f"Unknown middleware type: {middleware_type} for "
                f"{middleware_name}. Must be one of: "
                f"{', '.join([t.value for t in MiddlewareType])}"
            )

    def register_many(self, middlewares: List[BaseMiddleware]) -> None:
        """Register multiple middlewares at once.

        Args:
            middlewares: List of middleware instances to register
        """
        for middleware in middlewares:
            self.register(middleware)

    def get_registered_middleware(
        self, middleware_type: Optional[MiddlewareType] = None
    ) -> List[BaseMiddleware]:
        """Get registered middleware, optionally filtered by type.

        Args:
            middleware_type: Optional type to filter by. If None, returns all.

        Returns:
            List of registered middleware instances
        """
        if middleware_type is None:
            # Return all middleware from all types
            all_middleware = []
            for middleware_list in self._registered_middleware.values():
                all_middleware.extend(middleware_list)
            return all_middleware

        return self._registered_middleware.get(middleware_type, [])

    def get_middleware_count(
        self, middleware_type: Optional[MiddlewareType] = None
    ) -> int:
        """Get count of registered middleware.

        Args:
            middleware_type: Optional type to filter by. If None, returns total count.

        Returns:
            Number of registered middleware
        """
        if middleware_type is None:
            return sum(len(mw_list) for mw_list in self._registered_middleware.values())

        return len(self._registered_middleware.get(middleware_type, []))

    def clear(self, middleware_type: Optional[MiddlewareType] = None) -> None:
        """Clear registered middleware.

        Args:
            middleware_type: Optional type to clear. If None, clears all.
        """
        from .dispatchers import MessageDispatcher, ResponseDispatcher, ToolDispatcher

        if middleware_type is None:
            # Clear all
            self.tool_dispatcher = ToolDispatcher(self.bot)
            self.message_dispatcher = MessageDispatcher(self.bot)
            self.response_dispatcher = ResponseDispatcher(self.bot)
            for key in self._registered_middleware:
                self._registered_middleware[key] = []
            logger.info("Cleared all middleware from registry")
        else:
            # Clear specific type
            if middleware_type == MiddlewareType.TOOL:
                self.tool_dispatcher = ToolDispatcher(self.bot)
            elif middleware_type == MiddlewareType.MESSAGE:
                self.message_dispatcher = MessageDispatcher(self.bot)
            elif middleware_type == MiddlewareType.RESPONSE:
                self.response_dispatcher = ResponseDispatcher(self.bot)

            self._registered_middleware[middleware_type] = []
            logger.info(f"Cleared {middleware_type.value} middleware from registry")

    def __repr__(self) -> str:
        """String representation of the registry."""
        counts = {
            "tool": len(self._registered_middleware[MiddlewareType.TOOL]),
            "message": len(self._registered_middleware[MiddlewareType.MESSAGE]),
            "response": len(self._registered_middleware[MiddlewareType.RESPONSE]),
        }
        return (
            f"MiddlewareRegistry("
            f"tool={counts['tool']}, "
            f"message={counts['message']}, "
            f"response={counts['response']})"
        )
