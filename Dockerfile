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

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Configure Poetry to not create virtual environments
RUN poetry config virtualenvs.create false

# Copy dependency files
COPY ./ ./

# Install dependencies
RUN poetry install --no-interaction --no-ansi

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/trusted_scripts

# Set Python path to include src directory
ENV PYTHONPATH=/app/src

# Expose port for server
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "servers.chat:app", "--host", "0.0.0.0", "--port", "8000"]
