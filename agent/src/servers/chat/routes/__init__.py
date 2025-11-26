"""FastAPI routers for the chat server API."""

from .admin import router as admin_router
from .auth import router as auth_router
from .chats import router as chats_router
from .health import router as health_router
from .prompts import router as prompts_router
from .resources import router as resources_router
from .user import router as user_router
from .user_management import router as user_management_router

__all__ = [
    "health_router",
    "resources_router",
    "prompts_router",
    "user_router",
    "chats_router",
    "admin_router",
    "auth_router",
    "user_management_router",
]

