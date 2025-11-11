# Documentation

Sparky is an AI assistant designed for self-improvement and collaborative problem-solving. It leverages a knowledge graph, memory management, and various tools to assist users with a wide range of tasks. Sparky is built with the goal of continuous learning and adaptation, striving to become a more helpful and insightful partner over time.


## Getting Started

To get Sparky running, follow these steps:

1.  **Clone the repository:** `git clone <repository_url>`
2.  **Install dependencies:** `poetry install`
3.  **Configure API keys:** Set the necessary API keys in the `.env` file.
4.  **Run the bot:** `sparky server start` or `docker-compose up`
5. **Connect to bot:**: `sparky client start`

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

*   [Architecture Overview](docs/architecture_overview.md): High-level overview of Sparky's internal architecture and components.
*   [Identity](docs/identity.md): Details about Sparky's self-perception, values, and capabilities.
*   [Context Management](docs/context_management.md): Explanation of how Sparky manages and utilizes context during conversations and tasks.
*   [Message Middleware](docs/MESSAGE_MIDDLEWARE.md): Intercept and modify user messages with middleware.
*   [Quick Start: Command Middleware](docs/QUICK_START_MIDDLEWARE.md): 5-minute guide to slash commands.

## Examples

Here are a few examples of how to interact with Sparky:

*   "What is your purpose?"
*   "Analyze my recent performance and suggest areas for improvement."
*   "Summarize the key points from our last conversation."
*   "What tools can you use to help me with research?"

*   [Tool Usage](docs/tool_usage.md): Information on the tools Sparky can use and how they are employed to accomplish tasks.
*   [Knowledge Graph](docs/knowledge_graph.md): Description of Sparky's knowledge graph and how it is used for reasoning and information retrieval.