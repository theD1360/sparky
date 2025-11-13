"""MCP Server for Knowledge Graph Tools with Advanced Querying.

This server provides comprehensive graph operations including:
- Basic CRUD operations (add_node, add_edge, get_node_by_id, etc.)
- Advanced querying with openCypher-like syntax (query_graph)
- Path finding algorithms (find_path)
- Graph analytics (analyze_graph)
- Filtered traversal (filter_traverse)
- Memory management with full content storage (replaces memory_server)
- Full-text search capabilities
- FastMCP Prompts: Reusable templates for complex reasoning tasks
- FastMCP Resources: Direct read-only access to common data

PROMPTS (guidance templates):
- discover_concept: Explore knowledge about a concept
- solve_problem: Apply structured problem-solving
- plan_problem: Create a detailed plan without executing
- build_from_plan: Execute a plan from the plans directory
- execute_workflow: Run stored workflows
- organize_memories: Organize and consolidate memories
- analyze_knowledge_structure: Analyze graph structure

RESOURCES (direct data access):
- knowledge://stats - Graph statistics
- knowledge://memories - List all memories
- knowledge://memory/{key} - Specific memory content
- knowledge://workflows - List workflows
- knowledge://workflow/{name} - Workflow definition
- knowledge://thinking-patterns - Available thinking patterns
- knowledge://node/{id}/context - Node with neighbors
- knowledge://tool-usage/recent - Recent tool usage stats
- knowledge://plans - List all plan files from plans/ directory
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import logging
import os
from datetime import datetime
from typing import List, Optional

from database.database import DatabaseManager, get_database_manager
from database.repository import KnowledgeRepository
from mcp.server.fastmcp import FastMCP
from models import MCPResponse
from sparky.task_queue import TaskQueue

# SQLAlchemyError removed as it's no longer used in fastMCP version


logger = logging.getLogger(__name__)

# ============================================================================
# SECTION 0: DATABASE CONFIGURATION
# ============================================================================

# Database configuration will be loaded in _load_graph() to ensure environment variables are available


# ============================================================================
# SECTION 1: QUERY PARSING & EXECUTION (Simplified)
# ============================================================================


# ============================================================================
# SECTION 5: GRAPH DATA & INITIALIZATION
# ============================================================================

# Initialize the FastMCP server
mcp = FastMCP("knowledge-graph-tools")

# Global state
_db_manager: Optional[DatabaseManager] = None
_kb_repository: Optional[KnowledgeRepository] = None

# Content size limits for tool results to prevent frontend performance issues
MAX_NODE_CONTENT_SIZE = 5000  # 5KB per node content
MAX_TOTAL_RESULT_SIZE = 100000  # 100KB total result size


def _truncate_node_content(node_dict: dict, max_size: int = MAX_NODE_CONTENT_SIZE) -> dict:
    """Truncate node content if too large to prevent massive tool results.
    
    Args:
        node_dict: Node dictionary with 'content' field
        max_size: Maximum content size in bytes
        
    Returns:
        Modified node dict with truncated content if needed
    """
    if "content" in node_dict and node_dict["content"]:
        content = node_dict["content"]
        if len(content) > max_size:
            original_size = len(content)
            node_dict["content"] = content[:max_size] + f"\n[... truncated: {original_size:,} bytes total]"
            node_dict["_truncated"] = True
            node_dict["_original_size"] = original_size
    return node_dict


def _load_graph():
    """Load or initialize database using KnowledgeRepository."""
    global _kb_repository, _db_manager  # pylint: disable=global-statement

    # Get database URL from environment (required for PostgreSQL)
    db_url = os.getenv("SPARKY_DB_URL")
    if not db_url:
        raise RuntimeError(
            "SPARKY_DB_URL environment variable is required for database connection"
        )

    # Mask password in log for security
    safe_db_url = db_url.split("@")[-1] if "@" in db_url else db_url[:50]
    logger.info(f"Connecting to PostgreSQL database: ...@{safe_db_url}")

    _db_manager = get_database_manager(db_url=db_url)
    _db_manager.connect()  # Connect to database first

    # Create or connect to database using repository
    _kb_repository = KnowledgeRepository(_db_manager)

    # Get graph statistics
    stats = _kb_repository.get_graph_stats()
    node_count = stats["total_nodes"]
    edge_count = stats["total_edges"]

    if node_count == 0:
        logger.warning(
            "Empty database detected. Run 'sparky db migrate' to initialize schema and seed bot identity data."
        )
    else:
        logger.debug(
            "Connected to database: %d nodes, %d edges",
            node_count,
            edge_count,
        )

    # Initialize query engine with repository
    logger.debug("Query engine initialized successfully")


# ============================================================================
# SECTION 6: FASTMCP TOOL DEFINITIONS
# ============================================================================


# Graph CRUD Tools
@mcp.tool()
def add_node(
    node_id: str,
    node_type: str,
    label: str,
    content: str = None,
    properties: dict = None,
) -> dict:
    """Add or update a node in the knowledge graph.

    This is the primary tool for creating knowledge nodes. Nodes are the fundamental
    building blocks of the graph and can represent concepts, entities, sessions,
    memories, or any piece of information you want to store and connect.

    If a node with the given ID already exists, it will be updated with the new information.

    Args:
        node_id: Unique identifier for the node (e.g., "concept:python", "memory:user_prefs")
        node_type: Type category of the node (e.g., "Concept", "Memory", "Session", "Entity")
        label: Human-readable short description or title
        content: Full text content to store in the node (can be lengthy)
        properties: Additional metadata as key-value pairs (e.g., {"importance": "high"})

    Returns:
        Dictionary with node_id and action ("added" or "updated")

    Example:
        add_node("concept:python", "Concept", "Python Programming",
                 "Python is a high-level programming language...",
                 {"importance": "high", "category": "programming"})
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        existing = _kb_repository.get_node(node_id)
        _kb_repository.add_node(node_id, node_type, label, content, properties or {})

        action = "updated" if existing else "added"
        result_msg = f"Successfully {action} node '{node_id}'"
        return MCPResponse.success(
            result={"node_id": node_id, "action": action}, message=result_msg
        ).to_dict()
    except Exception as e:
        logger.error("Error adding node: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to add node: {str(e)}").to_dict()


@mcp.tool()
def add_edge(
    source_id: str, target_id: str, edge_type: str, properties: dict = None
) -> dict:
    """Add a directional relationship (edge) between two nodes in the knowledge graph.

    Edges define relationships between nodes and give structure to your knowledge. They are
    directional (from source to target) and typed (e.g., "RELATES_TO", "DEPENDS_ON").
    Both source and target nodes must exist before creating an edge.

    Args:
        source_id: ID of the source node where the relationship originates
        target_id: ID of the target node where the relationship points to
        edge_type: Type of relationship (e.g., "RELATES_TO", "INSTANCE_OF", "DEPENDS_ON", "CAUSED_BY")
        properties: Additional metadata about the relationship (e.g., {"strength": 0.9, "since": "2024"})

    Returns:
        Dictionary with source_id, target_id, and edge_type

    Example:
        add_edge("concept:python", "concept:programming", "INSTANCE_OF")
        add_edge("session:123", "tool_call:456", "PERFORMED", {"timestamp": "2024-01-01"})
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Check if nodes exist
        source_node = _kb_repository.get_node(source_id)
        target_node = _kb_repository.get_node(target_id)
        if not source_node or not target_node:
            missing = []
            if not source_node:
                missing.append(source_id)
            if not target_node:
                missing.append(target_id)
            return MCPResponse.error(
                f"Cannot create edge. Node(s) not found: {missing}"
            ).to_dict()

        _kb_repository.add_edge(source_id, target_id, edge_type, properties or {})

        result_msg = f"Successfully added edge from '{source_id}' to '{target_id}'"
        return MCPResponse.success(
            result={
                "source_id": source_id,
                "target_id": target_id,
                "edge_type": edge_type,
            },
            message=result_msg,
        ).to_dict()
    except Exception as e:
        logger.error("Error adding edge: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to add edge: {str(e)}").to_dict()


@mcp.tool()
def get_node_by_id(node_id: str) -> dict:
    """Retrieve a single node by its unique identifier.

    Use this to fetch complete information about a specific node when you know its ID.
    Returns all node data including ID, type, label, content, and properties.

    Args:
        node_id: The unique identifier of the node to retrieve

    Returns:
        Complete node data including id, type, label, content, properties, created_at, updated_at

    Example:
        get_node_by_id("concept:python")
        get_node_by_id("memory:user_preferences")
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    node = _kb_repository.get_node(node_id)
    if node:
        return MCPResponse.success(result=node.to_dict()).to_dict()
    else:
        return MCPResponse.error(f"Node with id '{node_id}' not found").to_dict()


