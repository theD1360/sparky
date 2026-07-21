"""Command DTOs for the Sparky command bus."""

from command_bus import CommandMessage


class RunAgentTaskCommand(CommandMessage):
    """Execute a pending agent task by knowledge-graph task id."""

    task_id: str
