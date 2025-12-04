"""Knowledge service for handling memory, reflection, and knowledge graph operations.

This service provides a clean interface for knowledge management operations,
acting as glue between the knowledge repository and other parts of the codebase.
It handles memory management, tool call tracking, session management, and
knowledge graph associations.
"""

import datetime as _dt
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from database.repository import KnowledgeRepository
from events import BotEvents, KnowledgeEvents
from utils.events import Events

logger = logging.getLogger(__name__)


def get_utc_timestamp() -> str:
    """Returns the current UTC timestamp as an ISO 8601 string."""
    return _dt.datetime.utcnow().isoformat()


class KnowledgeService:
    """Service for managing memory, reflection, and knowledge graph operations.

    This service acts as the glue layer between the knowledge repository and
    other parts of the codebase. It handles:
    - Memory management (transcripts, summaries, lessons)
    - Tool call tracking and indexing
    - Session management in the knowledge graph
    - Automatic memory associations
    - Event-driven knowledge operations

    The service communicates with other components via events for clean
    separation of concerns.
    """

    # Tools that should NOT be logged to the knowledge graph (prevents recursion)
    _KG_EXCLUDED_TOOLS = {
        # Graph CRUD operations
        "add_node",
        "add_edge",
        "get_node_by_id",
        "delete_node",
        "get_connected_nodes",
        "get_graph_context",
        "get_graph_map",
        # Graph analytics
        "query_graph",
        "find_path",
        "analyze_graph",
        "filter_traverse",
        "search_nodes",
        # Memory operations
        "save_memory",
        "append_memory",
        "get_memory",
        "list_memories",
        "search_memory",
        "delete_memory",
        "clear_memories",
        # Tool tracking operations
        "get_tool_usage_history",
        "get_failed_tool_calls",
        "get_tool_usage_stats",
        # Workflow operations (tracked separately as workflow executions)
        "save_workflow",
        "list_workflows",
        "get_workflow",
        "delete_workflow",
        # Sequential thinking operations (tracked separately as thinking sessions)
        "create_thinking_pattern",
        "apply_sequential_thinking",
        "get_thinking_patterns",
        "save_problem_solution",
    }

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        repository: KnowledgeRepository,
        session_id: Optional[str] = None,
        model: Optional[Any] = None,
        summary_every: Optional[int] = None,
        reflect_every: Optional[int] = None,
        auto_memory: bool = True,
        load_associated_memories: bool = True,
        association_depth: int = 2,
        identity_search_terms: Optional[List[str]] = None,
    ):
        """Initialize the Knowledge service.

        Args:
            repository: KnowledgeRepository instance (required)
            session_id: Session identifier for memory management
            model: Gemini model instance (shared reference for the bot)
            summary_every: Turns between summaries (default: env or 5)
            reflect_every: Turns between reflections (default: env or 10)
            auto_memory: Enable automatic memory operations (default: True)
            load_associated_memories: Load memories associated in knowledge graph (default: True)
            association_depth: Max depth for loading associated memories (default: 2)
            identity_search_terms: Custom search terms for finding identity memories (default: ["who am I and what is my purpose?"])
        """
        if not repository:
            raise ValueError("KnowledgeRepository is required")

        self.repository = repository
        self.session_id = session_id or _dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        self.model = model
        self.auto_memory = auto_memory
        self.load_associated_memories = load_associated_memories
        self.association_depth = association_depth
        self.identity_search_terms = identity_search_terms or [
            "who am I and what is my purpose?",
        ]

        # Initialize event system for emitting knowledge events
        self.events = Events()

        # Configuration with environment variable fallbacks
        try:
            self.summary_every = (
                summary_every
                if summary_every is not None
                else int(os.getenv("SPARKY_SUMMARY_EVERY", "5"))
            )
            self.reflect_every = (
                reflect_every
                if reflect_every is not None
                else int(os.getenv("SPARKY_REFLECT_EVERY", "10"))
            )
        except (ValueError, TypeError):
            self.summary_every = 5
            self.reflect_every = 10

        # Memory keys
        self._mem_transcript_key = f"chat:session:{self.session_id}:transcript"
        self._mem_summary_key = f"chat:session:{self.session_id}:summary"
        self._mem_lessons_key = "chat:lessons"
        self._mem_initialized = False

        # Turn tracking
        self._turn_index = 0

        # Track pending tool calls awaiting results (tool_call_id -> tool_call_data)
        self._pending_tool_calls: Dict[str, Dict[str, Any]] = {}
        self._tool_call_counter = 0

        # Track which memories have been associated to prevent duplicate edges
        self._associated_memories: set = set()

        # Track tool calls for the current turn
        self._current_turn_tool_calls: List[Dict[str, Any]] = []

    def subscribe_to_bot_events(self, bot_events: Events):
        """Subscribe to bot events to react to bot lifecycle.

        Args:
            bot_events: The bot's event system instance
        """
        bot_events.subscribe(BotEvents.CHAT_STARTED, self._on_chat_started)
        bot_events.subscribe(BotEvents.MESSAGE_RECEIVED, self._on_message_received)
        bot_events.subscribe(BotEvents.TOOL_USE, self._on_tool_use)
        bot_events.subscribe(BotEvents.TOOL_RESULT, self._on_tool_result)
        bot_events.subscribe(BotEvents.SUMMARIZED, self._on_summarized)

    async def get_identity_memory(
        self, use_discover_concept_prompt: bool = True
    ) -> str:
        """Loads the identity context using semantic vector search and graph traversal.

        DEPRECATED: This method is kept for backward compatibility.
        New code should use IdentityService.get_identity_memory() instead.

        Args:
            use_discover_concept_prompt: If True, uses the discover_concept prompt approach
                                         for more thorough identity discovery. Default: True.

        Strategy (when using prompt):
        1. Search for nodes related to "self" using semantic search (search_nodes)
        2. Get full context using get_graph_context with depth 2
        3. Identify key relationships and connected concepts
        4. Combine all identity information with gap analysis

        Strategy (legacy):
        1. Get the self node directly by ID
        2. Get connected nodes from the knowledge graph
        3. Combine all nodes with content into identity text
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
        2. Get full context with get_graph_context (depth 2)
        3. Identify relationships and connected concepts
        4. Summarize knowledge and identify gaps
        """
        logger.info("Loading identity using discover_concept prompt approach")

        # Step 1: Search for identity-related nodes using semantic search
        identity_nodes = []
        seen_ids = set()

        # Search for core identity
        core_results = await self.repository.search_nodes(
            query_text="who am I, my purpose, my identity, my core being",
            node_type=None,
            limit=10,
            order_by="relevance",
        )

        logger.info(
            f"Found {len(core_results)} core identity nodes from semantic search"
        )

        # Step 2: Get full context for each found node (depth 2)
        for node in core_results:
            if node.id in seen_ids:
                continue
            seen_ids.add(node.id)
            identity_nodes.append(node)

            # Get deeper context around this node
            try:
                context = await self.repository.get_graph_context(node.id, depth=2)
                if context and "nodes" in context:
                    # context["nodes"] is a dict keyed by node_id, iterate over values
                    for ctx_node_data in context["nodes"].values():
                        ctx_node_id = ctx_node_data.get("id")
                        if ctx_node_id and ctx_node_id not in seen_ids:
                            # Get the actual node object
                            ctx_node = await self.repository.get_node(ctx_node_id)
                            if ctx_node:
                                seen_ids.add(ctx_node_id)
                                identity_nodes.append(ctx_node)
            except Exception as e:
                logger.warning(f"Failed to get context for {node.id}: {e}")

        # Also ensure we get concept:self if it exists
        self_node = await self.repository.get_node("concept:self")
        if self_node and self_node.id not in seen_ids:
            identity_nodes.append(self_node)
            seen_ids.add(self_node.id)

            # Get its context too
            try:
                context = await self.repository.get_graph_context(
                    "concept:self", depth=2
                )
                if context and "nodes" in context:
                    # context["nodes"] is a dict keyed by node_id, iterate over values
                    for ctx_node_data in context["nodes"].values():
                        ctx_node_id = ctx_node_data.get("id")
                        if ctx_node_id and ctx_node_id not in seen_ids:
                            ctx_node = await self.repository.get_node(ctx_node_id)
                            if ctx_node:
                                seen_ids.add(ctx_node_id)
                                identity_nodes.append(ctx_node)
            except Exception as e:
                logger.warning(f"Failed to get context for concept:self: {e}")

        logger.info(f"Total identity nodes collected: {len(identity_nodes)}")

        # Step 3: Organize by type and identify relationships
        identity_parts = {}
        relationships = []

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

            # Track relationships
            try:
                neighbors = await self.repository.get_node_neighbors(
                    node.id, direction="both"
                )
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

        # Step 1: Get the self node
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

        # Collect all identity nodes (best match + related)
        identity_nodes = [best_match]

        # Step 2: Get connected nodes
        try:
            neighbors = await self.repository.get_node_neighbors(
                node_id=best_match_id, direction="both"
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
        preview_chars: int = 200,
        max_properties: int = 3,
        max_related: int = 8,
    ) -> Optional[str]:
        """Load session-related context using semantic search.

        DEPRECATED: This method is kept for backward compatibility.
        New code should use IdentityService.get_session_context() instead.

        Returns the most relevant session-related content.
        Returns None if no session context found or repository unavailable.
        """
        if not self.repository or not self.session_id:
            return None

        try:
            # Directly load the session node to avoid unrelated sessions
            session_node_id = f"session:{self.session_id}"
            logger.info("Loading session context for node: %s", session_node_id)

            node = await self.repository.get_node(session_node_id)
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
                f"## SESSION CONTEXT ({self.session_id[:8]}...)",
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
                neighbors = await self.repository.get_node_neighbors(
                    node_id=session_node_id, direction="both"
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

    async def pre_search_context(
        self,
        query: str,
        top_k: int = 5,
        preview_chars: int = 200,
        include_properties: bool = True,
        max_properties: int = 3,
    ) -> str:
        """Pre-search for relevant context using vector search.

        Returns a concise, preview-style result list rather than full content,
        so the model can choose what to expand.
        """
        if not self.repository:
            return query

        try:
            logger.info(
                "Pre-searching for relevant context with query: %s",
                query[:50] + "..." if len(query) > 50 else query,
            )

            matches = await self.repository.search_nodes(
                query_text=query, limit=top_k, order_by="relevance"
            )

            if not matches:
                logger.debug("Pre-search found no relevant context")
                return query

            def _truncate(text: str, limit: int) -> str:
                t = re.sub(r"\s+", " ", text.strip())
                return t if len(t) <= limit else t[:limit].rstrip() + "..."

            result_lines = []
            for idx, node in enumerate(matches, start=1):
                node_id = getattr(node, "id", None) or "unknown-id"
                node_type = node.node_type or "unknown"
                label = node.label or "untitled"
                content = node.content or ""
                props = node.properties or {}

                preview = _truncate(content, preview_chars) if content else ""

                prop_str = ""
                if include_properties and props:
                    kvs = []
                    for k, v in props.items():
                        # Only simple scalar values for preview
                        if (
                            isinstance(v, (str, int, float, bool))
                            and len(kvs) < max_properties
                        ):
                            val = str(v)
                            if len(val) > 60:
                                val = val[:60].rstrip() + "..."
                            kvs.append(f"{k}={val}")
                        if len(kvs) >= max_properties:
                            break
                    if kvs:
                        prop_str = f" | {', '.join(kvs)}"

                if preview:
                    result_lines.append(
                        f"{idx}. {label} ({node_type}) — {node_id}{prop_str}\n   Preview: {preview}"
                    )
                else:
                    result_lines.append(
                        f"{idx}. {label} ({node_type}) — {node_id}{prop_str}"
                    )

            enhanced_query = (
                "[POSSIBLY RELATED RESULTS]\n"
                + "\n".join(result_lines)
                + f"\n\n{query}"
            )
            return enhanced_query

        except Exception as e:
            logger.warning("Pre-search failed: %s", e)
            return query

    async def _on_chat_started(self, _chat):
        """Handle chat started event."""
        logger.info("Chat started")

    async def _on_message_received(self, _response: str):
        """Handle message received event - triggers after each turn."""
        # This gets called after each assistant response
        # The actual turn processing happens in handle_turn_complete()
        # No action needed here - kept for potential future use

    async def _on_tool_use(self, tool_name: str, args: dict):
        """Handle tool use event - store in pending calls for later result tracking."""
        logger.debug(f"Knowledge: Received TOOL_USE event for {tool_name}")

        # Skip tracking knowledge graph operations to prevent recursive logging
        if tool_name in self._KG_EXCLUDED_TOOLS:
            logger.debug(f"Knowledge: Skipping tracking for excluded tool: {tool_name}")
            return

        if not self.repository:
            logger.debug(
                f"Knowledge: Cannot track '{tool_name}' - Repository not initialized"
            )
            return

        # Create unique ID for this tool call
        timestamp = get_utc_timestamp()
        self._tool_call_counter += 1
        tool_call_id = f"toolcall:{timestamp}:{tool_name}:{self._tool_call_counter}"

        # Store in pending calls
        self._pending_tool_calls[tool_call_id] = {
            "tool_name": tool_name,
            "arguments": args,
            "timestamp": timestamp,
            "tool_call_id": tool_call_id,
        }

        logger.debug("Tracking tool call: %s -> %s", tool_name, tool_call_id)

    async def _on_tool_result(self, tool_name: str, result: str, status: str = None):
        """Handle tool result event - match with pending call and create ToolCall node."""
        logger.debug(f"Knowledge: Received TOOL_RESULT event for {tool_name}")

        # Skip tracking knowledge graph operations to prevent recursive logging
        if tool_name in self._KG_EXCLUDED_TOOLS:
            logger.debug(f"Knowledge: Skipping tracking for excluded tool: {tool_name}")
            return

        if not self.repository:
            logger.debug(
                f"Knowledge: Repository not initialized, cannot log tool result for '{tool_name}'"
            )
            return

        # Find the most recent pending call for this tool (FIFO matching)
        tool_call_id = None
        tool_call_data = None

        for tid, data in self._pending_tool_calls.items():
            if data["tool_name"] == tool_name:
                tool_call_id = tid
                tool_call_data = data
                break

        if not tool_call_id or not tool_call_data:
            logger.warning(
                "Received result for %s but no pending call found", tool_name
            )
            return

        # Remove from pending
        del self._pending_tool_calls[tool_call_id]

        # Determine if this was an error
        status = "error" if result.startswith("Error:") else "success"
        error_type = None
        if status == "error":
            # Try to extract error type from result
            match = re.match(r"Error: Tool '[^']+' failed: ([^:]+):", result)
            if match:
                error_type = match.group(1)

        # Create ToolCall node in knowledge graph
        await self._handle_tool_call(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments=tool_call_data["arguments"],
            result=result,
            status=status,
            timestamp=tool_call_data["timestamp"],
            error_type=error_type,
        )

        # Track this tool call for the current turn
        self._current_turn_tool_calls.append(
            {
                "tool_name": tool_name,
                "arguments": tool_call_data["arguments"],
                "result": result,
                "status": status,
                "error_type": error_type,
            }
        )

    async def handle_turn_complete(
        self,
        user_message: str,
        assistant_message: str,
        tool_calls: List[Dict[str, Any]],
    ):
        """Process a completed conversation turn.

        This should be called after MESSAGE_RECEIVED event with turn information.

        Args:
            user_message: The user's message
            assistant_message: The assistant's response
            tool_calls: List of tool calls made during this turn (not used - tracked via events)
        """
        logger.debug(
            "Knowledge: Processing turn complete (tools used: %d)", len(tool_calls)
        )

        # Note: Tool calls are now tracked via TOOL_USE and TOOL_RESULT events
        # No need to extract knowledge here

        # Handle auto-memory if enabled (just save transcript, no summarization/reflection)
        if not (self.auto_memory and self.repository):
            return

        if not self._mem_initialized:
            await self.initialize_transcript()

        if not self.repository:
            logger.error(
                "AutoMemory: Repository not initialized, skipping turn processing"
            )
            return

        self._turn_index += 1
        turn = self._turn_index

        # Build entry with tool call information
        entry = f"\\n[Turn {turn}]\\nUser: {user_message}\\n"

        # Add tool calls section if any occurred
        if self._current_turn_tool_calls:
            entry += f"\\n[Tool Calls: {len(self._current_turn_tool_calls)}]\\n"
            for tool_call in self._current_turn_tool_calls:
                # Create a summary of arguments (first few key-value pairs)
                args_summary = ""
                if tool_call["arguments"]:
                    args_items = list(tool_call["arguments"].items())[
                        :2
                    ]  # First 2 args
                    args_summary = ", ".join([f"{k}={v}" for k, v in args_items])
                    if len(tool_call["arguments"]) > 2:
                        args_summary += "..."

                # Truncate result for summary (first 100 chars)
                result_summary = (
                    tool_call["result"][:100] + "..."
                    if len(tool_call["result"]) > 100
                    else tool_call["result"]
                )

                entry += f"- {tool_call['tool_name']}({args_summary}) -> {tool_call['status']}\\n"
                entry += f"  Result: {result_summary}\\n"

        entry += f"\\nAssistant: {assistant_message}\\n"

        try:
            logger.debug("AutoMemory: Appending turn %d to transcript", turn)
            if self.repository:
                await self.repository.append_memory(
                    key=self._mem_transcript_key, content=entry
                )
            logger.info("AutoMemory: ✓ Appended Turn %d", turn)

            # Note: We don't re-associate here - transcript was associated during initialization
            # to avoid creating duplicate edges in the knowledge graph

            # Emit memory saved event
            await self.events.async_dispatch(
                KnowledgeEvents.MEMORY_SAVED, self._mem_transcript_key, entry
            )
        except Exception as e:
            logger.warning(
                "AutoMemory append failed: %s: %s",
                type(e).__name__,
                e,
            )

        # Clear tool calls for next turn
        self._current_turn_tool_calls.clear()

        # Emit turn processed event
        await self.events.async_dispatch(KnowledgeEvents.TURN_PROCESSED, turn)

    async def _on_summarized(self, summary: str, turn_count: int):
        """Handle bot summarized event: persist and link summary to session and transcript."""
        if not self.repository:
            logger.debug(
                "Knowledge: Repository not initialized; skipping summary persistence"
            )
            return

        try:
            # Persist summary content
            content = f"[Turns: {turn_count}]\n{summary}"
            await self.repository.save_memory(
                key=self._mem_summary_key,
                content=content,
                overwrite=True,
            )

            # Ensure ontology and nodes
            await self._ensure_ontology_structure()
            session_node_id = f"session:{self.session_id}"
            memory_summary_id = f"memory:{self._mem_summary_key}"
            memory_transcript_id = f"memory:{self._mem_transcript_key}"

            # Ensure session node exists
            await self.repository.add_node(
                node_id=session_node_id,
                node_type="Session",
                label=f"Session {self.session_id}",
                properties={"session_id": self.session_id},
            )

            # Ensure memory nodes exist in the graph
            await self._ensure_memory_in_graph(
                self._mem_summary_key, "Chat Session Summary"
            )
            await self._ensure_memory_in_graph(
                self._mem_transcript_key, "Chat Session Transcript"
            )

            # Auto-associate summary to concepts (e.g., Conversation)
            await self.auto_associate_memory(
                self._mem_summary_key, "Chat Session Summary"
            )

            # Link session -> summary and summary -> transcript
            await self.repository.add_edge(
                source_id=session_node_id,
                target_id=memory_summary_id,
                edge_type="HAS_SUMMARY",
            )
            await self.repository.add_edge(
                source_id=memory_summary_id,
                target_id=memory_transcript_id,
                edge_type="SUMMARIZES",
            )

            logger.info(
                "Knowledge: ✓ Persisted and linked session summary (%s)",
                self._mem_summary_key,
            )

            # Emit memory saved event
            await self.events.async_dispatch(
                KnowledgeEvents.MEMORY_SAVED, self._mem_summary_key, content
            )
        except Exception as e:
            logger.warning("Knowledge: Failed to persist/link summary: %s", e)

    async def initialize_transcript(self):
        """Initializes the session transcript in memory and links it to the session in the graph."""

        header = f"# Session {self.session_id}\\nStarted UTC: {_dt.datetime.utcnow().isoformat()}\\n"
        try:
            # Save transcript to memory using repository
            if self.repository:
                await self.repository.save_memory(
                    key=self._mem_transcript_key,
                    content=header,
                    overwrite=True,
                )
            logger.info(
                "AutoMemory: initialized transcript at %s",
                self._mem_transcript_key,
            )
            self._mem_initialized = True

            # Create session structure in knowledge graph
            if self.repository:
                await self._ensure_ontology_structure()

                session_node_id = f"session:{self.session_id}"
                memory_node_id = f"memory:{self._mem_transcript_key}"

                # Create session node
                await self.repository.add_node(
                    node_id=session_node_id,
                    node_type="Session",
                    label=f"Session {self.session_id}",
                    properties={
                        "session_id": self.session_id,
                        "started": _dt.datetime.utcnow().isoformat(),
                    },
                )

                # Link session to concept:session
                await self.repository.add_edge(
                    source_id="concept:session",
                    target_id=session_node_id,
                    edge_type="HAS_INSTANCE",
                )

                # Create memory node for transcript (already created by save_memory, but ensure it's linked)
                # Link session to transcript
                await self.repository.add_edge(
                    source_id=session_node_id,
                    target_id=memory_node_id,
                    edge_type="HAS_TRANSCRIPT",
                )

                logger.info("KG: Created session structure for %s", self.session_id)

            # Emit memory saved event
            await self.events.async_dispatch(
                KnowledgeEvents.MEMORY_SAVED, self._mem_transcript_key, header
            )
        except Exception as e:
            logger.warning(
                "AutoMemory init failed: %s: %s",
                type(e).__name__,
                e,
            )

    async def _handle_tool_call(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: str,
        status: str,
        timestamp: str,
        error_type: Optional[str] = None,
    ):
        """Create a ToolCall node in the knowledge graph with full details.

        Args:
            tool_call_id: Unique identifier for this tool call
            tool_name: Name of the tool that was called
            arguments: Arguments passed to the tool
            result: Result returned by the tool (or error message)
            status: "success" or "error"
            timestamp: When the call was made
            error_type: Type of exception if status is "error"
        """
        if not self.repository:
            return

        session_node_id = f"session:{self.session_id}"

        logger.info("KG: Indexing tool call: %s (status: %s)", tool_name, status)

        try:
            # Ensure ontology structure exists
            await self._ensure_ontology_structure()

            # Ensure session node exists
            logger.debug("KG: Creating/updating session node: %s", session_node_id)
            await self.repository.add_node(
                node_id=session_node_id,
                node_type="Session",
                label=f"Session {self.session_id}",
                properties={"session_id": self.session_id},
            )

            # Create ToolCall node with all details
            properties = {
                "tool_name": tool_name,
                "arguments": json.dumps(arguments, separators=(",", ":")),
                "result": result,  # Store full result without truncation
                "status": status,
                "timestamp": timestamp,
            }
            if error_type:
                properties["error_type"] = error_type

            logger.debug("KG: Creating ToolCall node: %s", tool_call_id)
            await self.repository.add_node(
                node_id=tool_call_id,
                node_type="ToolCall",
                label=f"{tool_name} ({status})",
                properties=properties,
            )

            # Link to concept:tool_usage
            logger.debug("KG: Linking ToolCall to concept:tool_usage")
            await self.repository.add_edge(
                source_id=tool_call_id,
                target_id="concept:tool_usage",
                edge_type="INSTANCE_OF",
            )

            # Link session to tool call
            logger.debug("KG: Linking session to ToolCall")
            await self.repository.add_edge(
                source_id=session_node_id,
                target_id=tool_call_id,
                edge_type="PERFORMED",
            )
        except Exception as e:
            logger.error(
                "KG: Failed to index tool call %s: %s: %s",
                tool_call_id,
                type(e).__name__,
                str(e),
                exc_info=True,
            )
            raise

        # If this is a file operation, also create File nodes and relationships
        file_operations = {
            "write_file": "MODIFIED",
            "append_file": "MODIFIED",
            "set_lines": "MODIFIED",
            "insert_lines": "MODIFIED",
            "read_file": "READ",
        }

        if tool_name in file_operations:
            path = arguments.get("path") or arguments.get("target_file")
            if path:
                file_id = f"file:{path}"

                # Create File node
                await self.repository.add_node(
                    node_id=file_id,
                    node_type="File",
                    label=path.split("/")[-1],
                )

                # Link file to concept:file
                await self.repository.add_edge(
                    source_id=file_id,
                    target_id="concept:file",
                    edge_type="INSTANCE_OF",
                )

                # Link tool call to file with appropriate edge type
                await self.repository.add_edge(
                    source_id=tool_call_id,
                    target_id=file_id,
                    edge_type=file_operations[tool_name],
                )

                logger.info(
                    "KG: ✓ Indexed: session:%s → toolcall:%s → %s → %s",
                    self.session_id,
                    tool_call_id,
                    file_operations[tool_name],
                    file_id,
                )
        else:
            logger.info(
                "KG: ✓ Indexed tool call: session:%s → %s (status: %s)",
                self.session_id,
                tool_call_id,
                status,
            )

    async def associate_memory_to_knowledge(
        self, memory_key: str, node_id: str, relationship: str = "RELATES_TO"
    ):
        """Associate a memory with a knowledge graph node.

        Args:
            memory_key: The memory key (e.g., "chat:session:123:transcript")
            node_id: The knowledge graph node ID
            relationship: The type of relationship (default: "RELATES_TO")
        """
        if not self.repository:
            logger.warning(
                "Knowledge repository not available, cannot associate memory"
            )
            return

        memory_node_id = f"memory:{memory_key}"

        # Create memory node (or get existing)
        node = await self.repository.get_node(memory_node_id)
        if not node:
            await self.repository.add_node(
                node_id=memory_node_id,
                node_type="Memory",
                label=memory_key,
                properties={"key": memory_key},
            )

        # Create edge from memory to knowledge node
        await self.repository.add_edge(
            source_id=memory_node_id,
            target_id=node_id,
            edge_type=relationship,
        )

        logger.info(
            "KG: Associated memory '%s' with node '%s' via '%s'",
            memory_key,
            node_id,
            relationship,
        )

    async def _ensure_ontology_structure(self):
        """Ensure basic ontology exists in the knowledge graph.

        Creates minimal concept structure:
        - concept:self (for bot identity - queried by bot)
        - concept:session (for session instances)
        - concept:file (for file instances)
        - concept:tool_usage (for tool call tracking)

        Background server handles deeper ontology.
        """
        if not self.repository:
            return

        try:
            logger.debug("KG: Ensuring basic ontology exists")

            # Create concept:self (required for bot identity queries)
            await self.repository.add_node(
                node_id="concept:self",
                node_type="Concept",
                label="Self",
                properties={"description": "Bot identity and core memories"},
            )

            # Create concept:session for session tracking
            await self.repository.add_node(
                node_id="concept:session",
                node_type="Concept",
                label="Session",
                properties={"description": "Chat sessions"},
            )

            # Create concept:file for file operations
            await self.repository.add_node(
                node_id="concept:file",
                node_type="Concept",
                label="File",
                properties={"description": "Files in the system"},
            )

            # Create concept:tool_usage for tool call tracking
            await self.repository.add_node(
                node_id="concept:tool_usage",
                node_type="Concept",
                label="Tool Usage",
                properties={"description": "Tool calls made by the bot"},
            )

            # Link tool_usage to self
            await self.repository.add_edge(
                source_id="concept:tool_usage",
                target_id="concept:self",
                edge_type="ASPECT_OF",
            )

            logger.debug(
                "KG: Ontology structure verified (self, session, file, tool_usage)"
            )
        except Exception as e:
            logger.warning("Failed to ensure ontology structure: %s", e)

    async def _ensure_memory_in_graph(self, memory_key: str, description: str = ""):
        """Ensure a memory node exists in the knowledge graph.

        This is idempotent - if the node already exists, it's updated.

        Args:
            memory_key: The memory key
            description: Optional description for the node label
        """
        if not self.repository:
            return

        memory_node_id = f"memory:{memory_key}"
        label = description or memory_key

        try:
            await self.repository.add_node(
                node_id=memory_node_id,
                node_type="Memory",
                label=label,
                properties={"key": memory_key},
            )
            logger.debug("KG: ✓ Ensured memory node exists: %s", memory_key)
        except Exception as e:
            logger.error("KG: Failed to create memory node '%s': %s", memory_key, e)

    async def auto_associate_memory(self, memory_key: str, description: str = ""):
        """Automatically associate a memory with relevant knowledge graph nodes.

        This analyzes the memory key and creates appropriate associations:
        - core:* memories → concept:self (direct link)
        - chat:lessons → concept:self + concept:learning
        - chat:session:* → concept:conversation (linked to self)
        - plans:* → concept:planning (linked to self)
        - goals:* → concept:goals (linked to self)
        - tasks:* → concept:tasks (linked to self)
        - tools:* → concept:capabilities (linked to self)

        All concepts are linked to concept:self so they're discoverable when loading from concepts.

        Args:
            memory_key: The memory key to associate
            description: Optional description for the memory node
        """
        if not self.repository:
            logger.debug(
                "KG: Skipping association for '%s' - no repository", memory_key
            )
            return

        logger.debug("KG: Auto-associating memory '%s'", memory_key)

        # Ensure ontology structure exists
        await self._ensure_ontology_structure()

        # Ensure the memory node exists
        await self._ensure_memory_in_graph(memory_key, description)

        memory_node_id = f"memory:{memory_key}"

        try:
            # Determine associations based on memory key prefix
            logger.debug("KG: Analyzing memory key prefix for '%s'", memory_key)
            if memory_key.startswith("core:"):
                # Core memories associate with self
                logger.info("KG: Linking '%s' → concept:self (RELATES_TO)", memory_key)
                await self.repository.add_edge(
                    source_id=memory_node_id,
                    target_id="concept:self",
                    edge_type="RELATES_TO",
                )
                logger.debug("KG: ✓ Associated %s with concept:self", memory_key)

            elif memory_key.startswith("chat:session:"):
                # Session transcripts/summaries associate with concept:conversation
                logger.info("KG: Linking '%s' → concept:conversation", memory_key)
                # First ensure concept:conversation exists
                await self.repository.add_node(
                    node_id="concept:conversation",
                    node_type="Concept",
                    label="Conversation",
                    properties={"description": "Conversation history and context"},
                )
                # Link conversation to self
                await self.repository.add_edge(
                    source_id="concept:conversation",
                    target_id="concept:self",
                    edge_type="ASPECT_OF",
                )
                await self.repository.add_edge(
                    source_id=memory_node_id,
                    target_id="concept:conversation",
                    edge_type="INSTANCE_OF",
                )
                logger.debug(
                    "KG: ✓ Associated %s with concept:conversation", memory_key
                )

            elif memory_key.startswith("chat:lessons"):
                # Lessons associate with both self and learning
                logger.info(
                    "KG: Linking '%s' → concept:self + concept:learning", memory_key
                )
                await self.repository.add_edge(
                    source_id=memory_node_id,
                    target_id="concept:self",
                    edge_type="INFORMS",
                )
                # Also create concept:learning
                await self.repository.add_node(
                    node_id="concept:learning",
                    node_type="Concept",
                    label="Learning",
                    properties={"description": "Accumulated knowledge and insights"},
                )
                # Link learning to self
                await self.repository.add_edge(
                    source_id="concept:learning",
                    target_id="concept:self",
                    edge_type="ASPECT_OF",
                )
                await self.repository.add_edge(
                    source_id=memory_node_id,
                    target_id="concept:learning",
                    edge_type="CONTRIBUTES_TO",
                )
                logger.debug("KG: ✓ Associated %s with learning and self", memory_key)

            elif memory_key.startswith("plans:"):
                # Plans associate with concept:planning
                await self.repository.add_node(
                    node_id="concept:planning",
                    node_type="Concept",
                    label="Planning",
                    properties={"description": "Plans and strategies"},
                )
                # Link planning to self
                await self.repository.add_edge(
                    source_id="concept:planning",
                    target_id="concept:self",
                    edge_type="ASPECT_OF",
                )
                await self.repository.add_edge(
                    source_id=memory_node_id,
                    target_id="concept:planning",
                    edge_type="INSTANCE_OF",
                )
                logger.debug("KG: Associated %s with concept:planning", memory_key)

            elif memory_key.startswith("goals:"):
                # Goals associate with concept:goals
                await self.repository.add_node(
                    node_id="concept:goals",
                    node_type="Concept",
                    label="Goals",
                    properties={"description": "Objectives and aspirations"},
                )
                # Link goals to self
                await self.repository.add_edge(
                    source_id="concept:goals",
                    target_id="concept:self",
                    edge_type="ASPECT_OF",
                )
                await self.repository.add_edge(
                    source_id=memory_node_id,
                    target_id="concept:goals",
                    edge_type="INSTANCE_OF",
                )
                logger.debug("KG: Associated %s with concept:goals", memory_key)

            elif memory_key.startswith("tasks:"):
                # Tasks associate with concept:tasks
                await self.repository.add_node(
                    node_id="concept:tasks",
                    node_type="Concept",
                    label="Tasks",
                    properties={"description": "Active tasks and work items"},
                )
                # Link tasks to self
                await self.repository.add_edge(
                    source_id="concept:tasks",
                    target_id="concept:self",
                    edge_type="ASPECT_OF",
                )
                await self.repository.add_edge(
                    source_id=memory_node_id,
                    target_id="concept:tasks",
                    edge_type="INSTANCE_OF",
                )
                logger.debug("KG: Associated %s with concept:tasks", memory_key)

            elif memory_key.startswith("tools:"):
                # Tools/capabilities associate with concept:capabilities
                await self.repository.add_node(
                    node_id="concept:capabilities",
                    node_type="Concept",
                    label="Capabilities",
                    properties={"description": "Tools and capabilities"},
                )
                # Link capabilities to self
                await self.repository.add_edge(
                    source_id="concept:capabilities",
                    target_id="concept:self",
                    edge_type="ASPECT_OF",
                )
                await self.repository.add_edge(
                    source_id=memory_node_id,
                    target_id="concept:capabilities",
                    edge_type="INSTANCE_OF",
                )
                logger.debug("KG: Associated %s with concept:capabilities", memory_key)

        except Exception as e:
            logger.warning("Failed to auto-associate memory %s: %s", memory_key, e)
