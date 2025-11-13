"""SQLAlchemy models for the knowledge graph."""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False

Base = declarative_base()


class Node(Base):
    """Node model representing entities in the knowledge graph.

    Nodes can be of various types: Memory, Concept, Task, File, Action, etc.
    Each node has a unique ID, type, label, optional content, and properties.
    """

    __tablename__ = "nodes"

    # Primary key
    id = Column(String, primary_key=True)

    # Core attributes
    node_type = Column(String, nullable=False, index=True)
    label = Column(String, nullable=False)
    content = Column(Text)
    properties = Column(JSON)  # JSON field for flexible metadata

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Embedding (for PostgreSQL with pgvector)
    # Note: For SQLite, embeddings are stored in the nodes_vec virtual table
    if PGVECTOR_AVAILABLE:
        embedding = Column(Vector(768), nullable=True)

    # Relationships
    outgoing_edges = relationship(
        "Edge",
        foreign_keys="Edge.source_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "Edge",
        foreign_keys="Edge.target_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("idx_nodes_type", "node_type"),
        Index("idx_nodes_updated", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<Node(id='{self.id}', type='{self.node_type}', label='{self.label}')>"

    def to_dict(self) -> dict:
        """Convert node to dictionary format compatible with existing API."""
        return {
            "id": self.id,
            "type": self.node_type,
            "label": self.label,
            "content": self.content,
            "properties": self.properties or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Edge(Base):
    """Edge model representing relationships between nodes.

    Edges connect nodes with typed relationships like RELATES_TO, DEPENDS_ON, etc.
    Each edge has a source and target node, relationship type, and optional properties.
    """

    __tablename__ = "edges"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    source_id = Column(
        String, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_id = Column(
        String, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
    )

    # Relationship attributes
    edge_type = Column(String, nullable=False, index=True)
    properties = Column(JSON)  # JSON field for flexible metadata

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    source_node = relationship(
        "Node", foreign_keys=[source_id], back_populates="outgoing_edges"
    )
    target_node = relationship(
        "Node", foreign_keys=[target_id], back_populates="incoming_edges"
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "edge_type", name="uq_edge_unique"),
        Index("idx_edges_source", "source_id"),
        Index("idx_edges_target", "target_id"),
        Index("idx_edges_type", "edge_type"),
    )

    def __repr__(self) -> str:
        return f"<Edge(source='{self.source_id}', target='{self.target_id}', type='{self.edge_type}')>"

    def to_dict(self) -> dict:
        """Convert edge to dictionary format compatible with existing API."""
        return {
            "id": self.id,
            "source": self.source_id,
            "target": self.target_id,
            "type": self.edge_type,
            "properties": self.properties or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
