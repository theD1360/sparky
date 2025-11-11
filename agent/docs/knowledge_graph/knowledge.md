# Knowledge Module (`knowledge.py`)

The `Knowledge` class, defined in `src/sparky/knowledge.py`, serves as the bot's long-term memory and cognitive architecture. It operates independently from the `Bot` class, communicating via an event-driven system to ensure a clean separation of concerns. Its primary responsibilities include identity management, context retrieval, and learning from interactions by building a comprehensive knowledge graph.

## Core Responsibilities

-   **Identity Loading**: At the start of a new chat session, the `Knowledge` module is responsible for loading the bot's core identity. It does this by querying the knowledge graph for the `concept:self` node and its directly connected nodes, assembling a rich "identity document" that primes the language model.
-   **Contextual Pre-search**: Before the bot processes any user message, the `Knowledge` module performs a vector search on its memory. It finds the most relevant pieces of information from the past and prepends them to the user's prompt, providing immediate and relevant context.
-   **Event-Driven Learning**: The module subscribes to events published by the `Bot` (e.g., `TOOL_USE`, `TOOL_RESULT`, `SUMMARIZED`). By observing these events, it can build a detailed record of the bot's actions and their outcomes without being tightly coupled to the bot's internal logic.
-   **Knowledge Graph Construction**: All significant events are indexed in a knowledge graph. This includes:
    -   **Sessions**: Each conversation is a `Session` node.
    -   **Tool Calls**: Every tool execution is logged as a `ToolCall` node, linked to the session in which it was used. This creates an auditable trail of actions.
    -   **File Operations**: When tools like `read_file` or `write_file` are used, the module creates `File` nodes and links them to the tool calls, tracking how files are modified over time.
    -   **Memories**: Transcripts and summaries are stored as `Memory` nodes and linked to their respective sessions.
-   **Automatic Association**: The module intelligently associates new memories with relevant concepts in the knowledge graph. For example, a memory saved with the key `chat:lessons` is automatically linked to the `concept:learning`, which in turn is an aspect of `concept:self`. This allows the bot's understanding of itself to grow organically.

## How Identity is Loaded

The `get_identity_memory` method is a cornerstone of the bot's self-awareness. It works as follows:

1.  It retrieves the central `concept:self` node from the knowledge graph.
2.  It traverses the graph to find all directly connected nodes (neighbors).
3.  It collects the `content` from all these nodes.
4.  It assembles this content into a structured markdown document, grouped by node type (e.g., `Concept`, `Memory`, `Insight`).

This final document is what the bot "reads" at the start of a session to understand who it is, what its purpose is, and what it has learned.

## Tool Call and Knowledge Indexing

The `Knowledge` module maintains a list of "excluded tools" (`_KG_EXCLUDED_TOOLS`), which are primarily tools that interact directly with the knowledge graph itself (e.g., `add_node`, `search_memory`). This prevents infinite recursive logging loops where, for instance, the act of logging a tool call would trigger another tool call to be logged.

When a non-excluded tool is used, the module creates a `ToolCall` node and links it to the current `Session` node, creating a rich, interconnected history of the bot's actions and the context in which they were performed.
