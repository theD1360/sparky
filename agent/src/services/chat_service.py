"""Chat service for handling chat operations.

Handles chat creation, renaming, archiving, and deletion operations.
"""

import logging
from typing import Optional

from database.models import Edge, Node
from database.repository import KnowledgeRepository
from sqlalchemy import select

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chats in the knowledge graph.

    Provides methods for creating, renaming, archiving, and deleting chats,
    with proper validation and error handling.
    """

    def __init__(self, repository: KnowledgeRepository):
        """Initialize the chat service.

        Args:
            repository: Knowledge graph repository instance
        """
        self.repository = repository

    async def create_chat(
        self, chat_id: str, chat_name: str, user_id: str
    ) -> Optional[Node]:
        """Create a chat node and link it directly to a user.

        Args:
            chat_id: Unique chat identifier
            chat_name: Display name for the chat
            user_id: User ID to link the chat to

        Returns:
            Created Chat node or None if user doesn't exist
        """
        try:
            chat_node = await self.repository.create_chat(
                chat_id=chat_id, chat_name=chat_name, user_id=user_id
            )
            if chat_node:
                logger.info(f"Created chat {chat_id} for user {user_id}")
            else:
                logger.warning(
                    f"Failed to create chat {chat_id}: user {user_id} not found"
                )
            return chat_node
        except Exception as e:
            logger.error(
                f"Failed to create chat {chat_id} for user {user_id}: {e}",
                exc_info=True,
            )
            return None

    async def get_chat(self, chat_id: str) -> Optional[Node]:
        """Get a chat by its ID.

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)

        Returns:
            Chat node if found, None otherwise
        """
        try:
            return await self.repository.get_chat(chat_id=chat_id)
        except Exception as e:
            logger.error(f"Failed to get chat {chat_id}: {e}", exc_info=True)
            return None

    async def get_or_create_chat(
        self, chat_id: str, chat_name: str, user_id: str
    ) -> Optional[Node]:
        """Get an existing chat or create a new one if it doesn't exist.

        Args:
            chat_id: Unique chat identifier
            chat_name: Display name for the chat (used only if creating new)
            user_id: User ID to link the chat to

        Returns:
            Chat node (existing or newly created), or None if creation failed
        """
        try:
            # Try to get existing chat
            existing_chat = await self.get_chat(chat_id)
            if existing_chat:
                logger.info(f"Found existing chat {chat_id}, reusing it")
                return existing_chat

            # Chat doesn't exist, create it
            logger.info(f"Chat {chat_id} not found, creating new chat")
            return await self.create_chat(
                chat_id=chat_id, chat_name=chat_name, user_id=user_id
            )
        except Exception as e:
            logger.error(
                f"Failed to get or create chat {chat_id} for user {user_id}: {e}",
                exc_info=True,
            )
            return None

    async def rename_chat(self, chat_id: str, new_name: str) -> Optional[Node]:
        """Rename a chat.

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)
            new_name: New name for the chat

        Returns:
            Updated Chat node or None if not found
        """
        try:
            updated_chat = await self.repository.update_chat_name(
                chat_id=chat_id, new_name=new_name
            )
            if updated_chat:
                logger.info(f"Renamed chat {chat_id} to '{new_name}'")
            else:
                logger.warning(f"Failed to rename chat {chat_id}: chat not found")
            return updated_chat
        except Exception as e:
            logger.error(
                f"Failed to rename chat {chat_id} to '{new_name}': {e}",
                exc_info=True,
            )
            return None

    async def archive_chat(self, chat_id: str) -> Optional[Node]:
        """Archive a chat (soft delete - hides from main list but preserves data).

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)

        Returns:
            Updated Chat node or None if not found
        """
        try:
            archived_chat = await self.repository.archive_chat(chat_id=chat_id)
            if archived_chat:
                logger.info(f"Archived chat {chat_id}")
            else:
                logger.warning(f"Failed to archive chat {chat_id}: chat not found")
            return archived_chat
        except Exception as e:
            logger.error(f"Failed to archive chat {chat_id}: {e}", exc_info=True)
            return None

    async def unarchive_chat(self, chat_id: str) -> Optional[Node]:
        """Unarchive a chat (restore from archived state).

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)

        Returns:
            Updated Chat node or None if not found
        """
        try:
            unarchived_chat = await self.repository.unarchive_chat(chat_id=chat_id)
            if unarchived_chat:
                logger.info(f"Unarchived chat {chat_id}")
            else:
                logger.warning(f"Failed to unarchive chat {chat_id}: chat not found")
            return unarchived_chat
        except Exception as e:
            logger.error(f"Failed to unarchive chat {chat_id}: {e}", exc_info=True)
            return None

    async def link_chat(self, chat_id: str, user_id: str) -> bool:
        """Link a chat to a user by creating a BELONGS_TO edge.

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)
            user_id: User identifier (without 'user:' prefix)

        Returns:
            True if linked successfully, False otherwise
        """
        try:
            chat_node_id = f"chat:{chat_id}"
            user_node_id = f"user:{user_id}"

            # Verify both nodes exist
            chat_node = await self.repository.get_node(chat_node_id)
            if not chat_node:
                logger.warning(f"Cannot link chat: chat {chat_id} not found")
                return False

            user_node = await self.repository.get_node(user_node_id)
            if not user_node:
                logger.warning(f"Cannot link chat: user {user_id} not found")
                return False

            # Check if edge already exists
            edges = await self.repository.get_edges(
                source_id=chat_node_id,
                target_id=user_node_id,
                edge_type="BELONGS_TO",
            )

            if not edges:
                # Create the edge
                await self.repository.add_edge(
                    source_id=chat_node_id,
                    target_id=user_node_id,
                    edge_type="BELONGS_TO",
                )
                logger.info(f"Linked chat {chat_id} to user {user_id}")
            else:
                logger.debug(f"Chat {chat_id} already linked to user {user_id}")

            return True
        except Exception as e:
            logger.error(
                f"Failed to link chat {chat_id} to user {user_id}: {e}",
                exc_info=True,
            )
            return False

    async def link_message(self, chat_id: str, message_node_id: str) -> bool:
        """Link a message node to a chat by creating a CONTAINS edge.

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)
            message_node_id: Full message node ID (e.g., "message:uuid" or "chat:chat_id:num")

        Returns:
            True if linked successfully, False otherwise
        """
        try:
            chat_node_id = f"chat:{chat_id}"

            # Verify both nodes exist
            chat_node = await self.repository.get_node(chat_node_id)
            if not chat_node:
                logger.warning(
                    f"Cannot link message: chat {chat_id} not found (message: {message_node_id})"
                )
                return False

            message_node = await self.repository.get_node(message_node_id)
            if not message_node:
                logger.warning(
                    f"Cannot link message: message {message_node_id} not found (chat: {chat_id})"
                )
                return False

            # Verify message is a ChatMessage node
            if message_node.node_type != "ChatMessage":
                logger.warning(
                    f"Cannot link message: node {message_node_id} is not a ChatMessage (type: {message_node.node_type})"
                )
                return False

            # Check if edge already exists
            edges = await self.repository.get_edges(
                source_id=chat_node_id,
                target_id=message_node_id,
                edge_type="CONTAINS",
            )

            if not edges:
                # Create the edge
                await self.repository.add_edge(
                    source_id=chat_node_id,
                    target_id=message_node_id,
                    edge_type="CONTAINS",
                )
                logger.info(
                    f"✓ Linked message {message_node_id} to chat {chat_id} "
                    f"(chat_node: {chat_node_id})"
                )

                # Update message properties to include chat_id if not already set
                if not message_node.properties or not message_node.properties.get(
                    "chat_id"
                ):
                    # Update the node properties
                    await self.repository.update_node(
                        node_id=message_node_id,
                        properties={"chat_id": chat_id},
                    )
                    logger.debug(
                        f"Updated message {message_node_id} properties with chat_id {chat_id}"
                    )
            else:
                logger.debug(
                    f"Message {message_node_id} already linked to chat {chat_id}"
                )

            return True
        except Exception as e:
            logger.error(
                f"Failed to link message {message_node_id} to chat {chat_id}: {e}",
                exc_info=True,
            )
            return False

    async def link_unlinked_messages(self, chat_id: str) -> int:
        """Link any unlinked messages to a chat by finding messages with chat_id in properties.

        This is useful for linking messages that were created before the chat node existed.

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)

        Returns:
            Number of messages linked
        """
        try:
            chat_node_id = f"chat:{chat_id}"

            # Verify chat node exists
            chat_node = await self.repository.get_node(chat_node_id)
            if not chat_node:
                logger.warning(f"Cannot link messages: chat {chat_id} not found")
                return 0

            # Find all ChatMessage nodes that have this chat_id in their properties
            # but aren't linked via CONTAINS edge
            async with self.repository.db_manager.get_session() as session:
                # Get all ChatMessage nodes with this chat_id in properties
                all_messages_result = await session.execute(
                    select(Node).filter(Node.node_type == "ChatMessage")
                )
                all_messages = all_messages_result.scalars().all()

                linked_count = 0
                for message in all_messages:
                    # Check if message has this chat_id in properties
                    if (
                        message.properties
                        and message.properties.get("chat_id") == chat_id
                    ):
                        # Check if already linked
                        existing_edges_result = await session.execute(
                            select(Edge).filter(
                                Edge.source_id == chat_node_id,
                                Edge.target_id == message.id,
                                Edge.edge_type == "CONTAINS",
                            )
                        )
                        existing_edges = existing_edges_result.scalars().all()

                        if not existing_edges:
                            # Link the message
                            await self.repository.add_edge(
                                source_id=chat_node_id,
                                target_id=message.id,
                                edge_type="CONTAINS",
                            )
                            linked_count += 1
                            logger.debug(
                                f"Linked unlinked message {message.id} to chat {chat_id}"
                            )

                if linked_count > 0:
                    logger.info(
                        f"Linked {linked_count} unlinked messages to chat {chat_id}"
                    )
                return linked_count

        except Exception as e:
            logger.error(
                f"Failed to link unlinked messages for chat {chat_id}: {e}",
                exc_info=True,
            )
            return 0

    async def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat and all its messages permanently.

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)

        Returns:
            True if deleted, False if not found
        """
        try:
            result = await self.repository.delete_chat(chat_id=chat_id)
            if result:
                logger.info(f"Deleted chat {chat_id} and all its messages")
            else:
                logger.warning(f"Failed to delete chat {chat_id}: chat not found")
            return result
        except Exception as e:
            logger.error(f"Failed to delete chat {chat_id}: {e}", exc_info=True)
            return False
