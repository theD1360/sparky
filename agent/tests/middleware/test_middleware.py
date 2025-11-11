"""Tests for the middleware system."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.sparky.middleware import (
    BaseMiddleware,
    ToolCallContext,
    SelfModificationGuard,
    NextMiddleware,
)
from src.sparky.tool_registry import ToolResult


class TestMiddleware:
    """Test suite for middleware functionality."""

    @pytest.mark.asyncio
    async def test_tool_call_context_creation(self):
        """Test that ToolCallContext can be created with basic parameters."""
        context = ToolCallContext(
            tool_name="test_tool",
            tool_args={"arg1": "value1"},
        )
        assert context.tool_name == "test_tool"
        assert context.tool_args == {"arg1": "value1"}
        assert context.result is None
        assert context.bot_instance is None

    @pytest.mark.asyncio
    async def test_simple_middleware_chain(self):
        """Test that a simple middleware chain executes properly."""
        
        class LoggingMiddleware(BaseMiddleware):
            def __init__(self):
                self.called = False
                
            async def __call__(self, context: ToolCallContext, next_call: NextMiddleware) -> ToolCallContext:
                self.called = True
                context.tool_args["logged"] = True
                return await next_call(context)
        
        # Create middleware instance
        logging_mw = LoggingMiddleware()
        
        # Create a mock "next" function that simulates tool execution
        async def final_action(ctx: ToolCallContext) -> ToolCallContext:
            ctx.result = ToolResult(status="success", result="executed")
            return ctx
        
        # Execute the middleware chain
        context = ToolCallContext(tool_name="test", tool_args={})
        result_context = await logging_mw(context, final_action)
        
        assert logging_mw.called
        assert result_context.tool_args.get("logged") is True
        assert result_context.result.status == "success"
        assert result_context.result.result == "executed"

    @pytest.mark.asyncio
    async def test_self_modification_guard_allows_non_source_files(self):
        """Test that SelfModificationGuard allows modifications to non-source files."""
        guard = SelfModificationGuard()
        
        # Create a mock bot instance
        mock_bot = MagicMock()
        
        # Create context for a non-source file
        context = ToolCallContext(
            tool_name="write_file",
            tool_args={"path": "tests/test_file.py"},
            bot_instance=mock_bot,
        )
        
        # Mock "next" function
        async def final_action(ctx: ToolCallContext) -> ToolCallContext:
            ctx.result = ToolResult(status="success", result="written")
            return ctx
        
        # Execute the guard
        result_context = await guard(context, final_action)
        
        # Should allow the modification
        assert result_context.result.status == "success"

    @pytest.mark.asyncio
    async def test_self_modification_guard_blocks_on_main_branch(self):
        """Test that SelfModificationGuard blocks source modifications on main branch."""
        guard = SelfModificationGuard()
        
        # Create a mock bot instance with toolchain
        mock_toolchain = AsyncMock()
        mock_toolchain.call = AsyncMock(return_value={
            "branches": [
                {"name": "main", "current": True}
            ]
        })
        
        mock_bot = MagicMock()
        mock_bot.toolchain = mock_toolchain
        
        # Create context for a source file modification
        context = ToolCallContext(
            tool_name="write_file",
            tool_args={"path": "src/badrobot/bot.py"},
            bot_instance=mock_bot,
        )
        
        # Mock "next" function (should not be called)
        async def final_action(ctx: ToolCallContext) -> ToolCallContext:
            ctx.result = ToolResult(status="success", result="written")
            return ctx
        
        # Execute the guard
        result_context = await guard(context, final_action)
        
        # Should block the modification
        assert result_context.result.status == "error"
        assert "SELF-MODIFICATION VIOLATION" in result_context.result.message

    @pytest.mark.asyncio
    async def test_self_modification_guard_allows_on_feature_branch(self):
        """Test that SelfModificationGuard allows source modifications on feature branch."""
        guard = SelfModificationGuard()
        
        # Create a mock bot instance with toolchain
        mock_toolchain = AsyncMock()
        mock_toolchain.call = AsyncMock(return_value={
            "branches": [
                {"name": "feature/test", "current": True}
            ]
        })
        
        mock_bot = MagicMock()
        mock_bot.toolchain = mock_toolchain
        
        # Create context for a source file modification
        context = ToolCallContext(
            tool_name="write_file",
            tool_args={"path": "src/badrobot/bot.py"},
            bot_instance=mock_bot,
        )
        
        # Mock "next" function
        async def final_action(ctx: ToolCallContext) -> ToolCallContext:
            ctx.result = ToolResult(status="success", result="written")
            return ctx
        
        # Execute the guard
        result_context = await guard(context, final_action)
        
        # Should allow the modification
        assert result_context.result.status == "success"

    @pytest.mark.asyncio
    async def test_multiple_middleware_chain(self):
        """Test that multiple middlewares can be chained together."""
        
        class Middleware1(BaseMiddleware):
            async def __call__(self, context: ToolCallContext, next_call: NextMiddleware) -> ToolCallContext:
                context.tool_args["mw1"] = True
                return await next_call(context)
        
        class Middleware2(BaseMiddleware):
            async def __call__(self, context: ToolCallContext, next_call: NextMiddleware) -> ToolCallContext:
                context.tool_args["mw2"] = True
                return await next_call(context)
        
        # Create middleware instances
        mw1 = Middleware1()
        mw2 = Middleware2()
        
        # Create final action
        async def final_action(ctx: ToolCallContext) -> ToolCallContext:
            ctx.result = ToolResult(status="success", result="done")
            return ctx
        
        # Chain them manually: mw1 -> mw2 -> final
        async def mw2_with_final(ctx):
            return await mw2(ctx, final_action)
        
        context = ToolCallContext(tool_name="test", tool_args={})
        result_context = await mw1(context, mw2_with_final)
        
        # Both middlewares should have executed
        assert result_context.tool_args.get("mw1") is True
        assert result_context.tool_args.get("mw2") is True
        assert result_context.result.status == "success"


