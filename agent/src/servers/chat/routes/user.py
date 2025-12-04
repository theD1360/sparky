"""User-related API endpoints."""

from typing import List

from database.database import get_database_manager
from database.repository import KnowledgeRepository
from fastapi import APIRouter, Depends, HTTPException, status
from middleware.auth_middleware import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/api/user", tags=["user"])


class ChatInfo(BaseModel):
    """Chat information response model."""

    chat_id: str
    chat_name: str
    created_at: str | None
    updated_at: str | None
    archived: bool = False


class UserChatsResponse(BaseModel):
    """Response model for user chats."""

    user_id: str
    chats: List[ChatInfo]


class UpdateChatNameRequest(BaseModel):
    """Request model for updating chat name."""

    chat_name: str


@router.get("/{user_id}/chats", response_model=UserChatsResponse)
async def get_user_chats(
    user_id: str,
    limit: int = 100,
    offset: int = 0,
    include_archived: bool = False,
    current_user=Depends(get_current_user),
):
    """
    Retrieves all chats for a specific user across all their sessions.

    Args:
        user_id: The user ID to retrieve chats for
        limit: Maximum number of chats to return (default: 100)
        offset: Number of chats to skip for pagination (default: 0)
        include_archived: Whether to include archived chats (default: False)
        current_user: Authenticated user from JWT token

    Returns:
        UserChatsResponse with list of user's chats

    Raises:
        HTTPException: 403 if user tries to access another user's chats, 404 if user not found, 500 on database error
    """
    # Verify that the authenticated user matches the requested user_id
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own chats",
        )

    try:
        # Get database manager and connect
        db_manager = get_database_manager()
        if not db_manager.engine:
            await db_manager.connect()

        repository = KnowledgeRepository(db_manager)

        # Use the repository method to get user chats
        chats = await repository.get_user_chats(
            user_id=user_id,
            limit=limit,
            offset=offset,
            include_archived=include_archived,
        )

        if not chats and offset == 0:
            # Check if user exists
            user_node = await repository.get_node(f"user:{user_id}")
            if not user_node:
                raise HTTPException(
                    status_code=404, detail=f"User '{user_id}' not found"
                )

        # Convert to response model
        chat_infos = [
            ChatInfo(
                chat_id=chat["chat_id"],
                chat_name=chat["chat_name"],
                created_at=chat["created_at"],
                updated_at=chat["updated_at"],
                archived=chat.get("archived", False),
            )
            for chat in chats
        ]

        return UserChatsResponse(user_id=user_id, chats=chat_infos)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/{user_id}/chats/{chat_id}")
async def update_chat_name(
    user_id: str,
    chat_id: str,
    request: UpdateChatNameRequest,
    current_user=Depends(get_current_user),
):
    """
    Updates the name of a specific chat.

    Args:
        user_id: The user ID (for validation)
        chat_id: The chat ID to update
        request: Request body containing the new chat name
        current_user: Authenticated user from JWT token

    Returns:
        Updated chat information

    Raises:
        HTTPException: 403 if user tries to access another user's chat, 404 if chat not found, 500 on database error
    """
    # Verify that the authenticated user matches the requested user_id
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own chats",
        )

    try:
        # Get database manager and connect
        db_manager = get_database_manager()
        if not db_manager.engine:
            await db_manager.connect()

        repository = KnowledgeRepository(db_manager)

        # Update chat name
        updated_chat = await repository.update_chat_name(chat_id, request.chat_name)

        if not updated_chat:
            raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

        return {
            "chat_id": chat_id,
            "chat_name": request.chat_name,
            "updated_at": (
                updated_chat.updated_at.isoformat() if updated_chat.updated_at else None
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/{user_id}/chats/{chat_id}")
async def delete_chat(
    user_id: str, chat_id: str, current_user=Depends(get_current_user)
):
    """
    Permanently deletes a chat and all its messages.

    Args:
        user_id: The user ID (for validation)
        chat_id: The chat ID to delete
        current_user: Authenticated user from JWT token

    Returns:
        Success message

    Raises:
        HTTPException: 403 if user tries to delete another user's chat, 404 if chat not found, 500 on database error
    """
    # Verify that the authenticated user matches the requested user_id
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own chats",
        )

    try:
        # Get database manager and connect
        db_manager = get_database_manager()
        if not db_manager.engine:
            await db_manager.connect()

        repository = KnowledgeRepository(db_manager)

        # Delete chat
        result = await repository.delete_chat(chat_id)

        if not result:
            raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

        return {"message": "Chat deleted successfully", "chat_id": chat_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/{user_id}/chats/{chat_id}/archive")
async def archive_chat(
    user_id: str, chat_id: str, current_user=Depends(get_current_user)
):
    """
    Archives a chat (soft delete - hides from main list but preserves data).

    Args:
        user_id: The user ID (for validation)
        chat_id: The chat ID to archive
        current_user: Authenticated user from JWT token

    Returns:
        Updated chat information

    Raises:
        HTTPException: 403 if user tries to archive another user's chat, 404 if chat not found, 500 on database error
    """
    # Verify that the authenticated user matches the requested user_id
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only archive your own chats",
        )

    try:
        # Get database manager and connect
        db_manager = get_database_manager()
        if not db_manager.engine:
            await db_manager.connect()

        repository = KnowledgeRepository(db_manager)

        # Archive chat
        archived_chat = await repository.archive_chat(chat_id)

        if not archived_chat:
            raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

        return {
            "message": "Chat archived successfully",
            "chat_id": chat_id,
            "archived_at": (
                archived_chat.properties.get("archived_at")
                if archived_chat.properties
                else None
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/{user_id}/chats/{chat_id}/unarchive")
async def unarchive_chat(
    user_id: str, chat_id: str, current_user=Depends(get_current_user)
):
    """
    Unarchives a chat (restores from archived state).

    Args:
        user_id: The user ID (for validation)
        chat_id: The chat ID to unarchive
        current_user: Authenticated user from JWT token

    Returns:
        Updated chat information

    Raises:
        HTTPException: 403 if user tries to unarchive another user's chat, 404 if chat not found, 500 on database error
    """
    # Verify that the authenticated user matches the requested user_id
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only unarchive your own chats",
        )

    try:
        # Get database manager and connect
        db_manager = get_database_manager()
        if not db_manager.engine:
            await db_manager.connect()

        repository = KnowledgeRepository(db_manager)

        # Unarchive chat
        unarchived_chat = await repository.unarchive_chat(chat_id)

        if not unarchived_chat:
            raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

        return {
            "message": "Chat unarchived successfully",
            "chat_id": chat_id,
            "updated_at": (
                unarchived_chat.updated_at.isoformat()
                if unarchived_chat.updated_at
                else None
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
