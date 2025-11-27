"""Token usage service for managing token estimation and tracking.

This service provides centralized token management for LLM interactions,
handling both estimation and actual usage tracking.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from services.token_usage.estimator import TokenEstimator

logger = logging.getLogger(__name__)


class TokenUsageService:
    """Centralized service for managing token estimation and usage tracking.
    
    This service handles all token-related operations including:
    - Estimating tokens for various message types
    - Tracking actual token usage from LLM responses
    - Managing token budgets and limits
    - Emitting token-related events
    
    The service monitors the provider and events system, rather than being
    called by them (inversion of control).
    """

    def __init__(
        self,
        token_estimator: Optional[TokenEstimator] = None,
        events: Optional[Any] = None,
        provider: Optional[Any] = None,
    ):
        """Initialize the token usage service.

        Args:
            token_estimator: Token estimator to use for calculations.
                           If None, creates a default CharacterBasedEstimator.
            events: Optional events system for emitting token events.
            provider: Optional LLM provider to monitor for token usage.
        """
        if token_estimator is None:
            from services.token_usage.estimator import CharacterBasedEstimator

            self.token_estimator = CharacterBasedEstimator()
        else:
            self.token_estimator = token_estimator
            
        self.events = events
        self.provider = provider
        
        # Subscribe to events if events system is available
        if self.events:
            self._subscribe_to_events()

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
            from sparky.event_types import BotEvents

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
            from sparky.event_types import BotEvents
            
            await self.events.async_dispatch(BotEvents.TOKEN_USAGE, usage_dict)
            logger.debug(
                f"Emitted token usage: {usage_dict.get('total_tokens', 0)} tokens"
            )
    
    def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events for token estimation.
        
        This method hooks into the events system to automatically estimate
        tokens when thoughts, tool calls, and tool results occur.
        """
        from sparky.event_types import BotEvents
        
        # Subscribe to THOUGHT events to estimate thinking tokens
        self.events.subscribe(BotEvents.THOUGHT, self._handle_thought)
        
        # Subscribe to TOOL_USE events to estimate tool call tokens
        self.events.subscribe(BotEvents.TOOL_USE, self._handle_tool_use)
        
        # Subscribe to TOOL_RESULT events to estimate tool result tokens
        self.events.subscribe(BotEvents.TOOL_RESULT, self._handle_tool_result)
        
        logger.debug("TokenUsageService subscribed to events")
    
    async def _handle_thought(self, thought_text: str) -> None:
        """Handle THOUGHT event and estimate tokens.
        
        Args:
            thought_text: The thought/reasoning text
        """
        try:
            thought_tokens = self.estimate_thought(thought_text)
            await self.emit_estimate(thought_tokens, "thought")
        except Exception as e:
            logger.debug(f"Failed to estimate thought tokens: {e}")
    
    async def _handle_tool_use(self, tool_name: str, tool_args: Dict[str, Any]) -> None:
        """Handle TOOL_USE event and estimate tokens.
        
        Args:
            tool_name: Name of the tool being called
            tool_args: Arguments passed to the tool
        """
        try:
            tool_call_tokens = self.estimate_tool_call(tool_name, tool_args)
            await self.emit_estimate(tool_call_tokens, "tool_call")
        except Exception as e:
            logger.debug(f"Failed to estimate tool call tokens: {e}")
    
    async def _handle_tool_result(self, tool_name: str, result_text: str, status: str = None) -> None:
        """Handle TOOL_RESULT event and estimate tokens.
        
        Args:
            tool_name: Name of the tool that was called
            result_text: Result returned by the tool
            status: Optional status of the tool execution ('success' or 'error')
        """
        try:
            # Parse result_text if it's a structured result
            # For now, treat it as a string
            tool_result_tokens = self.estimate_tool_result(result_text)
            await self.emit_estimate(tool_result_tokens, "tool_result")
        except Exception as e:
            logger.debug(f"Failed to estimate tool result tokens: {e}")
    
    def extract_actual_usage(self, response: Any) -> Optional[Dict[str, int]]:
        """Extract actual token usage from provider response.
        
        Args:
            response: Provider-specific response object
            
        Returns:
            Dict with token usage or None if not available
        """
        if self.provider and hasattr(self.provider, 'extract_token_usage'):
            return self.provider.extract_token_usage(response)
        return None

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
