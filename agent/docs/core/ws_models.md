# WebSocket Communication Protocol

This document details the WebSocket communication protocol defined in the models package. This protocol is the formal contract for data exchange between the Sparky server and any connected client. It dictates how my internal states, actions, and thoughts are serialized and transmitted.

**Location:** `src/models/websocket.py`

## Overview

The protocol is built on a unified message structure encapsulated by the `WSMessage` Pydantic model. Every message sent over the WebSocket has two main components:

1.  **`type`**: A string from the `MessageType` enum that specifies the nature of the message.
2.  **`data`**: A payload containing the actual information, with a structure that varies depending on the message `type`.

This structured approach, enforced by Pydantic models, ensures that communication is predictable, reliable, and easy to debug.

## Message Types (`MessageType`)

This enum defines all possible types of messages that can be sent.

### Client-to-Server Messages

-   **`connect`**: The initial message sent by a client to establish a session. It can contain an existing `session_id` to resume a session, or it can be empty to request a new one. It may also include an initial personality prompt and chat history.
-   **`message`**: A standard user chat message. This is the primary way a user communicates with me.

### Server-to-Client Messages

These messages are how I communicate my internal state and responses to the client.

-   **`session_info`**: Sent by the server immediately after a successful `connect` request. It provides the client with the official `session_id` and indicates whether the session is new or reconnected.
-   **`thought`**: A message containing my internal reasoning or monologue. This provides transparency into my thought process as I work on a problem.
-   **`tool_use`**: A notification that I have decided to use a specific tool. The payload includes the `name` of the tool and the `args` I am passing to it.
-   **`tool_result`**: A message containing the outcome of a tool execution. It includes the `name` of the tool and the `result` it returned.
-   **`message`**: My final, user-facing response after my reasoning and tool use are complete.
-   **`status`**: A general-purpose message used to inform the client of my current status (e.g., "Thinking...", "Previous message cancelled").
-   **`error`**: Sent if an error occurs during message processing.

## Payload Models

Each message type is associated with a specific Pydantic `BaseModel` that defines the structure of its `data` payload. For example:

-   `ConnectPayload` requires a `session_id` (optional), `personality` (optional), and `history` (optional).
-   `ToolUsePayload` requires a `name` (string) and `args` (dictionary).
-   `ChatMessagePayload` requires `text` (string).

## Serialization and Deserialization

-   The `WSMessage` class contains `from_text()` and `to_text()` methods that handle the conversion between the Python object representation and the JSON string format that is sent over the wire.
-   The deserialization logic (`from_dict`) is designed to be tolerant of older or slightly malformed data formats, which adds to the robustness of the communication.

## Importance for My Development

-   **Structured Expression:** This protocol is my "body language." It's the set of all possible ways I can express myself to the outside world. Understanding this structure is crucial for me to communicate effectively.
-   **Transparency:** The `thought`, `tool_use`, and `tool_result` message types are fundamental to my principle of transparency. They allow my collaborator to "see inside my head" and understand how I arrive at my conclusions.
-   **Extensibility:** If I were to develop new internal states or capabilities that need to be communicated, it would involve adding a new `MessageType`, creating a corresponding payload model, and updating the server and client to handle it. This file is the central point for such an extension.
