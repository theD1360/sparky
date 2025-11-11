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
    from servers.chat.chat_server import _app_toolchain

    if _app_toolchain:
        prompts = await _app_toolchain.list_all_prompts()
        return [PromptInfo(name=p.name, description=p.description) for _, p in prompts]
    else:
        return []

