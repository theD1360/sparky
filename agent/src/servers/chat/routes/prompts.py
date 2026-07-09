"""Prompt management API endpoints."""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["prompts"])


class PromptInfo(BaseModel):
    """Prompt information response model."""

    name: str
    description: str | None


@router.get("/prompts", response_model=List[PromptInfo])
async def list_prompts():
    """
    Endpoint to list available prompts from the toolchain.

    Returns:
        List of available prompts with name and description
    """
    # Import here to avoid circular dependency
    from servers.chat.chat_server import _connection_manager

    # Get toolchain from connection manager (per-user toolchains)
    # For API endpoint, we'll return prompts from the first available toolchain
    # In the future, this could be user-specific
    if _connection_manager and _connection_manager.langchain_toolchains:
        # Get first available toolchain
        toolchain = next(iter(_connection_manager.langchain_toolchains.values()))
        prompts = await toolchain.list_prompts()
        # Prompts are (server_name, prompt_name) tuples
        # We don't have descriptions easily available, so return names only
        return [
            PromptInfo(name=prompt_name, description=None) for _, prompt_name in prompts
        ]
    else:
        # Return empty if no toolchain available yet
        return []
