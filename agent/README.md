# Documentation

Sparky is a powerful AI assistant.

## Getting Started

To get Sparky running, follow these steps:

1.  **Clone the repository:** `git clone <repository_url>`
2.  **Install dependencies:** `poetry install`
3.  **Configure API keys:** Set the necessary API keys in the `.env` file.
4.  **Run the server:** `sparky chat start` or `docker-compose up`
5.  **Connect to bot:** `sparky client start` or use the web UI

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Features

- **Knowledge Graph**: Store and retrieve information using a graph-based memory system
- **MCP Integration**: Connect to multiple MCP (Model Context Protocol) servers for extended capabilities
- **Command Middleware**: Use slash commands (like `/discover_concept Python`) to invoke MCP prompts
- **Task Management**: Queue and manage tasks with dependencies
- **Middleware System**: Intercept and modify messages and tool calls
- **Event System**: Subscribe to bot events for custom behavior

## Table of Contents

*   [Architecture](docs/architecture/architecture.md): Details about Sparky's internal architecture and components.
*   [Message Middleware](docs/middleware/MESSAGE_MIDDLEWARE.md): Intercept and modify user messages with middleware.
*   [Quick Start: Command Middleware](docs/middleware/QUICK_START_MIDDLEWARE.md): 5-minute guide to slash commands.
*   [Knowledge Graph](docs/knowledge_graph/knowledge_graph.md): Description of Sparky's knowledge graph and how it is used for reasoning and information retrieval.

## Examples

Here are a few examples of how to interact with Sparky:

*   "What is your purpose?"
*   "Analyze my recent performance and suggest areas for improvement."
*   "Summarize the key points from our last conversation."
*   "What tools can you use to help me with research?"

This is a test append.