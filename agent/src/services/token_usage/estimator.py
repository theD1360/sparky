"""Token estimation for LLM messages.

Provides an abstract interface for token counting that can be swapped out
for different implementations (character-based, tiktoken, provider-specific, etc.).
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class TokenEstimator(ABC):
    """Abstract base class for token estimation."""

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate the number of tokens in a text string.

        Args:
            text: The text to estimate tokens for

        Returns:
            Estimated number of tokens
        """
        pass

    def estimate_messages_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate total tokens for a list of messages.

        Args:
            messages: List of message dictionaries with 'role' and 'parts' keys

        Returns:
            Estimated total number of tokens
        """
        total = 0
        for message in messages:
            # Add tokens for role
            role = message.get("role", "")
            total += self.estimate_tokens(str(role))

            # Add tokens for content parts
            parts = message.get("parts", [])
            for part in parts:
                if isinstance(part, str):
                    total += self.estimate_tokens(part)
                elif hasattr(part, "text"):
                    total += self.estimate_tokens(part.text)

            # Add overhead for message formatting (approximately 4 tokens per message)
            total += 4

        return total


class CharacterBasedEstimator(TokenEstimator):
    """Character-based token estimation.

    Uses a simple heuristic: approximately 4 characters per token.
    This is a rough approximation that works reasonably well for English text.
    """

    def __init__(self, chars_per_token: float = 4.0):
        """Initialize the estimator.

        Args:
            chars_per_token: Average number of characters per token (default: 4.0)
        """
        self.chars_per_token = chars_per_token

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens based on character count.

        Args:
            text: The text to estimate tokens for

        Returns:
            Estimated number of tokens
        """
        if not text:
            return 0

        char_count = len(text)
        token_estimate = int(char_count / self.chars_per_token)

        return max(1, token_estimate)  # Return at least 1 token for non-empty text

