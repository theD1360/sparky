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
   - **MetaMCP UI**: http://localhost:12008

That's it! Sparky is now running and ready to chat. 🎉

## 📦 What's Running?

The Docker Compose setup starts several services:

- **sparky-agent**: The autonomous agent that processes tasks and learns
- **sparky-server**: FastAPI backend providing the chat API
- **sparky-ui-dev**: React web interface for interacting with Sparky
- **postgres**: PostgreSQL database with pgvector extension
- **metamcp**: Model Context Protocol server for tool integration

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
   # Start the server
   poetry run uvicorn servers.chat:app --reload
   
   # In another terminal, start the agent
   poetry run sparky agent start
   ```

### Web UI Development

```bash
cd web_ui
npm install
npm start
```

## 📚 Documentation

- **[Agent Documentation](agent/README.md)** - Detailed information about Sparky's architecture and features
- **[Docker Setup Guide](DOCKER_SETUP.md)** - Complete Docker setup and troubleshooting
- **[Architecture Documentation](agent/docs/)** - In-depth technical documentation
  - [Architecture Overview](agent/docs/architecture/overview.md)
  - [Token Budget System](agent/docs/core/token_budget.md)
  - [Knowledge Graph](agent/docs/knowledge_graph/)
  - [Middleware System](agent/docs/middleware/)

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

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

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

---

Made with ❤️ using Google Gemini AI

