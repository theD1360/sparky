"""Database connection and session management for the knowledge base."""

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

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
            self.db_url = db_url
            self.is_sqlite = db_url.startswith("sqlite")
            self.db_path = None
        elif db_path:
            self.db_url = f"sqlite:///{db_path}"
            self.is_sqlite = True
            self.db_path = db_path
        else:
            raise ValueError("Either db_url or db_path must be provided")

        self.echo = echo
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None

    def connect(self) -> None:
        """Create database engine and session factory."""
        if self.engine is not None:
            logger.warning("Database already connected")
            return

        # Create engine with database-specific configurations
        if self.is_sqlite:
            # SQLite-specific configuration
            self.engine = create_engine(
                self.db_url,
                echo=self.echo,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,  # Allow multi-threading
                },
            )

            # Enable SQLite optimizations and load sqlite-vec
            @event.listens_for(self.engine, "connect")
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
            self.engine = create_engine(
                self.db_url,
                echo=self.echo,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
            )
            logger.debug(f"Database connected: {self.db_url}")

        # Create session factory (for both SQLite and PostgreSQL)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        # Initialize embedding manager singleton
        try:
            EmbeddingManager.get_instance()
            logger.debug("EmbeddingManager initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize EmbeddingManager: {e}")
        
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")

    def get_session(self) -> Session:
        """Get a new database session.

        Returns:
            SQLAlchemy session instance

        Raises:
            RuntimeError: If database not connected
        """
        if self.SessionLocal is None:
            raise RuntimeError("Database not connected. Call connect() first.")

        return self.SessionLocal()

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            self.SessionLocal = None
            logger.debug("Database connections closed")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


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


def get_session() -> Session:
    """Get a database session from the global manager.

    Returns:
        SQLAlchemy session instance

    Raises:
        RuntimeError: If database manager not initialized
    """
    if _db_manager is None:
        raise RuntimeError(
            "Database manager not initialized. Call get_database_manager() first."
        )

    return _db_manager.get_session()


def initialize_database(
    db_url: Optional[str] = None,
    db_path: Optional[Path] = None,
    echo: bool = False,
) -> DatabaseManager:
    """Initialize database with connection and table creation.

    Args:
        db_url: Database URL (for PostgreSQL or other databases)
        db_path: Path to database file (for SQLite). If None, uses default path.
        echo: Whether to echo SQL statements

    Returns:
        Initialized DatabaseManager instance
    """
    manager = get_database_manager(db_url=db_url, db_path=db_path)
    manager.echo = echo
    manager.connect()
    manager.create_tables()
    return manager


def close_database() -> None:
    """Close the global database manager."""
    global _db_manager
    if _db_manager:
        _db_manager.close()
        _db_manager = None
