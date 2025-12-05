"""Chat-specific API endpoints."""

from typing import List

from database.database import get_database_manager
from database.repository import KnowledgeRepository
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/chats", tags=["chats"])


class FileAttachment(BaseModel):
    """File attachment model."""

    file_id: str
    name: str
    description: str | None = None
    size: int | None = None


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str
    text: str
    created_at: str | None
    message_type: str | None = None
    tool_name: str | None = None
    tool_args: dict | None = None
    attachments: List[FileAttachment] | None = None


class ChatMessagesResponse(BaseModel):
    """Response model for chat messages."""

    chat_id: str
    messages: List[ChatMessage]


@router.get("/{chat_id}/messages", response_model=ChatMessagesResponse)
async def get_chat_messages(chat_id: str, limit: int = 100, offset: int = 0):
    """
    Retrieves messages for a specific chat.

    Args:
        chat_id: The chat ID to retrieve messages for
        limit: Maximum number of messages to return (default: 100)
        offset: Number of messages to skip for pagination (default: 0)

    Returns:
        List of chat messages

    Raises:
        HTTPException: 404 if chat not found, 500 on database error
    """
    try:
        # Get database manager and connect
        db_manager = get_database_manager()
        if not db_manager.engine:
            await db_manager.connect()

        repository = KnowledgeRepository(db_manager)

        # Get chat messages
        messages = await repository.get_chat_messages(
            chat_id, limit=limit, offset=offset
        )

        # Batch load all attachments for all messages in one query (avoid N+1 problem)
        message_ids = [msg.id for msg in messages]
        all_attachment_edges = []
        if message_ids:
            try:
                # Get all HAS_ATTACHMENT edges for all messages at once
                from database.models import Edge
                from sqlalchemy import select

                db_manager = repository.db_manager
                async with db_manager.get_session() as session:
                    stmt = select(Edge).filter(
                        Edge.source_id.in_(message_ids),
                        Edge.edge_type == "HAS_ATTACHMENT",
                    )
                    result = await session.execute(stmt)
                    all_attachment_edges = result.scalars().all()
                    # Expunge to detach from session
                    for edge in all_attachment_edges:
                        session.expunge(edge)
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(
                    f"Error batch loading attachments: {e}"
                )

        # Build attachment lookup: message_id -> list of file_ids
        attachment_lookup = {}
        for edge in all_attachment_edges:
            if edge.source_id not in attachment_lookup:
                attachment_lookup[edge.source_id] = []
            attachment_lookup[edge.source_id].append(edge.target_id)

        # Transform to response format, filtering out internal messages
        message_list = []
        for msg in messages:
            # Filter out internal messages (identity, context, etc.)
            # Check both 'internal' property and 'message_type' == 'internal'
            properties = msg.properties or {}
            is_internal = properties.get("internal", False)
            message_type = properties.get("message_type", "message")

            # Skip internal messages (identity prompts, summaries, etc.)
            if is_internal or message_type == "internal":
                continue

            # Get role from properties - should always be set for new messages
            # Ensure properties is a dict
            if not isinstance(properties, dict):
                import logging

                logging.getLogger(__name__).error(
                    "Message %s has invalid properties type: %s. Expected dict, got %s",
                    msg.id,
                    type(properties),
                    properties,
                )
                properties = {}

            # Get role - should be "user" or "model" (stored as lowercase)
            role = properties.get("role")

            # Normalize role to handle case sensitivity and whitespace
            if isinstance(role, str):
                role = role.strip().lower()

            # Validate role - must be "user" or "model"
            if role not in ("user", "model"):
                # Role is missing - this is an old message created before role tracking
                # These are legacy messages that predate role tracking
                # Default to "user" for backward compatibility
                # (We can't reliably infer which old messages were from user vs model)
                import logging

                logger = logging.getLogger(__name__)
                # Only log at debug level for old messages to reduce log noise
                logger.debug(
                    "Legacy message %s missing role property (created before role tracking). "
                    "Defaulting to 'user'. Properties: %s",
                    msg.id,
                    properties,
                )
                role = "user"
            else:
                # Role is present - log at debug to verify new messages work correctly
                import logging

                logging.getLogger(__name__).debug(
                    "Message %s has role '%s'", msg.id, role
                )

            text = msg.content or ""

            # Get tool data directly from properties (no parsing needed!)
            tool_name = properties.get("tool_name")
            tool_args = properties.get("tool_args")

            # OPTIMIZATION: Truncate large tool results to improve frontend performance
            # Large tool results (>50KB) can cause slow rendering and high memory usage
            MAX_TOOL_RESULT_SIZE = 50000  # 50KB limit for tool results
            if message_type == "tool_result" and len(text) > MAX_TOOL_RESULT_SIZE:
                truncated_size = len(text)
                text = (
                    text[:MAX_TOOL_RESULT_SIZE]
                    + f"\n\n... [Output truncated: {truncated_size:,} bytes total, showing first {MAX_TOOL_RESULT_SIZE:,} bytes]"
                )

            # Get file attachments for this message from our pre-loaded lookup
            attachments = []
            file_ids = attachment_lookup.get(msg.id, [])
            for file_id in file_ids:
                try:
                    file_node = await repository.get_node(file_id)
                    if file_node:
                        file_props = file_node.properties or {}
                        attachments.append(
                            FileAttachment(
                                file_id=file_node.id,
                                name=file_props.get("file_name", "unknown"),
                                description=file_props.get("ai_description"),
                                size=file_props.get("file_size"),
                            )
                        )
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning(
                        f"Error fetching file node {file_id}: {e}"
                    )

            message_list.append(
                ChatMessage(
                    role=role,
                    text=text,
                    created_at=msg.created_at.isoformat() if msg.created_at else None,
                    message_type=message_type,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    attachments=attachments if attachments else None,
                )
            )

        return ChatMessagesResponse(chat_id=chat_id, messages=message_list)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
