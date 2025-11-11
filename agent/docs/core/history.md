# Conversation History Management

The `HistoryManager` class in `src/sparky/history.py` is responsible for managing the conversation history for the agent. It is designed to prevent the history from growing indefinitely by using a sliding window mechanism.

## How it Works

The manager uses a Python `deque` (double-ended queue) to store conversation turns. When the number of turns exceeds the configured maximum, the oldest turns are automatically dropped from the history. This ensures that the context sent to the language model remains within a manageable size.

Each "turn" consists of a user message and a model response. So, a `max_turns` setting of 30 will actually store 60 messages (30 user, 30 model).

## Key Features

- **Sliding Window**: Automatically discards the oldest messages to keep the history size fixed.
- **Configurable Length**: The maximum number of turns can be set using the `SPARKY_MAX_TURNS` environment variable.
- **Summarization**: Includes methods to replace the entire history with a summary, which is crucial for maintaining context over long conversations.

## Configuration

You can configure the history length by setting the following environment variable:

- `SPARKY_MAX_TURNS`: The maximum number of conversation turns to retain. Defaults to `30`.

Example:
```bash
export SPARKY_MAX_TURNS=50
```
