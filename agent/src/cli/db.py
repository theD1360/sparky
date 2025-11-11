"""Database migration commands for Sparky CLI."""

import os
from pathlib import Path

import typer
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from cli.common import logger

db = typer.Typer(name="db", help="Database migration commands")


def get_alembic_config() -> Config:
    """Get Alembic configuration."""
    # Get the path to the alembic.ini file
    current_dir = Path(__file__).parent.parent / "database"
    alembic_ini_path = current_dir / "alembic.ini"

    if not alembic_ini_path.exists():
        logger.error(f"Alembic config not found at {alembic_ini_path}")
        raise typer.Exit(1)

    # Configure Alembic
    alembic_cfg = Config(str(alembic_ini_path))

    # Set database URL from environment or use default
    db_url = os.getenv("SPARKY_DB_URL")
    if not db_url:
        # Default to project root knowledge_graph.db if no env var is set
        project_root = Path(__file__).parent.parent.parent
        default_db_path = project_root / "knowledge_graph.db"
        db_url = f"sqlite:///{default_db_path}"

    logger.info(f"Using database URL: {db_url}")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Change to the database directory so migrations path is correct
    original_cwd = os.getcwd()
    os.chdir(current_dir)

    # Store the original working directory for restoration
    alembic_cfg._original_cwd = original_cwd

    return alembic_cfg


@db.command("migrate")
def run_migrations():
    """Run pending database migrations."""
    try:
        alembic_cfg = get_alembic_config()
        logger.info("Running database migrations...")
        command.upgrade(alembic_cfg, "head")
        logger.info("✓ Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise typer.Exit(1)
    finally:
        # Restore original working directory
        if hasattr(alembic_cfg, "_original_cwd"):
            os.chdir(alembic_cfg._original_cwd)


@db.command("downgrade")
def downgrade_migration(
    revision: str = typer.Argument(..., help="Revision to downgrade to")
):
    """Downgrade to a specific migration revision."""
    try:
        alembic_cfg = get_alembic_config()
        logger.info(f"Downgrading to revision: {revision}")
        command.downgrade(alembic_cfg, revision)
        logger.info(f"✓ Successfully downgraded to {revision}")
    except Exception as e:
        logger.error(f"Downgrade failed: {e}")
        raise typer.Exit(1)


@db.command("current")
def show_current():
    """Show current migration version."""
    try:
        alembic_cfg = get_alembic_config()

        # Get current revision
        script = ScriptDirectory.from_config(alembic_cfg)

        # Get database connection to check current revision
        from sqlalchemy import create_engine

        # Create engine from config
        engine = create_engine(alembic_cfg.get_main_option("sqlalchemy.url"))

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()

            if current_rev:
                logger.info(f"Current revision: {current_rev}")
            else:
                logger.info("No migrations applied yet")

    except Exception as e:
        logger.error(f"Failed to get current revision: {e}")
        raise typer.Exit(1)


@db.command("history")
def show_history():
    """Show migration history."""
    try:
        alembic_cfg = get_alembic_config()
        logger.info("Migration history:")
        command.history(alembic_cfg)
    except Exception as e:
        logger.error(f"Failed to show history: {e}")
        raise typer.Exit(1)


@db.command("init")
def initialize_db():
    """Initialize database and run all migrations."""
    try:
        alembic_cfg = get_alembic_config()
        logger.info("Initializing database...")

        # Run all migrations
        command.upgrade(alembic_cfg, "head")

        # Show current status
        # script = ScriptDirectory.from_config(alembic_cfg)

        # Get database connection to check current revision
        from sqlalchemy import create_engine

        # Create engine from config
        engine = create_engine(alembic_cfg.get_main_option("sqlalchemy.url"))

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()

            logger.info("✓ Database initialized successfully")
            logger.info(f"Current revision: {current_rev}")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise typer.Exit(1)
    finally:
        # Restore original working directory
        if hasattr(alembic_cfg, "_original_cwd"):
            os.chdir(alembic_cfg._original_cwd)


@db.command("create")
def create_migration(
    message: str = typer.Argument(..., help="Migration message"),
    autogenerate: bool = typer.Option(
        True,
        "--autogenerate/--no-autogenerate",
        help="Auto-generate migration from model changes",
    ),
):
    """Create a new migration."""
    try:
        alembic_cfg = get_alembic_config()

        if autogenerate:
            logger.info(f"Creating auto-generated migration: {message}")
            command.revision(alembic_cfg, message=message, autogenerate=True)
        else:
            logger.info(f"Creating empty migration: {message}")
            command.revision(alembic_cfg, message=message)

        logger.info("✓ Migration created successfully")

    except Exception as e:
        logger.error(f"Failed to create migration: {e}")
        raise typer.Exit(1)


@db.command("status")
def show_status():
    """Show detailed database status."""
    try:
        alembic_cfg = get_alembic_config()

        # Get current revision
        script = ScriptDirectory.from_config(alembic_cfg)

        # Get database connection to check current revision
        from sqlalchemy import create_engine

        # Create engine from config
        engine = create_engine(alembic_cfg.get_main_option("sqlalchemy.url"))

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()

            logger.info("Database Status:")
            logger.info(f"  Current revision: {current_rev or 'None'}")

            # Check for pending migrations
            head_rev = script.get_current_head()
            if current_rev != head_rev:
                logger.info(f"  Head revision: {head_rev}")
                logger.info("  ⚠️  Pending migrations detected")
            else:
                logger.info("  ✓ Database is up to date")

    except Exception as e:
        logger.error(f"Failed to get database status: {e}")
        raise typer.Exit(1)
