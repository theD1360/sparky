# Agent Development Guide

This document provides development best practices for contributors, both human and AI, to ensure consistency and quality in the project.

## Development Best Practices

### Unit Testing

- All new features, bug fixes, or significant changes should be accompanied by unit tests.
- Run the test suite to ensure your changes haven't introduced regressions.

### Conventional Commits

Commit messages should follow the Conventional Commits specification. This creates a more readable and structured commit history. The format is:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

- **`<type>`**: Must be one of the following:
    - **feat**: A new feature
    - **fix**: A bug fix
    - **docs**: Documentation only changes
    - **style**: Changes that do not affect the meaning of the code (white-space, formatting, etc)
    - **refactor**: A code change that neither fixes a bug nor adds a feature
    - **perf**: A code change that improves performance
    - **test**: Adding missing tests or correcting existing tests
    - **build**: Changes that affect the build system or external dependencies
    - **ci**: Changes to our CI configuration files and scripts

- **Example**: `feat: add user authentication endpoint`

## Environment Setup

### Poetry

This project uses [Poetry](https://python-poetry.org/) for dependency management and packaging.

- **Installation**: Follow the official instructions on the Poetry website.
- **Installing Dependencies**: `poetry install`
- **Activating the Virtual Environment**: `poetry shell`

### Docker

A Dockerfile is provided for building and running the application in a containerized environment.

- **Building the Image**: `docker build -t agent-project .`
- **Running the Container**: `docker run -it agent-project`

## Key Commands

- **Run the application**: `poetry run python src/main.py`
- **Run tests**: `poetry run pytest`
- **Lint the code**: `poetry run ruff check .`
- **Format the code**: `poetry run ruff format .`
