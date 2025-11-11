"""Health check API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    startup_error: str | None = None


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for container orchestration.

    Returns:
        HealthResponse with service status
    """
    # Import here to avoid circular dependency
    from servers.chat.chat_server import _startup_error

    return HealthResponse(
        status="healthy", service="sparky-server", startup_error=_startup_error
    )

