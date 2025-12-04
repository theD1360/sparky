"""Repository pattern for knowledge graph data access.

This module provides a clean interface for database operations, abstracting
the SQLAlchemy implementation details from the rest of the application.
"""

import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.orm.attributes import flag_modified

from .database import DatabaseManager
from .embeddings import EmbeddingManager
from .models import Edge, Node
from .opencypher.filter_evaluator import FilterEvaluator
from .opencypher.query_parser import QueryParser
from .opencypher.results_projector import ResultProjector
from .standards import normalize_edge_type, normalize_node_type

logger = logging.getLogger(__name__)


class KnowledgeRepository:
    """Repository for knowledge graph operations.

    Provides a clean interface for all database operations, maintaining
    compatibility with the existing GraphDatabase API while using SQLAlchemy.
    """

    def __init__(self, db_manager: DatabaseManager):
        """Initialize repository.

        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self.parser = QueryParser()
        self.evaluator = FilterEvaluator()
        self.projector = ResultProjector()

    def _get_json_property_query(self, property_key: str, operation: str = "=") -> str:
        """Generate database-agnostic JSON property query.

        Args:
            property_key: The JSON property key to query
            operation: SQL operation (=, LIKE, etc.)

        Returns:
            SQL fragment for JSON property query
        """
        is_postgres = self.db_manager.engine.dialect.name == "postgresql"
        if is_postgres:
            return f"properties->>'{property_key}' {operation} :value"
        else:
            return f"JSON_EXTRACT(properties, '$.{property_key}') {operation} :value"

    def _get_json_search_query(self, operation: str = "LIKE") -> str:
        """Generate database-agnostic JSON search query for entire properties field.

        Args:
            operation: SQL operation (LIKE, etc.)

        Returns:
            SQL fragment for JSON search query
        """
        is_postgres = self.db_manager.engine.dialect.name == "postgresql"
        if is_postgres:
            return f"properties::text {operation} :pattern"
        else:
            return f"JSON_EXTRACT(properties, '$') {operation} :pattern"

    async def query_graph(
        self, query: str, parameters: Optional[Dict] = None
    ) -> List[Dict]:
        """Execute a query against the knowledge graph using SQLAlchemy.

        Args:
            query: OpenCypher-style query string
            parameters: Optional parameters for parameterized queries

        Returns:
            List of results
        """
        ast = self.parser.parse(query)
        async with self.db_manager.get_session() as session:
            query_type = ast.get("type", "match")
            if query_type == "match":
                matches = await self._execute_sqlalchemy_query(session, ast["match"])
                if ast.get("where"):
                    matches = [
                        m for m in matches if self.evaluator.evaluate(ast["where"], m)
                    ]
                return self.projector.project(matches, ast["return"])
            elif query_type == "create":
                return await self._execute_create_operation(session, ast["create"])
            elif query_type == "update":
                return await self._execute_update_operation(
                    session, ast["update"], ast.get("where", [])
                )
            elif query_type == "delete":
                return await self._execute_delete_operation(
                    session, ast["delete"], ast.get("where", [])
                )
            else:
                raise ValueError(f"Unsupported query type: {query_type}")

    async def _execute_sqlalchemy_query(
        self, session: AsyncSession, match_pattern: Dict
    ) -> List[Dict]:
        """Execute SQLAlchemy query based on MATCH pattern.

        Args:
            session: SQLAlchemy async session
            match_pattern: Parsed MATCH pattern from QueryParser

        Returns:
            List of match dictionaries
        """
        if not match_pattern.get("nodes"):
            return []
        if len(match_pattern["nodes"]) == 1 and (not match_pattern.get("edges")):
            return await self._execute_simple_node_query(
                session, match_pattern["nodes"][0]
            )
        return await self._execute_complex_pattern_query(session, match_pattern)

    async def _execute_simple_node_query(
        self, session: AsyncSession, node_spec: Dict
    ) -> List[Dict]:
        """Execute a simple single-node query using SQLAlchemy."""
        stmt = select(Node)
        if "label" in node_spec:
            stmt = stmt.filter(Node.node_type == node_spec["label"])
        if "properties" in node_spec:
            for prop, value in node_spec["properties"].items():
                stmt = stmt.filter(
                    text(self._get_json_property_query(prop, "="))
                ).params(value=value)
        result = await session.execute(stmt)
        nodes = result.scalars().all()
        var_name = node_spec["var"]
        return [{var_name: {"id": node.id, **node.to_dict()}} for node in nodes]

    async def _execute_complex_pattern_query(
        self, session: AsyncSession, pattern: Dict
    ) -> List[Dict]:
        """Execute complex patterns with edges using SQLAlchemy."""
        first_node = pattern["nodes"][0]
        candidates = await self._execute_simple_node_query(session, first_node)
        if pattern.get("edges"):
            return await self._traverse_with_edges(session, pattern, candidates)
        return candidates

    async def _traverse_with_edges(
        self, session: AsyncSession, pattern: Dict, initial_matches: List[Dict]
    ) -> List[Dict]:
        """Traverse edges to extend matches using SQLAlchemy."""
        if len(pattern["nodes"]) < 2:
            return initial_matches
        results = []
        for match in initial_matches:
            source_var = pattern["nodes"][0]["var"]
            source_id = match[source_var]["id"]
            target_spec = pattern["nodes"][1]
            edge_spec = pattern["edges"][0]
            edge_type = edge_spec.get("type")
            stmt = (
                select(Edge, Node)
                .join(Node, Edge.target_id == Node.id)
                .filter(Edge.source_id == source_id)
            )
            if edge_type:
                stmt = stmt.filter(Edge.edge_type == edge_type)
            if target_spec.get("label"):
                stmt = stmt.filter(Node.node_type == target_spec["label"])
            if target_spec.get("properties"):
                for prop, value in target_spec["properties"].items():
                    stmt = stmt.filter(
                        text(self._get_json_property_query(prop, "="))
                    ).params(value=value)
            result = await session.execute(stmt)
            neighbors = result.all()
            for edge, target_node in neighbors:
                new_match = match.copy()
                new_match[target_spec["var"]] = {
                    "id": target_node.id,
                    **target_node.to_dict(),
                }
                results.append(new_match)
        return results

    async def _execute_create_operation(
        self, session: AsyncSession, create_spec: Dict
    ) -> List[Dict]:
        """Execute CREATE operation.

        Args:
            session: SQLAlchemy session
            create_spec: Parsed CREATE specification

        Returns:
            List of created objects
        """
        results = []
        for node_spec in create_spec.get("nodes", []):
            var = node_spec["var"]
            label = node_spec.get("label", "Node")
            properties = node_spec.get("properties", {})
            node_id = f"{var}_{self._generate_id()}"
            node = Node(
                id=node_id,
                node_type=label,
                label=properties.get("name", var),
                content=properties.get("content"),
                properties=properties,
            )
            session.add(node)
            await session.commit()
            results.append({var: {"id": node_id, **node.to_dict()}})
            logger.info(f"Created node {node_id} of type {label}")
        for edge_spec in create_spec.get("edges", []):
            edge_type = edge_spec["type"]
            var = edge_spec.get("var")
            if len(results) >= 2:
                source_var = create_spec["nodes"][0]["var"]
                target_var = create_spec["nodes"][1]["var"]
                source_id = results[0][source_var]["id"]
                target_id = results[1][target_var]["id"]
                edge = Edge(
                    source_id=source_id,
                    target_id=target_id,
                    edge_type=edge_type,
                    properties={},
                )
                session.add(edge)
                await session.commit()
                if var:
                    results.append({var: edge.to_dict()})
                logger.info(f"Created edge {source_id} -> {target_id}")
        return results

    async def _execute_update_operation(
        self, session: AsyncSession, update_spec: Dict, where_conditions: List
    ) -> List[Dict]:
        """Execute UPDATE operation.

        Args:
            session: SQLAlchemy session
            update_spec: Parsed UPDATE specification
            where_conditions: WHERE conditions to filter nodes

        Returns:
            List of updated objects
        """
        var = update_spec["variable"]
        properties = update_spec["properties"]
        stmt = select(Node)
        for condition in where_conditions:
            if condition["type"] == "equals":
                if condition["property"] == "id":
                    stmt = stmt.filter(Node.id == condition["value"])
                else:
                    stmt = stmt.filter(
                        text(self._get_json_property_query(condition["property"], "="))
                    ).params(value=condition["value"])
            elif condition["type"] == "starts_with":
                stmt = stmt.filter(
                    text(self._get_json_property_query(condition["property"], "LIKE"))
                ).params(value=f"{condition['value']}%")
        result = await session.execute(stmt)
        nodes_to_update = result.scalars().all()
        results = []
        for node in nodes_to_update:
            if node.properties is None:
                node.properties = {}
            for key, value in properties.items():
                node.properties[key] = value
            node.updated_at = datetime.now(timezone.utc)
            await session.commit()
            results.append({var: {"id": node.id, **node.to_dict()}})
            logger.info(f"Updated node {node.id}")
        return results

    async def _execute_delete_operation(
        self, session: AsyncSession, delete_spec: Dict, where_conditions: List
    ) -> List[Dict]:
        """Execute DELETE operation.

        Args:
            session: SQLAlchemy session
            delete_spec: Parsed DELETE specification
            where_conditions: WHERE conditions to filter nodes

        Returns:
            List of deleted objects
        """
        variables = delete_spec["variables"]
        results = []
        for var in variables:
            stmt = select(Node)
            for condition in where_conditions:
                if condition["type"] == "equals":
                    if condition["property"] == "id":
                        stmt = stmt.filter(Node.id == condition["value"])
                    else:
                        stmt = stmt.filter(
                            text(
                                self._get_json_property_query(
                                    condition["property"], "="
                                )
                            )
                        ).params(value=condition["value"])
                elif condition["type"] == "starts_with":
                    stmt = stmt.filter(
                        text(
                            self._get_json_property_query(condition["property"], "LIKE")
                        )
                    ).params(value=f"{condition['value']}%")
            result = await session.execute(stmt)
            nodes_to_delete = result.scalars().all()
            for node in nodes_to_delete:
                # Delete related edges
                delete_stmt = delete(Edge).filter(
                    or_(Edge.source_id == node.id, Edge.target_id == node.id)
                )
                await session.execute(delete_stmt)
                results.append({var: {"id": node.id, **node.to_dict()}})
                await session.delete(node)
                await session.commit()
                logger.info(f"Deleted node {node.id}")
        return results

    def _generate_id(self) -> str:
        """Generate a unique ID for new nodes."""
        import uuid

        return str(uuid.uuid4())[:8]

    async def _generate_and_store_embedding(
        self, session: AsyncSession, node: Node, rowid: Optional[int] = None
    ) -> None:
        """Generate and store embedding for a node.

        Args:
            session: Database session
            node: Node instance
            rowid: SQLite rowid of the node (not used for PostgreSQL)
        """
        try:
            is_postgres = self.db_manager.engine.dialect.name == "postgresql"
            text_parts = [node.node_type or "", node.label or ""]
            if node.content:
                text_parts.append(node.content)
            combined_text = " ".join(filter(None, text_parts))
            if not combined_text.strip():
                logger.debug(f"Skipping embedding for empty node {node.id}")
                return
            MAX_EMBEDDING_BYTES = 30000
            combined_text_bytes = combined_text.encode("utf-8")
            if len(combined_text_bytes) > MAX_EMBEDDING_BYTES:
                logger.warning(
                    f"Node {node.id} content too large ({len(combined_text_bytes)} bytes), truncating to {MAX_EMBEDDING_BYTES} bytes for embedding"
                )
                truncated_bytes = combined_text_bytes[:MAX_EMBEDDING_BYTES]
                combined_text = truncated_bytes.decode("utf-8", errors="ignore")
                combined_text += "..."
            embedding_manager = EmbeddingManager.get_instance()
            embedding = embedding_manager.embed_text(combined_text)
            if not embedding or all((v == 0.0 for v in embedding)):
                logger.warning(f"Generated empty/zero embedding for node {node.id}")
                return
            if is_postgres:
                embedding_str = "[" + ",".join(map(str, embedding)) + "]"
                escaped_id = node.id.replace("'", "''")
                update_query = f"UPDATE nodes SET embedding = '{embedding_str}'::vector WHERE id = '{escaped_id}'"
                await session.execute(text(update_query))
            else:
                await session.execute(
                    text("DELETE FROM nodes_vec WHERE rowid = :rowid"), {"rowid": rowid}
                )
                await session.execute(
                    text(
                        "INSERT INTO nodes_vec(rowid, embedding) VALUES (:rowid, json(:embedding))"
                    ),
                    {"rowid": rowid, "embedding": json.dumps(embedding)},
                )
            logger.debug(f"Generated and stored embedding for node {node.id}")
        except Exception as e:
            logger.warning(f"Failed to generate embedding for node {node.id}: {e}")

    async def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        content: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Node:
        """Add or update a node in the knowledge graph.

        Args:
            node_id: Unique identifier for the node
            node_type: Type of the node (e.g., 'Memory', 'Concept')
            label: Human-readable label
            content: Optional text content
            properties: Optional metadata dictionary

        Returns:
            The created or updated Node instance
        """
        node_type = normalize_node_type(node_type)
        async with self.db_manager.get_session() as session:
            stmt = select(Node).filter(Node.id == node_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.node_type = node_type
                existing.label = label
                existing.content = content
                existing.properties = properties or {}
                existing.updated_at = datetime.now(timezone.utc)
                await session.commit()
                is_postgres = self.db_manager.engine.dialect.name == "postgresql"
                if not is_postgres:
                    await session.refresh(existing)
                    rowid_result = await session.execute(
                        text("SELECT rowid FROM nodes WHERE id = :node_id"),
                        {"node_id": node_id},
                    )
                    rowid_row = rowid_result.fetchone()
                    if rowid_row:
                        await self._generate_and_store_embedding(
                            session, existing, rowid_row[0]
                        )
                else:
                    await self._generate_and_store_embedding(session, existing)
                await session.commit()
                await session.refresh(existing)
                session.expunge(existing)
                logger.info(f"Updated node {node_id}")
                return existing
            else:
                node = Node(
                    id=node_id,
                    node_type=node_type,
                    label=label,
                    content=content,
                    properties=properties or {},
                )
                session.add(node)
                try:
                    await session.flush()
                except IntegrityError:
                    # Race condition: node was inserted by another process
                    # Roll back and fetch the existing node
                    await session.rollback()
                    stmt = select(Node).filter(Node.id == node_id)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                    if existing:
                        # Update the existing node
                        existing.node_type = node_type
                        existing.label = label
                        existing.content = content
                        existing.properties = properties or {}
                        existing.updated_at = datetime.now(timezone.utc)
                        await session.commit()
                        is_postgres = (
                            self.db_manager.engine.dialect.name == "postgresql"
                        )
                        if not is_postgres:
                            await session.refresh(existing)
                            rowid_result = await session.execute(
                                text("SELECT rowid FROM nodes WHERE id = :node_id"),
                                {"node_id": node_id},
                            )
                            rowid_row = rowid_result.fetchone()
                            if rowid_row:
                                await self._generate_and_store_embedding(
                                    session, existing, rowid_row[0]
                                )
                        else:
                            await self._generate_and_store_embedding(session, existing)
                        await session.commit()
                        await session.refresh(existing)
                        session.expunge(existing)
                        logger.info(f"Updated node {node_id} (race condition handled)")
                        return existing
                    else:
                        # Should not happen, but re-raise if it does
                        raise
                is_postgres = self.db_manager.engine.dialect.name == "postgresql"
                if not is_postgres:
                    rowid_result = await session.execute(
                        text("SELECT rowid FROM nodes WHERE id = :node_id"),
                        {"node_id": node_id},
                    )
                    rowid_row = rowid_result.fetchone()
                    if rowid_row:
                        await self._generate_and_store_embedding(
                            session, node, rowid_row[0]
                        )
                else:
                    await self._generate_and_store_embedding(session, node)
                await session.commit()
                await session.refresh(node)
                session.expunge(node)
                logger.info(f"Created node {node_id}")
                return node

    async def bulk_add_nodes(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add or update multiple nodes in a single transaction.

        Args:
            nodes: List of node dictionaries, each containing:
                - node_id: Unique identifier for the node
                - node_type: Type of the node (e.g., 'Memory', 'Concept')
                - label: Human-readable label
                - content: Optional text content
                - properties: Optional metadata dictionary

        Returns:
            Dictionary with:
                - added: List of node IDs that were created
                - updated: List of node IDs that were updated
                - failed: List of dicts with node_id and error message
                - total: Total number of nodes processed
        """
        added = []
        updated = []
        failed = []
        async with self.db_manager.get_session() as session:
            is_postgres = self.db_manager.engine.dialect.name == "postgresql"
            for node_data in nodes:
                try:
                    node_id = node_data.get("node_id")
                    node_type = node_data.get("node_type")
                    label = node_data.get("label")
                    content = node_data.get("content")
                    properties = node_data.get("properties", {})
                    if not node_id or not node_type or (not label):
                        failed.append(
                            {
                                "node_id": node_id or "unknown",
                                "error": "Missing required fields: node_id, node_type, or label",
                            }
                        )
                        continue
                    node_type = normalize_node_type(node_type)
                    stmt = select(Node).filter(Node.id == node_id)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                    if existing:
                        existing.node_type = node_type
                        existing.label = label
                        existing.content = content
                        existing.properties = properties
                        existing.updated_at = datetime.now(timezone.utc)
                        await session.flush()
                        if not is_postgres:
                            rowid_result = await session.execute(
                                text("SELECT rowid FROM nodes WHERE id = :node_id"),
                                {"node_id": node_id},
                            )
                            rowid_row = rowid_result.fetchone()
                            if rowid_row:
                                await self._generate_and_store_embedding(
                                    session, existing, rowid_row[0]
                                )
                        else:
                            await self._generate_and_store_embedding(session, existing)
                        updated.append(node_id)
                    else:
                        node = Node(
                            id=node_id,
                            node_type=node_type,
                            label=label,
                            content=content,
                            properties=properties,
                        )
                        session.add(node)
                        await session.flush()
                        if not is_postgres:
                            rowid_result = await session.execute(
                                text("SELECT rowid FROM nodes WHERE id = :node_id"),
                                {"node_id": node_id},
                            )
                            rowid_row = rowid_result.fetchone()
                            if rowid_row:
                                await self._generate_and_store_embedding(
                                    session, node, rowid_row[0]
                                )
                        else:
                            await self._generate_and_store_embedding(session, node)
                        added.append(node_id)
                except Exception as e:
                    logger.error(
                        f"Error adding/updating node {node_data.get('node_id', 'unknown')}: {e}"
                    )
                    failed.append(
                        {
                            "node_id": node_data.get("node_id", "unknown"),
                            "error": str(e),
                        }
                    )
            await session.commit()
        logger.info(
            f"Bulk add nodes: {len(added)} added, {len(updated)} updated, {len(failed)} failed"
        )
        return {
            "added": added,
            "updated": updated,
            "failed": failed,
            "total": len(nodes),
        }

    async def update_node(
        self,
        node_id: str,
        node_type: Optional[str] = None,
        label: Optional[str] = None,
        content: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Node:
        """Update an existing node in the knowledge graph.

        Unlike add_node which creates or updates, this method only updates existing nodes
        and raises an error if the node doesn't exist. This is useful when you want to
        ensure you're modifying an existing node rather than accidentally creating a new one.

        Args:
            node_id: Unique identifier for the node to update
            node_type: New type for the node (optional, keeps existing if not provided)
            label: New label (optional, keeps existing if not provided)
            content: New content (optional, keeps existing if not provided)
            properties: New properties (optional, keeps existing if not provided)

        Returns:
            The updated Node instance

        Raises:
            ValueError: If the node doesn't exist
        """
        async with self.db_manager.get_session() as session:
            stmt = select(Node).filter(Node.id == node_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                raise ValueError(f"Node {node_id} not found")
            if node_type is not None:
                existing.node_type = normalize_node_type(node_type)
            if label is not None:
                existing.label = label
            if content is not None:
                existing.content = content
            if properties is not None:
                existing.properties = properties
            existing.updated_at = datetime.now(timezone.utc)
            await session.flush()
            is_postgres = self.db_manager.engine.dialect.name == "postgresql"
            if not is_postgres:
                rowid_result = session.execute(
                    text("SELECT rowid FROM nodes WHERE id = :node_id"),
                    {"node_id": node_id},
                ).fetchone()
                if rowid_result:
                    await self._generate_and_store_embedding(
                        session, existing, rowid_result[0]
                    )
            else:
                await self._generate_and_store_embedding(session, existing)
            await session.flush()
            await session.refresh(existing)
            session.expunge(existing)
            logger.info(f"Updated node {node_id}")
            return existing

    async def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by its ID.

        The node is properly detached from the session before returning to prevent
        "Instance is not present in this Session" errors. All scalar attributes
        (id, node_type, label, content, properties, timestamps) are loaded and
        accessible after the node is returned.

        Note: Relationships (outgoing_edges, incoming_edges) are not loaded and
        should not be accessed on the returned node. Use get_node_neighbors() or
        get_edges() methods instead.

        Args:
            node_id: Unique identifier of the node

        Returns:
            Node instance if found, None otherwise. The node is detached from the
            session and safe to use outside the session context.
        """
        async with self.db_manager.get_session() as session:
            stmt = select(Node).filter(Node.id == node_id)
            result = await session.execute(stmt)
            node = result.scalar_one_or_none()
            if node:
                # Refresh to ensure all attributes are loaded from the database
                await session.refresh(node)
                # Access properties to ensure they're loaded (JSON fields may be lazy)
                _ = node.properties
                # Expunge to detach from session and prevent session errors
                session.expunge(node)
            return node

    async def get_nodes(
        self,
        node_type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Node]:
        """Get nodes with optional filtering.

        Args:
            node_type: Filter by node type
            limit: Maximum number of nodes to return
            offset: Number of nodes to skip

        Returns:
            List of Node instances
        """
        async with self.db_manager.get_session() as session:
            stmt = select(Node)
            if node_type:
                stmt = stmt.filter(Node.node_type == node_type)
            stmt = stmt.order_by(Node.created_at)
            if offset:
                stmt = stmt.offset(offset)
            if limit:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            nodes = result.scalars().all()
            for node in nodes:
                await session.refresh(node)
                session.expunge(node)
            return nodes

    async def get_nodes_count(self, node_type: Optional[str] = None) -> int:
        """Get count of nodes with optional filtering.

        Args:
            node_type: Filter by node type

        Returns:
            Count of matching nodes
        """
        async with self.db_manager.get_session() as session:
            stmt = select(func.count(Node.id))
            if node_type:
                stmt = stmt.filter(Node.node_type == node_type)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Edge:
        """Add an edge between two nodes.

        Args:
            source_id: ID of the source node
            target_id: ID of the target node
            edge_type: Type of relationship
            properties: Optional metadata dictionary

        Returns:
            The created Edge instance

        Raises:
            ValueError: If source or target node doesn't exist
        """
        edge_type = normalize_edge_type(edge_type)
        async with self.db_manager.get_session() as session:
            stmt = select(Node).filter(Node.id == source_id)
            result = await session.execute(stmt)
            source = result.scalar_one_or_none()
            stmt = select(Node).filter(Node.id == target_id)
            result = await session.execute(stmt)
            target = result.scalar_one_or_none()
            if not source:
                raise ValueError(f"Source node {source_id} not found")
            if not target:
                raise ValueError(f"Target node {target_id} not found")
            stmt = select(Edge).filter(
                and_(
                    Edge.source_id == source_id,
                    Edge.target_id == target_id,
                    Edge.edge_type == edge_type,
                )
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.properties = properties or {}
                await session.commit()
                logger.info(f"Updated edge {source_id} -> {target_id}")
                return existing
            else:
                edge = Edge(
                    source_id=source_id,
                    target_id=target_id,
                    edge_type=edge_type,
                    properties=properties or {},
                )
                session.add(edge)
                await session.commit()
                logger.info(f"Created edge {source_id} -> {target_id}")
                return edge

    async def bulk_add_edges(self, edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add or update multiple edges in a single transaction.

        Args:
            edges: List of edge dictionaries, each containing:
                - source_id: ID of the source node
                - target_id: ID of the target node
                - edge_type: Type of relationship
                - properties: Optional metadata dictionary

        Returns:
            Dictionary with:
                - added: List of edge descriptions (source_id -> target_id) that were created
                - updated: List of edge descriptions that were updated
                - failed: List of dicts with edge info and error message
                - total: Total number of edges processed
        """
        added = []
        updated = []
        failed = []
        async with self.db_manager.get_session() as session:
            all_node_ids = set()
            for edge_data in edges:
                source_id = edge_data.get("source_id")
                target_id = edge_data.get("target_id")
                if source_id:
                    all_node_ids.add(source_id)
                if target_id:
                    all_node_ids.add(target_id)
            existing_nodes = (
                session.query(Node.id).filter(Node.id.in_(all_node_ids)).all()
                if all_node_ids
                else []
            )
            existing_node_ids = {node.id for node in existing_nodes}
            for edge_data in edges:
                try:
                    source_id = edge_data.get("source_id")
                    target_id = edge_data.get("target_id")
                    edge_type = edge_data.get("edge_type")
                    properties = edge_data.get("properties", {})
                    if not source_id or not target_id or (not edge_type):
                        failed.append(
                            {
                                "edge": f"{source_id} -> {target_id}",
                                "error": "Missing required fields: source_id, target_id, or edge_type",
                            }
                        )
                        continue
                    if source_id not in existing_node_ids:
                        failed.append(
                            {
                                "edge": f"{source_id} -> {target_id}",
                                "error": f"Source node {source_id} not found",
                            }
                        )
                        continue
                    if target_id not in existing_node_ids:
                        failed.append(
                            {
                                "edge": f"{source_id} -> {target_id}",
                                "error": f"Target node {target_id} not found",
                            }
                        )
                        continue
                    edge_type = normalize_edge_type(edge_type)
                    existing = (
                        session.query(Edge)
                        .filter(
                            and_(
                                Edge.source_id == source_id,
                                Edge.target_id == target_id,
                                Edge.edge_type == edge_type,
                            )
                        )
                        .first()
                    )
                    edge_desc = f"{source_id} -> {target_id} ({edge_type})"
                    if existing:
                        existing.properties = properties
                        updated.append(edge_desc)
                    else:
                        edge = Edge(
                            source_id=source_id,
                            target_id=target_id,
                            edge_type=edge_type,
                            properties=properties,
                        )
                        session.add(edge)
                        added.append(edge_desc)
                except Exception as e:
                    logger.error(
                        f"Error adding/updating edge {edge_data.get('source_id', '?')} -> {edge_data.get('target_id', '?')}: {e}"
                    )
                    failed.append(
                        {
                            "edge": f"{edge_data.get('source_id', '?')} -> {edge_data.get('target_id', '?')}",
                            "error": str(e),
                        }
                    )
            await session.commit()
        logger.info(
            f"Bulk add edges: {len(added)} added, {len(updated)} updated, {len(failed)} failed"
        )
        return {
            "added": added,
            "updated": updated,
            "failed": failed,
            "total": len(edges),
        }

    async def append_graph(
        self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Append a subgraph (nodes and edges) to the knowledge graph in a single operation.

        This is a convenience method that combines bulk_add_nodes and bulk_add_edges
        into a single atomic operation. It's useful when you have a complete subgraph
        (collection of related nodes and edges) that you want to merge into the
        knowledge graph all at once.

        The operation is performed in a single transaction: nodes are added first,
        then edges. If any individual node or edge fails, it's recorded in the
        failures list, but other items continue to be processed.

        Args:
            nodes: List of node dictionaries (same format as bulk_add_nodes)
            edges: List of edge dictionaries (same format as bulk_add_edges)

        Returns:
            Dictionary with:
                - nodes_added: List of node IDs that were created
                - nodes_updated: List of node IDs that were updated
                - nodes_failed: List of node failures
                - edges_added: List of edge descriptions that were created
                - edges_updated: List of edge descriptions that were updated
                - edges_failed: List of edge failures
                - total_nodes: Total number of nodes processed
                - total_edges: Total number of edges processed
        """
        node_result = await self.bulk_add_nodes(nodes)
        edge_result = await self.bulk_add_edges(edges)
        logger.info(
            f"Append graph: nodes ({len(node_result['added'])} added, {len(node_result['updated'])} updated, {len(node_result['failed'])} failed), edges ({len(edge_result['added'])} added, {len(edge_result['updated'])} updated, {len(edge_result['failed'])} failed)"
        )
        return {
            "nodes_added": node_result["added"],
            "nodes_updated": node_result["updated"],
            "nodes_failed": node_result["failed"],
            "edges_added": edge_result["added"],
            "edges_updated": edge_result["updated"],
            "edges_failed": edge_result["failed"],
            "total_nodes": node_result["total"],
            "total_edges": edge_result["total"],
        }

    async def find_similar_nodes(
        self,
        node_id: str,
        similarity_threshold: float = 0.7,
        limit: int = 20,
        include_self: bool = False,
    ) -> List[Dict[str, Any]]:
        """Find nodes similar to a given node using embedding similarity.

        Args:
            node_id: ID of the reference node
            similarity_threshold: Minimum cosine similarity (0-1)
            limit: Maximum number of similar nodes to return
            include_self: Whether to include the reference node in results

        Returns:
            List of dictionaries with node data and similarity scores

        Raises:
            ValueError: If node doesn't exist or has no embedding
        """
        async with self.db_manager.get_session() as session:
            ref_node = session.query(Node).filter(Node.id == node_id).first()
            if not ref_node:
                raise ValueError(f"Node {node_id} not found")
            is_postgres = self.db_manager.engine.dialect.name == "postgresql"
            if is_postgres:
                if not hasattr(ref_node, "embedding") or ref_node.embedding is None:
                    raise ValueError(f"Node {node_id} has no embedding")
                embedding_array = "[" + ",".join(map(str, ref_node.embedding)) + "]"
                base_query = "\n                    SELECT \n                        n.id,\n                        n.node_type,\n                        n.label,\n                        n.content,\n                        n.properties,\n                        n.created_at,\n                        n.updated_at,\n                        1 - (n.embedding <=> %s::vector) as similarity\n                    FROM nodes n\n                    WHERE n.embedding IS NOT NULL\n                        AND 1 - (n.embedding <=> %s::vector) >= %s\n                "
                if not include_self:
                    base_query += " AND n.id != %s"
                base_query += " ORDER BY n.embedding <=> %s::vector LIMIT %s"
                conn = session.connection()
                dbapi_conn = conn.connection
                cursor = dbapi_conn.cursor()
                params = [embedding_array, embedding_array, similarity_threshold]
                if not include_self:
                    params.append(node_id)
                params.extend([embedding_array, limit])
                cursor.execute(base_query, params)
                results = cursor.fetchall()
                cursor.close()
                similar_nodes = []
                for row in results:
                    similar_nodes.append(
                        {
                            "id": row[0],
                            "type": row[1],
                            "label": row[2],
                            "content": row[3],
                            "properties": row[4],
                            "created_at": row[5].isoformat() if row[5] else None,
                            "updated_at": row[6].isoformat() if row[6] else None,
                            "similarity": float(row[7]),
                        }
                    )
            else:
                rowid_result = session.execute(
                    text("SELECT rowid FROM nodes WHERE id = :node_id"),
                    {"node_id": node_id},
                ).fetchone()
                if not rowid_result:
                    raise ValueError(f"Node {node_id} not found")
                ref_rowid = rowid_result[0]
                vec_result = session.execute(
                    text("SELECT embedding FROM nodes_vec WHERE rowid = :rowid"),
                    {"rowid": ref_rowid},
                ).fetchone()
                if not vec_result:
                    raise ValueError(f"Node {node_id} has no embedding")
                query_sql = "\n                    SELECT \n                        n.id,\n                        n.node_type,\n                        n.label,\n                        n.content,\n                        n.properties,\n                        n.created_at,\n                        n.updated_at,\n                        1 - vec_distance_cosine(nv.embedding, ref_vec.embedding) as similarity\n                    FROM nodes n\n                    JOIN nodes_vec nv ON nv.rowid = n.rowid\n                    CROSS JOIN nodes_vec ref_vec\n                    WHERE ref_vec.rowid = :ref_rowid\n                        AND 1 - vec_distance_cosine(nv.embedding, ref_vec.embedding) >= :threshold\n                "
                if not include_self:
                    query_sql += " AND n.id != :node_id"
                query_sql += " ORDER BY vec_distance_cosine(nv.embedding, ref_vec.embedding) LIMIT :limit"
                params = {
                    "ref_rowid": ref_rowid,
                    "threshold": similarity_threshold,
                    "limit": limit,
                }
                if not include_self:
                    params["node_id"] = node_id
                results = session.execute(text(query_sql), params).fetchall()
                similar_nodes = []
                for row in results:
                    similar_nodes.append(
                        {
                            "id": row[0],
                            "type": row[1],
                            "label": row[2],
                            "content": row[3],
                            "properties": row[4],
                            "created_at": row[5].isoformat() if row[5] else None,
                            "updated_at": row[6].isoformat() if row[6] else None,
                            "similarity": float(row[7]),
                        }
                    )
            logger.info(f"Found {len(similar_nodes)} similar nodes to {node_id}")
            return similar_nodes

    async def validate_graph_integrity(
        self, checks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run integrity checks on the graph to detect issues.

        Args:
            checks: List of checks to run. If None, runs all checks.
                Available checks:
                - orphaned_nodes: Nodes with no edges
                - dangling_edges: Edges referencing non-existent nodes
                - missing_embeddings: Nodes without vector embeddings
                - duplicate_edges: Duplicate edge relationships
                - self_loops: Edges from a node to itself

        Returns:
            Dictionary with check results and issue counts
        """
        if checks is None:
            checks = [
                "orphaned_nodes",
                "dangling_edges",
                "missing_embeddings",
                "duplicate_edges",
                "self_loops",
            ]
        results = {
            "checks_run": checks,
            "issues_found": {},
            "total_issues": 0,
            "healthy": True,
        }
        async with self.db_manager.get_session() as session:
            is_postgres = self.db_manager.engine.dialect.name == "postgresql"
            if "orphaned_nodes" in checks:
                orphan_query = "\n                    SELECT n.id, n.node_type, n.label\n                    FROM nodes n\n                    WHERE NOT EXISTS (\n                        SELECT 1 FROM edges e WHERE e.source_id = n.id OR e.target_id = n.id\n                    )\n                    AND n.node_type NOT IN ('Memory', 'Session', 'ThinkingPattern', 'Workflow')\n                "
                orphaned = session.execute(text(orphan_query)).fetchall()
                if orphaned:
                    results["issues_found"]["orphaned_nodes"] = [
                        {"id": row[0], "type": row[1], "label": row[2]}
                        for row in orphaned
                    ]
                    results["total_issues"] += len(orphaned)
                    results["healthy"] = False
            if "dangling_edges" in checks:
                dangling_query = "\n                    SELECT e.id, e.source_id, e.target_id, e.edge_type\n                    FROM edges e\n                    WHERE NOT EXISTS (SELECT 1 FROM nodes n WHERE n.id = e.source_id)\n                       OR NOT EXISTS (SELECT 1 FROM nodes n WHERE n.id = e.target_id)\n                "
                dangling = session.execute(text(dangling_query)).fetchall()
                if dangling:
                    results["issues_found"]["dangling_edges"] = [
                        {
                            "edge_id": row[0],
                            "source_id": row[1],
                            "target_id": row[2],
                            "edge_type": row[3],
                        }
                        for row in dangling
                    ]
                    results["total_issues"] += len(dangling)
                    results["healthy"] = False
            if "missing_embeddings" in checks:
                if is_postgres:
                    missing_emb_query = "\n                        SELECT id, node_type, label\n                        FROM nodes\n                        WHERE embedding IS NULL\n                        AND node_type NOT IN ('Session', 'ToolCall', 'Message')\n                        LIMIT 100\n                    "
                else:
                    missing_emb_query = "\n                        SELECT n.id, n.node_type, n.label\n                        FROM nodes n\n                        WHERE n.rowid NOT IN (SELECT rowid FROM nodes_vec)\n                        AND n.node_type NOT IN ('Session', 'ToolCall', 'Message')\n                        LIMIT 100\n                    "
                missing_emb = session.execute(text(missing_emb_query)).fetchall()
                if missing_emb:
                    results["issues_found"]["missing_embeddings"] = [
                        {"id": row[0], "type": row[1], "label": row[2]}
                        for row in missing_emb
                    ]
                    results["total_issues"] += len(missing_emb)
            if "duplicate_edges" in checks:
                dup_edges_query = "\n                    SELECT source_id, target_id, edge_type, COUNT(*) as count\n                    FROM edges\n                    GROUP BY source_id, target_id, edge_type\n                    HAVING COUNT(*) > 1\n                "
                duplicates = session.execute(text(dup_edges_query)).fetchall()
                if duplicates:
                    results["issues_found"]["duplicate_edges"] = [
                        {
                            "source_id": row[0],
                            "target_id": row[1],
                            "edge_type": row[2],
                            "count": row[3],
                        }
                        for row in duplicates
                    ]
                    results["total_issues"] += len(duplicates)
                    results["healthy"] = False
            if "self_loops" in checks:
                self_loop_query = "\n                    SELECT id, source_id, edge_type\n                    FROM edges\n                    WHERE source_id = target_id\n                "
                self_loops = session.execute(text(self_loop_query)).fetchall()
                if self_loops:
                    results["issues_found"]["self_loops"] = [
                        {"edge_id": row[0], "node_id": row[1], "edge_type": row[2]}
                        for row in self_loops
                    ]
                    results["total_issues"] += len(self_loops)
        logger.info(
            f"Graph integrity check complete: {results['total_issues']} issues found, healthy={results['healthy']}"
        )
        return results

    async def extract_subgraph(
        self,
        root_node_ids: List[str],
        depth: int = 2,
        include_node_types: Optional[List[str]] = None,
        export_format: str = "json",
    ) -> Dict[str, Any]:
        """Extract a subgraph around specified root nodes.

        Args:
            root_node_ids: List of node IDs to use as starting points
            depth: How many hops to traverse from root nodes
            include_node_types: Optional list of node types to include
            export_format: Format for export (json, cypher, graphml)

        Returns:
            Dictionary with nodes, edges, and formatted export
        """
        async with self.db_manager.get_session() as session:
            visited_nodes = set()
            all_nodes = []
            all_edges = []
            queue = deque([(node_id, 0) for node_id in root_node_ids])
            visited = set(root_node_ids)
            while queue:
                current_id, current_depth = queue.popleft()
                node = session.query(Node).filter(Node.id == current_id).first()
                if not node:
                    continue
                if include_node_types and node.node_type not in include_node_types:
                    continue
                visited_nodes.add(current_id)
                all_nodes.append(node)
                if current_depth >= depth:
                    continue
                edges = (
                    session.query(Edge)
                    .filter(
                        or_(Edge.source_id == current_id, Edge.target_id == current_id)
                    )
                    .all()
                )
                for edge in edges:
                    if (
                        edge.source_id in visited_nodes
                        or edge.target_id in visited_nodes
                    ):
                        if edge not in all_edges:
                            all_edges.append(edge)
                    other_id = (
                        edge.target_id
                        if edge.source_id == current_id
                        else edge.source_id
                    )
                    if other_id not in visited:
                        visited.add(other_id)
                        queue.append((other_id, current_depth + 1))
            nodes_data = [node.to_dict() for node in all_nodes]
            edges_data = [
                {
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "edge_type": edge.edge_type,
                    "properties": edge.properties,
                }
                for edge in all_edges
            ]
            result = {
                "nodes": nodes_data,
                "edges": edges_data,
                "stats": {
                    "node_count": len(nodes_data),
                    "edge_count": len(edges_data),
                    "depth": depth,
                },
            }
            if export_format == "json":
                result["export"] = json.dumps(
                    {"nodes": nodes_data, "edges": edges_data}, indent=2
                )
            elif export_format == "cypher":
                cypher_statements = []
                for node in nodes_data:
                    props = json.dumps(node.get("properties", {}))
                    cypher_statements.append(
                        f"CREATE (n:{node['type']} {{id: '{node['id']}', label: '{node['label']}', properties: {props}}})"
                    )
                for edge in edges_data:
                    cypher_statements.append(
                        f"MATCH (a {{id: '{edge['source_id']}'}}), (b {{id: '{edge['target_id']}'}}) CREATE (a)-[:{edge['edge_type']}]->(b)"
                    )
                result["export"] = "\n".join(cypher_statements)
            elif export_format == "graphml":
                graphml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
                graphml_parts.append(
                    '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
                )
                graphml_parts.append('  <graph id="G" edgedefault="directed">')
                for node in nodes_data:
                    graphml_parts.append(
                        f"""    <node id="{node['id']}"><data key="label">{node['label']}</data><data key="type">{node['type']}</data></node>"""
                    )
                for i, edge in enumerate(edges_data):
                    graphml_parts.append(
                        f"""    <edge id="e{i}" source="{edge['source_id']}" target="{edge['target_id']}"><data key="type">{edge['edge_type']}</data></edge>"""
                    )
                graphml_parts.append("  </graph>")
                graphml_parts.append("</graphml>")
                result["export"] = "\n".join(graphml_parts)
            logger.info(
                f"Extracted subgraph: {len(nodes_data)} nodes, {len(edges_data)} edges"
            )
            return result

    async def merge_duplicate_nodes(
        self, node_ids: List[str], keep_node_id: str, merge_strategy: str = "union"
    ) -> Dict[str, Any]:
        """Merge duplicate nodes into a single node.

        Args:
            node_ids: List of node IDs to merge (including keep_node_id)
            keep_node_id: ID of the node to keep
            merge_strategy: How to merge properties:
                - union: Combine all properties
                - keep: Keep only properties from keep_node
                - prefer_newer: Use properties from most recently updated node

        Returns:
            Dictionary with merge results and updated node
        """
        if keep_node_id not in node_ids:
            raise ValueError(f"keep_node_id {keep_node_id} must be in node_ids list")
        if len(node_ids) < 2:
            raise ValueError("Need at least 2 nodes to merge")
        async with self.db_manager.get_session() as session:
            nodes = session.query(Node).filter(Node.id.in_(node_ids)).all()
            if len(nodes) != len(node_ids):
                found_ids = {n.id for n in nodes}
                missing = set(node_ids) - found_ids
                raise ValueError(f"Some nodes not found: {missing}")
            keep_node = next((n for n in nodes if n.id == keep_node_id))
            merge_nodes = [n for n in nodes if n.id != keep_node_id]
            merged_props = keep_node.properties.copy() if keep_node.properties else {}
            if merge_strategy == "union":
                for node in merge_nodes:
                    if node.properties:
                        merged_props.update(node.properties)
            elif merge_strategy == "prefer_newer":
                all_nodes_sorted = sorted(
                    nodes, key=lambda n: n.updated_at, reverse=True
                )
                for node in reversed(all_nodes_sorted):
                    if node.properties:
                        merged_props.update(node.properties)
            keep_node.properties = merged_props
            keep_node.updated_at = datetime.now(timezone.utc)
            edges_updated = 0
            for merge_node in merge_nodes:
                outgoing = (
                    session.query(Edge).filter(Edge.source_id == merge_node.id).all()
                )
                for edge in outgoing:
                    existing = (
                        session.query(Edge)
                        .filter(
                            and_(
                                Edge.source_id == keep_node_id,
                                Edge.target_id == edge.target_id,
                                Edge.edge_type == edge.edge_type,
                            )
                        )
                        .first()
                    )
                    if existing:
                        await session.delete(edge)
                    else:
                        edge.source_id = keep_node_id
                    edges_updated += 1
                incoming = (
                    session.query(Edge).filter(Edge.target_id == merge_node.id).all()
                )
                for edge in incoming:
                    existing = (
                        session.query(Edge)
                        .filter(
                            and_(
                                Edge.source_id == edge.source_id,
                                Edge.target_id == keep_node_id,
                                Edge.edge_type == edge.edge_type,
                            )
                        )
                        .first()
                    )
                    if existing:
                        await session.delete(edge)
                    else:
                        edge.target_id = keep_node_id
                    edges_updated += 1
            for merge_node in merge_nodes:
                await session.delete(merge_node)
            await session.commit()
            await session.refresh(keep_node)
            session.expunge(keep_node)
            result = {
                "kept_node_id": keep_node_id,
                "merged_node_ids": [n.id for n in merge_nodes],
                "edges_redirected": edges_updated,
                "merged_properties": merged_props,
                "node": keep_node.to_dict(),
            }
            logger.info(
                f"Merged {len(merge_nodes)} nodes into {keep_node_id}, redirected {edges_updated} edges"
            )
            return result

    async def get_edges(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        edge_type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Edge]:
        """Get edges with optional filtering.

        Args:
            source_id: Filter by source node ID
            target_id: Filter by target node ID
            edge_type: Filter by edge type
            limit: Maximum number of edges to return
            offset: Number of edges to skip

        Returns:
            List of Edge instances
        """
        async with self.db_manager.get_session() as session:
            query = select(Edge)
            if source_id:
                query = query.filter(Edge.source_id == source_id)
            if target_id:
                query = query.filter(Edge.target_id == target_id)
            if edge_type:
                query = query.filter(Edge.edge_type == edge_type)
            query = query.order_by(Edge.created_at)
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            result = await session.execute(query)
            edges = result.scalars().all()
            # Refresh and expunge all edges to detach from session
            for edge in edges:
                await session.refresh(edge)
                session.expunge(edge)
            return edges

    async def get_edges_count(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        edge_type: Optional[str] = None,
    ) -> int:
        """Get count of edges with optional filtering.

        Args:
            source_id: Filter by source node ID
            target_id: Filter by target node ID
            edge_type: Filter by edge type

        Returns:
            Count of matching edges
        """
        async with self.db_manager.get_session() as session:
            stmt = select(func.count(Edge.id))
            if source_id:
                stmt = stmt.filter(Edge.source_id == source_id)
            if target_id:
                stmt = stmt.filter(Edge.target_id == target_id)
            if edge_type:
                stmt = stmt.filter(Edge.edge_type == edge_type)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its edges.

        Args:
            node_id: ID of the node to delete

        Returns:
            True if node was deleted, False if not found
        """
        async with self.db_manager.get_session() as session:
            result = await session.execute(select(Node).filter(Node.id == node_id))
            node = result.scalar_one_or_none()
            if not node:
                return False
            await session.delete(node)
            await session.commit()
            logger.info(f"Deleted node {node_id}")
            return True

    async def bulk_delete_nodes(self, node_ids: List[str]) -> Dict[str, Any]:
        """Delete multiple nodes and all their edges in a single transaction.

        Args:
            node_ids: List of node IDs to delete

        Returns:
            Dictionary with:
                - deleted: List of node IDs that were deleted
                - not_found: List of node IDs that were not found
                - failed: List of dicts with node_id and error message
                - total: Total number of nodes processed
        """
        deleted = []
        not_found = []
        failed = []
        async with self.db_manager.get_session() as session:
            for node_id in node_ids:
                try:
                    node = session.query(Node).filter(Node.id == node_id).first()
                    if not node:
                        not_found.append(node_id)
                        continue
                    await session.delete(node)
                    deleted.append(node_id)
                except Exception as e:
                    logger.error(f"Error deleting node {node_id}: {e}")
                    failed.append({"node_id": node_id, "error": str(e)})
                    session.rollback()
            try:
                await session.commit()
                logger.info(
                    f"Bulk deleted {len(deleted)} nodes, {len(not_found)} not found, {len(failed)} failed"
                )
            except Exception as e:
                logger.error(f"Error committing bulk deletion: {e}")
                session.rollback()
                for node_id in deleted:
                    failed.append({"node_id": node_id, "error": "Commit failed"})
                deleted = []
        return {
            "deleted": deleted,
            "not_found": not_found,
            "failed": failed,
            "total": len(node_ids),
        }

    async def delete_edge(self, edge_id: int) -> bool:
        """Delete an edge by its ID.

        Args:
            edge_id: ID of the edge to delete

        Returns:
            True if edge was deleted, False if not found
        """
        async with self.db_manager.get_session() as session:
            edge = session.query(Edge).filter(Edge.id == edge_id).first()
            if not edge:
                return False
            await session.delete(edge)
            await session.commit()
            logger.info(f"Deleted edge {edge_id}")
            return True

    async def search_nodes(
        self,
        query_text: str,
        node_type: Optional[str] = None,
        order_by: str = "relevance",
        limit: int = 10,
        offset: int = 0,
    ) -> List[Node]:
        """Search nodes using semantic vector similarity search.

        Args:
            query_text: Text to search for
            node_type: Optional filter by node type
            order_by: Sort order ('relevance' or 'created_at')
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of matching Node instances
        """
        async with self.db_manager.get_session() as session:
            query_text = str(query_text).strip() if query_text else ""
            if not query_text and node_type:
                query = select(Node).filter(Node.node_type == node_type)
                if order_by == "created_at":
                    query = query.order_by(Node.created_at.desc())
                if offset:
                    query = query.offset(offset)
                query = query.limit(limit)
                nodes_result = await session.execute(query)
                nodes = nodes_result.scalars().all()
                for node in nodes:
                    await session.refresh(node)
                    session.expunge(node)
                return nodes
            if not query_text:
                return []
            if order_by == "relevance":
                try:
                    is_postgres = self.db_manager.engine.dialect.name == "postgresql"
                    embedding_manager = EmbeddingManager.get_instance()
                    query_embedding = embedding_manager.embed_text(query_text)
                    if not query_embedding or all((v == 0.0 for v in query_embedding)):
                        logger.warning("Generated empty/zero embedding for query")
                        return []
                    if is_postgres:
                        embedding_array = (
                            "[" + ",".join(map(str, query_embedding)) + "]"
                        )
                        # Build query with proper parameter binding for async
                        # Use CAST instead of ::vector syntax for parameter binding
                        query_parts = [
                            "SELECT",
                            "n.id,",
                            "n.node_type,",
                            "n.label,",
                            "n.content,",
                            "n.properties,",
                            "n.created_at,",
                            "n.updated_at,",
                            "1 - (n.embedding <=> CAST(:embedding AS vector)) as similarity",
                            "FROM nodes n",
                            "WHERE n.embedding IS NOT NULL",
                        ]
                        query_params = {"embedding": embedding_array}
                        if node_type:
                            query_parts.append("AND n.node_type = :node_type")
                            query_params["node_type"] = node_type
                        query_parts.append(
                            "ORDER BY n.embedding <=> CAST(:embedding AS vector)"
                        )
                        if offset:
                            query_parts.append("OFFSET :offset")
                            query_params["offset"] = offset
                        query_parts.append("LIMIT :limit")
                        query_params["limit"] = limit

                        base_query = " ".join(query_parts)
                        result = await session.execute(text(base_query), query_params)
                        results_list = result.fetchall()

                        class ResultWrapper:

                            def __init__(self, results):
                                self.results = results

                            def __iter__(self):
                                return iter(self.results)

                        vector_query = ResultWrapper(results_list)
                    else:
                        vector_query = session.execute(
                            text(
                                "\n                            SELECT \n                                n.id,\n                                n.node_type,\n                                n.label,\n                                n.content,\n                                n.properties,\n                                n.created_at,\n                                n.updated_at,\n                                (1.0 - distance) as similarity\n                            FROM nodes_vec\n                            JOIN nodes n ON nodes_vec.rowid = n.rowid\n                            WHERE nodes_vec.embedding MATCH json(:embedding) AND k = :k\n                            ORDER BY distance ASC\n                        "
                            ),
                            {"embedding": json.dumps(query_embedding), "k": limit * 2},
                        )
                    results = []
                    skipped = 0
                    for row in vector_query:
                        try:
                            created_at = row[5]
                            updated_at = row[6]
                            if isinstance(created_at, str):
                                created_at = datetime.fromisoformat(created_at)
                            if isinstance(updated_at, str):
                                updated_at = datetime.fromisoformat(updated_at)
                            if node_type and row[1] != node_type:
                                continue
                            node = Node(
                                id=row[0],
                                node_type=row[1],
                                label=row[2],
                                content=row[3],
                                properties=row[4],
                                created_at=created_at,
                                updated_at=updated_at,
                            )
                            results.append(node)
                        except Exception as e:
                            logger.error("Error creating Node from row %s: %s", row, e)
                            continue
                    return results
                except Exception as e:
                    logger.error(
                        "Error in vector search: %s. Returning empty results.", e
                    )
                    return []
            else:
                search_pattern = f"%{query_text}%"
                query = select(Node).filter(
                    or_(
                        Node.label.like(search_pattern),
                        Node.content.like(search_pattern),
                        text(self._get_json_search_query("LIKE")).params(
                            pattern=search_pattern
                        ),
                    )
                )
                if node_type:
                    query = query.filter(Node.node_type == node_type)
                query = query.order_by(Node.created_at).limit(limit)
                nodes_result = await session.execute(query)
                nodes = nodes_result.scalars().all()
                for node in nodes:
                    await session.refresh(node)
                    session.expunge(node)
                return nodes

    async def get_node_neighbors(
        self,
        node_id: str,
        direction: str = "both",
        edge_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Tuple[Edge, Node]]:
        """Get neighbors of a node.

        Args:
            node_id: ID of the node
            direction: 'incoming', 'outgoing', or 'both'
            edge_types: Optional filter by edge types
            limit: Optional maximum number of neighbors to return

        Returns:
            List of (Edge, Node) tuples
        """
        async with self.db_manager.get_session() as session:
            if direction in ["outgoing", "both"]:
                outgoing_query = (
                    select(Edge, Node)
                    .join(Node, Edge.target_id == Node.id)
                    .filter(Edge.source_id == node_id)
                )
                if edge_types:
                    outgoing_query = outgoing_query.filter(
                        Edge.edge_type.in_(edge_types)
                    )
                if limit:
                    outgoing_query = outgoing_query.limit(limit)
                outgoing_result = await session.execute(outgoing_query)
                outgoing_results = outgoing_result.all()
            else:
                outgoing_results = []
            if direction in ["incoming", "both"]:
                incoming_query = (
                    select(Edge, Node)
                    .join(Node, Edge.source_id == Node.id)
                    .filter(Edge.target_id == node_id)
                )
                if edge_types:
                    incoming_query = incoming_query.filter(
                        Edge.edge_type.in_(edge_types)
                    )
                if limit:
                    remaining_limit = (
                        limit - len(outgoing_results) if direction == "both" else limit
                    )
                    if remaining_limit > 0:
                        incoming_query = incoming_query.limit(remaining_limit)
                incoming_result = await session.execute(incoming_query)
                incoming_results = incoming_result.all()
            else:
                incoming_results = []
            all_results = outgoing_results + incoming_results
            # Expunge objects to detach from session (no refresh needed for freshly queried objects)
            for edge, node in all_results:
                session.expunge(edge)
                session.expunge(node)
            return all_results

    async def get_graph_stats(self) -> Dict[str, int]:
        """Get basic statistics about the graph.

        Returns:
            Dictionary with node count, edge count, and counts by type
        """
        async with self.db_manager.get_session() as session:
            stats = {
                "total_nodes": (
                    await session.execute(select(func.count(Node.id)))
                ).scalar()
                or 0,
                "total_edges": (
                    await session.execute(select(func.count(Edge.id)))
                ).scalar()
                or 0,
            }
            node_types_result = await session.execute(
                select(Node.node_type, func.count(Node.id)).group_by(Node.node_type)
            )
            node_types = node_types_result.all()
            stats["node_types"] = {nt: count for nt, count in node_types}
            edge_types_result = await session.execute(
                select(Edge.edge_type, func.count(Edge.id)).group_by(Edge.edge_type)
            )
            edge_types = edge_types_result.all()
            stats["edge_types"] = {et: count for et, count in edge_types}
            return stats

    async def export_to_memory_format(self) -> Dict[str, Any]:
        """Export graph data in the format expected by existing code.

        Returns:
            Dictionary with 'nodes' and 'edges' keys containing data
        """
        async with self.db_manager.get_session() as session:
            nodes = {node.id: node.to_dict() for node in session.query(Node).all()}
            edges = [edge.to_dict() for edge in session.query(Edge).all()]
            return {"nodes": nodes, "edges": edges}

    async def find_nodes_by_properties(
        self, properties: Dict[str, Any], node_type: Optional[str] = None
    ) -> List[Node]:
        """Find nodes matching property criteria.

        Args:
            properties: Dictionary of property key-value pairs to match
            node_type: Optional filter by node type

        Returns:
            List of matching Node instances
        """
        async with self.db_manager.get_session() as session:
            query = session.query(Node)
            if node_type:
                query = query.filter(Node.node_type == node_type)
            for key, value in properties.items():
                query = query.filter(
                    text(self._get_json_property_query(key, "="))
                ).params(value=value)
            return query.all()

    async def find_shortest_path(
        self, start_id: str, end_id: str, max_depth: Optional[int] = None
    ) -> Optional[List[str]]:
        """Find shortest path using BFS.

        Args:
            start_id: Starting node ID
            end_id: Target node ID
            max_depth: Maximum path length (optional)

        Returns:
            List of node IDs forming the path, or None if no path exists
        """
        async with self.db_manager.get_session() as session:
            start_node = session.query(Node).filter(Node.id == start_id).first()
            end_node = session.query(Node).filter(Node.id == end_id).first()
            if not start_node or not end_node:
                return None
            if start_id == end_id:
                return [start_id]
            queue = deque([(start_id, [start_id])])
            visited = {start_id}
            while queue:
                current, path = queue.popleft()
                if max_depth and len(path) > max_depth:
                    continue
                if current == end_id:
                    return path
                neighbors = await self.get_node_neighbors(current, direction="both")
                # Extract node IDs immediately to avoid detached instance issues
                neighbor_ids = [neighbor_node.id for _, neighbor_node in neighbors]
                for neighbor_id in neighbor_ids:
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append((neighbor_id, path + [neighbor_id]))
            return None

    async def find_all_paths(
        self, start_id: str, end_id: str, max_depth: int = 5
    ) -> List[List[str]]:
        """Find all paths using DFS.

        Args:
            start_id: Starting node ID
            end_id: Target node ID
            max_depth: Maximum path length

        Returns:
            List of paths, where each path is a list of node IDs
        """
        async with self.db_manager.get_session() as session:
            start_node = session.query(Node).filter(Node.id == start_id).first()
            end_node = session.query(Node).filter(Node.id == end_id).first()
            if not start_node or not end_node:
                return []
            if start_id == end_id:
                return [[start_id]]
            all_paths_list = []

            async def dfs(
                current: str, target: str, path: List[str], visited: Set[str]
            ):
                if len(path) > max_depth:
                    return
                if current == target:
                    all_paths_list.append(path.copy())
                    return
                neighbors = await self.get_node_neighbors(current, direction="both")
                # Extract node IDs immediately to avoid detached instance issues
                neighbor_ids = [neighbor_node.id for _, neighbor_node in neighbors]
                for neighbor_id in neighbor_ids:
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        path.append(neighbor_id)
                        dfs(neighbor_id, target, path, visited)
                        path.pop()
                        visited.remove(neighbor_id)

            await dfs(start_id, end_id, [start_id], {start_id})
            return all_paths_list

    async def calculate_degree_centrality(self) -> Dict[str, float]:
        """Calculate degree centrality for all nodes.

        Returns:
            Dictionary of node_id -> centrality score
        """
        async with self.db_manager.get_session() as session:
            total_nodes = session.query(Node).count()
            if total_nodes <= 1:
                return {}
            centrality = {}
            nodes = session.query(Node).all()
            for node in nodes:
                in_degree = (
                    session.query(Edge).filter(Edge.target_id == node.id).count()
                )
                out_degree = (
                    session.query(Edge).filter(Edge.source_id == node.id).count()
                )
                degree = in_degree + out_degree
                centrality[node.id] = (
                    degree / (total_nodes - 1) if total_nodes > 1 else 0
                )
            return centrality

    async def calculate_pagerank(
        self, damping: float = 0.85, iterations: int = 100, tolerance: float = 1e-06
    ) -> Dict[str, float]:
        """Calculate PageRank centrality.

        Args:
            damping: Damping factor (typically 0.85)
            iterations: Maximum iterations
            tolerance: Convergence threshold

        Returns:
            Dictionary of node_id -> pagerank score
        """
        async with self.db_manager.get_session() as session:
            nodes = session.query(Node).all()
            node_ids = [node.id for node in nodes]
            n = len(node_ids)
            if n == 0:
                return {}
            adjacency_out = defaultdict(list)
            adjacency_in = defaultdict(list)
            edges = session.query(Edge).all()
            for edge in edges:
                adjacency_out[edge.source_id].append(edge.target_id)
                adjacency_in[edge.target_id].append(edge.source_id)
            scores = {node_id: 1.0 / n for node_id in node_ids}
            for _ in range(iterations):
                new_scores = {}
                diff = 0.0
                for node_id in node_ids:
                    rank_sum = 0.0
                    for source in adjacency_in[node_id]:
                        out_degree = len(adjacency_out[source])
                        if out_degree > 0:
                            rank_sum += scores[source] / out_degree
                    new_score = (1 - damping) / n + damping * rank_sum
                    new_scores[node_id] = new_score
                    diff += abs(new_score - scores[node_id])
                scores = new_scores
                if diff < tolerance:
                    break
            return scores

    async def find_connected_components(self) -> List[Set[str]]:
        """Find connected components using BFS.

        Returns:
            List of sets, where each set contains node IDs in a component
        """
        async with self.db_manager.get_session() as session:
            nodes_result = await session.execute(select(Node))
            nodes = nodes_result.scalars().all()
            node_ids = [node.id for node in nodes]
            if not node_ids:
                return []
            visited = set()
            components = []

            async def bfs(start: str) -> Set[str]:
                """BFS to find all nodes in component."""
                component = set()
                queue = deque([start])
                component.add(start)
                visited.add(start)
                while queue:
                    current = queue.popleft()
                    neighbors = await self.get_node_neighbors(current, direction="both")
                    # Extract node IDs immediately to avoid detached instance issues
                    neighbor_ids = [neighbor_node.id for _, neighbor_node in neighbors]
                    for neighbor_id in neighbor_ids:
                        if neighbor_id not in visited:
                            visited.add(neighbor_id)
                            component.add(neighbor_id)
                            queue.append(neighbor_id)
                return component

            for node_id in node_ids:
                if node_id not in visited:
                    component = await bfs(node_id)
                    components.append(component)
            return components

    async def traverse_graph(
        self,
        start_nodes: List[str],
        edge_types: Optional[List[str]] = None,
        node_types: Optional[List[str]] = None,
        max_depth: int = 3,
        direction: str = "both",
    ) -> Dict[str, Any]:
        """Traverse the graph from starting nodes with filters.

        Args:
            start_nodes: List of starting node IDs
            edge_types: Optional filter by edge types
            node_types: Optional filter by node types
            max_depth: Maximum traversal depth
            direction: 'incoming', 'outgoing', or 'both'

        Returns:
            Dictionary containing traversed subgraph
        """
        async with self.db_manager.get_session() as session:
            valid_start_nodes = []
            for node_id in start_nodes:
                if session.query(Node).filter(Node.id == node_id).first():
                    valid_start_nodes.append(node_id)
            if not valid_start_nodes:
                return {
                    "nodes": [],
                    "edges": [],
                    "statistics": {"node_count": 0, "edge_count": 0},
                }
            visited_nodes = set(valid_start_nodes)
            visited_edges = []
            queue = deque([(node_id, 0) for node_id in valid_start_nodes])
            while queue:
                current, depth = queue.popleft()
                if depth >= max_depth:
                    continue
                neighbors = await self.get_node_neighbors(
                    current, direction=direction, edge_types=edge_types
                )
                # Extract node information immediately to avoid detached instance issues
                for edge, neighbor_node in neighbors:
                    neighbor_id = neighbor_node.id
                    neighbor_type = neighbor_node.node_type
                    if node_types and neighbor_type not in node_types:
                        continue
                    if edge not in visited_edges:
                        visited_edges.append(edge)
                    if neighbor_id not in visited_nodes:
                        visited_nodes.add(neighbor_id)
                        queue.append((neighbor_id, depth + 1))
            subgraph = {
                "nodes": [
                    node.to_dict()
                    for node in session.query(Node)
                    .filter(Node.id.in_(visited_nodes))
                    .all()
                ],
                "edges": [edge.to_dict() for edge in visited_edges],
                "statistics": {
                    "node_count": len(visited_nodes),
                    "edge_count": len(visited_edges),
                    "max_depth_reached": max_depth,
                },
            }
            return subgraph

    async def get_graph_context(self, node_id: str, depth: int = 1) -> Dict[str, Any]:
        """Get node and its neighbors up to specified depth.

        Args:
            node_id: ID of the central node
            depth: Maximum depth to traverse

        Returns:
            Dictionary containing nodes and edges in context
        """
        async with self.db_manager.get_session() as session:
            node = session.query(Node).filter(Node.id == node_id).first()
            if not node:
                return {"error": f"Node {node_id} not found"}
            nodes_to_visit = {node_id}
            context = {"nodes": {}, "edges": []}
            current_level = {node_id}
            for _ in range(depth):
                next_level = set()
                for node_id in current_level:
                    if node_id not in context["nodes"]:
                        context["nodes"][node_id] = (
                            node.to_dict()
                            if node_id == node.id
                            else session.query(Node)
                            .filter(Node.id == node_id)
                            .first()
                            .to_dict()
                        )
                    neighbors = await self.get_node_neighbors(node_id, direction="both")
                    # Extract node IDs immediately to avoid detached instance issues
                    neighbor_ids = [neighbor_node.id for _, neighbor_node in neighbors]
                    for neighbor_id in neighbor_ids:
                        next_level.add(neighbor_id)
                    # Also collect edges for context (extract immediately to avoid detached instance issues)
                    for edge, _ in neighbors:
                        edge_dict = edge.to_dict()
                        if edge_dict not in context["edges"]:
                            context["edges"].append(edge_dict)
                nodes_to_visit.update(next_level)
                current_level = next_level
            for node_id in nodes_to_visit:
                if node_id not in context["nodes"]:
                    node = session.query(Node).filter(Node.id == node_id).first()
                    if node:
                        context["nodes"][node_id] = node.to_dict()

            # Sort nodes by created_at in ascending order
            # Rebuild the nodes dict in sorted order (Python 3.7+ maintains insertion order)
            sorted_nodes = {}
            for node_id, node_dict in sorted(
                context["nodes"].items(),
                key=lambda x: x[1].get("created_at") or "",
            ):
                sorted_nodes[node_id] = node_dict
            context["nodes"] = sorted_nodes

            # Sort edges by created_at in ascending order
            context["edges"].sort(
                key=lambda x: x.get("created_at") or "",
            )

            return context

    async def save_memory(
        self, key: str, content: str, overwrite: bool = False
    ) -> Optional[Node]:
        """Save text content as a Memory node.

        Args:
            key: Memory key (e.g., "core:identity", "chat:session:123:transcript")
            content: Text content to store
            overwrite: If False and memory exists, raises ValueError. If True, updates existing.

        Returns:
            The created or updated Node instance

        Raises:
            ValueError: If memory exists and overwrite=False
        """
        node_id = f"memory:{key}"
        existing = await self.get_node(node_id)
        if existing and (not overwrite):
            raise ValueError(f"Memory '{key}' already exists (set overwrite=True)")
        node = await self.add_node(
            node_id=node_id,
            node_type="Memory",
            label=key,
            content=content,
            properties={"key": key, "content_size": len(content)},
        )
        return node

    async def append_memory(self, key: str, content: str) -> Node:
        """Append text content to a Memory node (creates if missing).

        Args:
            key: Memory key
            content: Text content to append

        Returns:
            The created or updated Node instance
        """
        node_id = f"memory:{key}"
        existing = await self.get_node(node_id)
        if existing and existing.content:
            new_content = existing.content + content
        else:
            new_content = content
        node = await self.add_node(
            node_id=node_id,
            node_type="Memory",
            label=key,
            content=new_content,
            properties={"key": key, "content_size": len(new_content)},
        )
        return node

    async def get_memory(self, key: str) -> Optional[str]:
        """Get the text content stored under a key.

        Args:
            key: Memory key

        Returns:
            Content string if found, None otherwise
        """
        if key.startswith("memory:"):
            node_id = key
        else:
            node_id = f"memory:{key}"
        node = await self.get_node(node_id)
        if not node:
            return None
        return node.content if node else None

    async def delete_memory(self, key: str) -> bool:
        """Delete a Memory node by key.

        Args:
            key: Memory key

        Returns:
            True if deleted, False if not found
        """
        node_id = f"memory:{key}"
        return await self.delete_node(node_id)

    async def list_memories(
        self,
        prefix: Optional[str] = None,
        sort_by_timestamp: bool = False,
        sort_order: str = "desc",
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List stored memory keys with metadata.

        Args:
            prefix: Optional filter by key prefix
            sort_by_timestamp: If True, sort by updated_at timestamp
            sort_order: "asc" or "desc" (only used if sort_by_timestamp=True)
            limit: Maximum number of memories to return
            offset: Number of memories to skip

        Returns:
            List of dictionaries with memory metadata:
            - key: Memory key
            - content_size: Length of content
            - created_at: Creation timestamp
            - updated_at: Last update timestamp
        """
        all_memories = await self.get_nodes(node_type="Memory")
        if prefix:
            all_memories = [
                m
                for m in all_memories
                if m.properties.get("key", "").startswith(prefix)
            ]
        memory_list = []
        for memory in all_memories:
            key = memory.properties.get("key")
            if not key:
                continue
            memory_dict = {
                "key": key,
                "content_size": memory.properties.get("content_size", 0),
                "created_at": (
                    memory.created_at.isoformat() if memory.created_at else None
                ),
                "updated_at": (
                    memory.updated_at.isoformat() if memory.updated_at else None
                ),
            }
            memory_list.append(memory_dict)
        if sort_by_timestamp:
            reverse = sort_order.lower() == "desc"
            memory_list.sort(
                key=lambda x: x["updated_at"] or x["created_at"] or "", reverse=reverse
            )
        if offset or limit:
            end_index = offset + limit if limit else None
            memory_list = memory_list[offset:end_index]
        return memory_list

    async def get_memories_count(self, prefix: Optional[str] = None) -> int:
        """Get count of stored memories with optional filtering.

        Args:
            prefix: Optional filter by key prefix

        Returns:
            Count of matching memories
        """
        total_count = await self.get_nodes_count(node_type="Memory")
        if not prefix:
            return total_count
        all_memories = await self.get_nodes(node_type="Memory")
        count = sum(
            (
                1
                for m in all_memories
                if m.properties and m.properties.get("key", "").startswith(prefix)
            )
        )
        return count

    async def search_memory(
        self, query: str, limit: int = 10, offset: int = 0, order_by: str = "relevance"
    ) -> List[Dict[str, Any]]:
        """Search Memory nodes using semantic vector similarity search.

        Args:
            query: Search query text
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: Sort order ("relevance" or "created_at")

        Returns:
            List of dictionaries with memory search results:
            - key: Memory key
            - content: Memory content
            - similarity: Relevance score (if order_by="relevance")
            - created_at: Creation timestamp
            - updated_at: Last update timestamp
        """
        search_results = await self.search_nodes(
            query, node_type="Memory", limit=limit, offset=offset, order_by=order_by
        )
        memory_results = []
        for node in search_results:
            key = node.properties.get("key") if node.properties else None
            if not key:
                continue
            memory_dict = {
                "key": key,
                "content": node.content,
                "created_at": node.created_at.isoformat() if node.created_at else None,
                "updated_at": node.updated_at.isoformat() if node.updated_at else None,
            }
            memory_results.append(memory_dict)
        return memory_results

    async def calculate_betweenness_centrality(
        self, normalized: bool = True
    ) -> Dict[str, float]:
        """Calculate betweenness centrality for all nodes using Brandes' algorithm (unweighted, treated as undirected).

        Args:
            normalized: If True, normalize scores to [0,1] range.

        Returns:
            Dictionary of node_id -> betweenness score
        """
        async with self.db_manager.get_session() as session:
            nodes = session.query(Node).all()
            node_ids = [node.id for node in nodes]
            n = len(node_ids)
            if n == 0:
                return {}
            edges = session.query(Edge).all()
            adjacency: Dict[str, List[str]] = defaultdict(list)
            for e in edges:
                if e.source_id != e.target_id:
                    adjacency[e.source_id].append(e.target_id)
                    adjacency[e.target_id].append(e.source_id)
            betweenness: Dict[str, float] = {v: 0.0 for v in node_ids}
            for s in node_ids:
                stack: List[str] = []
                predecessors: Dict[str, List[str]] = {v: [] for v in node_ids}
                sigma: Dict[str, float] = {v: 0.0 for v in node_ids}
                sigma[s] = 1.0
                distance: Dict[str, int] = {v: -1 for v in node_ids}
                distance[s] = 0
                queue = deque([s])
                while queue:
                    v = queue.popleft()
                    stack.append(v)
                    for w in adjacency.get(v, []):
                        if distance[w] < 0:
                            distance[w] = distance[v] + 1
                            queue.append(w)
                        if distance[w] == distance[v] + 1:
                            sigma[w] += sigma[v]
                            predecessors[w].append(v)
                delta: Dict[str, float] = {v: 0.0 for v in node_ids}
                while stack:
                    w = stack.pop()
                    for v in predecessors[w]:
                        if sigma[w] > 0:
                            delta_contrib = sigma[v] / sigma[w] * (1.0 + delta[w])
                            delta[v] += delta_contrib
                    if w != s:
                        betweenness[w] += delta[w]
            if normalized and n > 2:
                scale = 1.0 / ((n - 1) * (n - 2) / 2.0)
                for v in betweenness:
                    betweenness[v] *= scale
            return betweenness

    async def calculate_clustering_coefficient(self) -> Dict[str, float]:
        """Calculate local clustering coefficient for all nodes (treated as undirected).

        Returns:
            Dictionary of node_id -> clustering coefficient in [0,1]
        """
        async with self.db_manager.get_session() as session:
            nodes = session.query(Node).all()
            node_ids = [node.id for node in nodes]
            if not node_ids:
                return {}
            edges = session.query(Edge).all()
            neighbors: Dict[str, Set[str]] = {v: set() for v in node_ids}
            for e in edges:
                if e.source_id != e.target_id:
                    neighbors.setdefault(e.source_id, set()).add(e.target_id)
                    neighbors.setdefault(e.target_id, set()).add(e.source_id)
            clustering: Dict[str, float] = {}
            for v in node_ids:
                nbrs = list(neighbors.get(v, set()))
                k = len(nbrs)
                if k < 2:
                    clustering[v] = 0.0
                    continue
                neighbor_sets = neighbors
                links = 0
                for i in range(k):
                    u = nbrs[i]
                    for j in range(i + 1, k):
                        w = nbrs[j]
                        if w in neighbor_sets.get(u, set()):
                            links += 1
                possible = k * (k - 1) / 2.0
                clustering[v] = links / possible if possible > 0 else 0.0
            return clustering

    async def save_workflow(
        self,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
        version: Optional[int] = None,
    ) -> Node:
        """Save or update a workflow definition.

        Args:
            name: Workflow name
            description: Workflow description
            steps: List of workflow steps (each with tool_name, args, output_key)
            version: Specific version to save (None = auto-increment)

        Returns:
            The created/updated workflow node
        """
        async with self.db_manager.get_session() as session:
            if version is None:
                existing = (
                    session.query(Node)
                    .filter(
                        Node.node_type == "Workflow",
                        text(self._get_json_property_query("name")).bindparams(
                            value=name
                        ),
                    )
                    .order_by(text("CAST(properties->>'version' AS INTEGER) DESC"))
                    .first()
                )
                version = (
                    int(existing.properties.get("version", 0)) + 1 if existing else 1
                )
            workflow_id = f"workflow:{name}:{version}"
            properties = {
                "name": name,
                "version": version,
                "steps": json.dumps(steps),
                "execution_count": 0,
                "success_count": 0,
                "failure_count": 0,
            }
            node = await self.add_node(
                node_id=workflow_id,
                node_type="Workflow",
                label=f"{name} (v{version})",
                content=description,
                properties=properties,
            )
            await self.add_edge(
                source_id=workflow_id,
                target_id="concept:workflow",
                edge_type="INSTANCE_OF",
            )
            if version > 1:
                prev_workflow_id = f"workflow:{name}:{version - 1}"
                if await self.get_node(prev_workflow_id):
                    await self.add_edge(
                        source_id=workflow_id,
                        target_id=prev_workflow_id,
                        edge_type="VERSION_OF",
                    )
            return node

    async def get_workflow(
        self, name: str, version: Optional[int] = None
    ) -> Optional[Node]:
        """Get a workflow by name and version.

        Args:
            name: Workflow name
            version: Specific version (None = latest)

        Returns:
            Workflow node or None if not found
        """
        if version is not None:
            workflow_id = f"workflow:{name}:{version}"
            return await self.get_node(workflow_id)
        async with self.db_manager.get_session() as session:
            node = (
                session.query(Node)
                .filter(
                    Node.node_type == "Workflow",
                    text(self._get_json_property_query("name")).bindparams(value=name),
                )
                .order_by(text("CAST(properties->>'version' AS INTEGER) DESC"))
                .first()
            )
            if node:
                await session.refresh(node)
                session.expunge(node)
            return node

    async def list_workflows(
        self,
        include_versions: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Node]:
        """List all workflows.

        Args:
            include_versions: If False, return only latest version of each workflow
            limit: Maximum number of workflows to return
            offset: Number of workflows to skip

        Returns:
            List of workflow nodes
        """
        async with self.db_manager.get_session() as session:
            if include_versions:
                query = (
                    select(Node)
                    .filter(Node.node_type == "Workflow")
                    .order_by(
                        text("properties->>'name'"),
                        text("CAST(properties->>'version' AS INTEGER) DESC"),
                    )
                )
                if offset:
                    query = query.offset(offset)
                if limit:
                    query = query.limit(limit)
                result = await session.execute(query)
                workflows = result.scalars().all()
            else:
                query = (
                    select(Node)
                    .filter(Node.node_type == "Workflow")
                    .order_by(text("properties->>'name'"))
                )
                result = await session.execute(query)
                all_workflows = result.scalars().all()
                latest_by_name = {}
                for wf in all_workflows:
                    wf_name = wf.properties.get("name")
                    wf_version = int(wf.properties.get("version", 0))
                    if wf_name not in latest_by_name or wf_version > int(
                        latest_by_name[wf_name].properties.get("version", 0)
                    ):
                        latest_by_name[wf_name] = wf
                workflows = list(latest_by_name.values())
                if offset or limit:
                    end_index = offset + limit if limit else None
                    workflows = workflows[offset:end_index]
            for wf in workflows:
                await session.refresh(wf)
                session.expunge(wf)
            return workflows

    async def get_workflows_count(self, include_versions: bool = False) -> int:
        """Get count of workflows.

        Args:
            include_versions: If False, count only latest version of each workflow

        Returns:
            Count of workflows
        """
        async with self.db_manager.get_session() as session:
            if include_versions:
                result = await session.execute(
                    select(func.count(Node.id)).filter(Node.node_type == "Workflow")
                )
                return result.scalar() or 0
            else:
                result = await session.execute(
                    select(Node).filter(Node.node_type == "Workflow")
                )
                all_workflows = result.scalars().all()
                unique_names = set()
                for wf in all_workflows:
                    wf_name = wf.properties.get("name")
                    if wf_name:
                        unique_names.add(wf_name)
                return len(unique_names)

    async def get_workflow_execution_history(
        self, workflow_name: str, limit: int = 50
    ) -> List[Node]:
        """Get execution history for a workflow.

        Args:
            workflow_name: Workflow name
            limit: Maximum number of executions to return

        Returns:
            List of WorkflowExecution nodes
        """
        async with self.db_manager.get_session() as session:
            query = (
                select(Node)
                .filter(
                    Node.node_type == "WorkflowExecution",
                    text(self._get_json_property_query("workflow_name")).bindparams(
                        value=workflow_name
                    ),
                )
                .order_by(Node.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            executions = result.scalars().all()
            for node in executions:
                await session.refresh(node)
                session.expunge(node)
            return executions

    async def delete_workflow(self, name: str, version: Optional[int] = None) -> bool:
        """Delete a workflow.

        Args:
            name: Workflow name
            version: Specific version to delete (None = delete all versions)

        Returns:
            True if deleted, False if not found
        """
        if version is not None:
            workflow_id = f"workflow:{name}:{version}"
            return self.delete_node(workflow_id)
        async with self.db_manager.get_session() as session:
            query = select(Node).filter(
                Node.node_type == "Workflow",
                text(self._get_json_property_query("name")).bindparams(value=name),
            )
            result = await session.execute(query)
            workflows = result.scalars().all()
            if not workflows:
                return False
            for workflow in workflows:
                self.delete_node(workflow.id)
            return True

    async def increment_workflow_stats(
        self, workflow_name: str, version: int, success: bool
    ) -> None:
        """Increment execution statistics for a workflow.

        Args:
            workflow_name: Workflow name
            version: Workflow version
            success: Whether the execution was successful
        """
        workflow_id = f"workflow:{workflow_name}:{version}"
        node = await self.get_node(workflow_id)
        if not node:
            return
        session.refresh(node)
        session.refresh(node)
        session.refresh(node)
        async with self.db_manager.get_session() as session:
            db_node = session.query(Node).filter(Node.id == workflow_id).first()
            if not db_node:
                return
            props = db_node.properties or {}
            props["execution_count"] = props.get("execution_count", 0) + 1
            if success:
                props["success_count"] = props.get("success_count", 0) + 1
            else:
                props["failure_count"] = props.get("failure_count", 0) + 1
            db_node.properties = props
            db_node.updated_at = datetime.utcnow()
            await session.commit()

    async def save_thinking_pattern(
        self, name: str, description: str, steps: List[str], applicable_to: List[str]
    ) -> Node:
        """Save a thinking pattern.

        Args:
            name: Pattern name
            description: Pattern description
            steps: List of reasoning steps
            applicable_to: List of problem types this pattern applies to

        Returns:
            The created thinking pattern node
        """
        pattern_id = f"pattern:{name}"
        properties = {
            "name": name,
            "steps": json.dumps(steps),
            "applicable_to": json.dumps(applicable_to),
            "usage_count": 0,
            "success_rate": 0.0,
        }
        node = await self.add_node(
            node_id=pattern_id,
            node_type="ThinkingPattern",
            label=name,
            content=description,
            properties=properties,
        )
        await self.add_edge(
            source_id=pattern_id, target_id="concept:reasoning", edge_type="INSTANCE_OF"
        )
        return node

    async def get_thinking_patterns(
        self,
        query: str,
        problem_type: Optional[str] = None,
        limit: int = 5,
        offset: int = 0,
    ) -> List[Node]:
        """Get thinking patterns similar to a query.

        Args:
            query: Search query
            problem_type: Optional filter by problem type
            limit: Maximum number of patterns to return
            offset: Number of patterns to skip

        Returns:
            List of thinking pattern nodes
        """
        results = await self.search_nodes(
            query_text=query,
            node_type="ThinkingPattern",
            limit=limit * 2,
            offset=offset,
        )
        if problem_type:
            filtered = []
            for node in results:
                if node.properties:
                    applicable = json.loads(node.properties.get("applicable_to", "[]"))
                    if problem_type in applicable:
                        filtered.append(node)
            results = filtered[:limit]
        else:
            results = results[:limit]
        return results

    async def save_problem_solution(
        self,
        problem: str,
        approach_steps: List[str],
        outcome: str,
        lessons_learned: str,
        session_id: Optional[str] = None,
    ) -> Node:
        """Save a successful problem solution.

        Args:
            problem: Problem description
            approach_steps: Steps taken to solve the problem
            outcome: Result of the solution
            lessons_learned: Key insights from solving the problem
            session_id: Optional session ID to link to

        Returns:
            The created problem solution node
        """
        timestamp = datetime.utcnow().isoformat()
        import hashlib

        problem_hash = hashlib.md5(problem.encode()).hexdigest()[:8]
        solution_id = f"solution:{timestamp}:{problem_hash}"
        properties = {
            "problem": problem,
            "approach_steps": json.dumps(approach_steps),
            "outcome": outcome,
            "lessons_learned": lessons_learned,
        }
        problem_summary = problem[:50] + "..." if len(problem) > 50 else problem
        node = await self.add_node(
            node_id=solution_id,
            node_type="ProblemSolution",
            label=f"Solution to {problem_summary}",
            content=f"{problem}\n\nOutcome: {outcome}\n\nLessons: {lessons_learned}",
            properties=properties,
        )
        await self.add_edge(
            source_id=solution_id,
            target_id="concept:reasoning",
            edge_type="INSTANCE_OF",
        )
        if session_id:
            session_node_id = f"session:{session_id}"
            if await self.get_node(session_node_id):
                await self.add_edge(
                    source_id=session_node_id,
                    target_id=solution_id,
                    edge_type="PRODUCED",
                )
        return node

    async def create_thinking_session(
        self,
        problem: str,
        session_id: str,
        steps: List[str],
        pattern_name: Optional[str] = None,
    ) -> Node:
        """Create a thinking session node.

        Args:
            problem: Problem being solved
            session_id: Session ID
            steps: Generated reasoning steps
            pattern_name: Optional pattern used

        Returns:
            The created thinking session node
        """
        timestamp = datetime.utcnow().isoformat()
        thinking_id = f"thinking:{timestamp}:{session_id}"
        properties = {
            "problem": problem,
            "steps_generated": json.dumps(steps),
            "pattern_used": pattern_name or "",
        }
        node = await self.add_node(
            node_id=thinking_id,
            node_type="ThinkingSession",
            label="Problem-solving session",
            content=problem,
            properties=properties,
        )
        await self.add_edge(
            source_id=thinking_id,
            target_id="concept:reasoning",
            edge_type="INSTANCE_OF",
        )
        session_node_id = f"session:{session_id}"
        if await self.get_node(session_node_id):
            await self.add_edge(
                source_id=session_node_id, target_id=thinking_id, edge_type="PERFORMED"
            )
        if pattern_name:
            pattern_id = f"pattern:{pattern_name}"
            if await self.get_node(pattern_id):
                await self.add_edge(
                    source_id=thinking_id,
                    target_id=pattern_id,
                    edge_type="USES_PATTERN",
                )
        return node

    async def get_user_chats(
        self,
        user_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get all chats for a user, directly linked or via sessions (for backward compatibility).

        Args:
            user_id: User ID to get chats for
            limit: Maximum number of chats to return
            offset: Number of chats to skip
            include_archived: Whether to include archived chats

        Returns:
            List of chat dictionaries with metadata (deduplicated)
        """
        user_node_id = f"user:{user_id}"
        async with self.db_manager.get_session() as session:
            # Get user node
            stmt = select(Node).filter(Node.id == user_node_id)
            result = await session.execute(stmt)
            user_node = result.scalar_one_or_none()
            if not user_node:
                return []

            # Query for direct chats (Chat -> BELONGS_TO -> User)
            direct_chat_edge = aliased(Edge)
            direct_chats_stmt = (
                select(Node, direct_chat_edge)
                .join(
                    direct_chat_edge,
                    and_(
                        direct_chat_edge.source_id == Node.id,
                        direct_chat_edge.target_id == user_node_id,
                        direct_chat_edge.edge_type == "BELONGS_TO",
                    ),
                )
                .filter(Node.node_type == "Chat")
                .distinct(Node.id)
            )
            direct_result = await session.execute(direct_chats_stmt)
            direct_results = direct_result.all()

            # Query for session-linked chats (Chat -> BELONGS_TO_SESSION -> Session -> BELONGS_TO -> User)
            chat_to_session_edge = aliased(Edge)
            session_to_user_edge = aliased(Edge)
            session_chats_stmt = (
                select(Node, chat_to_session_edge)
                .join(
                    chat_to_session_edge,
                    and_(
                        chat_to_session_edge.source_id == Node.id,
                        chat_to_session_edge.edge_type == "BELONGS_TO_SESSION",
                    ),
                )
                .join(
                    session_to_user_edge,
                    and_(
                        session_to_user_edge.source_id
                        == chat_to_session_edge.target_id,
                        session_to_user_edge.target_id == user_node_id,
                        session_to_user_edge.edge_type == "BELONGS_TO",
                    ),
                )
                .filter(Node.node_type == "Chat")
                .distinct(Node.id)
            )
            session_result = await session.execute(session_chats_stmt)
            session_results = session_result.all()
            all_results = {}
            for chat_node, edge in direct_results + session_results:
                chat_id = (
                    chat_node.properties.get("chat_id")
                    if chat_node.properties
                    else chat_node.id.replace("chat:", "")
                )
                if chat_id not in all_results:
                    all_results[chat_id] = (chat_node, edge)
            results = list(all_results.values())
            chats = []
            seen_chat_ids = set()
            for chat_node, edge in results:
                chat_id = (
                    chat_node.properties.get("chat_id")
                    if chat_node.properties
                    else chat_node.id.replace("chat:", "")
                )
                if chat_id in seen_chat_ids:
                    continue
                seen_chat_ids.add(chat_id)
                if not include_archived:
                    is_archived = (
                        chat_node.properties.get("archived", False)
                        if chat_node.properties
                        else False
                    )
                    if is_archived:
                        continue
                chat_dict = {
                    "chat_id": chat_id,
                    "chat_name": (
                        chat_node.properties.get("chat_name")
                        if chat_node.properties
                        else chat_node.label
                    ),
                    "created_at": (
                        chat_node.created_at.isoformat()
                        if chat_node.created_at
                        else None
                    ),
                    "updated_at": (
                        chat_node.updated_at.isoformat()
                        if chat_node.updated_at
                        else None
                    ),
                    "archived": (
                        chat_node.properties.get("archived", False)
                        if chat_node.properties
                        else False
                    ),
                }
                chats.append(chat_dict)
            chats.sort(
                key=lambda x: x["updated_at"] or x["created_at"] or "", reverse=True
            )
            if offset:
                chats = chats[offset:]
            if limit:
                chats = chats[:limit]
            return chats

    async def create_chat(
        self, chat_id: str, chat_name: str, user_id: str
    ) -> Optional[Node]:
        """Create a chat node and link it directly to a user.

        Args:
            chat_id: Unique chat identifier
            chat_name: Display name for the chat
            user_id: User ID to link the chat to

        Returns:
            Created Chat node or None if user doesn't exist
        """
        user_node_id = f"user:{user_id}"
        user_node = await self.get_node(user_node_id)
        if not user_node:
            logger.warning(f"Cannot create chat: user {user_id} not found")
            return None
        chat_node_id = f"chat:{chat_id}"
        chat_node = await self.add_node(
            node_id=chat_node_id,
            node_type="Chat",
            label=chat_name,
            content=f"Chat created at {datetime.utcnow().isoformat()}",
            properties={"chat_id": chat_id, "chat_name": chat_name, "user_id": user_id},
        )
        await self.add_edge(
            source_id=chat_node_id, target_id=user_node_id, edge_type="BELONGS_TO"
        )
        logger.info(f"Created chat {chat_node_id} for user {user_id}")
        return chat_node

    async def get_chat(self, chat_id: str) -> Optional[Node]:
        """Get a chat by its ID.

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)

        Returns:
            Chat node if found, None otherwise
        """
        chat_node_id = f"chat:{chat_id}"
        return await self.get_node(chat_node_id)

    async def get_session_messages(
        self, session_id: str, limit: Optional[int] = None, offset: int = 0
    ) -> List[Node]:
        """Get all messages linked to a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of ChatMessage nodes ordered by creation time
        """
        async with self.db_manager.get_session() as session:
            session_node = session.query(Node).filter(Node.id == session_id).first()
            if not session_node:
                logger.warning(f"Session {session_id} not found")
                return []
            query = (
                session.query(Node)
                .join(Edge, Edge.target_id == Node.id)
                .filter(
                    Edge.source_id == session_id,
                    Edge.edge_type == "CONTAINS",
                    Node.node_type == "ChatMessage",
                )
                .order_by(Node.created_at.asc())
            )
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            messages = query.all()
            for msg in messages:
                await session.refresh(msg)
                session.expunge(msg)
            logger.debug(
                f"Retrieved {len(messages)} messages from session {session_id}"
            )
            return messages

    async def get_chat_messages(
        self, chat_id: str, limit: Optional[int] = None, offset: int = 0
    ) -> List[Node]:
        """Get messages for a chat.

        Args:
            chat_id: Chat identifier
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of ChatMessage nodes ordered by creation time
        """
        chat_node_id = f"chat:{chat_id}"
        async with self.db_manager.get_session() as session:
            chat_node_result = await session.execute(
                select(Node).filter(Node.id == chat_node_id)
            )
            chat_node = chat_node_result.scalar_one_or_none()
            if not chat_node:
                logger.warning(f"Chat {chat_id} not found")
                return []
            chat_query = (
                select(Node)
                .join(Edge, Edge.target_id == Node.id)
                .filter(
                    Edge.source_id == chat_node_id,
                    Edge.edge_type == "CONTAINS",
                    Node.node_type == "ChatMessage",
                )
            )
            chat_messages_result = await session.execute(chat_query)
            chat_messages = chat_messages_result.scalars().all()
            logger.debug(
                f"Found {len(chat_messages)} messages directly linked to chat {chat_id}"
            )

            def get_message_num(node):
                try:
                    parts = node.id.split(":")
                    return int(parts[-1]) if parts else 0
                except (ValueError, IndexError):
                    return (
                        node.created_at or datetime.min.replace(tzinfo=timezone.utc)
                    ).timestamp()

            chat_messages.sort(key=get_message_num)
            if offset:
                chat_messages = chat_messages[offset:]
            if limit:
                chat_messages = chat_messages[:limit]
            for msg in chat_messages:
                await session.refresh(msg)
                session.expunge(msg)
            return chat_messages

    async def update_chat_name(self, chat_id: str, new_name: str) -> Optional[Node]:
        """Update the name of a chat.

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)
            new_name: New name for the chat

        Returns:
            Updated Chat node or None if not found
        """
        chat_node_id = f"chat:{chat_id}"
        chat_node = await self.get_node(chat_node_id)
        if not chat_node:
            logger.warning(f"Cannot update chat name: chat {chat_id} not found")
            return None
        async with self.db_manager.get_session() as session:
            result = await session.execute(select(Node).filter(Node.id == chat_node_id))
            db_node = result.scalar_one_or_none()
            if not db_node:
                return None
            db_node.label = new_name
            if db_node.properties:
                db_node.properties["chat_name"] = new_name
            else:
                db_node.properties = {"chat_name": new_name}
            flag_modified(db_node, "properties")
            db_node.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(db_node)
            session.expunge(db_node)
            logger.info(f"Updated chat {chat_id} name to '{new_name}'")
            return db_node

    async def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat and all its messages permanently.

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)

        Returns:
            True if deleted, False if not found
        """
        chat_node_id = f"chat:{chat_id}"
        result = self.delete_node(chat_node_id)
        if result:
            logger.info(f"Deleted chat {chat_id} and all its messages")
        else:
            logger.warning(f"Cannot delete chat: chat {chat_id} not found")
        return result

    async def archive_chat(self, chat_id: str) -> Optional[Node]:
        """Archive a chat (soft delete - hides from main list but preserves data).

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)

        Returns:
            Updated Chat node or None if not found
        """
        chat_node_id = f"chat:{chat_id}"
        chat_node = await self.get_node(chat_node_id)
        if not chat_node:
            logger.warning(f"Cannot archive chat: chat {chat_id} not found")
            return None
        async with self.db_manager.get_session() as session:
            db_node = session.query(Node).filter(Node.id == chat_node_id).first()
            if not db_node:
                return None
            if not db_node.properties:
                db_node.properties = {}
            db_node.properties["archived"] = True
            db_node.properties["archived_at"] = datetime.now(timezone.utc).isoformat()
            db_node.updated_at = datetime.now(timezone.utc)
            flag_modified(db_node, "properties")
            await session.commit()
            await session.refresh(db_node)
            session.expunge(db_node)
            logger.info(f"Archived chat {chat_id}")
            return db_node

    async def unarchive_chat(self, chat_id: str) -> Optional[Node]:
        """Unarchive a chat (restore from archived state).

        Args:
            chat_id: Chat identifier (without 'chat:' prefix)

        Returns:
            Updated Chat node or None if not found
        """
        chat_node_id = f"chat:{chat_id}"
        chat_node = await self.get_node(chat_node_id)
        if not chat_node:
            logger.warning(f"Cannot unarchive chat: chat {chat_id} not found")
            return None
        async with self.db_manager.get_session() as session:
            db_node = session.query(Node).filter(Node.id == chat_node_id).first()
            if not db_node:
                return None
            if not db_node.properties:
                db_node.properties = {}
            db_node.properties.pop("archived", None)
            db_node.properties.pop("archived_at", None)
            db_node.updated_at = datetime.now(timezone.utc)
            flag_modified(db_node, "properties")
            await session.commit()
            await session.refresh(db_node)
            session.expunge(db_node)
            logger.info(f"Unarchived chat {chat_id}")
            return db_node
