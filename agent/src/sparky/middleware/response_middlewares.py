"""Response middleware implementations.

This module contains middleware that intercepts and processes bot responses
before they are returned to the user.

Response middleware can be used for:
- Content filtering and moderation
- Response formatting and styling
- Adding contextual information
- Translation or localization
- Analytics and logging
- Response validation
"""

import logging

from .base import BaseMiddleware, MiddlewareType, NextResponseMiddleware, ResponseContext

logger = logging.getLogger(__name__)


# Example placeholder middleware for future use
class ResponseFormatterMiddleware(BaseMiddleware):
    """
    Example response middleware that demonstrates the pattern.
    
    This is a placeholder for future implementations. Response middleware
    can modify the bot's response before it's returned to the user.
    
    Example use cases:
    - Add markdown formatting
    - Filter inappropriate content
    - Add timestamps or metadata
    - Translate responses
    - Add contextual hints
    """

    middleware_type = MiddlewareType.RESPONSE

    async def __call__(
        self, context: ResponseContext, next_call: NextResponseMiddleware
    ) -> ResponseContext:
        """Process the response."""
        # Example: You could modify the response here
        # context.modified_response = self.format(context.response)
        
        # For now, just pass through unchanged
        return await next_call(context)

    def format(self, response: str) -> str:
        """Format the response (placeholder implementation)."""
        return response

