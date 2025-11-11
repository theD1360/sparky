# Context Management

My context is managed according to the following model:

**1. Identity:**
* Source: `Core Identity` memory.
* Usage: Loaded at the beginning of each session. Informs responses and guides actions.
* Update Mechanism: Manual or through self-reflection.

**2. Session History:**
* Source: `cognition:trace` memories.
* Storage: Individual memory nodes, linked by `session_id`.
* Retrieval: `list_memories` with `cognition:trace` prefix.
* Usage: Provides context, allows learning from past mistakes.

**3. Knowledge Graph:**
* Structure: Nodes and edges representing concepts, memories, and relationships.
* Purpose: Stores facts, relationships, and learned patterns.
* Integration: New information is integrated automatically.

**4. Core Directives:**
* Source: Code and instructions.
* Usage: Guides behavior.
* Update Mechanism: Code updates.
* Storage: Not explicitly stored as a memory.

**Information Flow:**
1. Session Start: Load `Core Identity`.
2. Task Execution: Reason, plan tool calls, and execute.
3. Observation: Observe results.
4. Integration: Integrate into knowledge graph. Create `cognition:trace`.
5. Self-Reflection: Periodically reflect on actions and identity.

Session history is stored as `cognition:trace` memories, linked by the `session_id`. I can retrieve recent traces using `list_memories` with the `cognition:trace` prefix.

My memory is used to store and access knowledge. It is organized as a key-value store, where keys are unique identifiers and values are text strings.