@mcp.tool()
def delete_node(node_id: str) -> dict:
    """Delete a node and all its connected edges from the knowledge graph.

    WARNING: This permanently removes the node and ALL edges connected to it (both incoming
    and outgoing). This operation cannot be undone. Use with caution.

    Args:
        node_id: Unique identifier of the node to delete

    Returns:
        Dictionary with the deleted node_id

    Example:
        delete_node("temp:calculation_123")
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        deleted = _kb_repository.delete_node(node_id)
        if deleted:
            return MCPResponse.success(
                result={"node_id": node_id},
                message=f"Successfully deleted node '{node_id}'",
            ).to_dict()
        else:
            return MCPResponse.error(f"Node with id '{node_id}' not found").to_dict()
    except Exception as e:
        logger.error(f"Error deleting node {node_id}: {e}", exc_info=True)
        return MCPResponse.error(f"Failed to delete node: {str(e)}").to_dict()


@mcp.tool()
def get_connected_nodes(node_id: str, limit: int = 50, offset: int = 0) -> dict:
    """Finds all nodes directly connected to a given node.

    Args:
        node_id: ID of the node to find connections for
        limit: Maximum number of connected nodes to return
        offset: Number of connected nodes to skip

    Returns a standardized MCPResponse dict with a list of connected nodes.
    """
    if not _kb_repository:
        logger.error("Database not initialized")
        return MCPResponse.error("Database not initialized").to_dict()

    node = _kb_repository.get_node(node_id)
    if not node:
        logger.warning("Node with id '%s' not found", node_id)
        return MCPResponse.empty(f"Node '{node_id}' not found").to_dict()

    # Use repository for neighbor lookup
    connected = []
    try:
        neighbors = _kb_repository.get_node_neighbors(node_id, direction="both")

        for edge, neighbor_node in neighbors:
            direction = "outgoing" if edge.source_id == node_id else "incoming"
            connected.append(
                {
                    "node": neighbor_node.to_dict(),
                    "edge_type": edge.edge_type,
                    "direction": direction,
                }
            )

        if not connected and offset == 0:
            return MCPResponse.empty(
                f"No connected nodes found for '{node_id}'"
            ).to_dict()

        # Store total count
        total_count = len(connected)

        # Apply pagination
        paginated_connected = connected[offset : offset + limit]

        return MCPResponse.paginated_success(
            result=paginated_connected,
            offset=offset,
            limit=limit,
            total_count=total_count,
            message=f"Found {len(paginated_connected)} connected nodes (total: {total_count})",
        ).to_dict()
    except Exception as e:
        logger.error("Error getting connected nodes: %s", e, exc_info=True)
        return MCPResponse.error(f"Error getting connected nodes: {str(e)}").to_dict()


@mcp.tool()
def get_graph_context(node_id: str, depth: int = 1) -> dict:
    """Retrieve a node and its surrounding neighborhood up to a specified depth.

    This tool provides local context around a node by fetching it and all connected nodes
    within N hops. Depth 1 gives immediate neighbors, depth 2 gives neighbors of neighbors, etc.
    Very useful for understanding how a concept fits into the broader knowledge structure.

    Args:
        node_id: The central node to get context for
        depth: How many hops away to explore (default: 1, max recommended: 3)

    Returns:
        Dictionary containing the central node and all discovered nodes/edges within depth

    Example:
        get_graph_context("concept:python", depth=2)  # Get Python and related concepts
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        context = _kb_repository.get_graph_context(node_id, depth)
        if not context:
            return MCPResponse.empty(
                f"Node '{node_id}' not found or has no context"
            ).to_dict()
        return MCPResponse.success(result=context).to_dict()
    except Exception as e:
        logger.error("Error getting graph context: %s", e, exc_info=True)
        return MCPResponse.error(f"Error getting graph context: {str(e)}").to_dict()


@mcp.tool()
def get_graph_map(
    include_details: bool = False,
    group_by_type: bool = True,
    nodes_limit: int = 50,  # Reduced from 100 to prevent large results
    nodes_offset: int = 0,
    edges_limit: int = 50,  # Reduced from 100 to prevent large results
    edges_offset: int = 0,
) -> dict:
    """Returns a comprehensive map of the entire knowledge graph showing all nodes, relationships, and statistics.

    Args:
        include_details: Include full node/edge properties
        group_by_type: Group nodes by type (pagination applies per type when False)
        nodes_limit: Maximum number of nodes to return (when group_by_type=False)
        nodes_offset: Number of nodes to skip (when group_by_type=False)
        edges_limit: Maximum number of edges to return
        edges_offset: Number of edges to skip
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Get statistics from repository
        stats = _kb_repository.get_graph_stats()

        # Build the map
        graph_map = {
            "statistics": {
                "total_nodes": stats["total_nodes"],
                "total_edges": stats["total_edges"],
                "node_types": stats["node_types"],
                "edge_types": stats["edge_types"],
            }
        }

        # Add nodes information
        if group_by_type:
            nodes_by_type = {}
            for node_type, count in stats["node_types"].items():
                nodes_by_type[node_type] = []
                # Limit each type to avoid overwhelming response
                nodes = _kb_repository.get_nodes(node_type=node_type, limit=100)

                for node in nodes:
                    if include_details:
                        node_dict = node.to_dict()
                        # Truncate large content to prevent massive results
                        node_dict = _truncate_node_content(node_dict)
                        nodes_by_type[node_type].append(node_dict)
                    else:
                        nodes_by_type[node_type].append(
                            {"id": node.id, "label": node.label or ""}
                        )
            graph_map["nodes_by_type"] = nodes_by_type
        else:
            # Apply pagination when not grouping by type
            all_nodes = _kb_repository.get_nodes(limit=nodes_limit, offset=nodes_offset)
            if include_details:
                # Truncate large content to prevent massive results
                graph_map["nodes"] = [_truncate_node_content(node.to_dict()) for node in all_nodes]
            else:
                graph_map["nodes"] = [
                    {"id": node.id, "label": node.label or ""} for node in all_nodes
                ]
            # Add pagination info for nodes
            graph_map["nodes_pagination"] = {
                "offset": nodes_offset,
                "limit": nodes_limit,
                "total_count": stats["total_nodes"],
                "returned_count": len(all_nodes),
            }

        # Add edges information with pagination
        all_edges = _kb_repository.get_edges(limit=edges_limit, offset=edges_offset)
        graph_map["edges"] = [
            {
                "source": edge.source_id,
                "target": edge.target_id,
                "type": edge.edge_type,
                "properties": edge.properties or {} if include_details else {},
            }
            for edge in all_edges
        ]
        # Add pagination info for edges
        graph_map["edges_pagination"] = {
            "offset": edges_offset,
            "limit": edges_limit,
            "total_count": stats["total_edges"],
            "returned_count": len(all_edges),
        }

        return MCPResponse.success(
            result=graph_map,
            message=f"Graph map with {len(all_edges)} edges (total: {stats['total_edges']})",
        ).to_dict()
    except Exception as e:
        logger.error("Error getting graph map: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to get graph map: {str(e)}").to_dict()


# Graph Analytics Tools
@mcp.tool()
def query_graph(
    query: str, parameters: Optional[dict] = None, limit: int = 50, offset: int = 0
) -> dict:
    """Execute an openCypher-like query on the knowledge graph. Supports MATCH, WHERE, RETURN, ORDER BY, and LIMIT clauses.

    Args:
        query: OpenCypher-like query string
        parameters: Optional query parameters
        limit: Maximum number of results to return (applied after query execution)
        offset: Number of results to skip (applied after query execution)

    Note: limit and offset are applied after the query executes. If your query has a LIMIT clause,
    these parameters will further limit the results.
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    # Handle None parameters
    if parameters is None:
        parameters = {}

    try:
        query = str(query).strip()
        if not query:
            return MCPResponse.error("Query string cannot be empty").to_dict()

        results = _kb_repository.query_graph(query=query, parameters=parameters)

        # Ensure we always return a list
        if results is None:
            logger.warning("Repository returned None for query: %s", query)
            return MCPResponse.empty("Query returned no results").to_dict()

        if not isinstance(results, list):
            logger.error(
                "Repository returned unexpected type: %s for query: %s",
                type(results),
                query,
            )
            return MCPResponse.error(
                f"Unexpected result type: {type(results).__name__}"
            ).to_dict()

        if not results and offset == 0:
            return MCPResponse.empty("Query returned no results").to_dict()

        # Store total count before pagination
        total_count = len(results)

        # Apply pagination
        end_index = offset + limit if limit else None
        paginated_results = results[offset:end_index]

        return MCPResponse.paginated_success(
            result=paginated_results,
            offset=offset,
            limit=limit,
            total_count=total_count,
            message=f"Query returned {len(paginated_results)} results (total: {total_count})",
        ).to_dict()

    except (ValueError, KeyError, AttributeError, IndexError) as query_error:
        logger.error("Query execution failed: %s", query_error, exc_info=True)
        return MCPResponse.error(
            f"Query execution failed: {str(query_error)}"
        ).to_dict()
    except Exception as e:
        logger.error("Unexpected error in query_graph: %s", e, exc_info=True)
        return MCPResponse.error(f"Query failed: {str(e)}").to_dict()


