"""Custom middleware to persist summaries created by SummarizationMiddleware to knowledge graph."""

import asyncio
import logging
from typing import Any, Dict, Optional

from langchain_core.messages import BaseMessage

from events import BotEvents
from services.chat_service import ChatService
from services.message_service import MessageService

logger = logging.getLogger(__name__)


class KnowledgeGraphSummaryMiddleware:
    """Middleware that persists summaries to knowledge graph when SummarizationMiddleware creates them.

    This middleware hooks into the agent state to detect when SummarizationMiddleware
    has created a summary message and saves it to the knowledge graph via MessageService.
    """

    def __init__(
        self,
        chat_id: str,
        message_service: MessageService,
        chat_service: ChatService,
        events: Optional[Any] = None,
    ):
        """Initialize the knowledge graph summary middleware.

        Args:
            chat_id: Chat identifier for linking summaries
            message_service: MessageService instance for saving summaries
            chat_service: ChatService instance for linking summaries to chat
            events: Optional events system for dispatching SUMMARIZED events
        """
        self.chat_id = chat_id
        self.message_service = message_service
        self.chat_service = chat_service
        self.events = events
        self._processed_summaries = set()  # Track processed summaries to avoid duplicates

    def after_model(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Hook called after model invocation to detect and persist summaries.

        Args:
            state: Agent state dictionary with messages

        Returns:
            Unmodified state
        """
        try:
            messages = state.get("messages", [])
            if not messages:
                return state

            # Check if a summary message was added
            # SummarizationMiddleware adds messages with "[Summary]" prefix
            for message in messages:
                if isinstance(message, BaseMessage):
                    content = str(message.content) if hasattr(message, "content") else ""
                    
                    # Check if this is a summary message
                    # SummarizationMiddleware uses a prefix (default "[Summary] ")
                    is_summary = content.startswith("[Summary]") or (
                        hasattr(message, "additional_kwargs")
                        and message.additional_kwargs.get("summary", False)
                    )
                    
                    if is_summary:
                        # Extract summary text (remove prefix if present)
                        summary_text = content.replace("[Summary] ", "").strip()
                        
                        # Create a hash to track if we've processed this summary
                        summary_hash = hash(summary_text)
                        
                        if summary_text and summary_hash not in self._processed_summaries:
                            self._processed_summaries.add(summary_hash)
                            
                            # Save summary to knowledge graph asynchronously
                            # Schedule the async task
                            try:
                                loop = asyncio.get_event_loop()
                                if loop.is_running():
                                    # If loop is running, create a task
                                    asyncio.create_task(
                                        self._save_summary(summary_text)
                                    )
                                else:
                                    # If no loop running, run directly
                                    asyncio.run_coroutine_threadsafe(
                                        self._save_summary(summary_text), loop
                                    )
                            except RuntimeError:
                                # No event loop, we'll handle this in the async context
                                # The save will happen when the async method is called
                                pass
                            
                            logger.info(
                                "Detected summary for persistence to knowledge graph"
                            )

        except Exception as e:
            logger.warning("Error in KnowledgeGraphSummaryMiddleware: %s", e)

        return state

    async def _save_summary(self, summary_text: str) -> None:
        """Save summary to knowledge graph.

        Args:
            summary_text: The summary text to save
        """
        try:
            # Save summary message to knowledge graph
            message_node_id = await self.message_service.save_message(
                content=summary_text,
                role="model",
                internal=False,
                message_type="summary",
            )

            # Link summary to chat
            if message_node_id and self.chat_id:
                linked = await self.chat_service.link_message(
                    chat_id=self.chat_id,
                    message_node_id=message_node_id,
                )
                if not linked:
                    logger.warning(
                        "Failed to link summary message %s to chat %s",
                        message_node_id,
                        self.chat_id,
                    )

            # Fire SUMMARIZED event for compatibility with existing handlers
            if self.events:
                await self.events.async_dispatch(BotEvents.SUMMARIZED, summary_text)

            logger.info("Summary saved to knowledge graph successfully")
        except Exception as e:
            logger.error("Failed to save summary to knowledge graph: %s", e, exc_info=True)

