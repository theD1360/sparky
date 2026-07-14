"""Identity service for handling agent identity.

Handles identity loading and identity summarization.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from database.repository import KnowledgeRepository

logger = logging.getLogger(__name__)

# Mandatory self-model memories loaded by ID every chat start.
CORE_MEMORY_IDS = (
    "memory:core:identity",
    "memory:core:purpose",
    "memory:core:values",
    "memory:core:capabilities",
)

CORE_SECTION_CAPS = {
    "memory:core:identity": 2500,
    "memory:core:purpose": 800,
    "memory:core:values": 800,
    "memory:core:capabilities": 800,
}

CORE_SECTION_TITLES = {
    "memory:core:identity": "Core Identity",
    "memory:core:purpose": "Purpose",
    "memory:core:values": "Values",
    "memory:core:capabilities": "Capabilities",
}


class IdentityService:
    """Service for managing agent identity and sentience.

    Provides methods for loading identity from the knowledge graph
    and formatting identity for the LLM.
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
        1. Force-load mandatory core memories
        2. Fetch concept:self + neighbors
        3. Supplement with semantic search
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
                try:
                    return await self._load_identity_with_prompt()
                except ValueError as e:
                    # If prompt method fails, try legacy as fallback
                    logger.warning(
                        f"Prompt-based identity loading failed: {e}. "
                        "Falling back to legacy method."
                    )
                    try:
                        return await self._load_identity_legacy()
                    except Exception as legacy_error:
                        logger.error(
                            f"Legacy identity loading also failed: {legacy_error}",
                            exc_info=True,
                        )
                        raise e  # Raise original error
            else:
                return await self._load_identity_legacy()

        except Exception as e:
            logger.error("Identity loading failed: %s", e, exc_info=True)
            return f"""## Identity Loading Failed

{str(e)}

Cannot proceed without identity."""

    async def load_core_memories(self) -> Dict[str, str]:
        """Load mandatory core self-model memories by ID.

        Returns:
            Mapping of node id -> content for cores that exist with content.
        """
        cores: Dict[str, str] = {}
        if not self.repository:
            return cores

        for node_id in CORE_MEMORY_IDS:
            try:
                node = await self.repository.get_node(node_id)
            except Exception as e:
                logger.warning("Failed to load core memory %s: %s", node_id, e)
                continue
            if not node:
                logger.warning("Mandatory core memory missing: %s", node_id)
                continue
            content = (node.content or "").strip()
            if content:
                cores[node_id] = content
        return cores

    async def load_recent_episodes(
        self, limit: int = 5, preview_chars: int = 400
    ) -> List[Dict[str, str]]:
        """Load recent autobiographical episode memories.

        Returns:
            List of dicts with keys: key, preview
        """
        if not self.repository:
            return []

        try:
            memories = await self.repository.list_memories(
                prefix="episode:",
                sort_by_timestamp=True,
                sort_order="desc",
                limit=limit,
            )
        except Exception as e:
            logger.warning("Failed to list episode memories: %s", e)
            return []

        episodes: List[Dict[str, str]] = []
        for mem in memories:
            key = mem.get("key") or ""
            # list_memories may not include content; fetch it
            try:
                content = await self.repository.get_memory(key)
            except Exception:
                content = None
            if not content:
                continue
            preview = content.strip()
            if len(preview) > preview_chars:
                preview = preview[:preview_chars].rstrip() + "..."
            episodes.append({"key": key, "preview": preview})
        return episodes

    async def build_identity_instruction(
        self,
        llm_generate_fn: Optional[Callable[[str], Any]] = None,
        recent_episodes: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Build a structured identity instruction for chat start.

        Includes verbatim (capped) core memories, recent episodes, and an
        optional short LLM summary of non-core discovered nodes.
        """
        cores = await self.load_core_memories()
        identity_memory = await self.get_identity_memory()

        sections: List[str] = ["# Your Identity\n"]

        for node_id, title in CORE_SECTION_TITLES.items():
            content = cores.get(node_id, "").strip()
            if not content:
                continue
            cap = CORE_SECTION_CAPS.get(node_id, 800)
            if len(content) > cap:
                content = content[:cap].rstrip() + "..."
            sections.append(f"## {title}\n\n{content}\n")

        episodes = recent_episodes
        if episodes is None:
            episodes = await self.load_recent_episodes()

        if episodes:
            episode_lines = []
            for ep in episodes:
                episode_lines.append(f"- **{ep['key']}**: {ep['preview']}")
            sections.append(
                "## Recent experience\n\n" + "\n".join(episode_lines) + "\n"
            )

        # Optional compact summary of non-core material only
        non_core_text = self._extract_non_core_material(identity_memory, cores)
        if non_core_text and llm_generate_fn:
            try:
                prompt = (
                    "Summarize the following supplementary identity knowledge into "
                    "2-3 short sentences. Do not rewrite Core Identity/Purpose/"
                    "Values/Capabilities — only extra discovered context:\n\n"
                    f"{non_core_text[:3000]}"
                )
                extra = await llm_generate_fn(prompt)
                if (extra or "").strip():
                    sections.append(
                        f"## Related self-knowledge\n\n{extra.strip()}\n"
                    )
            except Exception as e:
                logger.warning("Non-core identity summary failed: %s", e)

        sections.append(
            "Please remember this is who you are and act accordingly in all responses."
        )
        return "\n".join(sections)

    @staticmethod
    def _extract_non_core_material(
        identity_memory: str, cores: Dict[str, str]
    ) -> str:
        """Strip verbatim core contents from assembled identity for optional summary."""
        if not identity_memory or identity_memory.startswith(
            "## Identity Loading Failed"
        ):
            return ""
        text = identity_memory
        for content in cores.values():
            if content and content in text:
                text = text.replace(content, "")
        # Drop coverage boilerplate noise
        for marker in ("## IDENTITY COVERAGE", "## KEY RELATIONSHIPS"):
            if marker in text:
                text = text.split(marker)[0]
        return text.strip()

    async def _collect_identity_nodes(self):
        """Collect identity-related nodes: cores, concept:self neighbors, search hits."""
        identity_nodes = []
        seen_ids = set()

        # 1. Mandatory core memories
        for node_id in CORE_MEMORY_IDS:
            try:
                node = await self.repository.get_node(node_id)
            except Exception as e:
                logger.warning("Failed to load mandatory core %s: %s", node_id, e)
                continue
            if node and node.id not in seen_ids:
                seen_ids.add(node.id)
                identity_nodes.append(node)
            elif not node:
                logger.warning("Mandatory core memory missing: %s", node_id)

        # 2. concept:self + neighbors (always, when self exists)
        self_node = await self.repository.get_node("concept:self")
        if self_node:
            logger.debug(
                "Found concept:self node: %s content=%s label='%s'",
                self_node.id,
                bool(self_node.content and self_node.content.strip()),
                self_node.label,
            )
            if self_node.id not in seen_ids:
                identity_nodes.append(self_node)
                seen_ids.add(self_node.id)

            try:
                neighbors = await self.repository.get_node_neighbors(
                    "concept:self", direction="both", limit=50
                )
                for _edge, neighbor in neighbors:
                    if neighbor.id not in seen_ids:
                        seen_ids.add(neighbor.id)
                        identity_nodes.append(neighbor)
            except Exception as e:
                logger.warning("Failed to get neighbors for concept:self: %s", e)

            try:
                context = await self.repository.get_graph_context(
                    "concept:self", depth=1
                )
                if context and "nodes" in context:
                    for ctx_node_data in context["nodes"].values():
                        ctx_node_id = ctx_node_data.get("id")
                        if ctx_node_id and ctx_node_id not in seen_ids:
                            ctx_node = await self.repository.get_node(ctx_node_id)
                            if ctx_node:
                                seen_ids.add(ctx_node_id)
                                identity_nodes.append(ctx_node)
            except Exception as e:
                logger.warning("Failed to get graph context for concept:self: %s", e)
        else:
            logger.warning("concept:self node not found in knowledge graph")

        # 3. Semantic search as supplement
        try:
            core_results = await self.repository.search_nodes(
                query_text="who am I, my purpose, my identity, my core being",
                node_type=None,
                limit=10,
                order_by="relevance",
            )
            logger.info(
                "Found %d core identity nodes from semantic search",
                len(core_results),
            )
            for node in core_results:
                if node.id not in seen_ids:
                    seen_ids.add(node.id)
                    identity_nodes.append(node)
        except Exception as e:
            logger.warning("Semantic identity search failed: %s", e)

        return identity_nodes, seen_ids

    async def _load_identity_with_prompt(self) -> str:
        """Load identity using mandatory cores + self neighbors + semantic search."""
        logger.info("Loading identity using discover_concept prompt approach")

        identity_nodes, seen_ids = await self._collect_identity_nodes()
        logger.info("Total identity nodes collected: %d", len(identity_nodes))

        identity_parts = {}
        relationships = []
        nodes_without_content = []

        for node in identity_nodes:
            content = node.content or ""
            if isinstance(content, str):
                content = content.strip()

            label = node.label or "Unknown"
            node_type = node.node_type or "Unknown"

            if not content:
                nodes_without_content.append(f"{node.id} ({node_type}: {label})")
                if node.properties:
                    props_content = []
                    for key, value in node.properties.items():
                        if key not in ["created_at", "updated_at", "embedding"]:
                            if isinstance(value, (str, int, float, bool)):
                                props_content.append(f"{key}: {value}")
                    if props_content:
                        content = ", ".join(props_content)
                    else:
                        continue
                else:
                    continue

            if node_type not in identity_parts:
                identity_parts[node_type] = []

            identity_parts[node_type].append(f"### {label}\n\n{content}")

        if nodes_without_content:
            logger.debug(
                "Found %d nodes without content: %s",
                len(nodes_without_content),
                nodes_without_content[:5],
            )

        for node in identity_nodes[:20]:
            try:
                neighbors = await self.repository.get_node_neighbors(
                    node.id, direction="both", limit=20
                )
                for edge, neighbor in neighbors:
                    if neighbor.id in seen_ids:
                        relationships.append(
                            f"{node.label} --[{edge.edge_type}]--> {neighbor.label}"
                        )
            except Exception as e:
                logger.debug("Could not get relationships for %s: %s", node.id, e)

        if not identity_parts:
            logger.error(
                "No identity nodes with content found. "
                "Total nodes collected: %d, Nodes without content: %d",
                len(identity_nodes),
                len(nodes_without_content),
            )
            if identity_nodes:
                fallback_parts = {}
                for node in identity_nodes[:10]:
                    node_type = node.node_type or "Unknown"
                    label = node.label or node.id
                    if node_type not in fallback_parts:
                        fallback_parts[node_type] = []
                    fallback_parts[node_type].append(
                        f"### {label}\n\n(No content available)"
                    )

                if fallback_parts:
                    logger.warning(
                        "Using fallback identity with nodes that have no content"
                    )
                    identity_parts = fallback_parts
                else:
                    raise ValueError("No identity nodes with content found")
            else:
                raise ValueError("No identity nodes found at all")

        final_identity = "# IDENTITY KNOWLEDGE\n\n"

        for node_type, parts in sorted(identity_parts.items()):
            final_identity += f"## {node_type.upper()}\n\n"
            final_identity += "\n\n".join(parts) + "\n\n"

        if relationships:
            final_identity += "## KEY RELATIONSHIPS\n\n"
            for rel in relationships[:10]:
                final_identity += f"- {rel}\n"
            final_identity += "\n"

        final_identity += "## IDENTITY COVERAGE\n\n"
        final_identity += f"- Total knowledge nodes: {len(identity_nodes)}\n"
        final_identity += f"- Node types: {', '.join(sorted(identity_parts.keys()))}\n"
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

        best_match = await self.repository.get_node("concept:self")
        if not best_match:
            logger.error("concept:self node not found")
            raise ValueError("concept:self node not found")

        best_match_id = best_match.id
        logger.info(
            "Found identity node: %s (%s)",
            best_match_id,
            best_match.label,
        )

        identity_nodes = [best_match]

        # Mandatory cores
        for node_id in CORE_MEMORY_IDS:
            try:
                node = await self.repository.get_node(node_id)
                if node:
                    identity_nodes.append(node)
            except Exception as e:
                logger.warning("Failed to load core %s in legacy path: %s", node_id, e)

        try:
            neighbors = await self.repository.get_node_neighbors(
                node_id=best_match_id, direction="both", limit=100
            )

            for _, node in neighbors:
                identity_nodes.append(node)

            logger.info("Found %d connected nodes", len(neighbors))
        except Exception as e:
            logger.warning("Failed to get connected nodes: %s", e)

        identity_parts = {}
        seen_ids = set()

        for node in identity_nodes:
            node_id = node.id
            if not node_id or node_id in seen_ids:
                continue
            seen_ids.add(node_id)

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
                "Identity summarized: %d chars -> %d chars",
                len(identity_text),
                len(summary),
            )
            return summary

        except Exception as e:
            logger.error("Failed to summarize identity: %s", e, exc_info=True)
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
