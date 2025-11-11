# Code Organization

This document outlines the current organization of the Sparky codebase after the restructuring to improve modularity and separation of concerns.

## Directory Structure

### Core Application (`src/sparky/`)

The core bot logic and foundational components:

- `bot.py` - Main Bot class and orchestration
- `knowledge.py` - Knowledge graph integration and memory management
- `history.py` - Session history management
- `initialization.py` - System initialization and setup
- `task_queue.py` - Task queue management (stores tasks in knowledge graph)
- `scheduled_tasks.py` - Scheduled task definitions and loading
- `middleware.py` - Request/response middleware (e.g., SelfModificationGuard)
- `event_types.py` - Event type definitions
- `async_util.py` - Async utility functions
- `constants.py` - Application constants
- `logging_config.py` - Logging configuration
- `tool_registry.py` - Tool registration and discovery

### Servers (`src/servers/`)

Server implementations for different interaction modes:

#### Chat Server (`src/servers/chat/`)
- `chat_server.py` - FastAPI WebSocket server for interactive chat
- `__init__.py` - Exports `ChatServer` (app), `ConnectionManager`

#### Task Server (`src/servers/task/`)
- `task_server.py` - AgentLoop for background task processing
- `__init__.py` - Exports `TaskServer` (AgentLoop), `run_agent_loop`

### Client (`src/client/`)

Client implementations for connecting to servers:

- `textual_client.py` - Rich terminal UI client using Textual framework
- `__init__.py` - Exports `ChatApp`, `run_textual_client`

### Models (`src/models/`)

Centralized Pydantic models for data validation:

- `websocket.py` - WebSocket message models (WSMessage, payloads)
- `enums.py` - Shared enumerations (MessageType, ResponseStatus)
- `mcp.py` - MCP (Model Context Protocol) models
- `__init__.py` - Exports all models for easy importing

### CLI (`src/cli/`)

Command-line interface for managing the system:

- `server.py` - Server management commands (start, stop, restart)
- `client.py` - Client commands (start client)
- `agent.py` - Agent/task management commands
- `db.py` - Database management commands
- `generate.py` - Code generation utilities
- `utils.py` - CLI utility functions
- `common.py` - Common CLI functionality
- `models.py` - CLI-specific models

### Tools (`src/tools/`)

MCP tool servers organized by category:

- `advanced_networking/` - Advanced networking tools
- `calculator/` - Calculator tools
- `code/` - Code editing and analysis tools
- `criminal_ip/` - Criminal IP integration
- `encryption/` - Encryption/decryption tools
- `filesystem/` - File system operations
- `git_tool/` - Git operations
- `introspection/` - System introspection
- `knowledge_graph/` - Knowledge graph operations
- `linter/` - Code linting
- `miscellaneous/` - Miscellaneous utilities
- `network/` - Network operations
- `self_correction/` - Self-correction capabilities
- `self_update/` - Self-update functionality
- `shell/` - Shell command execution
- `strings/` - String manipulation

### Utilities (`src/utils/`)

Shared utility modules:

#### File Operations (`src/utils/file_ops/`)
- `diff_edit.py` - Tolerant file editing with whitespace/indentation handling
- `search_replace.py` - Search-replace parsing and validation
- `__init__.py` - Exports file operation functions

#### Event System (`src/utils/events/`)
- Event bus and event handling utilities

### Database (`src/database/`)

Database models, migrations, and utilities:

- `database.py` - Database connection and setup
- `models.py` - SQLAlchemy models
- `repository.py` - Data access layer
- `embeddings.py` - Vector embedding utilities
- `migrations/` - Alembic database migrations
- `opencypher/` - OpenCypher query support

### MCP Integration (`src/badmcp/`)

Model Context Protocol integration layer:

- `tool_chain.py` - Tool chain orchestration
- `control.py` - Tool server control
- `server.py` - MCP server implementation
- `tool_client.py` - MCP tool client
- `config.py` - MCP configuration
- `validate_config.py` - Configuration validation
- `interfaces/` - MCP interface definitions
- `transform/` - Data transformation utilities

## Key Organizational Principles

1. **Separation of Concerns**: Clear boundaries between core logic, servers, clients, and utilities
2. **Modularity**: Each package has a focused responsibility
3. **Centralized Models**: All Pydantic models in `src/models/` for consistency
4. **Server Isolation**: Different server types (chat, task) are independently deployable
5. **Reusable Utilities**: Common functionality extracted to `src/utils/`
6. **Tool Server Pattern**: All tools follow MCP server pattern for consistency

## Import Patterns

### Recommended Imports

```python
# Models - use centralized models package
from models import WSMessage, MessageType, ChatMessagePayload

# Client components
from client import ChatApp, run_textual_client

# Server components
from servers.chat import ChatServer, ConnectionManager
from servers.task import TaskServer, AgentLoop, run_agent_loop

# Core bot functionality
from sparky.bot import Bot
from sparky.knowledge import Knowledge
from sparky.task_queue import create_task_queue

# File operations
from utils.file_ops import search_replace_edit_file
```

### Backward Compatibility

For backward compatibility, the server `__init__.py` files provide aliases:
- `TaskServer` → `AgentLoop`
- `ChatServer` → `app` (FastAPI instance)

## Migration Notes

### Previous Structure → New Structure

- `src/sparky/chat_server.py` → `src/servers/chat/chat_server.py`
- `src/sparky/task_server.py` → `src/servers/task/task_server.py`
- `src/sparky/textual_client.py` → `src/client/textual_client.py`
- `src/sparky/ws_models.py` → `src/models/websocket.py`
- `src/sparky/file_ops/` → `src/utils/file_ops/`
- `src/tools/mcp_response.py` → `src/models/mcp.py`

### Breaking Changes

If you have code that imports from the old locations, update your imports:

```python
# OLD (deprecated)
from sparky.textual_client import run_textual_client
from sparky.ws_models import WSMessage

# NEW (recommended)
from client import run_textual_client
from models import WSMessage
```

## Future Improvements

Areas for potential future refinement:

1. Consider moving `task_queue.py` to `src/servers/task/` for better cohesion
2. Evaluate if some `sparky/` modules could be further organized into subpackages
3. Create a unified testing structure that mirrors the source organization
4. Document API contracts between layers more explicitly

