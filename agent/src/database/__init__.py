"""Knowledge Base Module for BadRobot.

This module provides SQLAlchemy-based database management for the knowledge graph
with Alembic migrations and automatic bot identity initialization.
"""

from .database import DatabaseManager, get_session
from .embeddings import EmbeddingManager, EmbeddingProvider, GeminiEmbeddingProvider
from .install import run_migrations
from .models import Edge, Node
from .repository import KnowledgeRepository

__all__ = [
    "DatabaseManager",
    "get_session",
    "Node",
    "Edge",
    "KnowledgeRepository",
    "run_migrations",
    "EmbeddingManager",
    "EmbeddingProvider",
    "GeminiEmbeddingProvider",
]
