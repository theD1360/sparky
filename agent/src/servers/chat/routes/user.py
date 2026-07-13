"""User-related API endpoints."""

from typing import Any, Dict, List, Optional

from database.database import get_database_manager
from database.repository import KnowledgeRepository
from fastapi import APIRouter, Depends, HTTPException, status
from middleware.auth_middleware import get_current_user
from pydantic import BaseModel, Field
from services.chat_service import ChatService
from services.model_catalog import is_allowed_model, resolve_chat_model
from services.user_mcp import (
    extras_list_to_map,
    list_system_servers_readonly,
    map_to_extras_list,
    mask_extra_servers,
    normalize_remote_definition,
    system_server_names,
)
from services.user_service import UserService

router = APIRouter(prefix="/api/user", tags=["user"])


class ChatInfo(BaseModel):
    """Chat information response model."""

    chat_id: str
    chat_name: str
    created_at: str | None
    updated_at: str | None
    archived: bool = False
    model: Optional[str] = None


class UserChatsResponse(BaseModel):
    """Response model for user chats."""

    user_id: str
    chats: List[ChatInfo]


class UpdateChatNameRequest(BaseModel):
    """Request model for updating chat name."""

    chat_name: str


class UpdateChatModelRequest(BaseModel):
    """Request model for updating chat LLM model."""

    model: str = Field(..., min_length=1)


class UserMCPServerDefinition(BaseModel):
    """Remote-only MCP server definition for user extras."""

    name: Optional[str] = None
    url: Optional[str] = None
    type: Optional[str] = None
    transport: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    bearerToken: Optional[str] = None
    description: Optional[str] = None


async def _ensure_db() -> KnowledgeRepository:
    db_manager = get_database_manager()
    if not db_manager.engine:
        await db_manager.connect()
    return KnowledgeRepository(db_manager)


async def _get_connection_manager():
    from servers.chat.chat_server import _connection_manager

    return _connection_manager


@router.get("/{user_id}/chats", response_model=UserChatsResponse)
async def get_user_chats(
    user_id: str,
    limit: int = 100,
    offset: int = 0,
    include_archived: bool = False,
    current_user=Depends(get_current_user),
):
    """Retrieves all chats for a specific user across all their sessions."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own chats",
        )

    try:
        repository = await _ensure_db()
        chats = await repository.get_user_chats(
            user_id=user_id,
            limit=limit,
            offset=offset,
            include_archived=include_archived,
        )

        if not chats and offset == 0:
            user_node = await repository.get_node(f"user:{user_id}")
            if not user_node:
                raise HTTPException(
                    status_code=404, detail=f"User '{user_id}' not found"
                )

        chat_infos = [
            ChatInfo(
                chat_id=chat["chat_id"],
                chat_name=chat["chat_name"],
                created_at=chat["created_at"],
                updated_at=chat["updated_at"],
                archived=chat.get("archived", False),
                model=chat.get("model"),
            )
            for chat in chats
        ]

        return UserChatsResponse(user_id=user_id, chats=chat_infos)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/{user_id}/chats/{chat_id}/model")
async def update_chat_model(
    user_id: str,
    chat_id: str,
    request: UpdateChatModelRequest,
    current_user=Depends(get_current_user),
):
    """Set the LLM model for a chat and live-swap the active session if present."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own chats",
        )

    model_name = request.model.strip()
    if not is_allowed_model(model_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{model_name}' is not allowed",
        )

    try:
        repository = await _ensure_db()
        chat_service = ChatService(repository)
        chat = await chat_service.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

        props = chat.properties or {}
        if props.get("user_id") and props.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chat does not belong to this user",
            )

        updated = await chat_service.set_chat_model(chat_id, model_name)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Chat '{chat_id}' not found")

        cm = await _get_connection_manager()
        await cm.set_chat_model(user_id, chat_id, model_name)

        return {
            "chat_id": chat_id,
            "model": model_name,
            "effective_model": resolve_chat_model(model_name),
        }
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
    """Updates the name of a specific chat."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own chats",
        )

    try:
        repository = await _ensure_db()
        chat_service = ChatService(repository)
        updated_chat = await chat_service.rename_chat(chat_id, request.chat_name)

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
    """Permanently deletes a chat and all its messages."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own chats",
        )

    try:
        repository = await _ensure_db()
        chat_service = ChatService(repository)
        result = await chat_service.delete_chat(chat_id)

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
    """Archives a chat (soft delete - hides from main list but preserves data)."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only archive your own chats",
        )

    try:
        repository = await _ensure_db()
        chat_service = ChatService(repository)
        archived_chat = await chat_service.archive_chat(chat_id)

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
    """Unarchives a chat (restores from archived state)."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only unarchive your own chats",
        )

    try:
        repository = await _ensure_db()
        chat_service = ChatService(repository)
        unarchived_chat = await chat_service.unarchive_chat(chat_id)

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


