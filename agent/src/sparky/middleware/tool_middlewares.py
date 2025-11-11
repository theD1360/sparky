"""Tool call middleware implementations.

This module contains middleware that intercepts and processes tool calls
before they are executed by the toolchain.
"""

import logging

from sparky.tool_registry import ToolResult

from .base import BaseMiddleware, MiddlewareType, NextToolMiddleware, ToolCallContext

logger = logging.getLogger(__name__)


# --- Constants for SelfModificationGuard ---
SELF_MODIFYING_TOOLS = {
    "write_file",
    "search_replace_edit_file",
    "append_file",
    "delete",
    "move",
    "git_add",
    "git_commit",
    "git_checkout",
    "set_lines",
    "insert_lines",
}
SOURCE_CODE_ROOT = "src/sparky/"


class SelfModificationGuard(BaseMiddleware):
    """
    Prevents modifications to the bot's own source code on the 'main' branch.

    This middleware checks if a tool call would modify source code and validates
    that such modifications only occur on feature branches.
    """

    middleware_type = MiddlewareType.TOOL

    async def __call__(
        self, context: ToolCallContext, next_call: NextToolMiddleware
    ) -> ToolCallContext:
        """Process tool call and check for self-modification attempts."""
        if context.tool_name in SELF_MODIFYING_TOOLS:
            path = context.tool_args.get("path") or context.tool_args.get("source")
            if path and SOURCE_CODE_ROOT in str(path):
                # Check if we're on the main branch
                try:
                    current_branch = await self.get_current_git_branch(context)

                    if current_branch == "main":
                        # Stop the chain and return an error
                        logger.warning(
                            "SELF-MODIFICATION VIOLATION: Attempted to modify %s on 'main' branch",
                            path,
                        )
                        context.result = ToolResult(
                            status="error",
                            message="SELF-MODIFICATION VIOLATION: Cannot modify source on 'main' branch. Use a feature branch.",
                        )
                        return context
                except Exception as e:
                    # If we can't check the branch, log and allow (fail open for now)
                    logger.warning(
                        "Could not check git branch in SelfModificationGuard: %s. Allowing modification.",
                        str(e),
                    )

        # If checks pass, continue to the next middleware in the chain
        return await next_call(context)

    async def get_current_git_branch(self, context: ToolCallContext) -> str:
        """
        Helper function to get the current git branch.

        Bypasses the dispatcher to avoid infinite loops.

        Args:
            context: The tool call context containing bot instance reference

        Returns:
            The name of the current git branch, or empty string if not found
        """
        if not context.bot_instance or not context.bot_instance.toolchain:
            return ""

        try:
            # Call git_branch tool directly through the toolchain
            result = await context.bot_instance.toolchain.call("git_branch", {})

            if result and isinstance(result, dict):
                branches = result.get("branches", [])
                for branch in branches:
                    if branch.get("current"):
                        return branch.get("name", "")
        except Exception as e:
            logger.debug("Error getting current git branch: %s", str(e))

        return ""  # Default to empty string if not found

