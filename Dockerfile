# Dockerfile for Sparky development
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    npm \
    nodejs \
    curl \
    git \
    whois \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (used to launch third-party MCP servers such as ddg-search-mcp)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Configure Poetry to not create virtual environments
RUN poetry config virtualenvs.create false
RUN pip install pre-commit commitizen

# Copy the entire project
COPY . .

# Install dependencies from the agent directory where pyproject.toml is located
WORKDIR /app/agent
RUN poetry install --no-interaction --no-ansi

# Create necessary directories
RUN mkdir -p /app/agent/logs /app/agent/trusted_scripts

# Set Python path to include src directory
ENV PYTHONPATH=/app/agent/src

# Pre-warm third-party MCP server packages (avoids long first-run uvx installs)
RUN uvx --from ddg-search-mcp-Albertous007 python -c "import ddg_search_mcp" && \
    uvx --from mcp-server-fetch python -c "import mcp_server_fetch" && \
    uvx --from mcp-server-time python -c "import mcp_server_time"

# Expose port for server
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "servers.chat:app", "--host", "0.0.0.0", "--port", "8000"]
