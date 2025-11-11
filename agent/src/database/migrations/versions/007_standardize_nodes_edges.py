"""Standardize node types and edge types

Revision ID: 007
Revises: 003
Create Date: 2025-11-06 00:00:00.000000

This migration standardizes all node types and edge types in the knowledge graph:
- Node types are normalized to PascalCase (e.g., Memory, Concept, Session)
- Edge types are normalized to SCREAMING_SNAKE_CASE (e.g., RELATES_TO, INSTANCE_OF)
- Consolidates variations of the same semantic relationship
"""

import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "007"
down_revision = "003"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


# Import standards from the standards module
# These mappings define how to migrate old values to new canonical forms
NODE_TYPE_MIGRATIONS = {
    # Memory variations
    "memory": "Memory",
    "Memory": "Memory",
    # Concept variations
    "concept": "Concept",
    "Concept": "Concept",
    "CONCEPT": "Concept",
    # Session variations
    "session": "Session",
    "Session": "Session",
    # File variations
    "file": "File",
    "File": "File",
    # Category variations
    "category": "Category",
    "Category": "Category",
    # Tool variations
    "tool": "Tool",
    "Tool": "Tool",
    # ToolCall variations
    "ToolCall": "ToolCall",
    "toolcall": "ToolCall",
    # Summary variations
    "summary": "Summary",
    "Summary": "Summary",
    # Process variations
    "process": "Process",
    "Process": "Process",
    # Topic variations
    "topic": "Topic",
    "Topic": "Topic",
    # Agent variations
    "agent": "Agent",
    "Agent": "Agent",
    # User variations
    "user": "User",
    "User": "User",
    # Lesson variations
    "lesson": "Lesson",
    "Lesson": "Lesson",
    # Workflow variations
    "workflow": "Workflow",
    "Workflow": "Workflow",
    # Insight variations
    "insight": "Insight",
    "Insight": "Insight",
    # Identity variations
    "identity": "CoreIdentity",
    "CoreIdentity": "CoreIdentity",
    # Aspect variations (migrate to Concept)
    "aspect": "Concept",
    # Class variations (migrate to Concept)
    "class": "Concept",
    # Fact variations (migrate to Concept)
    "fact": "Concept",
    # Theory variations (migrate to Concept)
    "theory": "Concept",
    # Learning variations (migrate to Insight)
    "learning": "Insight",
    # Steps variations (migrate to Process)
    "steps": "Process",
    # File operation variations
    "file_operation": "FileOperation",
    "File Operation": "FileOperation",
    "FileOperation": "FileOperation",
    # Method variations (migrate to Capability)
    "method": "Capability",
    # Model variations (migrate to Concept)
    "model": "Concept",
    # Library variations (migrate to Software)
    "library": "Software",
    # Person variations (migrate to User)
    "person": "User",
    # Server management software variations
    "server_management_software": "Software",
    "web_server": "Software",
    # Standard types (already correct)
    "Algorithm": "Algorithm",
    "Capability": "Capability",
    "ConversationTurn": "ConversationTurn",
    "Directive": "Directive",
    "Directory": "Directory",
    "Error": "Error",
    "Feature": "Feature",
    "Goal": "Goal",
    "IncidentAnalysis": "IncidentAnalysis",
    "MemoryCategory": "MemoryCategory",
    "Ontology": "Ontology",
    "ProblemSolution": "ProblemSolution",
    "ProfoundInsight": "ProfoundInsight",
    "Prompt": "Prompt",
    "Purpose": "Purpose",
    "Reflection": "Reflection",
    "Relation": "Relation",
    "RootCause": "RootCause",
    "SessionSummary": "SessionSummary",
    "Software": "Software",
    "Synthesis": "Synthesis",
    "Task": "Task",
    "ThinkingPattern": "ThinkingPattern",
    "Transcript": "Transcript",
    "Value": "Value",
}


