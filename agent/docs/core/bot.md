# Bot Architecture (`bot.py`)

The `Bot` class, defined in `src/sparky/bot.py`, is the central orchestrator of the agent. It integrates all major components, including the generative AI model, toolchain, conversation history, and the knowledge base, to create a cohesive and intelligent system.

## Core Components

The bot's functionality is built upon several key modules:

- **Google Generative AI (`genai`)**: The underlying language model (e.g., Gemini 1.5 Pro) that provides reasoning and language capabilities.
- **`ToolChain`**: A collection of all available tools the bot can use to interact with its environment (e.g., file system, shell commands).
- **`HistoryManager`**: Manages the short-term conversation history, using a sliding window to keep the context size manageable.
- **`Knowledge`**: Provides the long-term memory and context for the bot. It's responsible for loading the bot's identity, searching for relevant information, and learning from interactions.
- **`Events`**: A system for decoupled communication between the bot's components. For example, events are dispatched for tool usage, message sending, and thoughts, allowing other modules (like `Knowledge`) to observe and react.

## The Lifecycle of a Message

When a user sends a message to the bot, it goes through a sophisticated processing pipeline:

1.  **Context Pre-search**: Before sending the user's message to the model, the `Bot` queries the `Knowledge` module. It performs a vector search on its memory to find relevant context, which is then prepended to the user's prompt. This enriches the prompt with pertinent information from past interactions.
2.  **Query Optimization**: For long or ambiguous queries, the bot first uses the LLM to clarify and summarize the user's intent. This sharpened query is then used for the vector search, improving the quality of the retrieved context.
3.  **Sending to Model**: The enhanced message (context + original message) is sent to the Gemini model.
4.  **Tool-Calling Loop**: If the model determines that it needs to use one or more tools, the `_handle_tool_calls` method is invoked.
    - The bot can handle multiple tool calls in parallel, executing them concurrently using `asyncio.gather` for maximum efficiency.
    - It logs the model's reasoning or "thinking" text that often precedes a tool call.
    - Once all tools have been executed, their results are collected and sent back to the model in a single response.
    - The loop continues until the model can generate a final text response without needing more tools.
5.  **Final Response**: The bot extracts the final text from the model's response.
6.  **Knowledge Integration**: The full turn (user message, tool calls, and final response) is passed to the `Knowledge` module's `handle_turn_complete` method, where the information is processed and integrated into the long-term knowledge graph.

## Identity and Session Management

The bot is designed to be stateful and aware of its own identity.

-   When a new conversation starts (`start_chat`), the bot queries the `Knowledge` module to load its core identity (`get_identity_memory()`) and any relevant context from past sessions (`get_session_context()`).
-   This information is injected into the chat history as the very first messages, effectively "priming" the model with a sense of self and purpose before it ever sees a user prompt.

## Long-Term Conversation Management

To avoid exceeding the model's context window limit, the bot implements an automatic summarization and restart mechanism.

-   When a conversation grows beyond a configurable threshold (`summary_turn_threshold`), the `_summarize_and_restart` method is triggered.
-   It uses the LLM to create a concise summary of the conversation so far.
-   It then **restarts the chat session**, creating a fresh history that includes the re-injected identity, session context, and the new summary. This process effectively condenses the conversational history while preserving essential context, allowing for virtually endless interactions.
