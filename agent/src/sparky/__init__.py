"""Sparky - AI agent framework with MCP tool integration."""

from .agent_orchestrator import AgentOrchestrator
from events import BotEvents

__version__ = "0.2.0"

__all__ = ["AgentOrchestrator", "BotEvents", "__version__"]
