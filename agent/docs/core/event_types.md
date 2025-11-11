# Event Types (`event_types.py`)

This module is the central hub for all event type definitions used within the Sparky system. Centralizing these event names prevents circular import issues and provides a clear overview of the types of messages that flow through the application's event bus.

These events are used to communicate between different components, such as the `Bot`, the `Knowledge` module, and the `TaskQueue`, without creating direct dependencies between them.

## `BotEvents`

This class contains events directly related to the bot's core operations and its interaction with the user.

*   `LOAD`: Triggered when the bot's initial state and identity have been loaded at the start of a session.
*   `CHAT_STARTED`: Fired when a new chat session is initiated.
*   `MESSAGE_SENT`: Fired when the bot sends a message to the user.
*   `MESSAGE_RECEIVED`: Fired when the bot receives a message from the user.
*   `TURN_COMPLETE`: Indicates that a full cycle of user message -> bot response has been completed.
*   `TOOL_USE`: Triggered when the bot decides to use a tool. The event data includes the tool name and its arguments.
*   `TOOL_RESULT`: Fired when a tool has finished execution, containing the result of the operation.
*   `THOUGHT`: Emitted when the bot has an internal thought or reasoning step.
*   `SUMMARIZED`: Fired when a conversation turn or session has been successfully summarized.

## `KnowledgeEvents`

This class defines events related to the `Knowledge` module, which handles memory, learning, and reflection.

*   `MEMORY_LOADED`: Fired when a memory is loaded from the knowledge graph.
*   `MEMORY_SAVED`: Fired when a new memory is saved to the knowledge graph.
*   `TURN_PROCESSED`: Indicates that the `Knowledge` module has processed a completed conversation turn.
*   `REFLECTION_STARTED`: Triggered when the bot begins a metacognitive reflection process.
*   `REFLECTION_COMPLETED`: Fired when the reflection process is complete, often including the insights gained.
*   `SUMMARIZATION_STARTED`: Triggered when the `Knowledge` module begins the process of summarizing a text.
*   `SUMMARIZATION_COMPLETED`: Fired when the summarization is complete.
*   `KNOWLEDGE_EXTRACTED`: Indicates that a new piece of structured knowledge (e.g., a node or edge) has been extracted and added to the knowledge graph.

## `TaskEvents`

This class contains events related to the background `TaskQueue`.

*   `TASK_ADDED`: Fired when a new task is added to the queue.
*   `TASK_AVAILABLE`: Indicates that there is a task in the queue ready to be processed.
*   `TASK_STARTED`: Triggered when a background worker picks up and starts a task.
*   `TASK_COMPLETED`: Fired when a task is successfully completed.
*   `TASK_FAILED`: Fired if a task fails during execution.
*   `TASK_STATUS_CHANGED`: A general event that is fired whenever a task's status changes (e.g., from `pending` to `in_progress`).
