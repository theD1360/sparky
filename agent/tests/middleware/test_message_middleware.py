"""Tests for message middleware system."""

import pytest

from sparky.middleware import (
    BaseMiddleware,
    CommandPromptMiddleware,
    MessageContext,
    MiddlewareType,
    ResponseContext,
    ResponseFormatterMiddleware,
)


class TestMessageContext:
    """Tests for MessageContext."""

    def test_message_context_creation(self):
        """Test creating a MessageContext."""
        context = MessageContext(message="test message")
        assert context.message == "test message"
        assert context.modified_message is None
        assert context.skip_model is False
        assert context.response is None
        assert context.bot_instance is None

    def test_message_context_with_bot(self):
        """Test MessageContext with bot instance."""
        bot = object()
        context = MessageContext(message="test", bot_instance=bot)
        assert context.bot_instance is bot


class SimpleMiddleware(BaseMiddleware):
    """Simple middleware for testing."""

    middleware_type = MiddlewareType.MESSAGE

    async def __call__(self, context: MessageContext, next_call):
        context.modified_message = context.message.upper()
        return await next_call(context)


class TestMessageMiddleware:
    """Tests for MessageMiddleware base class."""

    @pytest.mark.asyncio
    async def test_simple_middleware(self):
        """Test a simple middleware that modifies the message."""
        middleware = SimpleMiddleware()

        async def mock_next(ctx):
            return ctx

        context = MessageContext(message="hello world")
        result = await middleware(context, mock_next)

        assert result.modified_message == "HELLO WORLD"
        assert result.message == "hello world"

    @pytest.mark.asyncio
    async def test_middleware_chain(self):
        """Test multiple middlewares in a chain."""

        class FirstMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.MESSAGE

            async def __call__(self, context, next_call):
                context.modified_message = f"First: {context.message}"
                return await next_call(context)

        class SecondMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.MESSAGE

            async def __call__(self, context, next_call):
                msg = context.modified_message or context.message
                context.modified_message = f"Second: {msg}"
                return await next_call(context)

        async def final(ctx):
            return ctx

        # Build chain: second -> first -> final
        first = FirstMiddleware()
        second = SecondMiddleware()

        context = MessageContext(message="test")

        # Apply first middleware
        context = await first(context, final)
        assert context.modified_message == "First: test"

        # Apply second middleware
        context = await second(context, final)
        assert context.modified_message == "Second: First: test"


class TestCommandPromptMiddleware:
    """Tests for CommandPromptMiddleware."""

    @pytest.mark.asyncio
    async def test_non_command_message(self):
        """Test that non-command messages pass through unchanged."""
        middleware = CommandPromptMiddleware()

        async def mock_next(ctx):
            return ctx

        context = MessageContext(message="This is a normal message")
        result = await middleware(context, mock_next)

        assert result.modified_message is None
        assert result.message == "This is a normal message"

    @pytest.mark.asyncio
    async def test_command_pattern_matching(self):
        """Test command pattern matching."""
        middleware = CommandPromptMiddleware()

        # Valid commands
        assert middleware.COMMAND_PATTERN.match("/command input")
        assert middleware.COMMAND_PATTERN.match("/cmd test data")
        assert middleware.COMMAND_PATTERN.match("/test_123 value")

        # Invalid patterns
        assert not middleware.COMMAND_PATTERN.match("command input")
        assert not middleware.COMMAND_PATTERN.match("/ command input")
        assert not middleware.COMMAND_PATTERN.match("/command")
        assert not middleware.COMMAND_PATTERN.match("/")

    @pytest.mark.asyncio
    async def test_command_without_toolchain(self):
        """Test command when bot has no toolchain."""
        middleware = CommandPromptMiddleware()

        async def mock_next(ctx):
            return ctx

        # Bot without toolchain
        class MockBot:
            toolchain = None

        context = MessageContext(message="/test input", bot_instance=MockBot())
        result = await middleware(context, mock_next)

        # Should pass through unchanged
        assert result.message == "/test input"

    @pytest.mark.asyncio
    async def test_command_parsing(self):
        """Test parsing of command and input."""
        middleware = CommandPromptMiddleware()

        tests = [
            ("/discover_concept Python", "discover_concept", "Python"),
            ("/search_memory test query", "search_memory", "test query"),
            (
                "/cmd with multiple words",
                "cmd",
                "with multiple words",
            ),
        ]

        for message, expected_cmd, expected_input in tests:
            match = middleware.COMMAND_PATTERN.match(message)
            assert match is not None
            assert match.group(1) == expected_cmd
            assert match.group(2).strip() == expected_input

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        """Test handling of unknown commands."""
        middleware = CommandPromptMiddleware()

        async def mock_next(ctx):
            return ctx

        # Mock bot with prompts
        class MockPrompt:
            def __init__(self, name):
                self.name = name

        class MockBot:
            toolchain = True

            async def list_prompts(self):
                return [(None, MockPrompt("known_command"))]

        context = MessageContext(
            message="/unknown_command test", bot_instance=MockBot()
        )
        result = await middleware(context, mock_next)

        # Should provide helpful error message
        assert result.modified_message is not None
        assert "unknown_command" in result.modified_message
        assert "doesn't exist" in result.modified_message

    @pytest.mark.asyncio
    async def test_command_with_single_argument(self):
        """Test command with a single argument."""
        middleware = CommandPromptMiddleware()

        async def mock_next(ctx):
            return ctx

        class MockArgument:
            def __init__(self, name):
                self.name = name

        class MockPrompt:
            def __init__(self, name):
                self.name = name
                self.arguments = [MockArgument("concept_name")]

        class MockBot:
            toolchain = True

            async def list_prompts(self):
                return [(None, MockPrompt("discover_concept"))]

            async def get_prompt(self, name, args):
                return f"Prompt for {name} with {args}"

        context = MessageContext(
            message="/discover_concept Python", bot_instance=MockBot()
        )
        result = await middleware(context, mock_next)

        assert result.modified_message is not None
        assert "discover_concept" in result.modified_message

    @pytest.mark.asyncio
    async def test_direct_response_middleware(self):
        """Test middleware that provides direct response."""

        class DirectResponseMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.MESSAGE

            async def __call__(self, context, next_call):
                if context.message == "ping":
                    context.skip_model = True
                    context.response = "pong"
                    return context
                return await next_call(context)

        middleware = DirectResponseMiddleware()

        async def mock_next(ctx):
            return ctx

        # Test direct response
        context = MessageContext(message="ping")
        result = await middleware(context, mock_next)
        assert result.skip_model is True
        assert result.response == "pong"

        # Test pass-through
        context = MessageContext(message="other")
        result = await middleware(context, mock_next)
        assert result.skip_model is False
        assert result.response is None