@mcp.tool()
def find_path(
    start_id: str, end_id: str, max_depth: int = 5, algorithm: str = "shortest"
) -> dict:
    """Find connection paths between two nodes in the knowledge graph.

    Discovers how two concepts or entities are related by finding paths through the graph.
    Useful for understanding connections, dependencies, or reasoning chains between ideas.

    Args:
        start_id: Starting node ID
        end_id: Target node ID
        max_depth: Maximum path length to search (default: 5, higher values may be slow)
        algorithm: Path finding strategy - "shortest" (fastest route) or "all" (all possible paths)

    Returns:
        List of paths, where each path is a sequence of nodes and edges connecting start to end

    Example:
        find_path("concept:python", "concept:web_development", max_depth=3)
        find_path("problem:bug_123", "solution:fix_456", algorithm="shortest")
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        if algorithm == "shortest":
            path = _kb_repository.find_shortest_path(start_id, end_id, max_depth)
            if path:
                result = {"path": path, "length": len(path)}
                return MCPResponse.success(
                    result=result, message=f"Found shortest path with {len(path)} nodes"
                ).to_dict()
            else:
                return MCPResponse.empty(
                    f"No path found between '{start_id}' and '{end_id}'"
                ).to_dict()
        elif algorithm == "all":
            paths = _kb_repository.find_all_paths(start_id, end_id, max_depth)
            result = {"paths": paths, "count": len(paths)}
            if paths:
                return MCPResponse.success(
                    result=result, message=f"Found {len(paths)} paths"
                ).to_dict()
            else:
                return MCPResponse.empty(
                    f"No paths found between '{start_id}' and '{end_id}'"
                ).to_dict()
        else:
            return MCPResponse.error(
                f"Unknown algorithm: {algorithm}. Supported: 'shortest', 'all'"
            ).to_dict()
    except Exception as e:
        logger.error("Error finding path: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to find path: {str(e)}").to_dict()


@mcp.tool()
def analyze_graph(analysis_type: str, parameters: Optional[dict] = None) -> dict:
    """Run graph analytics algorithms to discover structural insights and important nodes.

    Performs various graph analysis algorithms to understand the structure and importance of nodes.
    Useful for identifying key concepts, finding disconnected knowledge clusters, or getting
    an overall understanding of your knowledge graph's structure.

    Args:
        analysis_type: Type of analysis to run:
            - "centrality": Find most connected nodes (nodes with most edges)
            - "pagerank": Find most important nodes using PageRank algorithm
            - "components": Find disconnected clusters of knowledge
            - "summary": Get comprehensive graph statistics and overview
        parameters: Optional algorithm parameters:
            - For "pagerank": {"damping": 0.85, "iterations": 100}

    Returns:
        Analysis results including scores, rankings, or statistics depending on analysis_type

    Example:
        analyze_graph("summary")  # Get overview of graph structure
        analyze_graph("centrality")  # Find most connected concepts
        analyze_graph("pagerank", {"damping": 0.9})  # Find most important nodes
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    # Handle None parameters
    if parameters is None:
        parameters = {}

    try:
        if analysis_type == "centrality":
            centrality_scores = _kb_repository.calculate_degree_centrality()
            # Sort by score descending
            sorted_scores = sorted(
                centrality_scores.items(), key=lambda x: x[1], reverse=True
            )
            result = {
                "type": "degree_centrality",
                "scores": dict(sorted_scores[:20]),  # Top 20
                "total_nodes": len(centrality_scores),
            }
            return MCPResponse.success(result=result).to_dict()

        elif analysis_type == "pagerank":
            damping = parameters.get("damping", 0.85)
            iterations = parameters.get("iterations", 100)
            pr_scores = _kb_repository.calculate_pagerank(damping, iterations)
            sorted_scores = sorted(pr_scores.items(), key=lambda x: x[1], reverse=True)
            result = {
                "type": "pagerank",
                "scores": dict(sorted_scores[:20]),  # Top 20
                "total_nodes": len(pr_scores),
            }
            return MCPResponse.success(result=result).to_dict()

        elif analysis_type == "components":
            components = _kb_repository.find_connected_components()
            result = {
                "type": "connected_components",
                "component_count": len(components),
                "components": [
                    {"size": len(comp), "nodes": list(comp)[:10]}  # First 10 nodes
                    for comp in sorted(components, key=len, reverse=True)
                ],
            }
            return MCPResponse.success(result=result).to_dict()

        elif analysis_type == "summary":
            # Comprehensive graph summary
            components = _kb_repository.find_connected_components()
            centrality_scores = _kb_repository.calculate_degree_centrality()
            stats = _kb_repository.get_graph_stats()

            result = {
                "type": "summary",
                "total_nodes": stats["total_nodes"],
                "total_edges": stats["total_edges"],
                "node_types": stats["node_types"],
                "edge_types": stats["edge_types"],
                "connected_components": len(components),
                "largest_component_size": (
                    max(len(c) for c in components) if components else 0
                ),
                "top_nodes_by_centrality": sorted(
                    centrality_scores.items(), key=lambda x: x[1], reverse=True
                )[:10],
            }
            return MCPResponse.success(result=result).to_dict()

        elif analysis_type == "betweenness":
            normalized = parameters.get("normalized", True)
            bc_scores = _kb_repository.calculate_betweenness_centrality(
                normalized=normalized
            )
            sorted_scores = sorted(bc_scores.items(), key=lambda x: x[1], reverse=True)
            result = {
                "type": "betweenness_centrality",
                "normalized": bool(normalized),
                "scores": dict(sorted_scores[:20]),
                "total_nodes": len(bc_scores),
            }
            return MCPResponse.success(result=result).to_dict()

        elif analysis_type == "clustering":
            coeffs = _kb_repository.calculate_clustering_coefficient()
            sorted_scores = sorted(coeffs.items(), key=lambda x: x[1], reverse=True)
            result = {
                "type": "clustering_coefficient",
                "scores": dict(sorted_scores[:20]),
                "total_nodes": len(coeffs),
            }
            return MCPResponse.success(result=result).to_dict()

        else:
            return MCPResponse.error(
                f"Unknown analysis_type: {analysis_type}. Supported types: centrality, pagerank, components, summary, betweenness, clustering"
            ).to_dict()

    except Exception as e:
        logger.error(f"Error in analyze_graph: {e}", exc_info=True)
        return MCPResponse.error(f"Analysis failed: {str(e)}").to_dict()


@mcp.tool()
def filter_traverse(
    start_nodes: List[str],
    edge_types: List[str] = None,
    node_types: List[str] = None,
    max_depth: int = 3,
    direction: str = "both",
    nodes_limit: int = 100,
    nodes_offset: int = 0,
) -> dict:
    """Traverse the graph from starting nodes with filters, returning matching subgraph.

    Args:
        start_nodes: List of node IDs to start traversal from
        edge_types: Optional filter for edge types
        node_types: Optional filter for node types
        max_depth: Maximum depth to traverse
        direction: Direction to traverse ('incoming', 'outgoing', or 'both')
        nodes_limit: Maximum number of nodes to return
        nodes_offset: Number of nodes to skip in results
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        result = _kb_repository.traverse_graph(
            start_nodes, edge_types, node_types, max_depth, direction
        )

        # Apply pagination to nodes if result contains them
        if isinstance(result, dict) and "nodes" in result:
            total_nodes = len(result["nodes"])
            result["nodes"] = result["nodes"][nodes_offset : nodes_offset + nodes_limit]

            # Add pagination metadata for nodes
            result["nodes_pagination"] = {
                "offset": nodes_offset,
                "limit": nodes_limit,
                "total_count": total_nodes,
                "returned_count": len(result["nodes"]),
            }

            return MCPResponse.success(
                result=result,
                message=f"Traversal returned {len(result['nodes'])} nodes (total: {total_nodes})",
            ).to_dict()

        return MCPResponse.success(result=result).to_dict()
    except Exception as e:
        logger.error("Error in filter_traverse: %s", e, exc_info=True)
        return MCPResponse.error(f"Traversal failed: {str(e)}").to_dict()


@mcp.prompt()
def ask(question: str) -> str:
    """Asks the agent a question, leveraging its knowledge graph for context."""
    return f"""You are being asked to answer the following question. Use your knowledge graph systematically to provide a comprehensive, well-researched answer.

QUESTION: {question}

APPROACH:

1. **Understand the Question**
   - Break down what is being asked
   - Identify key concepts, entities, or topics mentioned
   - Determine what type of information would best answer the question

2. **Search Your Knowledge Graph**
   - Use `search_memory` to find relevant memories using natural language queries
   - Use `query_graph` to find specific nodes, relationships, or patterns
   - Use `get_node_by_id` if you know specific node IDs that might be relevant
   - Use `filter_traverse` to explore connections from relevant nodes
   - Use `find_path` to discover relationships between concepts if needed

3. **Gather Context**
   - Don't stop at the first search result - explore multiple angles
   - Look at related nodes and edges to build a complete picture
   - Check node properties and full content fields for detailed information
   - If initial searches are sparse, try related concepts or broader queries

4. **Synthesize Information**
   - Combine information from multiple nodes and memories
   - Look for patterns and connections across different pieces of knowledge
   - Consider temporal information (timestamps) if relevant
   - Identify any gaps or contradictions in the available information

5. **Formulate Your Answer**
   - Provide a clear, direct answer to the question
   - Support your answer with specific evidence from the knowledge graph
   - Cite specific nodes, memories, or relationships you found (mention node IDs or memory keys)
   - Be explicit about confidence level - if information is incomplete or uncertain, say so
   - If the knowledge graph doesn't contain sufficient information, clearly state what's missing

6. **Be Thorough But Focused**
   - Prioritize quality over quantity - use the most relevant information
   - Include enough detail to be helpful without overwhelming with tangential data
   - If the question has multiple parts, address each one systematically

IMPORTANT: Actually use the knowledge graph tools! Don't just speculate - search for relevant information, explore connections, and base your answer on what you discover in the graph."""


@mcp.prompt()
def create_new_task(task_description: str) -> str:
    """Creates a new task in the task queue, gathering additional context."""
    return f"""I need to create a new task with the following description: {task_description}.

Before creating the task, I need to gather some additional information:

1.  What is the intended purpose of this task? What goal does it achieve?
2.  Are there any specific details or context that would be helpful for the agent to know when working on this task?

Use the `add_task` tool to create the task, including the purpose and details in the metadata.
"""


