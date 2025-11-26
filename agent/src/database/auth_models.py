"""SQLAlchemy models for user authentication and management."""

# Import Base - handle both relative and absolute imports for migration compatibility
# When loaded via importlib (migrations), Base will be injected into module __dict__ by env.py
import sys
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

_current_module = sys.modules.get(__name__)
if hasattr(_current_module, "Base") and "Base" in _current_module.__dict__:
    # Base was pre-injected (for migrations via importlib)
    Base = _current_module.__dict__["Base"]
else:
    # Normal import path
    try:
        # Try relative import (works when imported as a module)
        from .models import Base
    except (ImportError, ValueError, SystemError):
        # Fallback: load models directly
        from pathlib import Path

        database_dir = Path(__file__).parent
        models_path = database_dir / "models.py"
        import importlib.util

        spec = importlib.util.spec_from_file_location("models", models_path)
        models_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(models_module)
        Base = models_module.Base

# Check if PostgreSQL is available
try:
    from sqlalchemy.dialects import postgresql

    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False


def get_json_type():
    """Return appropriate JSON type based on database."""
    # This will be determined at runtime based on the database connection
    # For now, we'll use a generic approach
    return JSON


class User(Base):
    """User model for authentication and user management.

    Stores sensitive user data separate from the knowledge graph.
    Links to knowledge graph via external_id property in user nodes.
    """

    __tablename__ = "users"

    # Primary key - UUID
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Authentication fields
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)

    # Status fields
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_login = Column(DateTime, nullable=True)

    # Flexible metadata (for future OAuth/SAML integration)
    # For PostgreSQL: JSONB, for SQLite: JSON
    extradata = Column(JSON, nullable=True)

    # Relationships
    roles = relationship(
        "UserRole", back_populates="user", cascade="all, delete-orphan"
    )
    sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_users_username", "username"),
        Index("idx_users_email", "email"),
        Index("idx_users_active", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<User(id='{self.id}', username='{self.username}', email='{self.email}')>"
        )

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert user to dictionary format.

        Args:
            include_sensitive: If True, include sensitive fields like password_hash

        Returns:
            Dictionary representation of user
        """
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "metadata": self.extradata or {},
        }

        if include_sensitive:
            data["password_hash"] = self.password_hash

        return data


class UserRole(Base):
    """User role model for role-based access control.

    Supports multiple roles per user (e.g., admin, user, guest).
    """

    __tablename__ = "user_roles"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key to users
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Role name (e.g., "admin", "user", "guest")
    role = Column(String, nullable=False, index=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="roles")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_user_role"),
        Index("idx_user_roles_user", "user_id"),
        Index("idx_user_roles_role", "role"),
    )

    def __repr__(self) -> str:
        return f"<UserRole(user_id='{self.user_id}', role='{self.role}')>"

    def to_dict(self) -> dict:
        """Convert user role to dictionary format."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserSession(Base):
    """User session model for tracking active sessions and token revocation.

    Optional table for managing JWT token revocation and session tracking.
    """

    __tablename__ = "user_sessions"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key to users
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # JWT token ID (jti claim) for revocation
    token_jti = Column(String, unique=True, nullable=False, index=True)

    # Expiration timestamp
    expires_at = Column(DateTime, nullable=False)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="sessions")

    # Indexes
    __table_args__ = (
        Index("idx_user_sessions_user", "user_id"),
        Index("idx_user_sessions_jti", "token_jti"),
        Index("idx_user_sessions_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<UserSession(id='{self.id}', user_id='{self.user_id}', token_jti='{self.token_jti}')>"

    def to_dict(self) -> dict:
        """Convert user session to dictionary format."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "token_jti": self.token_jti,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
