"""Add user management tables

Revision ID: 008
Revises: 007
Create Date: 2025-01-27 00:00:00.000000

This migration creates the user management tables separate from the knowledge graph:
- users: Stores sensitive user data (passwords, emails)
- user_roles: Role-based access control
- user_sessions: JWT token tracking and revocation
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user management tables."""

    connection = op.get_bind()
    is_postgres = connection.dialect.name == "postgresql"

    # Determine JSON type based on database
    if is_postgres:
        json_type = postgresql.JSONB()
    else:
        json_type = sa.JSON()

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("extradata", json_type, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for users table
    op.create_index("idx_users_username", "users", ["username"], unique=True)
    op.create_index("idx_users_email", "users", ["email"], unique=True)
    op.create_index("idx_users_active", "users", ["is_active"])

    # Create user_roles table
    op.create_table(
        "user_roles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes and unique constraint for user_roles
    op.create_index("idx_user_roles_user", "user_roles", ["user_id"])
    op.create_index("idx_user_roles_role", "user_roles", ["role"])
    op.create_unique_constraint("uq_user_role", "user_roles", ["user_id", "role"])

    # Create user_sessions table
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token_jti", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for user_sessions
    op.create_index("idx_user_sessions_user", "user_sessions", ["user_id"])
    op.create_index(
        "idx_user_sessions_jti", "user_sessions", ["token_jti"], unique=True
    )
    op.create_index("idx_user_sessions_expires", "user_sessions", ["expires_at"])


def downgrade() -> None:
    """Drop user management tables."""

    # Drop indexes first
    op.drop_index("idx_user_sessions_expires", table_name="user_sessions")
    op.drop_index("idx_user_sessions_jti", table_name="user_sessions")
    op.drop_index("idx_user_sessions_user", table_name="user_sessions")
    op.drop_index("idx_user_roles_role", table_name="user_roles")
    op.drop_index("idx_user_roles_user", table_name="user_roles")
    op.drop_index("idx_users_active", table_name="users")
    op.drop_index("idx_users_email", table_name="users")
    op.drop_index("idx_users_username", table_name="users")

    # Drop tables (order matters due to foreign keys)
    op.drop_table("user_sessions")
    op.drop_table("user_roles")
    op.drop_table("users")