@mcp.tool()
def search_nodes(
    query: str,
    node_type: str = None,
    top_k: int = 5,  # Reduced from 10 to prevent large results
    offset: int = 0,
    order_by: str = "relevance",
) -> dict:
    """Search ALL nodes in the knowledge graph using vector-based natural language search.

    This tool uses vector embeddings to enable natural language queries. You can search using
    plain English questions or descriptions, and it will find relevant nodes even if they don't
    contain your exact words. The vector embeddings capture meaning and context.

    Unlike search_memory (which only searches memory nodes), this searches across ALL node types,
    labels, content, and properties. Use this as your primary discovery tool for finding concepts,
    entities, sessions, or any knowledge in the graph.

    Args:
        query: Natural language query (e.g., "how do I optimize databases?" or "python frameworks")
        node_type: Optional filter by node type (e.g., "Concept", "Memory", "Session")
        top_k: Maximum number of results to return (default: 10)
        offset: Number of results to skip for pagination (default: 0)
        order_by: Sort order - "relevance" (vector similarity) or "timestamp" (most recent first)

    Returns:
        List of matching nodes with complete data, ordered by vector similarity score

    Example:
        search_nodes("what do I know about python programming?")
        search_nodes("database optimization techniques", node_type="Concept", top_k=5)
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    query = str(query).strip()

    # Vector-based natural language search
    try:
        # Get total count for the search (fetch extra to get accurate count)
        all_results = _kb_repository.search_nodes(
            query,
            node_type=node_type,
            limit=top_k + offset + 100,  # Fetch extra for accurate count
            order_by=order_by,
        )
        total_count = len(all_results)

        # Apply offset and limit
        search_results = _kb_repository.search_nodes(
            query,
            node_type=node_type,
            limit=top_k,
            offset=offset,
            order_by=order_by,
        )

        # Check if we got an error string instead of results
        if isinstance(search_results, str):
            logger.error("Repository returned error string: %s", search_results)
            return MCPResponse.error(search_results).to_dict()

        # Check if search_results is None or not a list
        if search_results is None:
            logger.warning("Repository returned None for query: %s", query)
            search_results = []

        if not isinstance(search_results, list):
            logger.error(
                "Repository returned unexpected type: %s for query: %s",
                type(search_results),
                query,
            )
            search_results = []

        logger.info(
            "Vector search returned %d results for query: %s",
            len(search_results),
            query,
        )

        # Convert Node instances to dictionaries
        dict_results = []
        for node in search_results:
            try:
                if isinstance(node, str):
                    logger.error("Found string instead of Node object: %s", node)
                    continue
                dict_results.append(node.to_dict())
            except Exception as e:
                logger.error("Error converting node to dict: %s", e, exc_info=True)
                continue
        search_results = dict_results

        # Group results by match type
        direct_matches = []
        related_matches = []

        for node in search_results:
            # Check if node is a dictionary
            if not isinstance(node, dict):
                logger.error(
                    "Node is not a dictionary! Type: %s, Value: %s",
                    type(node),
                    node,
                )
                continue

            key = None
            # if we have a node_type, only include nodes of that type
            if node_type:
                # Only include {node_type} nodes in results
                if node.get("node_type") == node_type:
                    # Parse properties to get key
                    props = node.get("properties", {})
                    if isinstance(props, str):
                        try:
                            props = json.loads(props)
                        except json.JSONDecodeError:
                            props = {}
                    key = props.get("key") if props else None
            # if we don't have a node_type, include all nodes
            else:
                # Parse properties to get key
                props = node.get("properties", {})
                if isinstance(props, str):
                    try:
                        props = json.loads(props)
                    except json.JSONDecodeError:
                        props = {}
                key = props.get("key") if props else None

            # Parse properties if it's a JSON string
            properties = node.get("properties", {})
            if isinstance(properties, str):
                try:
                    properties = json.loads(properties)
                except json.JSONDecodeError:
                    properties = {}

            # Include the full node data regardless of whether it has a key
            result_entry = {
                "id": node.get("id"),
                "node_type": node.get("node_type"),
                "label": node.get("label"),
                "content": node.get("content"),
                "properties": properties,
                "created_at": node.get("created_at"),
                "updated_at": node.get("updated_at"),
                "match_type": "direct",
            }
            # Add key if it exists (for Memory nodes)
            if key:
                result_entry["key"] = key

            # Truncate large content to prevent massive results
            result_entry = _truncate_node_content(result_entry)
            direct_matches.append(result_entry)

        # Build structured response
        output = {
            "direct_matches": direct_matches,
            "related_matches": related_matches,
            "statistics": {
                "direct_count": len(direct_matches),
                "related_count": len(related_matches),
                "total": len(direct_matches) + len(related_matches),
            },
        }

        if output["statistics"]["total"] == 0 and offset == 0:
            return MCPResponse.empty("No nodes found matching query").to_dict()

        return MCPResponse.paginated_success(
            result=output,
            offset=offset,
            limit=top_k,
            total_count=total_count,
            message=f"Found {output['statistics']['total']} matching nodes ({output['statistics']['direct_count']} direct, {output['statistics']['related_count']} related)",
        ).to_dict()

    except Exception as e:
        logger.error("Unexpected error in search_nodes: %s", e, exc_info=True)
        return MCPResponse.error(f"Search error: {str(e)}").to_dict()


# Memory Management Tools
@mcp.tool()
def save_memory(name: str, content: str, overwrite: bool = False) -> dict:
    """Save persistent text content under a named key in the knowledge graph.

    This is the primary tool for storing information you want to remember across sessions.
    Memories are special nodes that store arbitrary text content and can be searched using
    vector-based natural language queries (see search_memory tool).
    Use this to remember user preferences, important facts, task results, or any persistent state.

    By default, attempting to save to an existing key will fail unless overwrite=True.

    Args:
        name: Unique key for this memory (e.g., "user_preferences", "project_status")
        content: Text content to store (can be lengthy)
        overwrite: If True, replace existing content; if False, fail if key exists (default: False)

    Returns:
        Dictionary with key and action ("saved" or "updated")

    Example:
        save_memory("user_timezone", "America/New_York")
        save_memory("task_results", "Completed analysis: findings indicate...", overwrite=True)
    """
    memory_key = str(name).strip()
    content = str(content)

    if not memory_key:
        return MCPResponse.error("name must not be empty").to_dict()

    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        existing = _kb_repository.get_node(f"memory:{memory_key}")
        _kb_repository.save_memory(memory_key, content, overwrite=overwrite)
        action = "updated" if existing else "saved"
        return MCPResponse.success(
            result={"key": memory_key, "action": action},
            message=f"Successfully {action} memory '{memory_key}'",
        ).to_dict()
    except ValueError as e:
        return MCPResponse.error(str(e)).to_dict()
    except Exception as e:
        logger.error("Error saving memory: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to save memory: {str(e)}").to_dict()


@mcp.tool()
def append_memory(name: str, content: str) -> dict:
    """Append text content to an existing memory or create a new one.

    Use this to add information to a memory without replacing existing content.
    If the memory doesn't exist, it will be created. Perfect for accumulating logs,
    notes, or building up information over time.

    Args:
        name: Key of the memory to append to
        content: Text content to add (will be appended to existing content)

    Returns:
        Dictionary with key, action ("appended" or "created"), and new content_size

    Example:
        append_memory("session_log", "\\n- Completed task X at 10:30 AM")
        append_memory("notes", "\\nAdditional insight: ...")
    """
    memory_key = str(name).strip()
    content = str(content)

    if not memory_key:
        return MCPResponse.error("name must not be empty").to_dict()

    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        existing = _kb_repository.get_node(f"memory:{memory_key}")
        node = _kb_repository.append_memory(memory_key, content)
        action = "appended" if existing and existing.content else "created"
        content_size = len(node.content) if node.content else 0
        return MCPResponse.success(
            result={"key": memory_key, "action": action, "content_size": content_size},
            message=f"Successfully {action} memory '{memory_key}'",
        ).to_dict()
    except Exception as e:
        logger.error("Error appending memory: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to append memory: {str(e)}").to_dict()


@mcp.tool()
def get_memory(name: str) -> dict:
    """Retrieve the text content stored under a memory key.

    Use this to recall information you've previously saved. Returns the full text
    content of the memory. If the memory doesn't exist, an error is returned.

    Args:
        name: Key of the memory to retrieve

    Returns:
        The text content of the memory

    Example:
        get_memory("user_preferences")
        get_memory("project_status")
    """
    memory_key = str(name).strip()

    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        content = _kb_repository.get_memory(memory_key)

        if content is None:
            return MCPResponse.error(f"memory '{memory_key}' not found").to_dict()

        # If content is empty, return an error (memory exists but is empty)
        if content == "":
            return MCPResponse.error(
                f"memory '{memory_key}' exists but has no content"
            ).to_dict()

        return MCPResponse.success(
            result=content, message=f"Retrieved memory '{memory_key}'"
        ).to_dict()
    except Exception as e:
        logger.error("Error getting memory: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to get memory: {str(e)}").to_dict()


@mcp.tool()
def list_memories(
    prefix: str = None,
    sort_by_timestamp: bool = False,
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List stored memory keys, optionally filtered by prefix and sorted by update time."""
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Get total count for pagination
        total_count = _kb_repository.get_memories_count(prefix=prefix)

        # Get paginated results
        memory_list = _kb_repository.list_memories(
            prefix=prefix,
            sort_by_timestamp=sort_by_timestamp,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

        # Extract memory keys from the list
        keys = [m["key"] for m in memory_list]

        if not keys and offset == 0:
            return MCPResponse.empty("No memories found").to_dict()

        return MCPResponse.paginated_success(
            result=keys,
            offset=offset,
            limit=limit,
            total_count=total_count,
            message=f"Found {len(keys)} memories (total: {total_count})",
        ).to_dict()
    except Exception as e:
        logger.error("Error listing memories: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to list memories: {str(e)}").to_dict()


@mcp.tool()
def search_memory(
    query: str,
    top_k: int = 10,
    offset: int = 0,
    order_by: str = "relevance",
) -> dict:
    """Search memory nodes using vector-based natural language search.

    This tool uses vector embeddings to enable natural language queries over your stored memories.
    You can search using plain English questions or descriptions, and it will find relevant memories
    even if they don't contain your exact words. For example, searching for "python coding" will
    find memories about "programming in Python" because the vector embeddings capture contextual meaning.

    Use this when you remember storing something but don't recall the exact key name, or when
    you want to find all memories related to a topic. For searching ALL node types (not just memories),
    use search_nodes instead.

    Args:
        query: Natural language query (e.g., "what are the user's preferences for Python?")
        top_k: Maximum number of results to return (default: 10)
        offset: Number of results to skip for pagination (default: 0)
        order_by: Sort order - "relevance" (vector similarity) or "timestamp" (most recent first)

    Returns:
        List of matching memory nodes with keys, content, and vector similarity scores

    Example:
        search_memory("what did the user say about Python preferences?")
        search_memory("database learnings from last week", top_k=5)
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Get total count (fetch extra to get accurate count)
        all_results = _kb_repository.search_memory(
            query, limit=top_k + offset + 100, order_by=order_by
        )
        total_count = len(all_results)

        # Get paginated results
        memory_results = _kb_repository.search_memory(
            query, limit=top_k, offset=offset, order_by=order_by
        )

        if not memory_results and offset == 0:
            return MCPResponse.empty("No memories found matching query").to_dict()

        # Format results for MCP response
        result = {
            "memories": memory_results,
            "count": len(memory_results),
        }

        return MCPResponse.paginated_success(
            result=result,
            offset=offset,
            limit=top_k,
            total_count=total_count,
            message=f"Found {len(memory_results)} memories matching query (total: {total_count})",
        ).to_dict()
    except Exception as e:
        logger.error("Error searching memory: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to search memory: {str(e)}").to_dict()


@mcp.tool()
def delete_memory(name: str) -> dict:
    """Delete stored memories matching a pattern. Supports SQL LIKE patterns: use '%' for wildcard (e.g., 'temp_%' for all memories starting with 'temp_'), or provide an exact name. Returns count of deleted memories."""
    pattern = str(name).strip()

    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Get all memory nodes matching pattern
        all_memories = _kb_repository.list_memories()

        import fnmatch

        matching_keys = []

        for m in all_memories:
            key = m.get("key", "")

            # Convert SQL LIKE pattern to Python fnmatch
            if "%" in pattern or "_" in pattern:
                # SQL LIKE pattern
                py_pattern = pattern.replace("%", "*").replace("_", "?")
                if fnmatch.fnmatch(key, py_pattern):
                    matching_keys.append(key)
            elif key == pattern:
                # Exact match
                matching_keys.append(key)

        if not matching_keys:
            return MCPResponse.error(
                f"no memories found matching pattern '{pattern}'"
            ).to_dict()

        # Delete all matching
        deleted_count = 0
        for key in matching_keys:
            if _kb_repository.delete_memory(key):
                deleted_count += 1

        names_list = ", ".join(matching_keys[:10])
        if deleted_count > 10:
            names_list += f", ... ({deleted_count - 10} more)"

        if deleted_count == 1:
            message = f"Deleted 1 memory: {matching_keys[0]}"
        else:
            message = f"Deleted {deleted_count} memories: {names_list}"

        return MCPResponse.success(
            result={"deleted_count": deleted_count, "deleted_keys": matching_keys},
            message=message,
        ).to_dict()
    except Exception as e:
        logger.error("Error deleting memory: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to delete memory: {str(e)}").to_dict()


@mcp.tool()
def clear_memories() -> dict:
    """Delete ALL stored memories from the knowledge graph.

    WARNING: This permanently deletes ALL memory nodes. This operation cannot be undone.
    Use only when you need to wipe all persistent memory state. Consider using delete_memory
    with a pattern instead if you only need to remove specific memories.

    Returns:
        Dictionary with count of deleted memories
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Get all memory keys
        all_memories = _kb_repository.list_memories()
        deleted_count = 0

        for memory in all_memories:
            key = memory.get("key")
            if key and _kb_repository.delete_memory(key):
                deleted_count += 1

        if deleted_count == 0:
            return MCPResponse.empty("No memories to clear").to_dict()

        return MCPResponse.success(
            result={"deleted_count": deleted_count},
            message=f"Cleared {deleted_count} memories",
        ).to_dict()
    except Exception as e:
        logger.error("Error clearing memories: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to clear memories: {str(e)}").to_dict()


# Tool Tracking Tools
@mcp.tool()
def get_tool_usage_history(
    session_id: str = None, tool_name: str = None, limit: int = 20, offset: int = 0
) -> dict:
    """Get history of tool calls made during sessions with their arguments, results, and success/failure status. Useful for understanding tool usage patterns."""
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Get all ToolCall nodes
        all_tool_calls = _kb_repository.get_nodes(node_type="ToolCall")
        # Convert SQLAlchemy models to dictionaries
        all_tool_calls = [tc.to_dict() for tc in all_tool_calls]

        # Filter by session if specified
        filtered_calls = []
        for tc in all_tool_calls:
            # Get properties
            props = tc.get("properties", {})

            # Filter by session_id if specified
            if session_id:
                # Find the session node connected to this tool call
                edges = _kb_repository.get_edges(target_id=tc["id"])
                session_match = False
                for edge in edges:
                    if (
                        edge.edge_type == "PERFORMED"
                        and edge.source_id == f"session:{session_id}"
                    ):
                        session_match = True
                        break
                if not session_match:
                    continue

            # Filter by tool_name if specified
            if tool_name and props.get("tool_name") != tool_name:
                continue

            # Truncate large tool results to prevent massive responses
            result = props.get("result")
            if result and isinstance(result, str) and len(result) > 10000:
                result = result[:10000] + f"\n[... truncated: {len(result):,} chars total]"
            
            filtered_calls.append(
                {
                    "tool_call_id": tc["id"],
                    "tool_name": props.get("tool_name"),
                    "arguments": props.get("arguments"),
                    "result": result,
                    "status": props.get("status"),
                    "timestamp": props.get("timestamp"),
                    "error_type": props.get("error_type"),
                }
            )

        # Sort by timestamp (most recent first)
        # Handle None timestamps by treating them as empty strings (sorted to end)
        filtered_calls.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

        # Store total count
        total_count = len(filtered_calls)

        # Apply pagination
        paginated_calls = filtered_calls[offset : offset + limit]

        result = {
            "tool_calls": paginated_calls,
            "count": len(paginated_calls),
            "filters": {
                "session_id": session_id,
                "tool_name": tool_name,
            },
        }

        if not paginated_calls and offset == 0:
            return MCPResponse.empty(
                "No tool usage history found matching filters"
            ).to_dict()

        return MCPResponse.paginated_success(
            result=result,
            offset=offset,
            limit=limit,
            total_count=total_count,
            message=f"Found {len(paginated_calls)} tool calls (total: {total_count})",
        ).to_dict()
    except Exception as e:
        logger.error("Error getting tool usage history: %s", e, exc_info=True)
        return MCPResponse.error(
            f"Failed to get tool usage history: {str(e)}"
        ).to_dict()


@mcp.tool()
def get_failed_tool_calls(
    session_id: str = None, limit: int = 20, offset: int = 0
) -> dict:
    """Get tool calls that resulted in errors. Useful for learning from failures and debugging issues."""
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Get all ToolCall nodes
        all_tool_calls = _kb_repository.get_nodes(node_type="ToolCall")
        # Convert SQLAlchemy models to dictionaries
        all_tool_calls = [tc.to_dict() for tc in all_tool_calls]

        # Filter for errors only
        failed_calls = []
        for tc in all_tool_calls:
            props = tc.get("properties", {})

            # Only include failures
            if props.get("status") != "error":
                continue

            # Filter by session_id if specified
            if session_id:
                edges = _kb_repository.get_edges(target_id=tc["id"])
                session_match = False
                for edge in edges:
                    if (
                        edge.edge_type == "PERFORMED"
                        and edge.source_id == f"session:{session_id}"
                    ):
                        session_match = True
                        break
                if not session_match:
                    continue

            failed_calls.append(
                {
                    "tool_call_id": tc["id"],
                    "tool_name": props.get("tool_name"),
                    "arguments": props.get("arguments"),
                    "result": props.get("result"),
                    "error_type": props.get("error_type"),
                    "timestamp": props.get("timestamp"),
                }
            )

        # Sort by timestamp (most recent first)
        failed_calls.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Store total count
        total_count = len(failed_calls)

        # Apply pagination
        paginated_calls = failed_calls[offset : offset + limit]

        result = {
            "failed_calls": paginated_calls,
            "count": len(paginated_calls),
            "session_id": session_id,
        }

        if not paginated_calls and offset == 0:
            return MCPResponse.empty(
                "No failed tool calls found matching filters"
            ).to_dict()

        return MCPResponse.paginated_success(
            result=result,
            offset=offset,
            limit=limit,
            total_count=total_count,
            message=f"Found {len(paginated_calls)} failed tool calls (total: {total_count})",
        ).to_dict()
    except Exception as e:
        logger.error("Error getting failed tool calls: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to get failed tool calls: {str(e)}").to_dict()


@mcp.tool()
def get_tool_usage_stats(session_id: str = None) -> dict:
    """Get statistics about tool usage including most used tools, success/failure rates, and recent patterns."""
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Get all ToolCall nodes
        all_tool_calls = _kb_repository.get_nodes(node_type="ToolCall")
        # Convert SQLAlchemy models to dictionaries
        all_tool_calls = [tc.to_dict() for tc in all_tool_calls]

        # Filter by session if specified
        filtered_calls = []
        for tc in all_tool_calls:
            if session_id:
                edges = _kb_repository.get_edges(target_id=tc["id"])
                session_match = False
                for edge in edges:
                    if (
                        edge.edge_type == "PERFORMED"
                        and edge.source_id == f"session:{session_id}"
                    ):
                        session_match = True
                        break
                if not session_match:
                    continue
            filtered_calls.append(tc)

        # Calculate statistics
        tool_counts = {}
        tool_success = {}
        tool_failures = {}
        error_types = {}
        recent_failures = []

        for tc in filtered_calls:
            props = tc.get("properties", {})
            tool_name = props.get("tool_name", "unknown")
            status = props.get("status", "unknown")

            # Count tool usage
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

            # Count successes and failures
            if status == "success":
                tool_success[tool_name] = tool_success.get(tool_name, 0) + 1
            elif status == "error":
                tool_failures[tool_name] = tool_failures.get(tool_name, 0) + 1

                # Track error types
                error_type = props.get("error_type", "Unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1

                # Collect recent failures
                recent_failures.append(
                    {
                        "tool_name": tool_name,
                        "error_type": error_type,
                        "timestamp": props.get("timestamp"),
                        "result": props.get("result", "")[:200],  # Truncate for brevity
                    }
                )

        # Sort recent failures by timestamp
        recent_failures.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        recent_failures = recent_failures[:10]  # Keep only 10 most recent

        # Calculate success rates
        tool_stats = {}
        for tool_name, total in tool_counts.items():
            successes = tool_success.get(tool_name, 0)
            failures = tool_failures.get(tool_name, 0)
            success_rate = (successes / total * 100) if total > 0 else 0

            tool_stats[tool_name] = {
                "total_calls": total,
                "successes": successes,
                "failures": failures,
                "success_rate": round(success_rate, 2),
            }

        # Sort by total calls (most used first)
        most_used = sorted(
            tool_stats.items(), key=lambda x: x[1]["total_calls"], reverse=True
        )

        result = {
            "total_tool_calls": len(filtered_calls),
            "unique_tools": len(tool_counts),
            "most_used_tools": dict(most_used[:10]),  # Top 10
            "error_types": error_types,
            "recent_failures": recent_failures,
            "session_id": session_id,
        }

        if not filtered_calls:
            return MCPResponse.empty("No tool usage data found").to_dict()

        return MCPResponse.success(
            result=result, message=f"Statistics for {len(filtered_calls)} tool calls"
        ).to_dict()
    except Exception as e:
        logger.error("Error getting tool usage stats: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to get tool usage stats: {str(e)}").to_dict()


@mcp.tool()
async def add_task(instruction: str, metadata: dict = None) -> dict:
    """
    Add a new task to the task queue. This schedules a task to be worked by the background task agent.
    Args:
        instruction: The instruction for the task.
        metadata: The metadata for the task.
    Returns:
        A dictionary containing the task.
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    # Validate instruction is not empty
    if not instruction or not instruction.strip():
        return MCPResponse.error(
            "Task instruction cannot be empty. Please provide a valid instruction."
        ).to_dict()

    try:
        # Create TaskQueue instance from the repository
        task_queue = TaskQueue(_kb_repository)
        task = await task_queue.add_task(
            instruction=instruction,
            metadata=metadata,
        )
        return MCPResponse.success(
            result=task, message=f"Successfully created task '{task['id']}'"
        ).to_dict()
    except Exception as e:
        logger.error("Error creating task: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to create task: {str(e)}").to_dict()


@mcp.tool()
async def list_tasks(limit: int = 50, offset: int = 0) -> dict:
    """
    List all tasks in the task queue. This is useful for monitoring the task queue and seeing what tasks are pending, in progress, completed, or failed.
    Args:
        limit: Maximum number of tasks to return
        offset: Number of tasks to skip
    Returns:
        A dictionary containing the tasks.
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        task_queue = TaskQueue(_kb_repository)

        # Get total count for pagination
        total_count = task_queue.get_tasks_count()

        # Get paginated results
        tasks = await task_queue.get_all_tasks(limit=limit, offset=offset)

        return MCPResponse.paginated_success(
            result=tasks,
            offset=offset,
            limit=limit,
            total_count=total_count,
            message=f"Successfully listed {len(tasks)} tasks (total: {total_count})",
        ).to_dict()
    except Exception as e:
        logger.error("Error listing tasks: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to list tasks: {str(e)}").to_dict()


@mcp.tool()
async def get_task(task_id: str) -> dict:
    """
    Get a task by its ID. This is useful for getting the details of a specific task.
    Args:
        task_id: The ID of the task.
    Returns:
        A dictionary containing the task.
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        task_queue = TaskQueue(_kb_repository)
        task = await task_queue.get_task(task_id)
        return MCPResponse.success(
            result=task, message=f"Successfully retrieved task '{task_id}'"
        ).to_dict()
    except Exception as e:
        logger.error("Error getting task: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to get task: {str(e)}").to_dict()


@mcp.tool()
async def delete_task(task_id: str) -> dict:
    """
    Delete a task from the task queue. This is useful for removing a task from the queue if it is no longer needed.
    Args:
        task_id: The ID of the task.
    Returns:
        A dictionary containing the task.
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        task_queue = TaskQueue(_kb_repository)
        await task_queue.delete_task(task_id)
        return MCPResponse.success(
            message=f"Successfully deleted task '{task_id}'"
        ).to_dict()
    except Exception as e:
        logger.error("Error deleting task: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to delete task: {str(e)}").to_dict()


@mcp.tool()
async def update_task(
    task_id: str, status: str, response: str = None, error: str = None
) -> dict:
    """
    Update the status of a task. This is useful for updating the status of a task if it is no longer needed.
    Args:
        task_id: The ID of the task.
        status: The status of the task.
        response: The response of the task.
        error: The error of the task.
    Returns:
        A dictionary containing the task.
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        task_queue = TaskQueue(_kb_repository)
        await task_queue.update_task_status(task_id, status, response, error)
        return MCPResponse.success(
            message=f"Successfully updated task '{task_id}'"
        ).to_dict()
    except Exception as e:
        logger.error("Error updating task: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to update task: {str(e)}").to_dict()


@mcp.tool()
async def get_task_stats() -> dict:
    """Get statistics about the task queue. This is useful for monitoring the task queue and seeing what tasks are pending, in progress, completed, or failed."""
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        task_queue = TaskQueue(_kb_repository)
        stats = await task_queue.get_task_stats()
        return MCPResponse.success(
            result=stats, message="Successfully got task stats"
        ).to_dict()
    except Exception as e:
        logger.error("Error getting task stats: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to get task stats: {str(e)}").to_dict()


# ============================================================================
# SECTION 6.5: WORKFLOW MANAGEMENT TOOLS
# ============================================================================


@mcp.tool()
def save_workflow(
    name: str, description: str, steps: List[dict], version: int = None
) -> dict:
    """Save or update a workflow definition as a versioned graph node.

    Workflows are sequential tool execution patterns that can be reused. Each save
    creates a new version, allowing you to track workflow evolution over time.

    Args:
        name: Unique workflow name (e.g., "analyze_codebase", "deploy_feature")
        description: What the workflow does and when to use it
        steps: List of workflow steps, each with: tool_name, args (dict), output_key (optional)
        version: Specific version number (auto-increments if None)

    Returns:
        The created workflow node with version info
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Validate steps structure
        if not isinstance(steps, list) or not steps:
            return MCPResponse.error(
                "steps must be a non-empty list of step definitions"
            ).to_dict()

        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                return MCPResponse.error(f"Step {i + 1} must be a dictionary").to_dict()
            if "tool_name" not in step:
                return MCPResponse.error(
                    f"Step {i + 1} missing required 'tool_name' field"
                ).to_dict()
            if "args" in step and not isinstance(step["args"], dict):
                return MCPResponse.error(
                    f"Step {i + 1} 'args' must be a dictionary"
                ).to_dict()

        # Save workflow using repository
        node = _kb_repository.save_workflow(
            name=name, description=description, steps=steps, version=version
        )

        # Ensure concept:workflow exists
        _kb_repository.add_node(
            node_id="concept:workflow",
            node_type="Concept",
            label="Workflow",
            properties={"description": "Sequential tool execution patterns"},
        )
        # Link to self
        _kb_repository.add_edge(
            source_id="concept:workflow",
            target_id="concept:self",
            edge_type="ASPECT_OF",
        )

        result = node.to_dict()
        return MCPResponse.success(
            result=result,
            message=f"Saved workflow '{name}' version {result['properties']['version']}",
        ).to_dict()
    except Exception as e:
        logger.error("Error saving workflow: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to save workflow: {str(e)}").to_dict()


# Note: Workflow execution happens in the bot, not in the knowledge server
# The bot has access to the toolchain and can execute tools
# This server only handles workflow storage/retrieval and tracking


@mcp.tool()
def list_workflows(
    include_versions: bool = False, limit: int = 50, offset: int = 0
) -> dict:
    """List all available workflows.

    Args:
        include_versions: If True, return all versions; if False, only latest version of each
        limit: Maximum number of workflows to return
        offset: Number of workflows to skip

    Returns:
        List of workflow definitions with names, versions, and usage stats
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Get total count for pagination
        total_count = _kb_repository.get_workflows_count(
            include_versions=include_versions
        )

        # Get paginated results
        workflows = _kb_repository.list_workflows(
            include_versions=include_versions, limit=limit, offset=offset
        )

        if not workflows and offset == 0:
            return MCPResponse.empty("No workflows found").to_dict()

        result = []
        for workflow in workflows:
            props = workflow.properties or {}
            result.append(
                {
                    "name": props.get("name"),
                    "version": props.get("version"),
                    "description": workflow.content or "",
                    "steps_count": len(json.loads(props.get("steps", "[]"))),
                    "execution_count": props.get("execution_count", 0),
                    "success_count": props.get("success_count", 0),
                    "failure_count": props.get("failure_count", 0),
                    "created_at": (
                        workflow.created_at.isoformat() if workflow.created_at else None
                    ),
                }
            )

        return MCPResponse.paginated_success(
            result=result,
            offset=offset,
            limit=limit,
            total_count=total_count,
            message=f"Found {len(result)} workflows (total: {total_count})",
        ).to_dict()
    except Exception as e:
        logger.error("Error listing workflows: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to list workflows: {str(e)}").to_dict()


@mcp.tool()
def get_workflow(workflow_name: str, version: int = None) -> dict:
    """Get a workflow definition by name and optional version.

    Args:
        workflow_name: Name of the workflow
        version: Specific version (None = latest)

    Returns:
        Complete workflow definition including all steps
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        workflow = _kb_repository.get_workflow(workflow_name, version)

        if not workflow:
            return MCPResponse.error(f"Workflow '{workflow_name}' not found").to_dict()

        props = workflow.properties or {}
        result = {
            "name": props.get("name"),
            "version": props.get("version"),
            "description": workflow.content or "",
            "steps": json.loads(props.get("steps", "[]")),
            "execution_count": props.get("execution_count", 0),
            "success_count": props.get("success_count", 0),
            "failure_count": props.get("failure_count", 0),
            "created_at": (
                workflow.created_at.isoformat() if workflow.created_at else None
            ),
            "updated_at": (
                workflow.updated_at.isoformat() if workflow.updated_at else None
            ),
        }

        return MCPResponse.success(result=result).to_dict()
    except Exception as e:
        logger.error("Error getting workflow: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to get workflow: {str(e)}").to_dict()


@mcp.tool()
def delete_workflow(workflow_name: str, version: int = None) -> dict:
    """Delete a workflow and optionally specific versions.

    Args:
        workflow_name: Name of the workflow to delete
        version: Specific version to delete (None = delete all versions)

    Returns:
        Confirmation of deletion
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        deleted = _kb_repository.delete_workflow(workflow_name, version)

        if not deleted:
            return MCPResponse.error(f"Workflow '{workflow_name}' not found").to_dict()

        if version:
            message = f"Deleted workflow '{workflow_name}' version {version}"
        else:
            message = f"Deleted all versions of workflow '{workflow_name}'"

        return MCPResponse.success(
            result={"workflow_name": workflow_name, "version": version},
            message=message,
        ).to_dict()
    except Exception as e:
        logger.error("Error deleting workflow: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to delete workflow: {str(e)}").to_dict()


# ============================================================================
# SECTION 6.6: SEQUENTIAL THINKING TOOLS
# ============================================================================


@mcp.tool()
def create_thinking_pattern(
    name: str, description: str, steps: List[str], applicable_to: List[str]
) -> dict:
    """Store a reusable thinking pattern for problem-solving.

    Thinking patterns are structured approaches to reasoning that can be retrieved
    and applied to similar problems in the future.

    Args:
        name: Pattern name (e.g., "debugging_approach", "feature_planning")
        description: What the pattern is and when to use it
        steps: List of reasoning steps (strings)
        applicable_to: List of problem types this applies to

    Returns:
        The created thinking pattern node
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Validate inputs
        if not isinstance(steps, list) or not steps:
            return MCPResponse.error("steps must be a non-empty list").to_dict()
        if not isinstance(applicable_to, list):
            return MCPResponse.error("applicable_to must be a list").to_dict()

        # Save pattern using repository
        node = _kb_repository.save_thinking_pattern(
            name=name, description=description, steps=steps, applicable_to=applicable_to
        )

        # Ensure concept:reasoning exists
        _kb_repository.add_node(
            node_id="concept:reasoning",
            node_type="Concept",
            label="Reasoning",
            properties={
                "description": "Thinking patterns and problem-solving approaches"
            },
        )
        # Link to self
        _kb_repository.add_edge(
            source_id="concept:reasoning",
            target_id="concept:self",
            edge_type="ASPECT_OF",
        )

        result = node.to_dict()
        return MCPResponse.success(
            result=result, message=f"Created thinking pattern '{name}'"
        ).to_dict()
    except Exception as e:
        logger.error("Error creating thinking pattern: %s", e, exc_info=True)
        return MCPResponse.error(
            f"Failed to create thinking pattern: {str(e)}"
        ).to_dict()


@mcp.tool()
def apply_sequential_thinking(
    problem: str, context: str = None, session_id: str = None
) -> dict:
    """Break down a problem using learned thinking patterns.

    Searches the knowledge graph for similar past problems and thinking patterns,
    then generates a structured step-by-step approach based on successful past reasoning.

    Args:
        problem: The problem to solve
        context: Optional additional context
        session_id: Optional session ID to track this thinking session

    Returns:
        Generated reasoning steps and related patterns
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Search for similar problems and patterns
        search_query = f"{problem} {context or ''}"
        patterns = _kb_repository.get_thinking_patterns(search_query, limit=3)

        # Generate steps based on patterns
        if patterns:
            # Use the top matching pattern
            top_pattern = patterns[0]
            pattern_props = top_pattern.properties or {}
            pattern_steps = json.loads(pattern_props.get("steps", "[]"))
            pattern_name = pattern_props.get("name")

            steps = [
                f"Based on '{pattern_name}' pattern:",
                *pattern_steps,
                "Apply these steps to your specific problem context.",
            ]
        else:
            # Generic problem-solving approach
            steps = [
                "1. Understand the problem - What exactly needs to be solved?",
                "2. Gather information - What do we know? What don't we know?",
                "3. Break it down - Can this be split into smaller sub-problems?",
                "4. Devise a plan - What approach should we take?",
                "5. Execute the plan - Implement the solution step by step",
                "6. Review and reflect - Did it work? What did we learn?",
            ]
            pattern_name = None

        # Create thinking session node if session_id provided
        if session_id:
            _kb_repository.create_thinking_session(
                problem=problem,
                session_id=session_id,
                steps=steps,
                pattern_name=pattern_name,
            )

        result = {
            "problem": problem,
            "steps": steps,
            "pattern_used": pattern_name,
            "similar_patterns": [
                {
                    "name": p.properties.get("name"),
                    "description": p.content,
                    "applicable_to": json.loads(
                        p.properties.get("applicable_to", "[]")
                    ),
                }
                for p in patterns[:3]
            ],
        }

        return MCPResponse.success(
            result=result,
            message=f"Generated {len(steps)} reasoning steps for problem",
        ).to_dict()
    except Exception as e:
        logger.error("Error applying sequential thinking: %s", e, exc_info=True)
        return MCPResponse.error(
            f"Failed to apply sequential thinking: {str(e)}"
        ).to_dict()


@mcp.tool()
def get_thinking_patterns(
    query: str, problem_type: str = None, limit: int = 5, offset: int = 0
) -> dict:
    """Retrieve thinking patterns similar to a query.

    Uses vector-based natural language search to find relevant reasoning patterns based
    on past successful problem-solving approaches.

    Args:
        query: Search query describing the type of problem
        problem_type: Optional filter by specific problem type
        limit: Maximum number of patterns to return
        offset: Number of patterns to skip

    Returns:
        List of matching thinking patterns with usage statistics
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Get extra patterns for total count
        all_patterns = _kb_repository.get_thinking_patterns(
            query, problem_type, limit + offset + 20
        )
        total_count = len(all_patterns)

        # Get paginated patterns
        patterns = _kb_repository.get_thinking_patterns(
            query, problem_type, limit, offset
        )

        if not patterns and offset == 0:
            return MCPResponse.empty("No thinking patterns found").to_dict()

        result = []
        for pattern in patterns:
            props = pattern.properties or {}
            result.append(
                {
                    "name": props.get("name"),
                    "description": pattern.content or "",
                    "steps": json.loads(props.get("steps", "[]")),
                    "applicable_to": json.loads(props.get("applicable_to", "[]")),
                    "usage_count": props.get("usage_count", 0),
                    "success_rate": props.get("success_rate", 0.0),
                }
            )

        return MCPResponse.paginated_success(
            result=result,
            offset=offset,
            limit=limit,
            total_count=total_count,
            message=f"Found {len(result)} thinking patterns (total: {total_count})",
        ).to_dict()
    except Exception as e:
        logger.error("Error getting thinking patterns: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to get thinking patterns: {str(e)}").to_dict()


@mcp.tool()
def save_problem_solution(
    problem: str,
    approach_steps: List[str],
    outcome: str,
    lessons_learned: str,
    session_id: str = None,
) -> dict:
    """Store a successful problem-solving approach for future reference.

    Captures effective reasoning approaches so they can be retrieved and applied
    to similar problems in the future.

    Args:
        problem: The problem that was solved
        approach_steps: Steps taken to solve it (list of strings)
        outcome: The result/solution
        lessons_learned: Key insights and takeaways
        session_id: Optional session ID to link to

    Returns:
        The created problem solution node
    """
    if not _kb_repository:
        return MCPResponse.error("Database not initialized").to_dict()

    try:
        # Validate inputs
        if not isinstance(approach_steps, list) or not approach_steps:
            return MCPResponse.error(
                "approach_steps must be a non-empty list"
            ).to_dict()

        # Save solution using repository
        node = _kb_repository.save_problem_solution(
            problem=problem,
            approach_steps=approach_steps,
            outcome=outcome,
            lessons_learned=lessons_learned,
            session_id=session_id,
        )

        result = node.to_dict()
        return MCPResponse.success(
            result=result, message="Saved problem solution for future reference"
        ).to_dict()
    except Exception as e:
        logger.error("Error saving problem solution: %s", e, exc_info=True)
        return MCPResponse.error(f"Failed to save problem solution: {str(e)}").to_dict()


# ============================================================================
# SECTION 6.7: PROMPTS FOR QUERY GUIDANCE
# ============================================================================


@mcp.prompt()
def deep_dive(concept_name: str) -> str:
    """Template for discovering what the knowledge graph knows about a concept."""
    return f"""I want to explore what I know about '{concept_name}'. Help me:

1. Search for nodes related to this concept using search_nodes
2. If found, get the full context using get_graph_context with depth 2
3. Identify key relationships and connected concepts
4. Summarize what I know and what gaps exist

Use natural language queries for search_nodes to find semantically related information."""


@mcp.prompt()
def solve_problem(problem_description: str) -> str:
    """Template for applying structured thinking to solve problems."""
    return f"""I need to solve this problem: {problem_description}

Follow this approach:
1. Use apply_sequential_thinking to get relevant thinking patterns
2. Break the problem into sub-problems
3. Search for similar past solutions using search_nodes
4. Execute the solution step by step
5. Save the approach with save_problem_solution for future reference

Focus on learning from past patterns and building reusable knowledge."""


@mcp.prompt()
def execute_workflow(workflow_name: str, context: str = "") -> str:
    """Template for executing a stored workflow."""
    return f"""Execute the workflow '{workflow_name}' with this context: {context}

Steps:
1. Use get_workflow to retrieve the workflow definition
2. Review each step and its arguments
3. Execute steps in sequence, passing outputs as needed
4. Track execution status
5. Report results and any failures

Workflows contain tool_name and args for each step. Use the tool call dispatch to execute them."""


@mcp.prompt()
def organize_memories(topic: str) -> str:
    """Template for organizing and reviewing memories about a topic."""
    return f"""Review and organize memories related to: {topic}

Process:
1. Use search_memory to find all related memories
2. Check for duplicates or outdated information
3. Consolidate related memories if needed
4. Create clear hierarchical memory keys (e.g., 'project/feature/status')
5. Link memories to relevant concept nodes in the graph

Good memory organization improves future retrieval."""


@mcp.prompt()
def analyze_knowledge_structure() -> str:
    """Template for analyzing the overall knowledge graph structure."""
    return """Analyze the structure and health of the knowledge graph:

1. Use analyze_graph('summary') to get overall statistics
2. Use analyze_graph('centrality') to find most connected concepts
3. Use analyze_graph('components') to find isolated knowledge clusters
4. Identify gaps: disconnected nodes or under-connected concepts
5. Suggest improvements: new edges, consolidation opportunities

A well-connected graph enables better reasoning and retrieval."""


@mcp.prompt()
def make_plan(problem_description: str) -> str:
    """Template for creating a detailed plan to solve a problem without executing it."""
    return f"""I need to create a plan to solve this problem: {problem_description}

Follow this approach:
1. Use apply_sequential_thinking to get relevant thinking patterns
2. Break the problem into sub-problems and steps
3. Search for similar past solutions using search_nodes
4. Identify required resources, tools, and dependencies
5. Create a detailed markdown plan document
6. Save the plan as a .md file in the plans/ directory with a descriptive name

The plan should include:
- Problem statement
- Analysis and approach
- Step-by-step execution plan
- Required resources
- Success criteria
- Potential risks and mitigations

Focus on thorough planning before saving the plan."""


@mcp.prompt()
def execute_plan(plan_name: str) -> str:
    """Template for executing a plan from the plans directory."""
    return f"""Execute the plan '{plan_name}' from the plans/ directory.

Steps:
1. Read the plan file from @directory://plans
2. Review the problem statement and approach
3. Verify all required resources and dependencies are available
4. Execute each step in the plan sequentially
5. Track progress and document any deviations from the plan
6. Update the plan file with execution results and learnings
7. Save outcomes with save_problem_solution for future reference

Follow the plan carefully and adapt as needed based on actual results."""


@mcp.prompt()
def report_issue(prompt: str) -> str:
    """Template for reporting an issue."""
    return f"""I need to report an issue: {prompt}. Create an issue report in the knowledge graph for me to work on later."""


@mcp.prompt()
def request_feature(prompt: str) -> str:
    """Template for requesting a new feature."""
    return f"""I need to request a new feature: {prompt}. Create a feature request in the knowledge graph for me to work on later."""


# ============================================================================
# SECTION 6.8: RESOURCES FOR DIRECT DATA ACCESS
# ============================================================================


@mcp.resource("knowledge://stats")
def resource_graph_stats() -> str:
    """Provides current knowledge graph statistics."""
    if not _kb_repository:
        return json.dumps({"error": "Database not initialized"})

    try:
        stats = _kb_repository.get_graph_stats()
        return json.dumps(stats, indent=2)
    except Exception as e:
        logger.error("Error getting graph stats resource: %s", e)
        return json.dumps({"error": str(e)})


@mcp.resource("knowledge://memories")
def resource_all_memories() -> str:
    """Lists all stored memory keys with metadata."""
    if not _kb_repository:
        return json.dumps({"error": "Database not initialized"})

    try:
        memories = _kb_repository.list_memories(limit=100)
        memory_list = [
            {
                "key": m.get("key"),
                "preview": m.get("content", "")[:100] if m.get("content") else "",
                "updated_at": m.get("updated_at"),
            }
            for m in memories
        ]
        return json.dumps(
            {"memories": memory_list, "count": len(memory_list)}, indent=2
        )
    except Exception as e:
        logger.error("Error getting memories resource: %s", e)
        return json.dumps({"error": str(e)})


@mcp.resource("knowledge://memory/{memory_key}")
def resource_memory_content(memory_key: str) -> str:
    """Provides content of a specific memory by key."""
    if not _kb_repository:
        return json.dumps({"error": "Database not initialized"})

    try:
        content = _kb_repository.get_memory(memory_key)
        if content is None:
            return json.dumps({"error": f"Memory '{memory_key}' not found"})
        return json.dumps({"key": memory_key, "content": content}, indent=2)
    except Exception as e:
        logger.error("Error getting memory resource: %s", e)
        return json.dumps({"error": str(e)})


@mcp.resource("knowledge://workflows")
def resource_workflows() -> str:
    """Lists all available workflows with metadata."""
    if not _kb_repository:
        return json.dumps({"error": "Database not initialized"})

    try:
        workflows = _kb_repository.list_workflows(include_versions=False, limit=50)
        workflow_list = [
            {
                "name": w.properties.get("name"),
                "version": w.properties.get("version"),
                "description": w.content or "",
                "steps_count": len(json.loads(w.properties.get("steps", "[]"))),
            }
            for w in workflows
        ]
        return json.dumps(
            {"workflows": workflow_list, "count": len(workflow_list)}, indent=2
        )
    except Exception as e:
        logger.error("Error getting workflows resource: %s", e)
        return json.dumps({"error": str(e)})


@mcp.resource("knowledge://workflow/{workflow_name}")
def resource_workflow_definition(workflow_name: str) -> str:
    """Provides complete workflow definition by name."""
    if not _kb_repository:
        return json.dumps({"error": "Database not initialized"})

    try:
        workflow = _kb_repository.get_workflow(workflow_name, version=None)
        if not workflow:
            return json.dumps({"error": f"Workflow '{workflow_name}' not found"})

        props = workflow.properties or {}
        result = {
            "name": props.get("name"),
            "version": props.get("version"),
            "description": workflow.content or "",
            "steps": json.loads(props.get("steps", "[]")),
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error("Error getting workflow resource: %s", e)
        return json.dumps({"error": str(e)})


@mcp.resource("knowledge://thinking-patterns")
def resource_thinking_patterns() -> str:
    """Lists available thinking patterns for problem-solving."""
    if not _kb_repository:
        return json.dumps({"error": "Database not initialized"})

    try:
        patterns = _kb_repository.get_thinking_patterns(
            query="problem solving reasoning", limit=20
        )
        pattern_list = []
        for p in patterns:
            # Safely parse applicable_to field
            applicable_to_raw = p.properties.get("applicable_to", "[]")
            try:
                # Handle empty strings and None values
                if not applicable_to_raw or applicable_to_raw.strip() == "":
                    applicable_to = []
                else:
                    applicable_to = json.loads(applicable_to_raw)
            except (json.JSONDecodeError, TypeError) as e:
                # Fallback to empty list if parsing fails
                logger.error(
                    f"Error parsing applicable_to for pattern {p.properties.get('name')}: {e}"
                )
                applicable_to = []

            pattern_list.append(
                {
                    "name": p.properties.get("name"),
                    "description": p.content or "",
                    "applicable_to": applicable_to,
                    "usage_count": p.properties.get("usage_count", 0),
                }
            )

        return json.dumps(
            {"patterns": pattern_list, "count": len(pattern_list)}, indent=2
        )
    except Exception as e:
        logger.error("Error getting thinking patterns resource: %s", e)
        return json.dumps({"error": str(e)})


@mcp.resource("knowledge://node/{node_id}/context")
def resource_node_context(node_id: str) -> str:
    """Provides a node and its immediate context (depth 1)."""
    if not _kb_repository:
        return json.dumps({"error": "Database not initialized"})

    try:
        context = _kb_repository.get_graph_context(node_id, depth=1)
        if not context:
            return json.dumps({"error": f"Node '{node_id}' not found"})
        return json.dumps(context, indent=2)
    except Exception as e:
        logger.error("Error getting node context resource: %s", e)
        return json.dumps({"error": str(e)})


@mcp.resource("knowledge://tool-usage/recent")
def resource_recent_tool_usage() -> str:
    """Provides statistics on recent tool usage and failures."""
    if not _kb_repository:
        return json.dumps({"error": "Database not initialized"})

    try:
        # Get recent tool calls
        all_tool_calls = _kb_repository.get_nodes(node_type="ToolCall")
        all_tool_calls = [tc.to_dict() for tc in all_tool_calls]

        # Sort by timestamp and get recent 20
        all_tool_calls.sort(
            key=lambda x: x.get("properties", {}).get("timestamp", ""), reverse=True
        )
        recent_calls = all_tool_calls[:20]

        # Format for resource
        formatted = [
            {
                "tool_name": tc.get("properties", {}).get("tool_name"),
                "status": tc.get("properties", {}).get("status"),
                "timestamp": tc.get("properties", {}).get("timestamp"),
            }
            for tc in recent_calls
        ]

        return json.dumps(
            {"recent_calls": formatted, "count": len(formatted)}, indent=2
        )
    except Exception as e:
        logger.error("Error getting recent tool usage resource: %s", e)
        return json.dumps({"error": str(e)})


@mcp.resource("knowledge://plans")
def resource_plans() -> str:
    """Lists all available plan files from the plans/ directory."""
    try:
        plans_dir = Path("plans")
        if not plans_dir.exists():
            return json.dumps(
                {"plans": [], "count": 0, "note": "plans/ directory does not exist"},
                indent=2,
            )

        plan_files = list(plans_dir.glob("*.md"))
        plan_list = []

        for plan_file in sorted(
            plan_files, key=lambda p: p.stat().st_mtime, reverse=True
        ):
            try:
                # Read first few lines to get a preview
                with open(plan_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    # Try to extract title from first heading
                    title = plan_file.stem
                    for line in lines[:10]:
                        if line.startswith("#"):
                            title = line.lstrip("#").strip()
                            break
                    preview = "".join(lines[:3]).strip()[:200]

                plan_list.append(
                    {
                        "name": plan_file.name,
                        "title": title,
                        "preview": preview,
                        "modified": datetime.fromtimestamp(
                            plan_file.stat().st_mtime
                        ).isoformat(),
                        "size_bytes": plan_file.stat().st_size,
                    }
                )
            except Exception as e:
                logger.error("Error reading plan file %s: %s", plan_file, e)
                continue

        return json.dumps({"plans": plan_list, "count": len(plan_list)}, indent=2)
    except Exception as e:
        logger.error("Error getting plans resource: %s", e)
        return json.dumps({"error": str(e)})


# ============================================================================
# SECTION 7: SERVER ENTRY POINT
# ============================================================================


def _cleanup_graph():
    """Close database connection and clean up resources."""
    global _kb_repository  # pylint: disable=global-statement
    if _kb_repository:
        logger.debug("Closing database connection...")
        _db_manager.close()
        _kb_repository = None
        logger.debug("Database connection closed")


def main():
    """Run the FastMCP server."""
    import signal

    _load_graph()

    # Register cleanup handlers
    def signal_handler(signum, _frame):
        """Handle shutdown signals."""
        logger.info("Received signal %s, cleaning up...", signum)
        _cleanup_graph()
        # Re-raise to allow normal shutdown
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # FastMCP handles stdio transport and async runtime automatically
        mcp.run()
    finally:
        # Ensure cleanup happens even if server crashes
        _cleanup_graph()


if __name__ == "__main__":
    main()
