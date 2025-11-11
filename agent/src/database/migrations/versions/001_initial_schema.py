"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-23 22:45:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial knowledge graph schema."""

    # Get connection to check database type
    connection = op.get_bind()
    is_postgres = connection.dialect.name == "postgresql"

    # Create nodes table
    if is_postgres:
        # Use PostgreSQL JSONB type for better performance
        properties_type = postgresql.JSONB()
    else:
        # SQLite uses generic JSON
        properties_type = sa.JSON()

    op.create_table(
        "nodes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("node_type", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("properties", properties_type, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create edges table
    op.create_table(
        "edges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("edge_type", sa.String(), nullable=False),
        sa.Column("properties", properties_type, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for nodes
    op.create_index("idx_nodes_type", "nodes", ["node_type"])
    op.create_index("idx_nodes_updated", "nodes", ["updated_at"])

    # Create indexes for edges
    op.create_index("idx_edges_source", "edges", ["source_id"])
    op.create_index("idx_edges_target", "edges", ["target_id"])
    op.create_index("idx_edges_type", "edges", ["edge_type"])

    # Create unique constraint for edges
    op.create_index(
        "uq_edge_unique", "edges", ["source_id", "target_id", "edge_type"], unique=True
    )

    if is_postgres:
        # PostgreSQL: Add tsvector column for full-text search
        op.add_column(
            "nodes", sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True)
        )

        # Create GIN index for fast full-text search
        op.execute(
            text(
                "CREATE INDEX idx_nodes_search_vector ON nodes USING GIN (search_vector)"
            )
        )

        # Create function to generate search vector
        op.execute(
            text(
                """
            CREATE OR REPLACE FUNCTION nodes_search_vector_update() RETURNS TRIGGER AS $$
            BEGIN
                NEW.search_vector :=
                    setweight(to_tsvector('english', COALESCE(NEW.label, '')), 'A') ||
                    setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B') ||
                    setweight(to_tsvector('english', COALESCE(NEW.node_type, '')), 'C') ||
                    setweight(to_tsvector('english', COALESCE(NEW.properties::text, '')), 'D');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """
            )
        )

        # Create trigger to auto-update search_vector
        op.execute(
            text(
                """
            CREATE TRIGGER nodes_search_vector_trigger
            BEFORE INSERT OR UPDATE ON nodes
            FOR EACH ROW
            EXECUTE FUNCTION nodes_search_vector_update();
        """
            )
        )

        # Update existing rows (if any) - trigger handles this automatically on INSERT/UPDATE
        # No need to update existing rows since this is a fresh database
        pass

    else:
        # SQLite: Create FTS5 virtual table for full-text search
        op.execute(
            text(
                """
            CREATE VIRTUAL TABLE nodes_fts USING fts5(
                node_type,
                label,
                content,
                properties,
                content='nodes'
            )
        """
            )
        )

        # Create triggers to maintain FTS5 table
        op.execute(
            text(
                """
            CREATE TRIGGER nodes_fts_insert AFTER INSERT ON nodes BEGIN
                INSERT INTO nodes_fts(rowid, node_type, label, content, properties)
                VALUES (new.rowid, new.node_type, new.label, new.content, new.properties);
            END
        """
            )
        )

        op.execute(
            text(
                """
            CREATE TRIGGER nodes_fts_delete AFTER DELETE ON nodes BEGIN
                DELETE FROM nodes_fts WHERE rowid = old.rowid;
            END
        """
            )
        )

        op.execute(
            text(
                """
            CREATE TRIGGER nodes_fts_update AFTER UPDATE ON nodes BEGIN
                DELETE FROM nodes_fts WHERE rowid = old.rowid;
                INSERT INTO nodes_fts(rowid, node_type, label, content, properties)
                VALUES (new.rowid, new.node_type, new.label, new.content, new.properties);
            END
        """
            )
        )


def downgrade() -> None:
    """Drop initial schema."""

    connection = op.get_bind()
    is_postgres = connection.dialect.name == "postgresql"

    if is_postgres:
        # Drop PostgreSQL triggers and function
        op.execute(text("DROP TRIGGER IF EXISTS nodes_search_vector_trigger ON nodes"))
        op.execute(text("DROP FUNCTION IF EXISTS nodes_search_vector_update()"))
        op.drop_column("nodes", "search_vector")
    else:
        # Drop SQLite triggers and FTS5 table
        op.execute(text("DROP TRIGGER IF EXISTS nodes_fts_insert"))
        op.execute(text("DROP TRIGGER IF EXISTS nodes_fts_delete"))
        op.execute(text("DROP TRIGGER IF EXISTS nodes_fts_update"))
        op.execute(text("DROP TABLE IF EXISTS nodes_fts"))

    # Drop indexes
    op.drop_index("uq_edge_unique", table_name="edges")
    op.drop_index("idx_edges_type", table_name="edges")
    op.drop_index("idx_edges_target", table_name="edges")
    op.drop_index("idx_edges_source", table_name="edges")
    op.drop_index("idx_nodes_updated", table_name="nodes")
    op.drop_index("idx_nodes_type", table_name="nodes")

    # Drop tables
    op.drop_table("edges")
    op.drop_table("nodes")
