"""User management API endpoints for admin panel."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from database.auth_models import User
from middleware.auth_middleware import get_current_active_user, get_db, require_admin
from services.user_management_service import UserManagementService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/admin/users", tags=["user-management"])


class CreateUserRequest(BaseModel):
    """Create user request model."""

    username: str
    email: EmailStr
    password: str
    is_active: bool = True
    is_verified: bool = False
    roles: List[str] = ["user"]


class UpdateUserRequest(BaseModel):
    """Update user request model."""

    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserResponse(BaseModel):
    """User response model."""

    id: str
    username: str
    email: str
    is_active: bool
    is_verified: bool
    roles: List[str]
    created_at: str
    updated_at: str
    last_login: Optional[str] = None

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
            created_at=user.created_at.isoformat() if user.created_at else "",
            updated_at=user.updated_at.isoformat() if user.updated_at else "",
            last_login=user.last_login.isoformat() if user.last_login else None,
        )


class AssignRoleRequest(BaseModel):
    """Assign role request model."""

    role: str


@router.get("", response_model=List[UserResponse])
@require_admin
async def list_users(
    limit: int = 100,
    offset: int = 0,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all users (admin only).

    Args:
        limit: Maximum number of users to return
        offset: Number of users to skip
        is_active: Filter by active status
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of users
    """
    user_service = UserManagementService(db)
    users = user_service.list_users(limit=limit, offset=offset, is_active=is_active)
    return [UserResponse.from_user(user, user_service) for user in users]


@router.get("/{user_id}", response_model=UserResponse)
@require_admin
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get user by ID (admin only).

    Args:
        user_id: User ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        User information

    Raises:
        HTTPException: If user not found
    """
    user_service = UserManagementService(db)
    user = user_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found",
        )

    return UserResponse.from_user(user, user_service)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@require_admin
async def create_user(
    request: CreateUserRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new user (admin only).

    Args:
        request: Create user request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created user information

    Raises:
        HTTPException: If creation fails
    """
    user_service = UserManagementService(db)
    user = user_service.create_user(
        username=request.username,
        email=request.email,
        password=request.password,
        is_active=request.is_active,
        is_verified=request.is_verified,
        roles=request.roles,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists",
        )

    return UserResponse.from_user(user, user_service)


@router.put("/{user_id}", response_model=UserResponse)
@require_admin
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update user information (admin only).

    Args:
        user_id: User ID
        request: Update user request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated user information

    Raises:
        HTTPException: If user not found or update fails
    """
    user_service = UserManagementService(db)

    # Build update kwargs
    update_kwargs = {}
    if request.username is not None:
        update_kwargs["username"] = request.username
    if request.email is not None:
        update_kwargs["email"] = request.email
    if request.password is not None:
        update_kwargs["password"] = request.password
    if request.is_active is not None:
        update_kwargs["is_active"] = request.is_active
    if request.is_verified is not None:
        update_kwargs["is_verified"] = request.is_verified

    user = user_service.update_user(user_id, **update_kwargs)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found or update failed",
        )

    return UserResponse.from_user(user, user_service)


@router.delete("/{user_id}")
@require_admin
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete a user (admin only).

    Args:
        user_id: User ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If user not found
    """
    user_service = UserManagementService(db)
    success = user_service.delete_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found",
        )

    return {"message": "User deleted successfully", "user_id": user_id}


@router.post("/{user_id}/roles", status_code=status.HTTP_201_CREATED)
@require_admin
async def assign_role(
    user_id: str,
    request: AssignRoleRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Assign a role to a user (admin only).

    Args:
        user_id: User ID
        request: Assign role request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If user not found or assignment fails
    """
    user_service = UserManagementService(db)
    success = user_service.assign_role(user_id, request.role)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found or role assignment failed",
        )

    return {"message": f"Role '{request.role}' assigned successfully", "user_id": user_id}


@router.delete("/{user_id}/roles/{role}")
@require_admin
async def remove_role(
    user_id: str,
    role: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Remove a role from a user (admin only).

    Args:
        user_id: User ID
        role: Role name
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If user not found or role removal fails
    """
    user_service = UserManagementService(db)
    success = user_service.remove_role(user_id, role)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found or role '{role}' not assigned",
        )

    return {"message": f"Role '{role}' removed successfully", "user_id": user_id}

