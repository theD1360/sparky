# Docker Development Setup

This guide explains how to run Sparky using Docker Compose for development.

## Prerequisites

- Docker and Docker Compose installed
- Google API Key from [Google AI Studio](https://makersuite.google.com/app/apikey)

## Quick Start

1. **Create environment file**

   Create a `.env` file in the project root with your configuration:

   ```env
   # Required: Google API Key for Gemini AI
   GOOGLE_API_KEY=your_api_key_here

   # Optional: Model configuration
   AGENT_MODEL=gemini-2.0-flash

   # Optional: History management
   BADROBOT_MAX_HISTORY_TURNS=25

   # Optional: Knowledge graph settings
   BADROBOT_SUMMARY_EVERY=5
   BADROBOT_REFLECT_EVERY=10

   # Optional: Logging
   LOG_DIR=logs
   ```

2. **Start the services**

   ```bash
   docker-compose up
   ```

   Or run in detached mode:

   ```bash
   docker-compose up -d
   ```

3. **Access the server**

   The server will be available at `ws://localhost:8000/ws/chat`

## Services

### Server Service

- **Container**: `sparky-server`
- **Port**: 8000
- **Features**: Live reload enabled via uvicorn `--reload` flag
- **Command**: `uvicorn servers.chat:app --host 0.0.0.0 --port 8000 --reload`

### Agent Service

- **Container**: `sparky-agent`
- **Features**: Background task processor
- **Command**: `poetry run sparky agent start --interval 10`

## Development Workflow

### Live Reload

Changes to Python files in the `./src` directory will automatically trigger a reload of the server. The agent service will also pick up changes on restart.

### Viewing Logs

```bash
# View all logs
docker-compose logs -f

# View server logs only
docker-compose logs -f server

# View agent logs only
docker-compose logs -f agent
```

### Restarting Services

```bash
# Restart both services
docker-compose restart

# Restart server only
docker-compose restart server

# Restart agent only
docker-compose restart agent
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Shared Data

The following directories and files are shared between services:

- `./src` - Source code (mounted for live reload)
- `./prompts` - Prompt templates
- `./knowledge_graph.db` - SQLite database
- `./logs` - Application logs
- `./mcp.json` - MCP configuration (read-only)
- `./scheduled_tasks.yaml` - Scheduled tasks configuration (read-only)

## Troubleshooting

### Permission Issues

If you encounter permission issues with the database or logs:

```bash
sudo chown -R $USER:$USER logs/ knowledge_graph.db
```

### Port Already in Use

If port 8000 is already in use, modify the port mapping in `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Change 8001 to your preferred port
```

### Rebuilding After Dependency Changes

After updating `pyproject.toml` or `poetry.lock`:

```bash
docker-compose build
docker-compose up
```

### Connecting Client

To connect a client to the Docker server:

```bash
# From host machine
poetry run sparky client start-client --host localhost --port 8000

# Or use the example client
poetry run python examples/simple_chat.py
```

## Health Check

The server includes a health check endpoint. Verify it's running:

```bash
curl http://localhost:8000/health
```

## Production Considerations

This setup is optimized for **development only**. For production:

1. Remove the `--reload` flag from uvicorn
2. Use production-grade WSGI server
3. Set up proper secrets management
4. Configure proper logging and monitoring
5. Use Docker secrets instead of environment variables
6. Set up proper database backups

