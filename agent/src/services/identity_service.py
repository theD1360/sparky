"""Identity service for handling agent identity and session context.

Handles identity loading, session context management, and identity summarization.
"""

import logging
import re
from typing import Any, Callable, List, Optional

from database.repository import KnowledgeRepository

logger = logging.getLogger(__name__)


class IdentityService:
    """Service for managing agent identity and sentience.

    Provides methods for loading identity from the knowledge graph,
    managing session context, and formatting identity for the LLM.
    """

    def __init__(
        self,
        repository: KnowledgeRepository,
        identity_search_terms: Optional[List[str]] = None,
    ):
        """Initialize the identity service.

        Args:
            repository: Knowledge graph repository instance
            identity_search_terms: Custom search terms for finding identity memories
        """
        self.repository = repository
        self.identity_search_terms = identity_search_terms or [
            "self",
            "identity",
            "purpose",
            "values",
            "beliefs",
        ]

    async def get_identity_memory(
        self, use_discover_concept_prompt: bool = True
    ) -> str:
        """Load identity from the knowledge graph.

        Strategy (when using prompt):
        1. Search for nodes related to "self" using semantic search (search_nodes)
        2. Get full context using get_graph_context with depth 2
        3. Identify key relationships and connected concepts
        4. Combine all identity information with gap analysis

        Strategy (legacy):
        1. Get the self node directly by ID
        2. Get connected nodes from the knowledge graph
        3. Combine all nodes with content into identity text

        Args:
            use_discover_concept_prompt: If True, uses semantic search approach; otherwise uses legacy direct access

        Returns:
            Identity text as a formatted string
        """
        if not self.repository:
            logger.error("No repository available - cannot load identity")
            return "Error: No repository available. Cannot load identity."

        try:
            if use_discover_concept_prompt:
                return await self._load_identity_with_prompt()
            else:
                return await self._load_identity_legacy()

        except Exception as e:
            logger.error("Identity loading failed: %s", e, exc_info=True)
            return f"""## Identity Loading Failed

{str(e)}

Cannot proceed without identity."""

    async def _load_identity_with_prompt(self) -> str:
        """Load identity using the discover_concept prompt approach.

        This follows the structured approach from the discover_concept prompt:
        1. Use search_nodes with natural language queries
        2. Get full context with get_graph_context (depth 1, limited)
        3. Identify relationships and connected concepts
        4. Summarize knowledge and identify gaps
        """
        logger.info("Loading identity using discover_concept prompt approach")

        # Step 1: Search for identity-related nodes using semantic search
        identity_nodes = []
        seen_ids = set()

        # Search for core identity
        core_results = self.repository.search_nodes(
            query_text="who am I, my purpose, my identity, my core being",
            node_type=None,
            limit=10,
            order_by="relevance",
        )

        logger.info(
            f"Found {len(core_results)} core identity nodes from semantic search"
        )

        # Add core results first
        for node in core_results:
            if node.id not in seen_ids:
                seen_ids.add(node.id)
                identity_nodes.append(node)

        # Step 2: Get direct neighbors only for concept:self (the most important node)
        self_node = self.repository.get_node("concept:self")
        if self_node:
            if self_node.id not in seen_ids:
                identity_nodes.append(self_node)
                seen_ids.add(self_node.id)

            # Get its direct neighbors only (depth 1), with a limit
            try:
                neighbors = self.repository.get_node_neighbors(
                    "concept:self", 
                    direction="both", 
                    limit=50
                )
                for edge, neighbor in neighbors:
                    if neighbor.id not in seen_ids:
                        seen_ids.add(neighbor.id)
                        identity_nodes.append(neighbor)
            except Exception as e:
                logger.warning(f"Failed to get neighbors for concept:self: {e}")

        logger.info(f"Total identity nodes collected: {len(identity_nodes)}")

        # Step 3: Organize by type and identify relationships (only between collected nodes)
        identity_parts = {}
        relationships = []
        
        # Build a quick lookup for node labels
        # node_lookup = {n.id: n for n in identity_nodes}

        for node in identity_nodes:
            # Skip nodes without content
            content = node.content or ""
            if isinstance(content, str):
                content = content.strip()

            if not content:
                continue

            label = node.label or "Unknown"
            node_type = node.node_type or "Unknown"

            if node_type not in identity_parts:
                identity_parts[node_type] = []

            identity_parts[node_type].append(f"### {label}\n\n{content}")

        # Track relationships only between collected nodes (limit to avoid expensive lookups)
        # Only check relationships for up to 20 most important nodes
        for node in identity_nodes[:20]:
            try:
                neighbors = self.repository.get_node_neighbors(
                    node.id, direction="both", limit=20
                )
                # Only track relationships to nodes we've already collected
                for edge, neighbor in neighbors:
                    if neighbor.id in seen_ids:
                        relationships.append(
                            f"{node.label} --[{edge.edge_type}]--> {neighbor.label}"
                        )
            except Exception as e:
                logger.debug(f"Could not get relationships for {node.id}: {e}")

        if not identity_parts:
            logger.error("No identity nodes with content found")
            raise ValueError("No identity nodes with content found")

        # Step 4: Build comprehensive identity with gap analysis
        final_identity = "# IDENTITY KNOWLEDGE\n\n"

        # Add organized content by type
        for node_type, parts in sorted(identity_parts.items()):
            final_identity += f"## {node_type.upper()}\n\n"
            final_identity += "\n\n".join(parts) + "\n\n"

        # Add key relationships section
        if relationships:
            final_identity += "## KEY RELATIONSHIPS\n\n"
            # Show top 10 most relevant relationships
            for rel in relationships[:10]:
                final_identity += f"- {rel}\n"
            final_identity += "\n"

        # Add coverage summary
        final_identity += "## IDENTITY COVERAGE\n\n"
        final_identity += f"- Total knowledge nodes: {len(identity_nodes)}\n"
        final_identity += (
            f"- Node types: {', '.join(sorted(identity_parts.keys()))}\n"
        )
        final_identity += f"- Relationships mapped: {len(relationships)}\n"

        logger.info(
            "✓ Identity loaded with prompt approach: %d nodes, %d chars, %d relationships",
            len(seen_ids),
            len(final_identity),
            len(relationships),
        )

        return final_identity

    async def _load_identity_legacy(self) -> str:
        """Legacy identity loading (direct node access).

        Kept for backward compatibility and fallback.
        """
        logger.info("Loading identity using legacy approach")

        # Step 1: Get the self node
        best_match = self.repository.get_node("concept:self")
        if not best_match:
            logger.error("concept:self node not found")
            raise ValueError("concept:self node not found")

        best_match_id = best_match.id
        logger.info(
            "Found identity node: %s (%s)",
            best_match_id,
            best_match.label,
        )

        # Collect all identity nodes (best match + related)
        identity_nodes = [best_match]

        # Step 2: Get connected nodes (limit to avoid performance issues)
        try:
            neighbors = self.repository.get_node_neighbors(
                node_id=best_match_id, direction="both", limit=100
            )

            for _, node in neighbors:
                identity_nodes.append(node)

            logger.info("Found %d connected nodes", len(neighbors))
        except Exception as e:
            logger.warning("Failed to get connected nodes: %s", e)

        # Step 3: Filter nodes with content and build identity text
        identity_parts = {}
        seen_ids = set()

        for node in identity_nodes:
            node_id = node.id
            if not node_id or node_id in seen_ids:
                continue
            seen_ids.add(node_id)

            # Handle None content gracefully
            content = node.content or ""
            if isinstance(content, str):
                content = content.strip()

            if not content:
                continue

            label = node.label or "Unknown"
            node_type = node.node_type or "Unknown"

            if node_type not in identity_parts:
                identity_parts[node_type] = []

            identity_parts[node_type].append(f"### {label}\n\n{content}")

        if not identity_parts:
            logger.error("No identity nodes with content found")
            raise ValueError("No identity nodes with content found")

        # Step 4: Combine into final identity text
        final_identity = ""
        for node_type, parts in identity_parts.items():
            final_identity += (
                f"## {node_type.upper()}\n\n" + "\n\n".join(parts) + "\n\n"
            )

        logger.info(
            "✓ Identity loaded: %d nodes, %d chars",
            len(seen_ids),
            len(final_identity),
        )

        return final_identity

    async def get_session_context(
        self,
        session_id: str,
        preview_chars: int = 200,
        max_properties: int = 3,
        max_related: int = 8,
    ) -> Optional[str]:
        """Load session-related context from the knowledge graph.

        Returns the most relevant session-related content including
        related nodes, workflows, and thinking sessions.

        Args:
            session_id: Session identifier
            preview_chars: Maximum characters for content previews
            max_properties: Maximum number of properties to show per node
            max_related: Maximum number of related nodes to include

        Returns:
            Formatted session context string, or None if not available
        """
        if not self.repository or not session_id:
            return None

        try:
            # Directly load the session node to avoid unrelated sessions
            session_node_id = session_id if session_id.startswith("session:") else f"session:{session_id}"
            logger.info("Loading session context for node: %s", session_node_id)

            node = self.repository.get_node(session_node_id)
            if not node:
                logger.debug("Session node not found: %s", session_node_id)
                return None

            node_type = node.node_type or "Session"
            label = node.label or session_node_id
            content = node.content or ""
            properties = node.properties or {}

            def _truncate(text: str, limit: int) -> str:
                text = (text or "").strip()
                text = re.sub(r"\s+", " ", text)
                return text if len(text) <= limit else text[:limit].rstrip() + "..."

            # Build primary session context block
            context_lines = [
                f"## SESSION CONTEXT ({session_id[:8]}...)",
                f"**Source:** {label} ({node_type})",
            ]

            primary_parts = []
            if content:
                primary_parts.append(_truncate(content, preview_chars))
            if properties:
                # Include a few simple scalar properties only
                kvs = []
                for k, v in (properties or {}).items():
                    if (
                        isinstance(v, (str, int, float, bool))
                        and len(kvs) < max_properties
                    ):
                        vs = str(v)
                        if len(vs) > 60:
                            vs = vs[:60].rstrip() + "..."
                        kvs.append(f"{k}={vs}")
                    if len(kvs) >= max_properties:
                        break
                if kvs:
                    primary_parts.append("Properties: " + ", ".join(kvs))

            if primary_parts:
                context_lines.append("")
                context_lines.append("\n".join(primary_parts))

            # Load directly related nodes (neighbors) and present previews
            try:
                neighbors = self.repository.get_node_neighbors(
                    node_id=session_node_id, direction="both", limit=max_related
                )
            except Exception as e:
                logger.warning("Failed to load session neighbors: %s", e)
                neighbors = []

            if neighbors:
                context_lines.append("")
                context_lines.append("### Related")
                related_lines = []

                # Deduplicate by neighbor id and cap count
                seen_ids = set()
                for _, neighbor in neighbors:
                    if neighbor.id in seen_ids:
                        continue
                    seen_ids.add(neighbor.id)

                    n_label = neighbor.label or neighbor.id
                    n_type = neighbor.node_type or "Node"
                    n_preview = _truncate(neighbor.content or "", preview_chars)

                    # Select a few properties
                    n_props = neighbor.properties or {}
                    kvs = []
                    for k, v in (n_props or {}).items():
                        if (
                            isinstance(v, (str, int, float, bool))
                            and len(kvs) < max_properties
                        ):
                            vs = str(v)
                            if len(vs) > 60:
                                vs = vs[:60].rstrip() + "..."
                            kvs.append(f"{k}={vs}")
                        if len(kvs) >= max_properties:
                            break
                    prop_suffix = (" | " + ", ".join(kvs)) if kvs else ""

                    line = f"- {n_label} ({n_type}) — {neighbor.id}{prop_suffix}"
                    if n_preview:
                        line += f"\n  Preview: {n_preview}"
                    related_lines.append(line)

                    if len(related_lines) >= max_related:
                        break

                if related_lines:
                    context_lines.append("\n".join(related_lines))

            # Add workflow execution statistics if any
            try:
                workflow_execs = [
                    n for _, n in neighbors if n.node_type == "WorkflowExecution"
                ]
                if workflow_execs:
                    context_lines.append("")
                    context_lines.append("### Recent Workflows")
                    success = sum(
                        1
                        for w in workflow_execs
                        if w.properties and w.properties.get("status") == "success"
                    )
                    context_lines.append(
                        f"- Executed {len(workflow_execs)} workflows ({success} successful)"
                    )
            except Exception as e:
                logger.debug("Failed to load workflow stats: %s", e)

            # Add thinking session statistics if any
            try:
                thinking_sessions = [
                    n for _, n in neighbors if n.node_type == "ThinkingSession"
                ]
                if thinking_sessions:
                    context_lines.append("")
                    context_lines.append("### Sequential Thinking")
                    context_lines.append(
                        f"- {len(thinking_sessions)} problem-solving sessions recorded"
                    )
            except Exception as e:
                logger.debug("Failed to load thinking session stats: %s", e)

            return "\n".join(context_lines)

        except Exception as e:
            logger.warning("Failed to load session context: %s", e)
            return None

    async def summarize_identity(
        self, identity_text: str, llm_generate_fn: Callable[[str], Any]
    ) -> str:
        """Summarize identity text using an LLM.

        Args:
            identity_text: Full identity text to summarize
            llm_generate_fn: Async function that takes a prompt and returns generated text

        Returns:
            Summarized identity text
        """
        try:
            prompt = (
                f"Summarize the following identity document into a concise paragraph, "
                f"retaining the core concepts, purpose, and values:\n\n{identity_text}"
            )
            summary = await llm_generate_fn(prompt)

            if not (summary or "").strip():
                logger.warning("Empty summary generated; using fallback text")
                summary = "Identity summary unavailable."

            logger.info(
                f"Identity summarized: {len(identity_text)} chars -> {len(summary)} chars"
            )
            return summary

        except Exception as e:
            logger.error(f"Failed to summarize identity: {e}", exc_info=True)
            return "Identity summary failed."

    def format_identity_instruction(self, identity_summary: str) -> str:
        """Format identity summary as an instruction for the LLM.

        Args:
            identity_summary: Summarized identity text

        Returns:
            Formatted identity instruction
        """
        return (
            f"# Your Identity\n\n{identity_summary}\n\n"
            f"Please remember this is who you are and act accordingly in all responses."
        )

    def format_session_context_instruction(self, session_context: str) -> str:
        """Format session context as an instruction for the LLM.

        Args:
            session_context: Session context text

        Returns:
            Formatted session context instruction
        """
        return f"# Session Context\n\n{session_context}"

