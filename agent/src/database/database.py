"""Database connection and session management for the knowledge base."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool, StaticPool

from .embeddings import EmbeddingManager
from .models import Base

logger = logging.getLogger(__name__)

# Global database manager instance
_db_manager: Optional["DatabaseManager"] = None


class DatabaseManager:
    """Manages database connections and sessions.

    Provides a centralized way to manage database connections with proper
    connection pooling, transaction handling, and cleanup.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        db_path: Optional[Path] = None,
        echo: bool = False,
    ):
        """Initialize database manager.

        Args:
            db_url: Database URL (for PostgreSQL or other databases)
            db_path: Path to the SQLite database file (for SQLite)
            echo: Whether to echo SQL statements for debugging

        Note: Either db_url or db_path must be provided. If both are provided,
        db_url takes precedence.
        """
        if db_url:
            # Convert PostgreSQL URL to async format if needed
            if db_url.startswith("postgresql://") and not db_url.startswith(
                "postgresql+psycopg://"
            ):
                self.db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
            elif db_url.startswith("postgresql+asyncpg://"):
                self.db_url = db_url.replace(
                    "postgresql+asyncpg://", "postgresql+psycopg://", 1
                )
            elif db_url.startswith("postgresql+psycopg2://"):
                self.db_url = db_url.replace(
                    "postgresql+psycopg2://", "postgresql+psycopg://", 1
                )
            else:
                self.db_url = db_url
            self.is_sqlite = db_url.startswith("sqlite")
            self.db_path = None
        elif db_path:
            # Convert SQLite to async format
            self.db_url = f"sqlite+aiosqlite:///{db_path}"
            self.is_sqlite = True
            self.db_path = db_path
        else:
            raise ValueError("Either db_url or db_path must be provided")

        self.echo = echo
        self.engine: Optional[AsyncEngine] = None
        self.SessionLocal: Optional[async_sessionmaker] = None

    async def connect(self) -> None:
        """Create database engine and session factory."""
        if self.engine is not None:
            logger.warning("Database already connected")
            return

        # Create engine with database-specific configurations
        if self.is_sqlite:
            # SQLite-specific configuration with aiosqlite
            self.engine = create_async_engine(
                self.db_url,
                echo=self.echo,
                poolclass=NullPool,  # SQLite with aiosqlite works better with NullPool
                connect_args={
                    "check_same_thread": False,  # Allow multi-threading
                },
            )

            # Enable SQLite optimizations and load sqlite-vec
            @event.listens_for(self.engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")

                # Load sqlite-vec extension
                try:
                    import sqlite_vec

                    # Enable extension loading
                    dbapi_connection.enable_load_extension(True)
                    sqlite_vec.load(dbapi_connection)
                    dbapi_connection.enable_load_extension(False)
                    logger.debug("sqlite-vec extension loaded successfully")
                except ImportError:
                    logger.warning(
                        "sqlite-vec not available. Vector search will not work."
                    )
                except Exception as e:
                    logger.warning(f"Failed to load sqlite-vec extension: {e}")

                cursor.close()

            logger.debug(f"Database connected: {self.db_path}")
        else:
            # PostgreSQL or other database configuration
            # Note: For async engines, poolclass is automatically AsyncAdaptedQueuePool
            self.engine = create_async_engine(
                self.db_url,
                echo=self.echo,
                pool_size=10,  # Increased pool size for better performance
                max_overflow=20,  # Increased overflow
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,  # Recycle connections after 1 hour
                connect_args={
                    "connect_timeout": 10,  # 10 second connection timeout for psycopg
                } if "postgresql" in self.db_url else {},
            )

            logger.debug(f"Database connected: {self.db_url}")

        # Create async session factory
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        # Initialize embedding manager singleton
        try:
            EmbeddingManager.get_instance()
            logger.debug("EmbeddingManager initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize EmbeddingManager: {e}")

        # Enable pgvector for PostgreSQL on first connection
        if not self.is_sqlite and "postgresql" in self.db_url:
            try:
                async with self.engine.begin() as conn:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    logger.debug("pgvector extension enabled")
            except Exception as e:
                logger.warning(f"Failed to enable pgvector extension: {e}")

        # Note: Table creation is handled by Alembic migrations
        # Run migrations with: sparky db migrate
        # Base.metadata.create_all(bind=self.engine) is not needed when using Alembic
        logger.debug(
            "Database connection established (tables managed by Alembic migrations)"
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a new database session with proper transaction management.

        This context manager ensures that:
        - Transactions are committed on successful completion
        - Transactions are rolled back on exceptions
        - Sessions are properly closed after use

        Yields:
            SQLAlchemy async session instance

        Raises:
            RuntimeError: If database not connected
        """
        if self.SessionLocal is None:
            raise RuntimeError("Database not connected. Call connect() first.")

        async with self.SessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.SessionLocal = None
            logger.debug("Database connections closed")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


def get_database_manager(
    db_url: Optional[str] = None, db_path: Optional[Path] = None
) -> DatabaseManager:
    """Get or create the global database manager.

    Args:
        db_url: Database URL (for PostgreSQL or other databases)
        db_path: Path to database file (for SQLite). If None, uses default path.

    Returns:
        DatabaseManager instance
    """
    global _db_manager

    if _db_manager is None:
        # Check for database URL from environment variable first
        if db_url is None:
            import os

            db_url = os.getenv("SPARKY_DB_URL")

        if db_url is None and db_path is None:
            # Check for DATABASE_PATH environment variable
            import os

            db_path_env = os.getenv("DATABASE_PATH")
            if db_path_env:
                db_path = Path(db_path_env)
            else:
                # Default to SQLite in current directory
                db_path = Path("knowledge_graph.db")

        _db_manager = DatabaseManager(db_url=db_url, db_path=db_path)

    return _db_manager


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session from the global manager.

    Yields:
        SQLAlchemy async session instance

    Raises:
        RuntimeError: If database manager not initialized
    """
    if _db_manager is None:
        raise RuntimeError(
            "Database manager not initialized. Call get_database_manager() first."
        )

    async with _db_manager.get_session() as session:
        yield session


async def initialize_database(
    db_url: Optional[str] = None,
    db_path: Optional[Path] = None,
    echo: bool = False,
) -> DatabaseManager:
    """Initialize database with connection.

    Note: Table creation is handled by Alembic migrations.
    Run migrations with: sparky db migrate

    Args:
        db_url: Database URL (for PostgreSQL or other databases)
        db_path: Path to database file (for SQLite). If None, uses default path.
        echo: Whether to echo SQL statements

    Returns:
        Initialized DatabaseManager instance
    """
    manager = get_database_manager(db_url=db_url, db_path=db_path)
    manager.echo = echo
    await manager.connect()
    # Tables are created via Alembic migrations, not create_all()
    return manager


async def close_database() -> None:
    """Close the global database manager."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None