EDGE_TYPE_MIGRATIONS = {
    # RELATES_TO variations
    "relates_to": "RELATES_TO",
    "RELATES_TO": "RELATES_TO",
    "related_to": "RELATES_TO",
    "RELATED_TO": "RELATES_TO",
    "related_concept": "RELATES_TO",
    "is_related_to": "RELATES_TO",
    # PART_OF variations
    "part_of": "PART_OF",
    "PART_OF": "PART_OF",
    "is_part_of": "PART_OF",
    "IS_PART_OF": "PART_OF",
    "is_component_of": "PART_OF",
    "is_a_part_of": "PART_OF",
    # DEFINES variations
    "defines": "DEFINES",
    "DEFINES": "DEFINES",
    "is_defined_by": "DEFINES",
    # MENTIONS variations
    "mentions": "MENTIONS",
    "MENTIONS": "MENTIONS",
    # PERFORMS variations
    "performs": "PERFORMS",
    "PERFORMS": "PERFORMS",
    # HAS_SUMMARY variations
    "has_summary": "HAS_SUMMARY",
    "HAS_SUMMARY": "HAS_SUMMARY",
    # SUMMARIZES variations
    "SUMMARIZES": "SUMMARIZES",
    "summarized_by": "SUMMARIZES",
    "SUMMARIZED_BY": "SUMMARIZES",
    # USES variations
    "uses": "USES",
    "USES": "USES",
    "used": "USES",
    "employs": "USES",
    # USED_BY variations
    "used_by": "USED_BY",
    "USED_BY": "USED_BY",
    # IMPLEMENTS variations
    "implements": "IMPLEMENTS",
    "IMPLEMENTS": "IMPLEMENTS",
    # IS_A variations (should be INSTANCE_OF)
    "is_a": "INSTANCE_OF",
    "IS_A": "INSTANCE_OF",
    "is_about": "RELATES_TO",
    # MODIFIES variations
    "modifies": "MODIFIES",
    "MODIFIES": "MODIFIES",
    # MODIFIED variations
    "modified_by": "MODIFIED",
    "MODIFIED_BY": "MODIFIED",
    "MODIFIED": "MODIFIED",
    # INFORMS variations
    "informs": "INFORMS",
    "INFORMS": "INFORMS",
    # APPLIES_TO variations
    "applies_to": "APPLIES_TO",
    "APPLIES_TO": "APPLIES_TO",
    # CONTRIBUTES_TO variations
    "contributes_to": "CONTRIBUTES_TO",
    "CONTRIBUTES_TO": "CONTRIBUTES_TO",
    # HAS_VULNERABILITY variations (migrate to RELATES_TO)
    "has_vulnerability": "RELATES_TO",
    "HAS_VULNERABILITY": "RELATES_TO",
    # Various semantic relationships
    "addressed_by": "RELATES_TO",
    "addresses": "RELATES_TO",
    "analyzed_by": "RELATES_TO",
    "argues_for": "RELATES_TO",
    "builds": "CREATED",
    "can_lead_to": "LEADS_TO",
    "can_perform": "CAN_PERFORM",
    "categorized_as": "CATEGORIZED_AS",
    "complementary_to": "RELATES_TO",
    "demonstrates": "RELATES_TO",
    "describes": "DESCRIBES",
    "developed_by": "CREATED_BY",
    "discusses": "MENTIONS",
    "enables": "ENABLES",
    "erodes": "RELATES_TO",
    "explained_by": "EXPLAINS",
    "guides": "INFORMS",
    "has_aspect": "ASPECT_OF",
    "has_component": "HAS_COMPONENT",
    "has_method": "CAPABLE_OF",
    "includes": "HAS_COMPONENT",
    "is_built_on": "DEPENDS_ON",
    "is_driven_by": "RELATES_TO",
    "IS_DRIVEN_BY": "RELATES_TO",
    "is_embodied_as": "RELATES_TO",
    "IS_EMBODIED_AS": "RELATES_TO",
    "motivates": "INFORMS",
    "prevents": "BLOCKS",
    "recommends_caution_with": "RELATES_TO",
    "recommends_tool": "USES",
    "requires": "REQUIRES",
    "response_to": "RELATES_TO",
    "verifies": "RELATES_TO",
    # Preserve standard forms
    "INSTANCE_OF": "INSTANCE_OF",
    "HAS_INSTANCE": "HAS_INSTANCE",
    "PERFORMED": "PERFORMED",
    "READ": "READ",
    "READS": "READ",
    "DEPENDS_ON": "DEPENDS_ON",
    "CAUSED_BY": "CAUSED_BY",
    "CAUSES": "CAUSES",
    "HAS_TRANSCRIPT": "HAS_TRANSCRIPT",
    "ASPECT_OF": "ASPECT_OF",
    "CHILD_OF": "CHILD_OF",
    "PRECEDES": "PRECEDES",
    "VERSION_OF": "VERSION_OF",
    "HAS_PREDECESSOR": "HAS_PREDECESSOR",
    "ENABLED": "ENABLES",
    "CAPABLE_OF": "CAPABLE_OF",
    "HAS_CAPABILITY": "CAPABLE_OF",
    "CONTRIBUTED_TO": "CONTRIBUTED_TO",
    "IMPLEMENTED_IN": "IMPLEMENTED_IN",
    "MITIGATED_BY": "MITIGATED_BY",
    "CREATED": "CREATED",
    "CREATED_BY": "CREATED_BY",
    "BLOCKED": "BLOCKS",
    "LEADS_TO": "LEADS_TO",
    "CAN_PERFORM": "CAN_PERFORM",
    "CATEGORIZED_AS": "CATEGORIZED_AS",
    "DESCRIBES": "DESCRIBES",
    "EXPLAINS": "EXPLAINS",
    "HAS_COMPONENT": "HAS_COMPONENT",
    "BLOCKS": "BLOCKS",
    "WRITTEN": "WRITTEN",
    "DELETED": "DELETED",
    "REQUIRES": "REQUIRES",
    # Additional standard types from analysis
    "ACTS_ON": "MODIFIES",
    "ATTEMPTED_CONSOLIDATION": "RELATES_TO",
    "ATTRIBUTE_OF": "HAS_ATTRIBUTE",
    "HAS_ATTRIBUTE": "HAS_ATTRIBUTE",
    "BELIEF_IN": "RELATES_TO",
    "CLARIFIES": "CLARIFIES",
    "EXPRESSES": "RELATES_TO",
    "GENERATED": "CREATED",
    "HAS_A": "HAS_COMPONENT",
    "HAS_CHARACTERISTIC": "HAS_ATTRIBUTE",
    "HAS_GOAL": "RELATES_TO",
    "HAS_INSIGHT": "RELATES_TO",
    "HAS_OPERATION": "CAPABLE_OF",
    "HAS_PARTICIPANT": "HAS_PARTICIPANT",
    "HAS_PURPOSE_OF": "RELATES_TO",
    "HAS_REPRESENTATION": "RELATES_TO",
    "HAS_STEPS": "HAS_COMPONENT",
    "HAS_VALUE": "RELATES_TO",
    "INSIGHT_INTO": "RELATES_TO",
    "INVOLVES": "RELATES_TO",
    "LEARNED": "RELATES_TO",
    "LOCATED_IN": "PART_OF",
    "OPERATES_ON": "MODIFIES",
    "OUTCOME": "LEADS_TO",
    "PROVIDES": "CREATES",
    "STEP": "CHILD_OF",
    "TRIGGERS": "LEADS_TO",
    "VALUES": "RELATES_TO",
}


