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
    from servers.chat.chat_server import _connection_manager

    # Get toolchain from connection manager (per-user toolchains)
    # For API endpoint, we'll return resources from the first available toolchain
    # In the future, this could be user-specific
    if _connection_manager and _connection_manager.langchain_toolchains:
        # Get first available toolchain
        toolchain = next(iter(_connection_manager.langchain_toolchains.values()))
        resources = await toolchain.list_resources()
        # Resources are (server_name, resource_uri) tuples
        # We don't have descriptions easily available, so return URIs only
        return [
            ResourceInfo(uri=str(resource_uri), description=None)
            for _, resource_uri in resources
        ]
    else:
        # Return empty if no toolchain available yet
        return []
