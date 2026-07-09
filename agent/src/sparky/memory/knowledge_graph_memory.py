"""Custom LangChain ChatMessageHistory backend that persists to knowledge graph."""

import logging
from typing import Any, List, Optional

from events import BotEvents
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    messages_from_dict,
    messages_to_dict,
)
from services.chat_service import ChatService
from services.message_service import MessageService

logger = logging.getLogger(__name__)


class KnowledgeGraphChatMessageHistory(BaseChatMessageHistory):
    """Chat message history that persists to knowledge graph.

    This implementation extends LangChain's BaseChatMessageHistory to store
    messages in the knowledge graph via MessageService and ChatService.
    Messages are automatically linked to the chat node.
    """

    def __init__(
        self,
        chat_id: str,
        message_service: MessageService,
        chat_service: ChatService,
        events: Optional[Any] = None,
    ):
        """Initialize the knowledge graph chat message history.

        Args:
            chat_id: Chat identifier for this conversation
            message_service: MessageService instance for saving/retrieving messages
            chat_service: ChatService instance for linking messages to chat
            events: Optional events system for dispatching SUMMARIZED events
        """
        super().__init__()
        self.chat_id = chat_id
        self.message_service = message_service
        self.chat_service = chat_service
        self.events = events
        self._cached_messages: Optional[List[BaseMessage]] = None
        self._processed_summaries = (
            set()
        )  # Track processed summaries to avoid duplicates

    @property
    def messages(self) -> List[BaseMessage]:
        """Retrieve messages from knowledge graph.

        Note: This is a synchronous property, but message loading is async.
        For async access, use aget_messages() instead.

        Returns:
            List of LangChain BaseMessage objects (from cache if available)
        """
        # Return cached messages if available
        if self._cached_messages is not None:
            return self._cached_messages

        # For synchronous access, return empty list and log warning
        # Callers should use aget_messages() for async loading
        logger.warning(
            "messages property accessed but no cache available. "
            "Use aget_messages() for async loading."
        )
        return []

    async def aget_messages(self) -> List[BaseMessage]:
        """Async version of messages property."""
        if self._cached_messages is not None:
            return self._cached_messages

        try:
            # Get messages in LLM format from message service
            llm_messages = await self.message_service.get_recent_messages(
                chat_id=self.chat_id, limit=None, prefer_summaries=True
            )

            # Convert to LangChain messages
            langchain_messages = []
            for msg in llm_messages:
                role = msg.get("role", "user")
                parts = msg.get("parts", [])
                content = " ".join(str(part) for part in parts) if parts else ""

                if role == "user":
                    langchain_messages.append(HumanMessage(content=content))
                elif role == "model":
                    langchain_messages.append(AIMessage(content=content))
                elif role == "system":
                    langchain_messages.append(SystemMessage(content=content))

            self._cached_messages = langchain_messages
            logger.debug(
                f"Loaded {len(langchain_messages)} messages from knowledge graph for chat {self.chat_id}"
            )
            return langchain_messages

        except Exception as e:
            logger.error(
                f"Failed to load messages from knowledge graph: {e}", exc_info=True
            )
            return []

    def add_message(self, message: BaseMessage) -> None:
        """Add a single message to the history.

        Note: This is synchronous but message saving is async.
        For async access, use aadd_message() instead.

        Args:
            message: LangChain BaseMessage to add
        """
        logger.warning(
            "add_message() called synchronously. Use aadd_message() for async saving."
        )
        # Invalidate cache
        self._cached_messages = None

    def add_messages(self, messages: List[BaseMessage]) -> None:
        """Add multiple messages to the history.

        Note: This is synchronous but message saving is async.
        For async access, use aadd_messages() instead.

        Args:
            messages: List of LangChain BaseMessage objects to add
        """
        logger.warning(
            "add_messages() called synchronously. Use aadd_messages() for async saving."
        )
        # Invalidate cache
        self._cached_messages = None

    async def aadd_message(self, message: BaseMessage) -> None:
        """Async version of add_message."""
        await self.aadd_messages([message])

    async def aadd_messages(self, messages: List[BaseMessage]) -> None:
        """Async version of add_messages."""
        # Invalidate cache
        self._cached_messages = None

        for message in messages:
            try:
                # Convert LangChain message to knowledge graph format
                role = self._get_role_from_message(message)
                content = self._get_content_from_message(message)

                # Check if this is a summary message (from SummarizationMiddleware)
                is_summary = content.startswith("[Summary]") or (
                    hasattr(message, "additional_kwargs")
                    and message.additional_kwargs.get("summary", False)
                )

                # Determine message type
                if is_summary:
                    message_type = "summary"
                    # Remove prefix from summary content
                    content = content.replace("[Summary] ", "").strip()
                elif isinstance(message, SystemMessage):
                    message_type = "internal"
                elif isinstance(message, ToolMessage):
                    message_type = "tool_result"
                else:
                    message_type = "message"

                # Save message to knowledge graph
                message_node_id = await self.message_service.save_message(
                    content=content,
                    role=role,
                    internal=(message_type == "internal"),
                    message_type=message_type,
                )

                # Link message to chat
                if message_node_id:
                    await self.chat_service.link_message(
                        chat_id=self.chat_id, message_node_id=message_node_id
                    )

                # If this is a summary, fire SUMMARIZED event for compatibility
                if is_summary and self.events:
                    # Create a hash to track if we've processed this summary
                    summary_hash = hash(content)
                    if summary_hash not in self._processed_summaries:
                        self._processed_summaries.add(summary_hash)
                        await self.events.async_dispatch(BotEvents.SUMMARIZED, content)
                        logger.info("Summary detected and event fired")

                logger.debug(
                    "Saved message to knowledge graph: %s, role=%s, type=%s",
                    message_node_id,
                    role,
                    message_type,
                )

            except Exception as e:
                logger.error(
                    "Failed to save message to knowledge graph: %s", e, exc_info=True
                )

    def clear(self) -> None:
        """Clear all messages from history.

        Note: This doesn't delete from knowledge graph, just clears cache.
        For actual deletion, use repository methods.
        """
        self._cached_messages = []
        logger.warning(
            f"Cleared message cache for chat {self.chat_id} (messages still in graph)"
        )

    async def aclear(self) -> None:
        """Async version of clear."""
        self.clear()

    def _get_role_from_message(self, message: BaseMessage) -> str:
        """Extract role from LangChain message.

        Args:
            message: LangChain BaseMessage

        Returns:
            Role string ("user", "model", "system")
        """
        if isinstance(message, HumanMessage):
            return "user"
        elif isinstance(message, AIMessage):
            return "model"
        elif isinstance(message, SystemMessage):
            return "system"
        elif isinstance(message, ToolMessage):
            return "model"  # Tool results are from the model
        else:
            # Default to user for unknown message types
            logger.warning(
                f"Unknown message type: {type(message)}, defaulting to 'user'"
            )
            return "user"

    def _get_content_from_message(self, message: BaseMessage) -> str:
        """Extract content from LangChain message.

        Args:
            message: LangChain BaseMessage

        Returns:
            Content string
        """
        if hasattr(message, "content"):
            content = message.content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Handle list of content parts (e.g., text + images)
                text_parts = [str(part) for part in content if isinstance(part, str)]
                return " ".join(text_parts)
            else:
                return str(content)
        return ""
