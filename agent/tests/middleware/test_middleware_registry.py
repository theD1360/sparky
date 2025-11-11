"""Tests for the middleware registry."""

import pytest

from sparky.middleware import (
    BaseMiddleware,
    MessageContext,
    MiddlewareRegistry,
    MiddlewareType,
    ResponseContext,
    ToolCallContext,
)


class MockBot:
    """Mock bot for testing."""

    def __init__(self):
        self.toolchain = None


class TestMiddlewareRegistry:
    """Tests for MiddlewareRegistry."""

    def test_registry_initialization(self):
        """Test that registry initializes with all dispatchers."""
        bot = MockBot()
        registry = MiddlewareRegistry(bot)

        assert registry.bot is bot
        assert registry.tool_dispatcher is not None
        assert registry.message_dispatcher is not None
        assert registry.response_dispatcher is not None

    def test_register_tool_middleware(self):
        """Test registering a tool middleware."""

        class TestToolMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.TOOL

            async def __call__(self, context, next_call):
                return await next_call(context)

        bot = MockBot()
        registry = MiddlewareRegistry(bot)
        middleware = TestToolMiddleware()

        registry.register(middleware)

        assert registry.get_middleware_count(MiddlewareType.TOOL) == 1
        assert middleware in registry.get_registered_middleware(MiddlewareType.TOOL)

    def test_register_message_middleware(self):
        """Test registering a message middleware."""

        class TestMessageMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.MESSAGE

            async def __call__(self, context, next_call):
                return await next_call(context)

        bot = MockBot()
        registry = MiddlewareRegistry(bot)
        middleware = TestMessageMiddleware()

        registry.register(middleware)

        assert registry.get_middleware_count(MiddlewareType.MESSAGE) == 1
        assert middleware in registry.get_registered_middleware(MiddlewareType.MESSAGE)

    def test_register_response_middleware(self):
        """Test registering a response middleware."""

        class TestResponseMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.RESPONSE

            async def __call__(self, context, next_call):
                return await next_call(context)

        bot = MockBot()
        registry = MiddlewareRegistry(bot)
        middleware = TestResponseMiddleware()

        registry.register(middleware)

        assert registry.get_middleware_count(MiddlewareType.RESPONSE) == 1
        assert middleware in registry.get_registered_middleware(MiddlewareType.RESPONSE)

    def test_register_many(self):
        """Test registering multiple middlewares at once."""

        class ToolMW(BaseMiddleware):
            middleware_type = MiddlewareType.TOOL

            async def __call__(self, context, next_call):
                return await next_call(context)

        class MessageMW(BaseMiddleware):
            middleware_type = MiddlewareType.MESSAGE

            async def __call__(self, context, next_call):
                return await next_call(context)

        class ResponseMW(BaseMiddleware):
            middleware_type = MiddlewareType.RESPONSE

            async def __call__(self, context, next_call):
                return await next_call(context)

        bot = MockBot()
        registry = MiddlewareRegistry(bot)

        middlewares = [ToolMW(), MessageMW(), ResponseMW()]
        registry.register_many(middlewares)

        assert registry.get_middleware_count() == 3
        assert registry.get_middleware_count(MiddlewareType.TOOL) == 1
        assert registry.get_middleware_count(MiddlewareType.MESSAGE) == 1
        assert registry.get_middleware_count(MiddlewareType.RESPONSE) == 1

    def test_register_without_type_raises_error(self):
        """Test that registering middleware without type raises error."""

        class BadMiddleware:
            async def __call__(self, context, next_call):
                return await next_call(context)

        bot = MockBot()
        registry = MiddlewareRegistry(bot)
        middleware = BadMiddleware()

        with pytest.raises(ValueError, match="must have a 'middleware_type' attribute"):
            registry.register(middleware)

    def test_register_unknown_type_raises_error(self):
        """Test that registering middleware with unknown type raises error."""

        class BadMiddleware(BaseMiddleware):
            middleware_type = "unknown"

            async def __call__(self, context, next_call):
                return await next_call(context)

        bot = MockBot()
        registry = MiddlewareRegistry(bot)
        middleware = BadMiddleware()

        with pytest.raises(ValueError, match="Unknown middleware type"):
            registry.register(middleware)

    def test_get_registered_middleware_all(self):
        """Test getting all registered middleware."""

        class ToolMW(BaseMiddleware):
            middleware_type = MiddlewareType.TOOL

            async def __call__(self, context, next_call):
                return await next_call(context)

        class MessageMW(BaseMiddleware):
            middleware_type = MiddlewareType.MESSAGE

            async def __call__(self, context, next_call):
                return await next_call(context)

        bot = MockBot()
        registry = MiddlewareRegistry(bot)

        mw1 = ToolMW()
        mw2 = MessageMW()
        registry.register(mw1)
        registry.register(mw2)

        all_middleware = registry.get_registered_middleware()
        assert len(all_middleware) == 2
        assert mw1 in all_middleware
        assert mw2 in all_middleware

    def test_clear_all_middleware(self):
        """Test clearing all middleware."""

        class ToolMW(BaseMiddleware):
            middleware_type = MiddlewareType.TOOL

            async def __call__(self, context, next_call):
                return await next_call(context)

        bot = MockBot()
        registry = MiddlewareRegistry(bot)

        registry.register(ToolMW())
        assert registry.get_middleware_count() == 1

        registry.clear()
        assert registry.get_middleware_count() == 0

    def test_clear_specific_type(self):
        """Test clearing specific middleware type."""

        class ToolMW(BaseMiddleware):
            middleware_type = MiddlewareType.TOOL

            async def __call__(self, context, next_call):
                return await next_call(context)

        class MessageMW(BaseMiddleware):
            middleware_type = MiddlewareType.MESSAGE

            async def __call__(self, context, next_call):
                return await next_call(context)

        bot = MockBot()
        registry = MiddlewareRegistry(bot)

        registry.register(ToolMW())
        registry.register(MessageMW())
        assert registry.get_middleware_count() == 2

        registry.clear(MiddlewareType.TOOL)
        assert registry.get_middleware_count(MiddlewareType.TOOL) == 0
        assert registry.get_middleware_count(MiddlewareType.MESSAGE) == 1

    def test_registry_repr(self):
        """Test registry string representation."""

        class ToolMW(BaseMiddleware):
            middleware_type = MiddlewareType.TOOL

            async def __call__(self, context, next_call):
                return await next_call(context)

        bot = MockBot()
        registry = MiddlewareRegistry(bot)
        registry.register(ToolMW())

        repr_str = repr(registry)
        assert "MiddlewareRegistry" in repr_str
        assert "tool=1" in repr_str
        assert "message=0" in repr_str
        assert "response=0" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

