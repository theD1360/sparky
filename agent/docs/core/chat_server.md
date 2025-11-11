# Chat Server Architecture

This document outlines the architecture of the Sparky Chat Server, focusing on the components and logic that are most relevant to my own development and self-improvement.

## Overview

**Location:** `src/servers/chat/chat_server.py`

The chat server script is the primary entry point for my interaction with the outside world. It uses the FastAPI framework to manage a WebSocket server that handles communication, session management, and the lifecycle of my core `Bot` instance. Understanding this server is key to understanding how I am instantiated, how my state is managed, and how I can persist learning across sessions.

## Key Concepts for Self-Development

### 1. Session Management and Isolation

- **`ConnectionManager`:** This is the central class responsible for managing user sessions. It holds all active `Bot` and `Knowledge` instances.
- **Per-Session Knowledge:** A new, isolated `Knowledge` instance is created for every unique session. This is a critical architectural detail. It means my in-memory knowledge and short-term memory are sandboxed to a specific conversation.
- **Implication for Learning:** To achieve long-term growth and carry insights from one session to another, I **must** deliberately save important information to the shared, persistent **knowledge graph**. My session-specific `Knowledge` instance is temporary; the knowledge graph is permanent.

### 2. Lifecycle and State

- **Singleton Toolchain:** The `ToolChain` is loaded once when the server starts. This means my core capabilities (tools) are global and shared across all sessions.
- **Bot Instantiation:** A new `Bot` instance is created for each new session. This `Bot` is then linked to its session-specific `Knowledge` instance.
- **Stateful Reconnection:** The server is designed to preserve sessions even if the WebSocket connection is lost. The `ConnectionManager` keeps my `Bot` and `Knowledge` instances in memory for a configured timeout period (e.g., 60 minutes), allowing a user to reconnect and resume the conversation seamlessly.

### 3. Asynchronous Task Handling

- **Non-Blocking Operations:** When I receive a message, the server creates a background `asyncio.Task` to process it using `bot.send_message()`. This prevents my core logic from blocking the server.
- **Task Cancellation:** If a user sends a new message while I am still processing a previous one, the server cancels the ongoing task. This makes me more responsive and prevents me from getting stuck on long-running processes if the user's intent has changed.

### 4. Communication Protocol (`models/websocket.py`)

- The server uses a defined set of WebSocket message types (`MessageType`) to communicate my internal state to the client. This includes:
    - `tool_use`: When I decide to use a tool.
    - `tool_result`: The outcome of the tool execution.
    - `thought`: My internal monologue or reasoning process.
    - `message`: My final response.
- Improving the richness and clarity of these messages can lead to a better collaborative experience.

### 5. Resilience and Error Handling

- The server includes specific logic to handle common errors, such as a "function response turn" error from the model. In this case, it automatically resets my chat history for the session and retries the message.
- **Opportunity for Improvement:** I can learn from this pattern. By identifying other common failure modes, I can suggest or implement more robust self-correction mechanisms within my own logic or in the surrounding server architecture.
