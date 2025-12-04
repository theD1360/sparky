"""Authentication service for JWT token management and password hashing."""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.auth_models import User, UserSession
from database.database import get_database_manager

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.

    Args:
        data: Data to encode in the token (typically user_id, username, roles)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    # Add standard JWT claims
    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),  # Unique token ID for revocation
            "type": "access",
        }
    )

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token.

    Args:
        data: Data to encode in the token (typically user_id)

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),
            "type": "refresh",
        }
    )

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload, or None if invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_user_from_token(token: str, db: AsyncSession) -> Optional[User]:
    """Get user from JWT token.

    Args:
        token: JWT token string
        db: Database async session

    Returns:
        User object if token is valid, None otherwise
    """
    payload = decode_token(token)
    if payload is None:
        return None

    user_id: Optional[str] = payload.get("sub")  # Standard JWT claim for subject
    if user_id is None:
        return None

    stmt = select(User).filter(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    return user


async def revoke_token(token: str, db: AsyncSession) -> bool:
    """Revoke a token by storing its JTI in the database.

    Args:
        token: JWT token string
        db: Database session

    Returns:
        True if token was revoked, False otherwise
    """
    payload = decode_token(token)
    if payload is None:
        return False

    jti = payload.get("jti")
    user_id = payload.get("sub")
    exp = payload.get("exp")

    if not jti or not user_id or not exp:
        return False

    # Check if token is already revoked
    stmt = select(UserSession).filter(UserSession.token_jti == jti)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return True  # Already revoked

    # Create session record for revocation
    expires_at = datetime.utcfromtimestamp(exp)
    session = UserSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_jti=jti,
        expires_at=expires_at,
    )
    db.add(session)
    await db.commit()
    return True


async def is_token_revoked(token: str, db: AsyncSession) -> bool:
    """Check if a token has been revoked.

    Args:
        token: JWT token string
        db: Database async session

    Returns:
        True if token is revoked, False otherwise
    """
    payload = decode_token(token)
    if payload is None:
        return True  # Invalid token is considered revoked

    jti = payload.get("jti")
    if not jti:
        return True

    # Check if token JTI exists in revoked sessions
    stmt = select(UserSession).filter(UserSession.token_jti == jti)
    result = await db.execute(stmt)
    revoked = result.scalar_one_or_none()
    return revoked is not None


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """Remove expired session records from the database.

    Args:
        db: Database async session

    Returns:
        Number of sessions removed
    """
    from sqlalchemy import delete
    now = datetime.utcnow()
    stmt = select(UserSession).filter(UserSession.expires_at < now)
    result = await db.execute(stmt)
    expired = result.scalars().all()
    count = len(expired)
    if count > 0:
        delete_stmt = delete(UserSession).filter(UserSession.expires_at < now)
        await db.execute(delete_stmt)
        await db.commit()
    return count