def upgrade() -> None:
    """Standardize node types and edge types."""
    connection = op.get_bind()

    logger.info("Starting standardization migration...")

    # Step 1: Standardize node types
    logger.info("Standardizing node types...")
    node_type_counts = {}

    for old_type, new_type in NODE_TYPE_MIGRATIONS.items():
        if old_type != new_type:
            result = connection.execute(
                text(
                    "UPDATE nodes SET node_type = :new_type WHERE node_type = :old_type"
                ),
                {"new_type": new_type, "old_type": old_type},
            )
            if result.rowcount > 0:
                node_type_counts[f"{old_type} -> {new_type}"] = result.rowcount
                logger.info(
                    f"  Updated {result.rowcount} nodes: {old_type} -> {new_type}"
                )

    logger.info(f"Standardized {len(node_type_counts)} node type variations")

    # Step 2: Standardize edge types
    logger.info("Standardizing edge types...")
    edge_type_counts = {}

    for old_type, new_type in EDGE_TYPE_MIGRATIONS.items():
        if old_type != new_type:
            # Check for potential duplicates before updating
            # This handles cases where edges might be consolidated
            result = connection.execute(
                text(
                    """
                    SELECT e1.id, e1.source_id, e1.target_id
                    FROM edges e1
                    WHERE e1.edge_type = :old_type
                    AND EXISTS (
                        SELECT 1 FROM edges e2
                        WHERE e2.source_id = e1.source_id
                        AND e2.target_id = e1.target_id
                        AND e2.edge_type = :new_type
                        AND e2.id != e1.id
                    )
                """
                ),
                {"old_type": old_type, "new_type": new_type},
            )
            duplicates = result.fetchall()

            if duplicates:
                # Delete duplicates that would conflict
                logger.info(
                    f"  Removing {len(duplicates)} duplicate edges for {old_type} -> {new_type}"
                )
                for dup in duplicates:
                    connection.execute(
                        text("DELETE FROM edges WHERE id = :edge_id"),
                        {"edge_id": dup[0]},
                    )

            # Now update the edge type
            result = connection.execute(
                text(
                    "UPDATE edges SET edge_type = :new_type WHERE edge_type = :old_type"
                ),
                {"new_type": new_type, "old_type": old_type},
            )
            if result.rowcount > 0:
                edge_type_counts[f"{old_type} -> {new_type}"] = result.rowcount
                logger.info(
                    f"  Updated {result.rowcount} edges: {old_type} -> {new_type}"
                )

    logger.info(f"Standardized {len(edge_type_counts)} edge type variations")

    # Step 3: Report final statistics
    logger.info("Migration complete! Final statistics:")

    result = connection.execute(
        text("SELECT DISTINCT node_type FROM nodes ORDER BY node_type")
    )
    node_types = [row[0] for row in result]
    logger.info(f"  Total unique node types: {len(node_types)}")

    result = connection.execute(
        text("SELECT DISTINCT edge_type FROM edges ORDER BY edge_type")
    )
    edge_types = [row[0] for row in result]
    logger.info(f"  Total unique edge types: {len(edge_types)}")

    logger.info("Standardization migration completed successfully!")


def downgrade() -> None:
    """
    Downgrade is not supported for this migration as it consolidates multiple
    variations into canonical forms. The original variations cannot be reliably restored.
    """
    logger.warning(
        "Downgrade not supported for standardization migration. "
        "Original node/edge type variations cannot be restored."
    )
    pass
