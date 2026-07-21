# Sparky AI Agent 🤖

Sparky is an autonomous AI assistant powered by Google's Gemini models, designed for continuous learning, self-improvement, and collaborative problem-solving. Built with a sophisticated knowledge graph and memory management system, Sparky provides intelligent assistance while adapting and growing through interactions.

## ✨ Key Features

- **🧠 Knowledge Graph**: Store and retrieve information using a graph-based memory system with vector embeddings
- **🔌 MCP Integration**: Connect to multiple Model Context Protocol (MCP) servers for extended capabilities
- **⚡ Smart Context Management**: Token-based context window optimization with automatic summarization
- **🎯 Task Management**: Queue and manage tasks with dependencies and scheduling
- **🔧 Middleware System**: Extensible middleware for intercepting and modifying messages and tool calls
- **📊 Reflection & Learning**: Periodic self-reflection and concept discovery for continuous improvement
- **💬 Web UI**: Modern React-based chat interface for seamless interaction
- **🗄️ PostgreSQL + pgvector**: Persistent storage with vector similarity search

## 🚀 Quick Start

### Prerequisites

- **Docker & Docker Compose** (recommended)
- **Google API Key** - Get yours at [Google AI Studio](https://aistudio.google.com/app/apikey)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository_url>
   cd BadRobot
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your Google API key:
   ```env
   GOOGLE_API_KEY=your_google_api_key_here
   ```

3. **Start the services**
   ```bash
   docker-compose up
   ```

4. **Access Sparky**
   - **Web UI**: Open http://localhost:3000
   - **API Server**: http://localhost:8000
   - **Admin → MCP Servers**: manage tool servers from the UI

That's it! Sparky is now running and ready to chat. 🎉

## 📦 What's Running?

The Docker Compose setup starts several services:

- **sparky-server**: FastAPI backend with chat API and integrated agent loop
- **sparky-ui-dev**: React web interface for interacting with Sparky
- **sparky-pg**: PostgreSQL database with pgvector extension (`sparky_db`)

## 🛠️ Development Setup

### Local Development (without Docker)

1. **Install Poetry** (Python dependency manager)
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Install dependencies**
   ```bash
   cd agent
   poetry install
   ```

3. **Set up database**
   ```bash
   # Start PostgreSQL with pgvector (or use Docker for just the database)
   docker-compose up postgres -d
   
   # Run migrations
   poetry run badrobot db migrate
   ```

4. **Run Sparky**
   ```bash
   # Start Redis + Postgres (or full stack)
   docker-compose up redis postgres -d

   # Start the chat server
   poetry run sparky chat start

   # In another terminal: start the agent worker
   REDIS_URL=redis://localhost:6379/0 poetry run sparky agent worker
   ```

### Web UI Development

The UI talks to the API directly (`REACT_APP_API_URL`, default `http://localhost:8000`). FastAPI CORS allows the CRA origin (`API_CORS_ORIGINS`). No webpack/CRA proxy.

```bash
cd web_ui
npm install
REACT_APP_API_URL=http://localhost:8000 npm start
```

Open http://localhost:3000 (API must be listening on :8000).

## 📚 Documentation

- **[Agent Development Guide](docs/agent_development_guide.md)** - Development best practices and conventions for contributors.
- **[Docker Setup Guide](DOCKER_SETUP.md)** - Complete Docker setup and troubleshooting
- **[Graph Intelligence Features](docs/features/graph_intelligence_features.md)** - Semantic similarity search, health checks, graph exports, and duplicate management.
- **[Task Chat Integration](docs/features/task_chat_integration.md)** - Executing tasks within existing chat contexts.

## 🎮 Usage Examples

Once Sparky is running, try these interactions:

```
You: What is your purpose?
You: Help me understand how machine learning works
You: /discover_concept Python decorators
You: Summarize our conversation so far
```

## 🏗️ Project Structure

```
BadRobot/
├── agent/                  # Core AI agent and services
│   ├── src/
│   │   ├── sparky/        # Main agent orchestrator
│   │   ├── services/      # Business logic services
│   │   ├── database/      # Database models and migrations
│   │   ├── tools/         # MCP tool integrations
│   │   └── servers/       # API servers
│   ├── tests/             # Test suite
│   └── docs/              # Technical documentation
├── web_ui/                # React frontend
│   └── docs/              # WEB UI Specific documentation, including speech models
├── docker-compose.yml     # Docker orchestration
├── Dockerfile            # Container definition
└── .env.example          # Environment template

```

## 🧪 Running Tests

```bash
cd agent
poetry run pytest
```

## 🔧 Configuration

Key environment variables (see `.env.example` for all options):

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` | Google AI API key | (required) |
| `AGENT_MODEL` | Gemini model to use | `gemini-2.0-flash` |
| `SPARKY_TOKEN_BUDGET_PERCENT` | Context window usage | `0.8` (80%) |
| `SPARKY_SUMMARY_TOKEN_THRESHOLD` | When to summarize | `0.85` (85%) |
| `SPARKY_REFLECT_EVERY` | Reflection frequency | `10` turns |

## 🤝 Contributing

We follow conventional commits for clear commit history:

```bash
feat: add new feature
fix: bug fix
docs: documentation changes
test: add or update tests
```

Pre-commit hooks are configured to enforce code quality and commit message standards.

## 🐛 Troubleshooting

### Database connection issues
```bash
# Check if postgres is running
docker-compose ps

# Reset the database
docker-compose down -v
docker-compose up postgres -d
```

### "Column embedding does not exist" error
```bash
# Run database migrations
docker-compose exec agent poetry run badrobot db migrate
```

### Pre-commit hooks failing
```bash
# Clean and reinstall
pre-commit clean
pre-commit install
```

For more help, check the [Docker Setup Guide](DOCKER_SETUP.md) or open an issue.

### Speech Model issues

See `web_ui/docs/SPEECH_MODELS_TROUBLESHOOTING.md` and `web_ui/docs/vits_voice_fix_summary.md` for common issues

---

Made with ❤️ using Google Gemini AI