class TestCustomMiddlewares:
    """Tests for custom middleware examples."""

    @pytest.mark.asyncio
    async def test_content_filter_middleware(self):
        """Test content filtering middleware."""
        import re

        class ContentFilterMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.MESSAGE

            PATTERNS = [
                (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN REDACTED]"),
                (r"\b\d{16}\b", "[CARD REDACTED]"),
            ]

            async def __call__(self, context, next_call):
                filtered = context.message
                for pattern, replacement in self.PATTERNS:
                    filtered = re.sub(pattern, replacement, filtered)

                if filtered != context.message:
                    context.modified_message = filtered

                return await next_call(context)

        middleware = ContentFilterMiddleware()

        async def mock_next(ctx):
            return ctx

        # Test SSN filtering
        context = MessageContext(message="My SSN is 123-45-6789")
        result = await middleware(context, mock_next)
        assert result.modified_message == "My SSN is [SSN REDACTED]"

        # Test card filtering
        context = MessageContext(message="Card: 1234567890123456")
        result = await middleware(context, mock_next)
        assert result.modified_message == "Card: [CARD REDACTED]"

    @pytest.mark.asyncio
    async def test_alias_middleware(self):
        """Test command alias middleware."""

        class AliasMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.MESSAGE

            ALIASES = {
                "/help": "What can you help me with?",
                "/status": "What is the current status?",
            }

            async def __call__(self, context, next_call):
                msg = context.message.strip()
                if msg in self.ALIASES:
                    context.modified_message = self.ALIASES[msg]
                return await next_call(context)

        middleware = AliasMiddleware()

        async def mock_next(ctx):
            return ctx

        # Test alias expansion
        context = MessageContext(message="/help")
        result = await middleware(context, mock_next)
        assert result.modified_message == "What can you help me with?"

        # Test non-alias
        context = MessageContext(message="normal message")
        result = await middleware(context, mock_next)
        assert result.modified_message is None


class TestResponseMiddleware:
    """Tests for response middleware."""

    def test_response_context_creation(self):
        """Test creating a ResponseContext."""
        context = ResponseContext(response="test response")
        assert context.response == "test response"
        assert context.modified_response is None
        assert context.user_message is None
        assert context.metadata is None
        assert context.bot_instance is None

    def test_response_context_with_metadata(self):
        """Test ResponseContext with metadata."""
        metadata = {"model": "gemini", "tokens": 100}
        context = ResponseContext(
            response="test",
            user_message="hello",
            metadata=metadata
        )
        assert context.user_message == "hello"
        assert context.metadata == metadata

    @pytest.mark.asyncio
    async def test_response_formatter_middleware(self):
        """Test the built-in ResponseFormatterMiddleware."""
        middleware = ResponseFormatterMiddleware()

        async def mock_next(ctx):
            return ctx

        context = ResponseContext(response="Hello World")
        result = await middleware(context, mock_next)

        # Should pass through unchanged by default
        assert result.response == "Hello World"
        assert result.modified_response is None

    @pytest.mark.asyncio
    async def test_custom_response_middleware(self):
        """Test a custom response middleware that modifies responses."""

        class UpperCaseResponseMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.RESPONSE

            async def __call__(self, context: ResponseContext, next_call):
                context.modified_response = context.response.upper()
                return await next_call(context)

        middleware = UpperCaseResponseMiddleware()

        async def mock_next(ctx):
            return ctx

        context = ResponseContext(response="hello world")
        result = await middleware(context, mock_next)

        assert result.modified_response == "HELLO WORLD"
        assert result.response == "hello world"

    @pytest.mark.asyncio
    async def test_response_middleware_chain(self):
        """Test multiple response middlewares in a chain."""

        class AddPrefixMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.RESPONSE

            async def __call__(self, context, next_call):
                response = context.modified_response or context.response
                context.modified_response = f"[Bot] {response}"
                return await next_call(context)

        class AddSuffixMiddleware(BaseMiddleware):
            middleware_type = MiddlewareType.RESPONSE

            async def __call__(self, context, next_call):
                response = context.modified_response or context.response
                context.modified_response = f"{response} [End]"
                return await next_call(context)

        async def final(ctx):
            return ctx

        prefix = AddPrefixMiddleware()
        suffix = AddSuffixMiddleware()

        context = ResponseContext(response="Hello")

        # Apply prefix
        context = await prefix(context, final)
        assert context.modified_response == "[Bot] Hello"

        # Apply suffix
        context = await suffix(context, final)
        assert context.modified_response == "[Bot] Hello [End]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

