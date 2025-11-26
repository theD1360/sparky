"""Authentication API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from database.auth_models import User
from middleware.auth_middleware import get_current_active_user, get_db
from services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    revoke_token,
)
from services.user_management_service import UserManagementService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """Login request model."""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """Registration request model."""

    username: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response model."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Refresh token request model."""

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Change password request model."""

    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request model."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request model."""

    token: str
    new_password: str


class UserResponse(BaseModel):
    """User response model."""

    id: str
    username: str
    email: str
    is_active: bool
    is_verified: bool
    roles: list[str]

    @classmethod
    def from_user(cls, user: User, user_service: UserManagementService) -> "UserResponse":
        """Create UserResponse from User model."""
        roles = user_service.get_user_roles(user.id)
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_verified=user.is_verified,
            roles=roles,
        )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new user.

    Args:
        request: Registration request
        db: Database session

    Returns:
        Created user information

    Raises:
        HTTPException: If registration fails
    """
    user_service = UserManagementService(db)
    
    # Check if this is the first user - make them admin
    user_count = len(user_service.list_users(limit=1))
    is_first_user = user_count == 0
    
    user = user_service.create_user(
        username=request.username,
        email=request.email,
        password=request.password,
        is_verified=False,  # Email verification required
        roles=["admin"] if is_first_user else ["user"],  # First user gets admin role
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists",
        )

    return UserResponse.from_user(user, user_service)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """Login and get JWT tokens.

    Args:
        request: Login request
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If authentication fails
    """
    import time
    start_time = time.time()
    
    user_service = UserManagementService(db)
    
    # Authenticate user (optimized single query)
    auth_start = time.time()
    user = user_service.authenticate_user(request.username, request.password)
    auth_time = time.time() - auth_start
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user roles (optimized query)
    roles_start = time.time()
    roles = user_service.get_user_roles(user.id)
    roles_time = time.time() - roles_start

    # Create tokens (should be instant)
    token_start = time.time()
    token_data = {
        "sub": user.id,
        "username": user.username,
        "email": user.email,
        "roles": roles,
    }
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data={"sub": user.id})
    token_time = time.time() - token_start
    
    total_time = time.time() - start_time
    
    # Log timing for debugging (remove in production if not needed)
    if total_time > 1.0:  # Only log if slow
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Slow login detected: total={total_time:.2f}s, "
            f"auth={auth_time:.2f}s, roles={roles_time:.2f}s, token={token_time:.2f}s"
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """Refresh access token using refresh token.

    Args:
        request: Refresh token request
        db: Database session

    Returns:
        New access and refresh tokens

    Raises:
        HTTPException: If refresh token is invalid
    """
    payload = decode_token(request.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_service = UserManagementService(db)
    user = user_service.get_user_by_id(user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user roles
    roles = user_service.get_user_roles(user.id)

    # Create new tokens
    token_data = {
        "sub": user.id,
        "username": user.username,
        "email": user.email,
        "roles": roles,
    }
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data={"sub": user.id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Logout and revoke token.

    Args:
        current_user: Current authenticated user (from token)
        db: Database session

    Returns:
        Success message

    Note:
        Token revocation is handled client-side by removing tokens from storage.
        For stateless JWTs, this is typically sufficient. If token revocation
        is needed, the token JTI can be stored in user_sessions table.
    """
    # Token was already validated by get_current_active_user
    # Client will remove tokens from localStorage
    # Optional: Could revoke token here by storing JTI in user_sessions table
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get current user information.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Current user information
    """
    user_service = UserManagementService(db)
    return UserResponse.from_user(current_user, user_service)


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Change user password.

    Args:
        request: Change password request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If current password is incorrect
    """
    user_service = UserManagementService(db)

    # Verify current password
    user = user_service.authenticate_user(current_user.username, request.current_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Update password
    updated_user = user_service.update_user(current_user.id, password=request.new_password)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password",
        )

    return {"message": "Password changed successfully"}


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """Request password reset.

    Args:
        request: Forgot password request
        db: Database session

    Returns:
        Success message (always returns success for security)

    Note:
        In production, this should send an email with reset link
    """
    user_service = UserManagementService(db)
    user = user_service.get_user_by_email(request.email)

    # Always return success to prevent email enumeration
    # In production, send reset email if user exists
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Reset password using reset token.

    Args:
        request: Reset password request
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If reset token is invalid

    Note:
        Reset token should be a JWT token with reset claim
    """
    # Decode reset token
    payload = decode_token(request.token)
    if payload is None or payload.get("type") != "reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    user_service = UserManagementService(db)
    updated_user = user_service.update_user(user_id, password=request.new_password)

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to reset password",
        )

    return {"message": "Password reset successfully"}

