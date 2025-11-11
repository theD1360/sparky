"""Alembic environment configuration for knowledge base migrations."""

import logging
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add the database directory to the Python path
database_dir = Path(__file__).parent.parent
sys.path.insert(0, str(database_dir))

from models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """Get database URL from environment or config."""
    # Try to get from environment first (highest priority)
    db_url = os.getenv("SPARKY_DB_URL")
    if db_url:
        # Mask password in log
        safe_url = db_url.split("@")[-1] if "@" in db_url else db_url[:30]
        logging.info(
            f"Using database URL from SPARKY_DB_URL environment variable: ...@{safe_url}"
        )
        return db_url

    # Fall back to config file
    config_url = config.get_main_option("sqlalchemy.url")
    if config_url and config_url.strip():
        logging.info(f"Using database URL from alembic.ini: {config_url[:30]}...")
        return config_url

    # Final fallback: SQLite for local development
    default_path = Path(__file__).parent.parent.parent.parent / "knowledge_graph.db"
    default_url = f"sqlite:///{default_path}"
    logging.warning(
        f"No database URL found in SPARKY_DB_URL environment variable or alembic.ini config. "
        f"Falling back to SQLite: {default_url}"
    )
    logging.warning(
        "To use PostgreSQL, set SPARKY_DB_URL environment variable before running migrations."
    )
    return default_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
