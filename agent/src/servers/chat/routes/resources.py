"""Resource management API endpoints."""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["resources"])


class ResourceInfo(BaseModel):
    """Resource information response model."""

    uri: str
    description: str | None


@router.get("/resources", response_model=List[ResourceInfo])
async def list_resources():
    """
    Endpoint to list available resources from the toolchain.

    Returns:
        List of available resources with URI and description
    """
    # Import here to avoid circular dependency
    from servers.chat.chat_server import _app_toolchain

    if _app_toolchain:
        resources = await _app_toolchain.list_all_resources()
        return [
            ResourceInfo(uri=str(r.uri), description=r.description)
            for _, r in resources
        ]
    else:
        return []
