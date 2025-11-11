"""ontology_structure

Revision ID: 6c7176a33ab6
Revises: 002
Create Date: 2025-10-28 09:32:13.443494

"""

from datetime import datetime

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "6c7176a33ab6"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create comprehensive ontology structure with organized hierarchies."""

    connection = op.get_bind()  # type: ignore[attr-defined]
    is_postgres = connection.dialect.name == "postgresql"
    now = datetime.utcnow()

    try:
        # 1. Create root ontology node
        if is_postgres:
            connection.execute(
                text(
                    """
                INSERT INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
                VALUES (
                    'ontology',
                    'Ontology',
                    'Ontology Root',
                    'The root node of the knowledge graph ontology structure',
                    '{"description": "Root organizational node for all ontology types"}',
                    :now,
                    :now
                )
                ON CONFLICT (id) DO NOTHING
            """
                ),
                {"now": now},
            )
        else:
            connection.execute(
                text(
                    """
                INSERT OR IGNORE INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
                VALUES (
                    'ontology',
                    'Ontology',
                    'Ontology Root',
                    'The root node of the knowledge graph ontology structure',
                    '{"description": "Root organizational node for all ontology types"}',
                    :now,
                    :now
                )
            """
                ),
                {"now": now},
            )

        # 2. Create ontology type nodes
        ontology_types = [
            {
                "id": "ontology:concept",
                "label": "Concept Ontology",
                "description": "Organizes all abstract concept types in the knowledge graph",
            },
            {
                "id": "ontology:relation",
                "label": "Relation Ontology",
                "description": "Organizes all relationship types used in the knowledge graph",
            },
            {
                "id": "ontology:memory",
                "label": "Memory Ontology",
                "description": "Organizes memory categories and stored information",
            },
            {
                "id": "ontology:domain",
                "label": "Domain Ontology",
                "description": "Organizes knowledge domains and subject areas",
            },
            {
                "id": "ontology:chat",
                "label": "Chat Ontology",
                "description": "Organizes chat and conversation domain structures",
            },
        ]

        for ot in ontology_types:
            if is_postgres:
                properties_json = f'{{"description": "{ot["description"]}"}}'
                connection.execute(
                    text(
                        """
                    INSERT INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
                    VALUES (
                        :id,
                        'Ontology',
                        :label,
                        :description,
                        :properties,
                        :now,
                        :now
                    )
                    ON CONFLICT (id) DO NOTHING
                """
                    ),
                    {
                        "id": ot["id"],
                        "label": ot["label"],
                        "description": ot["description"],
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
                        'Ontology',
                        :label,
                        :description,
                        json('{"description": "' || :description || '"}'),
                        :now,
                        :now
                    )
                """
                    ),
                    {
                        "id": ot["id"],
                        "label": ot["label"],
                        "description": ot["description"],
                        "now": now,
                    },
                )

            # Link ontology types to root
            if is_postgres:
                connection.execute(
                    text(
                        """
                    INSERT INTO edges (source_id, target_id, edge_type, properties, created_at)
                    VALUES (:source_id, 'ontology', 'CHILD_OF', '{}', :now)
                    ON CONFLICT DO NOTHING
                """
                    ),
                    {"source_id": ot["id"], "now": now},
                )
            else:
                connection.execute(
                    text(
                        """
                    INSERT OR IGNORE INTO edges (source_id, target_id, edge_type, properties, created_at)
                    VALUES (:source_id, 'ontology', 'CHILD_OF', '{}', :now)
                """
                    ),
                    {"source_id": ot["id"], "now": now},
                )

        # 3. Link existing concept:self to ontology:concept
        if is_postgres:
            connection.execute(
                text(
                    """
                INSERT INTO edges (source_id, target_id, edge_type, properties, created_at)
                VALUES ('concept:self', 'ontology:concept', 'CHILD_OF', '{}', :now)
                ON CONFLICT DO NOTHING
            """
                ),
                {"now": now},
            )
        else:
            connection.execute(
                text(
                    """
                INSERT OR IGNORE INTO edges (source_id, target_id, edge_type, properties, created_at)
                VALUES ('concept:self', 'ontology:concept', 'CHILD_OF', '{}', :now)
            """
                ),
                {"now": now},
            )

        # 4. Create seed relation type nodes
        relation_types = [
            (
                "relation:HAS_INSTANCE",
                "HAS_INSTANCE",
                "Concept to instance relationship",
            ),
            ("relation:INSTANCE_OF", "INSTANCE_OF", "Instance to concept relationship"),
            ("relation:PERFORMED", "PERFORMED", "Actor performs action relationship"),
            ("relation:MODIFIED", "MODIFIED", "Action modifies entity relationship"),
            ("relation:READ", "READ", "Action reads entity relationship"),
            ("relation:RELATES_TO", "RELATES_TO", "General relation between nodes"),
            ("relation:ASPECT_OF", "ASPECT_OF", "Component or aspect relationship"),
            ("relation:CHILD_OF", "CHILD_OF", "Hierarchical parent-child relationship"),
            (
                "relation:HAS_TRANSCRIPT",
                "HAS_TRANSCRIPT",
                "Session has transcript relationship",
            ),
            (
                "relation:CONTRIBUTES_TO",
                "CONTRIBUTES_TO",
                "Contributes to concept relationship",
            ),
            ("relation:DEFINES", "DEFINES", "Defines or specifies relationship"),
            (
                "relation:ATTRIBUTE_OF",
                "ATTRIBUTE_OF",
                "Attribute of entity relationship",
            ),
            ("relation:INFORMS", "INFORMS", "Informs or influences relationship"),
        ]

        for rel_id, rel_label, rel_desc in relation_types:
            if is_postgres:
                properties_json = f'{{"description": "{rel_desc}"}}'
                connection.execute(
                    text(
                        """
                    INSERT INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
                    VALUES (
                        :id,
                        'Relation',
                        :label,
                        :description,
                        :properties,
                        :now,
                        :now
                    )
                    ON CONFLICT (id) DO NOTHING
                """
                    ),
                    {
                        "id": rel_id,
                        "label": rel_label,
                        "description": rel_desc,
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
                        'Relation',
                        :label,
                        :description,
                        json('{"description": "' || :description || '"}'),
                        :now,
                        :now
                    )
                """
                    ),
                    {
                        "id": rel_id,
                        "label": rel_label,
                        "description": rel_desc,
                        "now": now,
                    },
                )

            # Link relations to ontology:relation
            if is_postgres:
                connection.execute(
                    text(
                        """
                    INSERT INTO edges (source_id, target_id, edge_type, properties, created_at)
                    VALUES (:source_id, 'ontology:relation', 'CHILD_OF', '{}', :now)
                    ON CONFLICT DO NOTHING
                """
                    ),
                    {"source_id": rel_id, "now": now},
                )
            else:
                connection.execute(
                    text(
                        """
                    INSERT OR IGNORE INTO edges (source_id, target_id, edge_type, properties, created_at)
                    VALUES (:source_id, 'ontology:relation', 'CHILD_OF', '{}', :now)
                """
                    ),
                    {"source_id": rel_id, "now": now},
                )

        # 5. Create memory category nodes (for organizing memories by type)
        memory_categories = [
            (
                "memory_category:core",
                "Core Memories",
                "Core identity and foundational memories",
            ),
            (
                "memory_category:chat",
                "Chat Memories",
                "Conversation and chat-related memories",
            ),
            (
                "memory_category:plans",
                "Plan Memories",
                "Planning and strategy memories",
            ),
            ("memory_category:goals", "Goal Memories", "Goal-related memories"),
            ("memory_category:tasks", "Task Memories", "Task-related memories"),
            ("memory_category:tools", "Tool Memories", "Tool and capability memories"),
        ]

        for cat_id, cat_label, cat_desc in memory_categories:
            if is_postgres:
                properties_json = f'{{"description": "{cat_desc}"}}'
                connection.execute(
                    text(
                        """
                    INSERT INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
                    VALUES (
                        :id,
                        'MemoryCategory',
                        :label,
                        :description,
                        :properties,
                        :now,
                        :now
                    )
                    ON CONFLICT (id) DO NOTHING
                """
                    ),
                    {
                        "id": cat_id,
                        "label": cat_label,
                        "description": cat_desc,
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
                        'MemoryCategory',
                        :label,
                        :description,
                        json('{"description": "' || :description || '"}'),
                        :now,
                        :now
                    )
                """
                    ),
                    {
                        "id": cat_id,
                        "label": cat_label,
                        "description": cat_desc,
                        "now": now,
                    },
                )

            # Link memory categories to ontology:memory
            if is_postgres:
                connection.execute(
                    text(
                        """
                    INSERT INTO edges (source_id, target_id, edge_type, properties, created_at)
                    VALUES (:source_id, 'ontology:memory', 'CHILD_OF', '{}', :now)
                    ON CONFLICT DO NOTHING
                """
                    ),
                    {"source_id": cat_id, "now": now},
                )
            else:
                connection.execute(
                    text(
                        """
                    INSERT OR IGNORE INTO edges (source_id, target_id, edge_type, properties, created_at)
                    VALUES (:source_id, 'ontology:memory', 'CHILD_OF', '{}', :now)
                """
                    ),
                    {"source_id": cat_id, "now": now},
                )

        # 6. Link chat-related concepts to ontology:chat
        # First ensure concept:conversation and concept:session exist
        chat_concepts = [
            (
                "concept:conversation",
                "Conversation",
                "Conversation and dialogue concept",
            ),
            ("concept:session", "Session", "Chat session concept"),
        ]

        for cc_id, cc_label, cc_desc in chat_concepts:
            if is_postgres:
                properties_json = f'{{"description": "{cc_desc}"}}'
                connection.execute(
                    text(
                        """
                    INSERT INTO nodes (id, node_type, label, content, properties, created_at, updated_at)
                    VALUES (
                        :id,
                        'Concept',
                        :label,
                        :description,
                        :properties,
                        :now,
                        :now
                    )
                    ON CONFLICT (id) DO NOTHING
                """
                    ),
                    {
                        "id": cc_id,
                        "label": cc_label,
                        "description": cc_desc,
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
                        'Concept',
                        :label,
                        :description,
                        json('{"description": "' || :description || '"}'),
                        :now,
                        :now
                    )
                """
                    ),
                    {
                        "id": cc_id,
                        "label": cc_label,
                        "description": cc_desc,
                        "now": now,
                    },
                )

            # Link to ontology:concept
            if is_postgres:
                connection.execute(
                    text(
                        """
                    INSERT INTO edges (source_id, target_id, edge_type, properties, created_at)
                    VALUES (:source_id, 'ontology:concept', 'CHILD_OF', '{}', :now)
                    ON CONFLICT DO NOTHING
                """
                    ),
                    {"source_id": cc_id, "now": now},
                )
            else:
                connection.execute(
                    text(
                        """
                    INSERT OR IGNORE INTO edges (source_id, target_id, edge_type, properties, created_at)
                    VALUES (:source_id, 'ontology:concept', 'CHILD_OF', '{}', :now)
                """
                    ),
                    {"source_id": cc_id, "now": now},
                )

            # Link to ontology:chat (to show they're part of chat domain)
            if is_postgres:
                connection.execute(
                    text(
                        """
                    INSERT INTO edges (source_id, target_id, edge_type, properties, created_at)
                    VALUES (:source_id, 'ontology:chat', 'PART_OF', '{}', :now)
                    ON CONFLICT DO NOTHING
                """
                    ),
                    {"source_id": cc_id, "now": now},
                )
            else:
                connection.execute(
                    text(
                        """
                    INSERT OR IGNORE INTO edges (source_id, target_id, edge_type, properties, created_at)
                    VALUES (:source_id, 'ontology:chat', 'PART_OF', '{}', :now)
                """
                    ),
                    {"source_id": cc_id, "now": now},
                )
    except Exception as e:
        import logging
        import traceback

        logger = logging.getLogger(__name__)
        logger.error(f"Migration failed: {e}")
        logger.error(traceback.format_exc())
        raise


def downgrade() -> None:
    """Remove ontology structure."""

    connection = op.get_bind()

    # Delete edges first (due to foreign key constraints)
    connection.execute(
        text(
            """
            DELETE FROM edges 
            WHERE source_id LIKE 'ontology:%' 
               OR target_id LIKE 'ontology:%'
               OR source_id LIKE 'relation:%'
               OR source_id LIKE 'memory_category:%'
               OR target_id = 'ontology'
               OR source_id = 'ontology'
               OR (source_id = 'concept:self' AND target_id = 'ontology:concept')
               OR (source_id LIKE 'concept:%' AND target_id = 'ontology:chat')
               OR (source_id LIKE 'concept:%' AND target_id = 'ontology:concept'
                   AND source_id IN ('concept:conversation', 'concept:session'))
        """
        )
    )

    # Delete nodes
    connection.execute(
        text(
            """
            DELETE FROM nodes 
            WHERE id LIKE 'ontology%' 
               OR id LIKE 'relation:%' 
               OR id LIKE 'memory_category:%'
               OR id IN ('concept:conversation', 'concept:session')
        """
        )
    )
