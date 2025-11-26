"""User management service for CRUD operations and role management."""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.auth_models import User, UserRole
from database.database import get_database_manager
from services.auth_service import get_password_hash, verify_password

logger = logging.getLogger(__name__)


class UserManagementService:
    """Service for managing users, roles, and authentication."""

    def __init__(self, db: Session):
        """Initialize the user management service.

        Args:
            db: Database session
        """
        self.db = db

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        is_active: bool = True,
        is_verified: bool = False,
        roles: Optional[List[str]] = None,
        **metadata: Any,
    ) -> Optional[User]:
        """Create a new user.

        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password (will be hashed)
            is_active: Whether user is active
            is_verified: Whether email is verified
            roles: List of roles to assign (default: ["user"])
            **metadata: Additional metadata to store

        Returns:
            Created User object, or None if creation failed
        """
        try:
            # Check if username or email already exists
            existing_user = (
                self.db.query(User)
                .filter(
                    (User.username == username) | (User.email == email)
                )
                .first()
            )
            if existing_user:
                logger.warning(
                    f"User with username '{username}' or email '{email}' already exists"
                )
                return None

            # Hash password
            password_hash = get_password_hash(password)

            # Create user
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                is_active=is_active,
                is_verified=is_verified,
                extradata=metadata if metadata else None,
            )
            self.db.add(user)
            self.db.flush()  # Flush to get user.id

            # Assign default role if none provided
            if roles is None:
                roles = ["user"]

            # Create roles
            for role in roles:
                user_role = UserRole(user_id=user.id, role=role)
                self.db.add(user_role)

            self.db.commit()
            self.db.refresh(user)

            logger.info(f"Created user: {username} (id: {user.id})")
            return user

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create user {username}: {e}", exc_info=True)
            return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User object, or None if not found
        """
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username.

        Args:
            username: Username

        Returns:
            User object, or None if not found
        """
        return self.db.query(User).filter(User.username == username).first()

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email.

        Args:
            email: Email address

        Returns:
            User object, or None if not found
        """
        return self.db.query(User).filter(User.email == email).first()

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user by username and password.

        Args:
            username: Username or email
            password: Plain text password

        Returns:
            User object if authentication succeeds, None otherwise
        """
        # Optimize: Single query to find user by username OR email
        from sqlalchemy import or_
        from database.auth_models import User
        
        user = (
            self.db.query(User)
            .filter(or_(User.username == username, User.email == username))
            .first()
        )

        if not user:
            logger.debug(f"User not found: {username}")
            return None

        if not user.is_active:
            logger.debug(f"User {username} is not active")
            return None

        if not verify_password(password, user.password_hash):
            logger.debug(f"Invalid password for user: {username}")
            return None

        # Update last login
        from datetime import datetime

        user.last_login = datetime.utcnow()
        self.db.commit()

        return user

    def update_user(
        self,
        user_id: str,
        username: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        **metadata: Any,
    ) -> Optional[User]:
        """Update user information.

        Args:
            user_id: User ID
            username: New username (optional)
            email: New email (optional)
            password: New password (optional, will be hashed)
            is_active: Active status (optional)
            is_verified: Verified status (optional)
            **metadata: Additional metadata to update

        Returns:
            Updated User object, or None if not found
        """
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                logger.warning(f"User not found: {user_id}")
                return None

            # Check for username/email conflicts if changing
            if username and username != user.username:
                existing = self.get_user_by_username(username)
                if existing:
                    logger.warning(f"Username already exists: {username}")
                    return None
                user.username = username

            if email and email != user.email:
                existing = self.get_user_by_email(email)
                if existing:
                    logger.warning(f"Email already exists: {email}")
                    return None
                user.email = email

            if password:
                user.password_hash = get_password_hash(password)

            if is_active is not None:
                user.is_active = is_active

            if is_verified is not None:
                user.is_verified = is_verified

            # Update metadata
            if metadata:
                current_metadata = user.extradata or {}
                current_metadata.update(metadata)
                user.extradata = current_metadata

            self.db.commit()
            self.db.refresh(user)

            logger.info(f"Updated user: {user_id}")
            return user

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update user {user_id}: {e}", exc_info=True)
            return None

    def delete_user(self, user_id: str) -> bool:
        """Delete a user.

        Args:
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                logger.warning(f"User not found: {user_id}")
                return False

            self.db.delete(user)
            self.db.commit()

            logger.info(f"Deleted user: {user_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete user {user_id}: {e}", exc_info=True)
            return False

    def list_users(
        self, limit: int = 100, offset: int = 0, is_active: Optional[bool] = None
    ) -> List[User]:
        """List users with pagination.

        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            is_active: Filter by active status (optional)

        Returns:
            List of User objects
        """
        query = self.db.query(User)

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        return query.offset(offset).limit(limit).all()

    def get_user_roles(self, user_id: str) -> List[str]:
        """Get all roles for a user.

        Args:
            user_id: User ID

        Returns:
            List of role names
        """
        # Optimize: Use direct query with only role column
        roles = (
            self.db.query(UserRole.role)
            .filter(UserRole.user_id == user_id)
            .all()
        )
        return [role[0] for role in roles]  # Extract role from tuple

    def assign_role(self, user_id: str, role: str) -> bool:
        """Assign a role to a user.

        Args:
            user_id: User ID
            role: Role name

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if user exists
            user = self.get_user_by_id(user_id)
            if not user:
                logger.warning(f"User not found: {user_id}")
                return False

            # Check if role already assigned
            existing = (
                self.db.query(UserRole)
                .filter(UserRole.user_id == user_id, UserRole.role == role)
                .first()
            )
            if existing:
                logger.debug(f"Role '{role}' already assigned to user {user_id}")
                return True

            # Create role
            user_role = UserRole(user_id=user_id, role=role)
            self.db.add(user_role)
            self.db.commit()

            logger.info(f"Assigned role '{role}' to user {user_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to assign role '{role}' to user {user_id}: {e}", exc_info=True
            )
            return False

    def remove_role(self, user_id: str, role: str) -> bool:
        """Remove a role from a user.

        Args:
            user_id: User ID
            role: Role name

        Returns:
            True if successful, False otherwise
        """
        try:
            user_role = (
                self.db.query(UserRole)
                .filter(UserRole.user_id == user_id, UserRole.role == role)
                .first()
            )

            if not user_role:
                logger.warning(
                    f"Role '{role}' not assigned to user {user_id}"
                )
                return False

            self.db.delete(user_role)
            self.db.commit()

            logger.info(f"Removed role '{role}' from user {user_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to remove role '{role}' from user {user_id}: {e}", exc_info=True
            )
            return False

    def has_role(self, user_id: str, role: str) -> bool:
        """Check if a user has a specific role.

        Args:
            user_id: User ID
            role: Role name

        Returns:
            True if user has the role, False otherwise
        """
        user_role = (
            self.db.query(UserRole)
            .filter(UserRole.user_id == user_id, UserRole.role == role)
            .first()
        )
        return user_role is not None

    def has_any_role(self, user_id: str, roles: List[str]) -> bool:
        """Check if a user has any of the specified roles.

        Args:
            user_id: User ID
            roles: List of role names

        Returns:
            True if user has any of the roles, False otherwise
        """
        user_roles = (
            self.db.query(UserRole)
            .filter(UserRole.user_id == user_id, UserRole.role.in_(roles))
            .first()
        )
        return user_roles is not None

