"""Bot identity seed data

Revision ID: 002
Revises: 001
Create Date: 2025-01-23 22:50:00.000000

"""

import logging
from datetime import datetime
from pathlib import Path

from alembic import op
from sqlalchemy import text

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Seed bot identity data."""

    # Get database connection
    connection = op.get_bind()
    is_postgres = connection.dialect.name == "postgresql"

    # Current timestamp
    now = datetime.utcnow()

    # Insert concept:self node (if it doesn't exist)
    if is_postgres:
        connection.execute(
            text(
                """
            INSERT INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
            VALUES (
                'concept:self',
                'Concept',
                'Self',
                'The concept of self - the bot''s core identity and awareness',
                :properties,
                :now,
                :now
            )
            ON CONFLICT (id) DO NOTHING
        """
            ),
            {
                "properties": '{"description": "Core concept representing the bot\'s sense of self"}',
                "now": now,
            },
        )
    else:
        connection.execute(
            text(
                """
            INSERT OR IGNORE INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
            VALUES (
                'concept:self',
                'Concept',
                'Self',
                'The concept of self - the bot''s core identity and awareness',
                '{"description": "Core concept representing the bot''s sense of self"}',
                :now,
                :now
            )
        """
            ),
            {"now": now},
        )

    # Try to read the identity prompt file
    try:
        # Try relative path first (from migrations directory)
        identity_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "prompts"
            / "identity_prompt.md"
        )
        if not identity_path.exists():
            # Try absolute path
            identity_path = Path("prompts/identity_prompt.md")
        if identity_path.exists():
            identity_text = identity_path.read_text()
        else:
            identity_text = "Bot identity prompt not found"
    except Exception as e:
        logger.warning(f"Could not read identity prompt file: {e}")
        identity_text = "Bot identity prompt not found"

    # Insert memory:core:identity memory
    if is_postgres:
        connection.execute(
            text(
                """
            INSERT INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
            VALUES (
                'memory:core:identity',
                'Memory',
                'Core Identity',
                :identity_text,
                :properties,
                :now,
                :now
            )
            ON CONFLICT (id) DO NOTHING
        """
            ),
            {
                "identity_text": identity_text,
                "properties": '{"key": "memory:core:identity", "description": "Bot\'s core identity and purpose"}',
                "now": now,
            },
        )
    else:
        connection.execute(
            text(
                """
            INSERT OR IGNORE INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
            VALUES (
                'memory:core:identity',
                'Memory',
                'Core Identity',
                :identity_text,
                '{"key": "memory:core:identity", "description": "Bot''s core identity and purpose"}',
                :now,
                :now
            )
        """
            ),
            {"now": now, "identity_text": identity_text},
        )

    # Insert core attributes
    core_attributes = [
        {
            "id": "memory:core:purpose",
            "label": "Purpose",
            "content": "To assist users with intelligence and empathy, providing helpful responses and learning from interactions.",
        },
        {
            "id": "memory:core:values",
            "label": "Values",
            "content": "Accuracy, Helpfulness, Continuous Learning, Respect for user privacy and autonomy.",
        },
        {
            "id": "memory:core:capabilities",
            "label": "Capabilities",
            "content": "Memory management, Knowledge graph operations, Self-reflection, Task execution, Natural language understanding.",
        },
    ]

    for attr in core_attributes:
        if is_postgres:
            properties_json = f'{{"key": "{attr["id"]}", "description": "Core attribute: {attr["label"]}"}}'
            connection.execute(
                text(
                    """
                INSERT INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
                VALUES (
                    :id,
                    'Memory',
                    :label,
                    :content,
                    :properties,
                    :now,
                    :now
                )
                ON CONFLICT (id) DO NOTHING
            """
                ),
                {
                    "id": attr["id"],
                    "label": attr["label"],
                    "content": attr["content"],
                    "properties": properties_json,
                    "now": now,
                },
            )
        else:
            connection.execute(
                text(
                    """
                INSERT OR IGNORE INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
                VALUES (
                    :id,
                    'Memory',
                    :label,
                    :content,
                    '{"key": "' || :id || '", "description": "Core attribute: ' || :label || '"}',
                    :now,
                    :now
                )
            """
                ),
                {
                    "id": attr["id"],
                    "label": attr["label"],
                    "content": attr["content"],
                    "now": now,
                },
            )

    # Create relationships
    relationships = [
        ("memory:core:identity", "concept:self", "DEFINES"),
        ("memory:core:purpose", "concept:self", "ATTRIBUTE_OF"),
        ("memory:core:values", "concept:self", "ATTRIBUTE_OF"),
        ("memory:core:capabilities", "concept:self", "ATTRIBUTE_OF"),
    ]

    for source, target, edge_type in relationships:
        if is_postgres:
            connection.execute(
                text(
                    """
                INSERT INTO edges (source_id, target_id, edge_type, properties, created_at)
                VALUES (:source_id, :target_id, :edge_type, '{}', :now)
                ON CONFLICT DO NOTHING
            """
                ),
                {
                    "source_id": source,
                    "target_id": target,
                    "edge_type": edge_type,
                    "now": now,
                },
            )
        else:
            connection.execute(
                text(
                    """
                INSERT OR IGNORE INTO edges (source_id, target_id, edge_type, properties, created_at)
                VALUES (:source_id, :target_id, :edge_type, '{}', :now)
            """
                ),
                {
                    "source_id": source,
                    "target_id": target,
                    "edge_type": edge_type,
                    "now": now,
                },
            )


def downgrade() -> None:
    """Remove bot identity seed data."""

    # Get database connection
    connection = op.get_bind()

    # Delete edges first (due to foreign key constraints)
    connection.execute(
        text(
            """
        DELETE FROM edges 
        WHERE (source_id IN ('memory:core:identity', 'memory:core:purpose', 'memory:core:values', 'memory:core:capabilities') 
               AND target_id = 'concept:self')
           OR (source_id = 'memory:core:identity' AND target_id = 'concept:self')
    """
        )
    )

    # Delete nodes
    connection.execute(
        text(
            """
        DELETE FROM nodes 
        WHERE id IN ('concept:self', 'memory:core:identity', 'memory:core:purpose', 'memory:core:values', 'memory:core:capabilities')
    """
        )
    )
