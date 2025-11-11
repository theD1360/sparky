"""Add vector search support

Revision ID: 003
Revises: 6c7176a33ab6
Create Date: 2025-01-27 12:00:00.000000

"""

import logging

from alembic import op
from sqlalchemy import text

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "6c7176a33ab6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add vector search table and triggers for embedding management."""
    # Get the connection to check database type
    connection = op.get_bind()
    is_postgres = connection.dialect.name == "postgresql"

    if is_postgres:
        # PostgreSQL: Use pgvector extension
        try:
            # Create pgvector extension
            op.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("Created pgvector extension")
        except Exception as e:
            logger.error(f"Failed to create pgvector extension: {e}")
            raise RuntimeError(
                "pgvector extension is required but could not be created. "
                "Make sure you're using a PostgreSQL database with pgvector installed."
            )

        # Check if column already exists
        try:
            result = connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='nodes' AND column_name='embedding'"
                )
            ).fetchone()
            if result:
                logger.info("embedding column already exists, skipping creation")
                return
        except Exception:
            pass  # Continue if check fails

        # Add embedding column to nodes table using pgvector's vector type
        op.execute(text("ALTER TABLE nodes ADD COLUMN embedding vector(768)"))

        # Create HNSW index for fast similarity search
        try:
            op.execute(
                text(
                    "CREATE INDEX idx_nodes_embedding ON nodes USING hnsw (embedding vector_cosine_ops)"
                )
            )
            logger.info("Created HNSW index on embedding column")
        except Exception as e:
            logger.warning(
                f"Could not create HNSW index: {e}. Falling back to IVFFlat."
            )
            # Fallback to IVFFlat index (requires data first, will need manual creation)
            op.execute(
                text(
                    "CREATE INDEX idx_nodes_embedding ON nodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
                )
            )

    else:
        # SQLite: Use sqlite-vec extension
        # Check if table already exists
        try:
            result = connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='nodes_vec'"
                )
            ).fetchone()
            if result:
                logger.info("nodes_vec table already exists, skipping creation")
                return
        except Exception:
            pass  # Continue if check fails

        # Load sqlite-vec extension
        sqlite_vec_loaded = False
        try:
            import sqlite_vec

            # Get the underlying SQLite connection from SQLAlchemy
            dbapi_conn = connection.connection
            # Enable extension loading
            dbapi_conn.enable_load_extension(True)
            sqlite_vec.load(dbapi_conn)
            dbapi_conn.enable_load_extension(False)
            sqlite_vec_loaded = True
            logger.info("Loaded sqlite-vec extension")
        except ImportError:
            logger.error(
                "sqlite-vec not available. Cannot create vector table. Please install sqlite-vec."
            )
            raise RuntimeError(
                "sqlite-vec extension is required but not available. "
                "Install it with: pip install sqlite-vec"
            )
        except AttributeError:
            # If connection doesn't have .connection attribute, try direct load
            try:
                connection.enable_load_extension(True)
                sqlite_vec.load(connection)
                connection.enable_load_extension(False)
                sqlite_vec_loaded = True
                logger.info("Loaded sqlite-vec extension (direct)")
            except Exception as e:
                logger.error(f"Failed to load sqlite-vec extension: {e}")
                raise RuntimeError(f"Cannot load sqlite-vec extension: {e}")
        except Exception as e:
            logger.error(f"Failed to load sqlite-vec extension: {e}")
            raise RuntimeError(f"Cannot load sqlite-vec extension: {e}")

        # Ensure sqlite-vec is loaded before creating table
        if not sqlite_vec_loaded:
            raise RuntimeError("sqlite-vec extension failed to load")

        try:
            # Re-load extension for the CREATE statement (in case it was lost)
            dbapi_conn = connection.connection
            dbapi_conn.enable_load_extension(True)
            sqlite_vec.load(dbapi_conn)

            # Create vector table using sqlite-vec
            op.execute(
                text(
                    """
                CREATE VIRTUAL TABLE nodes_vec USING vec0(embedding float[768])
            """
                )
            )

            dbapi_conn.enable_load_extension(False)
            logger.info("Created nodes_vec virtual table for vector search")
        except Exception as e:
            logger.error(f"Failed to create nodes_vec virtual table: {e}")
            raise

    # Note: We cannot create triggers that call Python functions directly from SQL
    # Instead, we'll rely on application-level triggers in the repository layer
    # to generate embeddings when nodes are inserted/updated.
    #
    # This is because SQL triggers cannot easily invoke the Gemini API to generate
    # embeddings. The embedding generation will be handled in:
    # - Repository.add_node() - generate embedding on insert
    # - Repository.update_node() - regenerate embedding on update
    #
    # SQL triggers would require embedding the data synchronously, which could
    # be slow and requires API calls that should be managed by the application layer.


def downgrade() -> None:
    """Remove vector search table."""

    connection = op.get_bind()
    is_postgres = connection.dialect.name == "postgresql"

    if is_postgres:
        # PostgreSQL: Drop embedding column and index
        try:
            op.drop_index("idx_nodes_embedding", table_name="nodes")
            logger.info("Dropped HNSW index on embedding column")
        except Exception:
            pass  # Index might not exist

        try:
            op.drop_column("nodes", "embedding")
            logger.info("Dropped embedding column from nodes table")
        except Exception:
            pass  # Column might not exist

        # Note: We don't drop the pgvector extension as it might be used by other tables
    else:
        # SQLite: Try to load sqlite-vec for the DROP operation
        try:
            import sqlite_vec

            dbapi_conn = connection.connection
            dbapi_conn.enable_load_extension(True)
            sqlite_vec.load(dbapi_conn)
            dbapi_conn.enable_load_extension(False)
        except Exception:
            # If we can't load sqlite-vec, try dropping anyway
            # SQLite might still allow dropping the table
            pass

        # Drop vector table (if it exists)
        try:
            op.execute(text("DROP TABLE IF EXISTS nodes_vec"))
            logger.info("Dropped nodes_vec virtual table")
        except Exception as e:
            logger.warning(
                f"Failed to drop nodes_vec table: {e}. You may need to drop it manually."
            )
