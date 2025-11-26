"""Message service for handling chat message operations.

Handles message CRUD operations, token estimation, history management,
and summary preference logic.
"""

import datetime
import logging

# Import TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from database.models import Node
from database.repository import KnowledgeRepository

from .token_usage import TokenEstimator

if TYPE_CHECKING:
    from .file_service import FileService

logger = logging.getLogger(__name__)


class MessageService:
    """Service for managing chat messages in the knowledge graph.

    Provides methods for saving, retrieving, and formatting chat messages,
    with support for token estimation and summary-based history truncation.
    """

    def __init__(
        self,
        repository: KnowledgeRepository,
        token_estimator: Optional[TokenEstimator] = None,
        file_service: Optional["FileService"] = None,
    ):
        """Initialize the message service.

        Args:
            repository: Knowledge graph repository instance
            token_estimator: Optional token estimator (if None, creates CharacterBasedEstimator)
            file_service: Optional file service for handling file attachments
        """
        self.repository = repository
        if token_estimator is None:
            from .token_usage import CharacterBasedEstimator

            self.token_estimator = CharacterBasedEstimator()
        else:
            self.token_estimator = token_estimator

        self.file_service = file_service

    def save_message(
        self,
        content: str,
        role: str,
        session_id: Optional[str] = None,  # Deprecated: kept for backward compatibility
        chat_id: Optional[str] = None,
        internal: bool = False,
        message_type: str = "message",
        tool_name: Optional[str] = None,
        tool_args: Optional[dict] = None,
        file_node_id: Optional[str] = None,
    ) -> Optional[str]:
        """Save a message to the knowledge graph.

        Args:
            content: The message content
            role: The role of the speaker (e.g., 'user', 'model')
            session_id: Deprecated - Session identifier (kept for backward compatibility)
            chat_id: Chat identifier (required)
            internal: Whether this is an internal/system message
            message_type: Type of message ('message', 'tool_use', 'tool_result', 'thought', 'summary', 'internal')
            tool_name: Optional tool name for tool_use and tool_result messages
            tool_args: Optional tool arguments for tool_use messages
            file_node_id: Optional file node ID for attachments

        Returns:
            The node ID of the created message, or None if failed
        """
        if not chat_id:
            logger.warning(
                f"Cannot save message to graph: chat_id is None (role={role})"
            )
            return None

        try:
            # Get current message count from graph for this chat
            # Get messages for accurate count
            current_messages = self.repository.get_chat_messages(
                chat_id=chat_id
            )
            message_num = len(current_messages) + 1
            logger.debug(
                f"Calculated message_num={message_num} for chat {chat_id} "
                f"(found {len(current_messages)} existing messages)"
            )

            chat_node_id = f"chat:{chat_id}:{message_num}"

            logger.info(
                f"Saving message to graph: node_id={chat_node_id}, role={role}, "
                f"chat_id={chat_id}, internal={internal}, "
                f"message_type={message_type}"
            )

            # Build properties with role, internal flag, message type, and optional tool data
            properties = {
                "role": role,
                "internal": internal,
                "message_type": message_type,
            }

            # Add tool-specific properties if provided
            if tool_name:
                properties["tool_name"] = tool_name
            if tool_args:
                properties["tool_args"] = tool_args

            self.repository.add_node(
                node_id=chat_node_id,
                node_type="ChatMessage",
                label=f"Chat Message {message_num}",
                content=content,
                properties=properties,
            )
            logger.debug(f"Created ChatMessage node: {chat_node_id}")

            # Link message to chat node
            chat_node_full_id = f"chat:{chat_id}"
            try:
                # Verify chat node exists before linking
                chat_node = self.repository.get_node(chat_node_full_id)
                if chat_node:
                    self.repository.add_edge(
                        source_id=chat_node_full_id,
                        target_id=chat_node_id,
                        edge_type="CONTAINS",
                    )
                    logger.debug(
                        f"Linked message to chat node: {chat_node_full_id} -[CONTAINS]-> {chat_node_id}"
                    )
                else:
                    logger.warning(
                        f"Chat node {chat_node_full_id} not found, cannot link message"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to link message to chat node for chat_id={chat_id}: {e}"
                )

            # Link file attachment if provided
            if file_node_id:
                logger.debug(
                    f"Linking file attachment: {chat_node_id} -> {file_node_id}"
                )
                # Use file service if available, otherwise use direct repository
                if self.file_service:
                    self.file_service.link_file_to_message(file_node_id, chat_node_id)
                else:
                    self.repository.add_edge(
                        source_id=chat_node_id,
                        target_id=file_node_id,
                        edge_type="HAS_ATTACHMENT",
                    )
                logger.info(
                    f"Successfully linked file to message: {chat_node_id} -[HAS_ATTACHMENT]-> {file_node_id}"
                )

            logger.info(f"Successfully saved message to graph: {chat_node_id}")
            return chat_node_id

        except Exception as e:
            logger.error(
                f"Failed to create chat node for session={session_id}, chat_id={chat_id}: {e}",
                exc_info=True,
            )
            return None

    def get_recent_messages(
        self,
        chat_id: Optional[str],
        limit: Optional[int] = None,
        prefer_summaries: bool = True,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent messages from the knowledge graph.

        Prioritizes summaries over old chat history to reduce token usage:
        - If summaries exist and prefer_summaries is True, only includes messages after the most recent summary
        - Includes the summary itself to provide context
        - This prevents loading all historical messages when they've been summarized
        - Uses session fallback to handle orphaned messages

        Args:
            chat_id: Chat identifier to retrieve messages from
            limit: Maximum number of messages to retrieve. If None, uses a reasonable default.
            prefer_summaries: If True, prefers loading from most recent summary forward

        Returns:
            List of messages in LLM format: [{"role": "user/model", "parts": ["content"]}]
        """
        if not chat_id:
            logger.debug("No chat_id provided - starting fresh chat with no history")
            return []

        try:
            # Get all messages from the graph
            nodes = self.repository.get_chat_messages(
                chat_id=chat_id, limit=None
            )
            logger.debug(
                f"Retrieved {len(nodes)} total messages for chat {chat_id} (including session fallback)"
            )

            if prefer_summaries:
                # Find the most recent summary
                most_recent_summary_idx = -1
                for i in range(len(nodes) - 1, -1, -1):
                    node = nodes[i]
                    if (
                        node.properties
                        and node.properties.get("message_type") == "summary"
                    ):
                        most_recent_summary_idx = i
                        break

                # If we found a summary, only include messages from that point forward
                if most_recent_summary_idx >= 0:
                    nodes = nodes[most_recent_summary_idx:]
                    logger.info(
                        f"Found summary at index {most_recent_summary_idx}, "
                        f"using {len(nodes)} messages from that point forward"
                    )
                else:
                    # No summary found, take the last N messages to stay within context window
                    if limit:
                        nodes = nodes[-limit:] if len(nodes) > limit else nodes
                    logger.info(f"No summary found, using last {len(nodes)} messages")
            else:
                # Just apply limit if provided
                if limit:
                    nodes = nodes[-limit:] if len(nodes) > limit else nodes

            # Convert to LLM format
            messages = self._convert_nodes_to_llm_format(nodes)

            logger.info(
                f"Retrieved {len(messages)} messages from graph for chat {chat_id}"
            )
            return messages

        except Exception as e:
            logger.error(f"Failed to retrieve messages from graph: {e}", exc_info=True)
            return []

    def format_for_summary(self, chat_id: str, since_last_summary: bool = True) -> str:
        """Create a concise text dump of conversation for summarization.

        Only summarizes messages since the last summary to avoid re-summarizing
        already summarized content and to stay within token limits.
        Uses session fallback to ensure all messages are included.

        Args:
            chat_id: Chat identifier
            since_last_summary: If True, only format messages after the most recent summary

        Returns:
            Formatted string with role: content pairs
        """
        try:
            # Get all messages for the chat
            nodes = self.repository.get_chat_messages(
                chat_id=chat_id
            )
            logger.debug(
                f"Retrieved {len(nodes)} messages for summary formatting (chat {chat_id})"
            )

            if since_last_summary:
                # Find the most recent summary to avoid re-summarizing old content
                most_recent_summary_idx = -1
                for i in range(len(nodes) - 1, -1, -1):
                    node = nodes[i]
                    if (
                        node.properties
                        and node.properties.get("message_type") == "summary"
                    ):
                        most_recent_summary_idx = i
                        break

                # Only format messages after the last summary
                if most_recent_summary_idx >= 0:
                    # Skip the summary itself, only get messages after it
                    nodes = nodes[most_recent_summary_idx + 1 :]
                    logger.info(
                        f"Formatting {len(nodes)} messages for summary "
                        f"(since last summary at index {most_recent_summary_idx})"
                    )

            if nodes:
                return self._format_nodes_for_summary(nodes)

            return ""

        except Exception as e:
            logger.warning(f"Failed to format history from graph: {e}")
            return ""

    def estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate the total number of tokens in a list of messages.

        Args:
            messages: List of messages in LLM format

        Returns:
            Estimated total number of tokens
        """
        return self.token_estimator.estimate_messages_tokens(messages)

    def get_messages_within_token_limit(
        self, chat_id: str, max_tokens: int, prefer_summaries: bool = True
    ) -> List[Dict[str, Any]]:
        """Retrieve messages that fit within a token limit.

        Retrieves messages starting from the most recent and working backward,
        stopping when the token limit would be exceeded.
        Uses session fallback to ensure all messages are accessible.

        Args:
            chat_id: Chat identifier
            max_tokens: Maximum number of tokens to include
            prefer_summaries: If True, prefers loading from most recent summary forward

        Returns:
            List of messages in LLM format that fit within the token limit
        """
        # Get recent messages (with summary preference and session fallback enabled)
        messages = self.get_recent_messages(
            chat_id=chat_id, limit=None, prefer_summaries=prefer_summaries
        )
        logger.debug(
            f"Retrieved {len(messages)} messages to fit within {max_tokens} token limit"
        )

        if not messages:
            return []

        # Estimate tokens and truncate if necessary
        total_tokens = self.estimate_tokens(messages)

        if total_tokens <= max_tokens:
            logger.info(
                f"All {len(messages)} messages fit within {max_tokens} token limit "
                f"(estimated {total_tokens} tokens)"
            )
            return messages

        # Need to truncate - work backward from the end
        logger.info(
            f"Messages exceed token limit ({total_tokens} > {max_tokens}), truncating..."
        )

        included_messages = []
        current_tokens = 0

        # Start from the most recent message and work backward
        for message in reversed(messages):
            message_tokens = self.token_estimator.estimate_messages_tokens([message])

            if current_tokens + message_tokens <= max_tokens:
                included_messages.insert(0, message)
                current_tokens += message_tokens
            else:
                # Stop if adding this message would exceed the limit
                break

        logger.info(
            f"Truncated to {len(included_messages)} messages "
            f"(estimated {current_tokens} tokens)"
        )

        return included_messages

    def _convert_nodes_to_llm_format(self, nodes: List[Node]) -> List[Dict[str, Any]]:
        """Convert ChatMessage nodes to LLM format.

        Args:
            nodes: List of ChatMessage Node objects

        Returns:
            List of messages in format: {"role": "user/model", "parts": ["content"]}
        """
        messages = []

        for node in nodes:
            try:
                # Extract role from node properties (default to 'user' if not found)
                role = (
                    node.properties.get("role", "user") if node.properties else "user"
                )

                # Get content from node
                content = node.content or ""

                # Build message in LLM format
                message = {"role": role, "parts": [content]}

                messages.append(message)

            except Exception as e:
                logger.warning(f"Failed to convert node {node.id} to LLM format: {e}")
                continue

        return messages

    def _format_nodes_for_summary(self, nodes: List[Node]) -> str:
        """Format ChatMessage nodes as text for summarization.

        Args:
            nodes: List of ChatMessage Node objects

        Returns:
            Formatted string with role: content pairs
        """
        lines: List[str] = []

        try:
            for node in nodes or []:
                # Extract role from node properties
                role = node.properties.get("role", "") if node.properties else ""
                role_str = str(role) or ""

                # Get content from node
                content = node.content or ""

                if content:
                    lines.append(f"{role_str}: {content}")

        except Exception as e:
            logger.warning(f"Failed to format nodes for summary: {e}")

        # Return last 400 lines to limit size
        return "\n".join(lines[-400:])
