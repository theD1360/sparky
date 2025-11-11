"""Post-install hook for automatic database migrations.

This module provides the entry point for running migrations automatically
when the package is installed via poetry.
"""

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """Run database migrations automatically on poetry install.

    This function is called by the post-install script defined in pyproject.toml.
    It ensures the database is properly initialized with the latest schema.
    """
    try:
        # Get the path to the alembic.ini file
        current_dir = Path(__file__).parent
        alembic_ini_path = current_dir / "alembic.ini"

        if not alembic_ini_path.exists():
            logger.warning(f"Alembic config not found at {alembic_ini_path}")
            return

        # Configure Alembic
        alembic_cfg = Config(str(alembic_ini_path))

        # Set database URL from environment or use default
        db_url = os.getenv("SPARKY_DB_URL", "sqlite://knowledge_graph.db")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        # Change to the knowledge_base directory so migrations path is correct
        original_cwd = os.getcwd()
        os.chdir(current_dir)

        # Run migrations to head
        logger.info("Running database migrations...")
        command.upgrade(alembic_cfg, "head")
        logger.info("✓ Database migrations completed successfully")

        # Restore original working directory
        os.chdir(original_cwd)

    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}")
        # Don't raise the exception to avoid breaking the installation
        # The user can run migrations manually later


def run_migrations_verbose() -> None:
    """Run migrations with verbose output for debugging."""
    import sys

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    run_migrations()


if __name__ == "__main__":
    run_migrations_verbose()