# ---------------------------------------------------------------------------
# User MCP extras (remote servers only; system catalog is read-only)
# ---------------------------------------------------------------------------


@router.get("/{user_id}/mcp/servers")
async def list_user_mcp_servers(
    user_id: str, current_user=Depends(get_current_user)
) -> Dict[str, Any]:
    """List system (read-only) and personal remote MCP servers."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own MCP servers",
        )
    repository = await _ensure_db()
    user_service = UserService(repository)
    extras = await user_service.get_user_preference(user_id, "mcp.extra", [])
    if not isinstance(extras, list):
        extras = []
    return {
        "success": True,
        "system": list_system_servers_readonly(),
        "extra": mask_extra_servers(extras),
    }


@router.post("/{user_id}/mcp/servers", status_code=201)
async def create_user_mcp_server(
    user_id: str,
    body: UserMCPServerDefinition,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Add a personal remote MCP server."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own MCP servers",
        )
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Server name is required")
    if name in system_server_names():
        raise HTTPException(
            status_code=403,
            detail=f"'{name}' is a system server and cannot be overridden",
        )

    repository = await _ensure_db()
    user_service = UserService(repository)
    extras = await user_service.get_user_preference(user_id, "mcp.extra", [])
    if not isinstance(extras, list):
        extras = []
    servers = extras_list_to_map(extras)
    if name in servers:
        raise HTTPException(status_code=409, detail=f"Server '{name}' already exists")

    try:
        definition = normalize_remote_definition(
            body.model_dump(exclude_none=True, exclude={"name"})
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    servers[name] = definition
    await user_service.set_user_preference(
        user_id, "mcp.extra", map_to_extras_list(servers)
    )

    cm = await _get_connection_manager()
    tool_count, reload_error = await cm.reload_tools_for_user(user_id)

    return {
        "success": True,
        "server": mask_extra_servers([{"name": name, **definition}])[0],
        "tools_loaded": tool_count,
        "reload_error": reload_error,
    }


@router.put("/{user_id}/mcp/servers/{server_name}")
async def update_user_mcp_server(
    user_id: str,
    server_name: str,
    body: UserMCPServerDefinition,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Update a personal remote MCP server."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own MCP servers",
        )
    if server_name in system_server_names():
        raise HTTPException(
            status_code=403,
            detail="System MCP servers cannot be modified by users",
        )

    repository = await _ensure_db()
    user_service = UserService(repository)
    extras = await user_service.get_user_preference(user_id, "mcp.extra", [])
    if not isinstance(extras, list):
        extras = []
    servers = extras_list_to_map(extras)
    if server_name not in servers:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")

    try:
        definition = normalize_remote_definition(
            body.model_dump(exclude_none=True, exclude={"name"}),
            existing=servers[server_name],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    servers[server_name] = definition
    await user_service.set_user_preference(
        user_id, "mcp.extra", map_to_extras_list(servers)
    )

    cm = await _get_connection_manager()
    tool_count, reload_error = await cm.reload_tools_for_user(user_id)

    return {
        "success": True,
        "server": mask_extra_servers([{"name": server_name, **definition}])[0],
        "tools_loaded": tool_count,
        "reload_error": reload_error,
    }


@router.delete("/{user_id}/mcp/servers/{server_name}")
async def delete_user_mcp_server(
    user_id: str,
    server_name: str,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Remove a personal remote MCP server."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own MCP servers",
        )
    if server_name in system_server_names():
        raise HTTPException(
            status_code=403,
            detail="System MCP servers cannot be deleted by users",
        )

    repository = await _ensure_db()
    user_service = UserService(repository)
    extras = await user_service.get_user_preference(user_id, "mcp.extra", [])
    if not isinstance(extras, list):
        extras = []
    servers = extras_list_to_map(extras)
    if server_name not in servers:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")

    del servers[server_name]
    await user_service.set_user_preference(
        user_id, "mcp.extra", map_to_extras_list(servers)
    )

    cm = await _get_connection_manager()
    tool_count, reload_error = await cm.reload_tools_for_user(user_id)

    return {
        "success": True,
        "deleted": server_name,
        "tools_loaded": tool_count,
        "reload_error": reload_error,
    }


@router.post("/{user_id}/mcp/reload")
async def reload_user_mcp(
    user_id: str, current_user=Depends(get_current_user)
) -> Dict[str, Any]:
    """Reload this user's toolchain only (system + personal extras)."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only reload your own tools",
        )
    cm = await _get_connection_manager()
    tool_count, reload_error = await cm.reload_tools_for_user(user_id)
    if reload_error:
        raise HTTPException(status_code=500, detail=reload_error)
    return {"success": True, "tools_loaded": tool_count}
