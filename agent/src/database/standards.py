"""Standardization utilities for knowledge graph node types, edge types, and ID generation.

This module provides normalization functions that standardize common variations while
allowing the AI agent to dynamically create new types as needed.

Conventions:
- Node types: PascalCase (e.g., "Memory", "Concept", "ToolCall")
- Edge types: SCREAMING_SNAKE_CASE (e.g., "RELATES_TO", "INSTANCE_OF")
- Node ID prefixes: lowercase matching node type, followed by colon (e.g., "memory:", "concept:")

The normalization is permissive - if a type doesn't match known variations,
it's converted to the conventional format but still allowed through.
"""

import re
from typing import Optional


def _to_pascal_case(s: str) -> str:
    """Convert string to PascalCase.

    Examples:
        'user_profile' -> 'UserProfile'
        'user profile' -> 'UserProfile'
        'userProfile' -> 'UserProfile'
    """
    # Split on underscores, spaces, or camelCase boundaries
    words = re.findall(
        r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", s.replace("_", " ").replace("-", " ")
    )
    return "".join(word.capitalize() for word in words)


def _to_screaming_snake_case(s: str) -> str:
    """Convert string to SCREAMING_SNAKE_CASE.

    Examples:
        'relatesTo' -> 'RELATES_TO'
        'relates to' -> 'RELATES_TO'
        'relates-to' -> 'RELATES_TO'
    """
    # Insert underscore before capitals in camelCase
    s = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s)
    # Replace spaces and hyphens with underscores
    s = s.replace(" ", "_").replace("-", "_")
    # Remove multiple underscores
    s = re.sub("_+", "_", s)
    return s.upper()


# Known node type variations that should be normalized to canonical forms
# Maps variations to their canonical PascalCase form
NODE_TYPE_NORMALIZATIONS = {
    # Core variations - different casing of the same type
    "memory": "Memory",
    "concept": "Concept",
    "session": "Session",
    "file": "File",
    "category": "Category",
    "tool": "Tool",
    "summary": "Summary",
    "process": "Process",
    "topic": "Topic",
    "agent": "Agent",
    "user": "User",
    "lesson": "Lesson",
    "workflow": "Workflow",
    "insight": "Insight",
    "CONCEPT": "Concept",  # ALL_CAPS to PascalCase
    # Semantic consolidations - similar concepts merged
    "identity": "CoreIdentity",
    "aspect": "Concept",
    "class": "Concept",
    "fact": "Concept",
    "theory": "Concept",
    "learning": "Insight",
    "steps": "Process",
    "method": "Capability",
    "model": "Concept",
    "library": "Software",
    "person": "User",
    "server_management_software": "Software",
    "web_server": "Software",
    # Multi-word variations
    "file_operation": "FileOperation",
    "File Operation": "FileOperation",
    "file operation": "FileOperation",
    "tool_call": "ToolCall",
    "toolcall": "ToolCall",
    "tool call": "ToolCall",
}


# Known edge type variations that should be normalized to canonical forms
# Maps variations to their canonical SCREAMING_SNAKE_CASE form
EDGE_TYPE_NORMALIZATIONS = {
    # Semantic consolidation - various forms meaning "related"
    "relates_to": "RELATES_TO",
    "related_to": "RELATES_TO",
    "related_concept": "RELATES_TO",
    "is_related_to": "RELATES_TO",
    "addressed_by": "RELATES_TO",
    "addresses": "RELATES_TO",
    "analyzed_by": "RELATES_TO",
    "argues_for": "RELATES_TO",
    "complementary_to": "RELATES_TO",
    "demonstrates": "RELATES_TO",
    "erodes": "RELATES_TO",
    "is_driven_by": "RELATES_TO",
    "is_embodied_as": "RELATES_TO",
    "recommends_caution_with": "RELATES_TO",
    "response_to": "RELATES_TO",
    "verifies": "RELATES_TO",
    "has_vulnerability": "RELATES_TO",
    "is_about": "RELATES_TO",
    # Part/component relationships
    "part_of": "PART_OF",
    "is_part_of": "PART_OF",
    "is_component_of": "PART_OF",
    "is_a_part_of": "PART_OF",
    # Instance/type relationships
    "is_a": "INSTANCE_OF",
    # Definition relationships
    "defines": "DEFINES",
    "is_defined_by": "DEFINES",
    # Mention relationships
    "mentions": "MENTIONS",
    "discusses": "MENTIONS",
    # Performance relationships
    "performs": "PERFORMS",
    # Summary relationships
    "has_summary": "HAS_SUMMARY",
    "summarized_by": "SUMMARIZES",
    # Usage relationships
    "uses": "USES",
    "used": "USES",
    "employs": "USES",
    "recommends_tool": "USES",
    "used_by": "USED_BY",
    # Implementation relationships
    "implements": "IMPLEMENTS",
    # Modification relationships
    "modifies": "MODIFIES",
    "modified_by": "MODIFIED",
    # Information relationships
    "informs": "INFORMS",
    "guides": "INFORMS",
    "motivates": "INFORMS",
    # Application relationships
    "applies_to": "APPLIES_TO",
    # Contribution relationships
    "contributes_to": "CONTRIBUTES_TO",
    # Description/explanation
    "describes": "DESCRIBES",
    "explained_by": "EXPLAINS",
    # Creation relationships
    "builds": "CREATED",
    "developed_by": "CREATED_BY",
    # Temporal relationships
    "can_lead_to": "LEADS_TO",
    # Capability relationships
    "can_perform": "CAN_PERFORM",
    "has_method": "CAPABLE_OF",
    # Categorization
    "categorized_as": "CATEGORIZED_AS",
    # Enablement
    "enables": "ENABLES",
    # Blocking
    "prevents": "BLOCKS",
    # Component relationships
    "has_aspect": "ASPECT_OF",
    "has_component": "HAS_COMPONENT",
    "includes": "HAS_COMPONENT",
    # Dependency relationships
    "is_built_on": "DEPENDS_ON",
    "requires": "REQUIRES",
    # Read operations
    "READS": "READ",
    "ENABLED": "ENABLES",
    "HAS_CAPABILITY": "CAPABLE_OF",
}


