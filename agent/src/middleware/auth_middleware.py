"""Authentication middleware for FastAPI routes and WebSocket connections."""

import logging
from functools import wraps
from typing import AsyncGenerator, Callable, List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_database_manager
from services.auth_service import (
    decode_token,
    get_user_from_token,
    is_token_revoked,
)
from services.user_management_service import UserManagementService

logger = logging.getLogger(__name__)

# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    db_manager = get_database_manager()
    # Ensure connection is established (only connects once)
    if not db_manager.engine:
        await db_manager.connect()
    # Create session from the already-connected manager
    async with db_manager.get_session() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> "User":  # type: ignore
    """Dependency to get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer token credentials
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    from database.auth_models import User

    token = credentials.credentials

    # Decode and verify token
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if token is revoked
    if await is_token_revoked(token, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from token
    user = await get_user_from_token(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def get_current_active_user(
    current_user: "User" = Depends(get_current_user),  # type: ignore
) -> "User":  # type: ignore
    """Dependency to get current active user.

    Args:
        current_user: Current user from get_current_user

    Returns:
        Active user object

    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return current_user


def require_roles(*required_roles: str):
    """Decorator to require specific roles for a route.

    Args:
        *required_roles: Required role names (user must have at least one)

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(
            current_user: "User" = Depends(get_current_user),  # type: ignore
            db: AsyncSession = Depends(get_db),
            *args,
            **kwargs,
        ):
            from services.user_management_service import UserManagementService

            user_service = UserManagementService(db)
            user_roles = await user_service.get_user_roles(current_user.id)

            # Check if user has any of the required roles
            if not any(role in user_roles for role in required_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required roles: {', '.join(required_roles)}",
                )

            return await func(current_user=current_user, db=db, *args, **kwargs)

        return wrapper

    return decorator


def require_admin(func: Callable) -> Callable:
    """Decorator to require admin role for a route.

    Args:
        func: Route function to protect

    Returns:
        Decorated function
    """
    return require_roles("admin")(func)


async def get_user_from_websocket_token(token: Optional[str]) -> Optional["User"]:  # type: ignore
    """Get user from JWT token for WebSocket connections.

    Args:
        token: JWT token string (optional)

    Returns:
        User object if token is valid, None otherwise
    """
    if not token:
        return None

    try:
        db_manager = get_database_manager()
        if not db_manager.engine:
            await db_manager.connect()
        
        async with db_manager.get_session() as db:
            payload = decode_token(token)
            if payload is None:
                return None

            # Check if token is revoked
            if await is_token_revoked(token, db):
                return None

            user = await get_user_from_token(token, db)
            if user and user.is_active:
                return user

            return None
    except Exception as e:
        logger.error(f"Error validating WebSocket token: {e}", exc_info=True)
        return None

