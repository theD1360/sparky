# Textual Client (`client/textual_client.py`)

This module provides a rich, interactive command-line interface for chatting with the Sparky, built using the `textual` framework. It connects to the main `chat_server.py` over WebSockets and provides a user-friendly way to interact with the bot in a local development environment.

**Location:** `src/client/textual_client.py` - Part of the `client` package for better organization.

## Key Features

*   **Rich Interface:** Uses the `textual` library to create a modern, responsive terminal UI that goes beyond a simple text prompt.
*   **Dual-Panel View:** The screen is split into two main sections:
    *   **Chat Log:** Displays the conversation history with the bot, including user messages, bot responses, and status updates.
    *   **Tool Activity Log:** Shows a real-time stream of the bot's internal operations, such as tool calls, tool results, and thoughts. This is invaluable for debugging and understanding the bot's reasoning process.
*   **WebSocket Communication:** Communicates with the server using the WebSocket protocol, allowing for real-time, bidirectional message passing.
*   **Automatic Reconnection:** If the connection to the server is lost, the client will automatically try to reconnect with an exponential backoff strategy.
*   **Session Management:** Can connect to a specific session ID, allowing you to resume a previous conversation.
*   **Dedicated Logging:** It has its own logger (`sparky.client`) that writes to a separate `client.log` file, keeping client-side and server-side logs distinct.

## Core Components

### `ChatApp`

This is the main `textual` application class that orchestrates the entire UI.

*   **Layout (`compose`)**: Defines the visual layout of the application, including the two main scrollable panels (`ChatLog` and `InfoLog`) and the text input area.
*   **WebSocket Handling (`_connect_and_run`)**: This is the main background task. It connects to the server, sends the initial `connect` handshake (including any session ID), and then enters a loop to listen for incoming messages.
*   **Message Parsing**: It deserializes incoming JSON messages into `WSMessage` objects and dispatches them to the appropriate UI component based on their `MessageType`.
*   **UI Updates (`_drain_incoming`)**: It uses an internal `asyncio.Queue` to decouple the network receiver from the UI. A timer periodically drains this queue and updates the `ChatLog` and `InfoLog` widgets with new events.
*   **User Input (`on_text_area_submitted`)**: When the user sends a message, it echoes the message to the local `ChatLog`, sends it to the server over the WebSocket, and clears the input field.

### `ChatLog` and `InfoLog`

These are custom `textual` widgets that extend `Static`. They are responsible for rendering the color-coded, formatted messages in their respective panels. They use the `rich` library's `Markdown` and `Text` objects to create visually appealing output.

### `run_textual_client()`

This is the main entry point function. It creates an instance of the `ChatApp` and runs it.

## Communication Protocol

The client adheres to the WebSocket protocol defined in `models/websocket.py`. It sends `message` and `connect` messages and is capable of receiving and displaying all message types sent by the server, including `message`, `status`, `error`, `tool_use`, `tool_result`, and `thought`.
