"""Token usage service for managing token estimation and tracking.

This service provides centralized token management for LLM interactions,
handling both estimation and actual usage tracking.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from services.token_estimation.estimator import TokenEstimator

logger = logging.getLogger(__name__)


class TokenUsageService:
    """Centralized service for managing token estimation and usage tracking.

    This service handles all token-related operations including:
    - Estimating tokens for various message types
    - Tracking actual token usage from LLM responses
    - Managing token budgets and limits
    - Emitting token-related events
    """

    def __init__(
        self,
        token_estimator: Optional[TokenEstimator] = None,
        events: Optional[Any] = None,
    ):
        """Initialize the token usage service.

        Args:
            token_estimator: Token estimator to use for calculations.
                           If None, creates a default CharacterBasedEstimator.
            events: Optional events system for emitting token events.
        """
        if token_estimator is None:
            from services.token_estimation.estimator import CharacterBasedEstimator

            self.token_estimator = CharacterBasedEstimator()
        else:
            self.token_estimator = token_estimator

        self.events = events

    def estimate_user_message(self, message: str) -> int:
        """Estimate tokens for a user message.

        Args:
            message: The user's message text

        Returns:
            Estimated number of tokens
        """
        if not message:
            return 0

        # Estimate the message content plus overhead for role and formatting
        base_tokens = self.token_estimator.estimate_tokens(message)
        overhead = 10  # Overhead for role, message structure, etc.

        return base_tokens + overhead

    def estimate_expected_response(
        self, user_message: str, is_complex: bool = False
    ) -> int:
        """Estimate expected response size based on the user message.

        Uses heuristics to predict response length:
        - Simple queries: ~2-3x user message length
        - Complex queries (with tool calls likely): ~4-5x user message length

        Args:
            user_message: The user's message text
            is_complex: Whether the message is likely to trigger complex operations

        Returns:
            Estimated number of tokens for the response
        """
        if not user_message:
            return 100  # Default minimum response size

        user_tokens = self.token_estimator.estimate_tokens(user_message)

        # Use heuristics based on message complexity
        if is_complex:
            # Complex queries with tools: expect longer responses
            multiplier = 4.5
            minimum = 200
        else:
            # Simple queries: expect moderate responses
            multiplier = 2.5
            minimum = 100

        estimated = int(user_tokens * multiplier)
        return max(estimated, minimum)

    def estimate_thought(self, thought_text: str) -> int:
        """Estimate tokens for a thought/reasoning text.

        Args:
            thought_text: The AI's thinking text

        Returns:
            Estimated number of tokens
        """
        if not thought_text:
            return 0

        # Thoughts have minimal overhead
        base_tokens = self.token_estimator.estimate_tokens(thought_text)
        overhead = 5

        return base_tokens + overhead

    def estimate_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> int:
        """Estimate tokens for a tool call (name + arguments).

        Args:
            tool_name: Name of the tool being called
            tool_args: Arguments passed to the tool

        Returns:
            Estimated number of tokens
        """
        # Tool name
        name_tokens = self.token_estimator.estimate_tokens(tool_name)

        # Tool arguments (serialize to JSON for estimation)
        try:
            args_str = json.dumps(tool_args)
            args_tokens = self.token_estimator.estimate_tokens(args_str)
        except (TypeError, ValueError):
            # Fallback for non-serializable args
            args_tokens = self.token_estimator.estimate_tokens(str(tool_args))

        # Overhead for function call structure
        overhead = 15

        return name_tokens + args_tokens + overhead

    def estimate_tool_result(self, result: Any) -> int:
        """Estimate tokens for a tool result.

        Args:
            result: The tool's return value

        Returns:
            Estimated number of tokens
        """
        if result is None:
            return 5

        # Convert result to string for estimation
        if isinstance(result, str):
            result_str = result
        elif isinstance(result, (dict, list)):
            try:
                result_str = json.dumps(result)
            except (TypeError, ValueError):
                result_str = str(result)
        else:
            result_str = str(result)

        # Estimate based on string length
        base_tokens = self.token_estimator.estimate_tokens(result_str)

        # Cap extremely large results (they're often truncated anyway)
        max_tokens = 10000
        base_tokens = min(base_tokens, max_tokens)

        # Overhead for result structure
        overhead = 10

        return base_tokens + overhead

    def estimate_messages_list(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate total tokens for a list of messages (chat history).

        Args:
            messages: List of message dictionaries with 'role' and 'parts' keys

        Returns:
            Estimated total number of tokens
        """
        return self.token_estimator.estimate_messages_tokens(messages)

    async def emit_estimate(self, estimated_tokens: int, source: str) -> None:
        """Emit a token estimate event if events system is configured.

        Args:
            estimated_tokens: Number of tokens estimated
            source: Source of the estimate (e.g., 'history', 'message', 'thought')
        """
        if self.events:
            from events import BotEvents

            await self.events.async_dispatch(
                BotEvents.TOKEN_ESTIMATE, estimated_tokens, source
            )
            logger.debug(f"Emitted token estimate: {estimated_tokens} ({source})")

    async def emit_usage(self, usage_dict: Dict[str, int]) -> None:
        """Emit actual token usage event if events system is configured.

        Args:
            usage_dict: Dictionary with token counts (input_tokens, output_tokens, etc.)
        """
        if self.events:
            from events import BotEvents

            await self.events.async_dispatch(BotEvents.TOKEN_USAGE, usage_dict)
            logger.debug(
                f"Emitted token usage: {usage_dict.get('total_tokens', 0)} tokens"
            )

    def detect_complexity(self, message: str) -> bool:
        """Detect if a message is likely to trigger complex operations.

        Looks for keywords/patterns that suggest tool usage, code generation,
        analysis, etc.

        Args:
            message: The user's message text

        Returns:
            True if message appears complex, False otherwise
        """
        if not message:
            return False

        message_lower = message.lower()

        # Keywords that suggest complex operations
        complex_keywords = [
            "analyze",
            "generate",
            "create",
            "build",
            "implement",
            "search",
            "find",
            "calculate",
            "compare",
            "scan",
            "test",
            "check",
            "review",
            "explain in detail",
            "write",
            "code",
            "function",
            "script",
        ]

        # Check for complexity indicators
        has_keyword = any(keyword in message_lower for keyword in complex_keywords)
        is_long = len(message) > 200  # Long queries tend to be complex

        return has_keyword or is_long