def normalize_node_type(node_type: str) -> str:
    """Normalize a node type to its canonical form.

    First checks if it's a known variation, then converts to PascalCase.
    This allows new types to be created dynamically while maintaining consistency.

    Args:
        node_type: The raw node type string

    Returns:
        Normalized node type in PascalCase

    Examples:
        >>> normalize_node_type("memory")
        'Memory'
        >>> normalize_node_type("custom_entity")
        'CustomEntity'
        >>> normalize_node_type("NewType")
        'NewType'
    """
    if not node_type:
        return "Unknown"

    # Check if it's a known variation
    if node_type in NODE_TYPE_NORMALIZATIONS:
        return NODE_TYPE_NORMALIZATIONS[node_type]

    # If already in PascalCase, keep it
    if node_type[0].isupper() and "_" not in node_type and " " not in node_type:
        return node_type

    # Convert to PascalCase
    return _to_pascal_case(node_type)


def normalize_edge_type(edge_type: str) -> str:
    """Normalize an edge type to its canonical form.

    First checks if it's a known variation, then converts to SCREAMING_SNAKE_CASE.
    This allows new edge types to be created dynamically while maintaining consistency.

    Args:
        edge_type: The raw edge type string

    Returns:
        Normalized edge type in SCREAMING_SNAKE_CASE

    Examples:
        >>> normalize_edge_type("relates_to")
        'RELATES_TO'
        >>> normalize_edge_type("customRelation")
        'CUSTOM_RELATION'
        >>> normalize_edge_type("NEW_EDGE")
        'NEW_EDGE'
    """
    if not edge_type:
        return "UNKNOWN"

    # Check if it's a known variation
    if edge_type in EDGE_TYPE_NORMALIZATIONS:
        return EDGE_TYPE_NORMALIZATIONS[edge_type]

    # If already in SCREAMING_SNAKE_CASE, keep it
    if edge_type.isupper() and "_" in edge_type:
        return edge_type

    # Convert to SCREAMING_SNAKE_CASE
    return _to_screaming_snake_case(edge_type)


def generate_node_id(node_type: str, identifier: str) -> str:
    """Generate a standardized node ID.

    Args:
        node_type: The node type (will be normalized)
        identifier: The unique identifier for this specific node

    Returns:
        Formatted node ID (e.g., "memory:core:identity", "session:abc-123")

    Examples:
        >>> generate_node_id("Memory", "core:identity")
        'memory:core:identity'
        >>> generate_node_id("Session", "abc-123")
        'session:abc-123'
        >>> generate_node_id("CustomType", "12345")
        'customtype:12345'
    """
    # Normalize the node type first
    normalized_type = normalize_node_type(node_type)
    # Use lowercase for the prefix
    prefix = normalized_type.lower()
    return f"{prefix}:{identifier}"


def parse_node_id(node_id: str) -> tuple[str, str]:
    """Parse a node ID into prefix and identifier.

    Args:
        node_id: The node ID to parse

    Returns:
        Tuple of (prefix, identifier)

    Examples:
        >>> parse_node_id("memory:core:identity")
        ('memory', 'core:identity')
        >>> parse_node_id("session:abc-123")
        ('session', 'abc-123')
    """
    if ":" not in node_id:
        return ("", node_id)

    parts = node_id.split(":", 1)
    return (parts[0], parts[1])


def validate_node_id(node_id: str, node_type: str) -> bool:
    """Validate that a node ID matches its node type.

    Args:
        node_id: The node ID to validate
        node_type: The expected node type

    Returns:
        True if the ID prefix matches the node type, False otherwise
    """
    prefix, _ = parse_node_id(node_id)
    normalized_type = normalize_node_type(node_type)
    expected_prefix = normalized_type.lower()

    return prefix == expected_prefix
