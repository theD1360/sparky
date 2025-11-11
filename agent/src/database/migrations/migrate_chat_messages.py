"""
Migration script to update existing chat messages to the new schema.

This script:
1. Updates node_type from "Chat" to "ChatMessage" for message nodes
2. Creates missing CONTAINS edges from Chat nodes to message nodes
"""

from sqlalchemy.orm.attributes import flag_modified

from database.database import get_database_manager
from database.models import Edge, Node


def migrate_chat_messages():
    """Migrate existing chat messages to the new schema."""
    db_manager = get_database_manager()
    if not db_manager.engine:
        db_manager.connect()

    with db_manager.get_session() as session:
        # Find all nodes with node_type="Chat" that are actually messages
        # (they have properties with "role" field)
        message_nodes = session.query(Node).filter(Node.node_type == "Chat").all()

        updated_count = 0
        edges_created = 0

        for node in message_nodes:
            # Check if it's actually a message (has role property)
            if node.properties and "role" in node.properties:
                # Update node_type
                node.node_type = "ChatMessage"
                flag_modified(node, "node_type")
                updated_count += 1

                # Find which session this message belongs to
                session_edge = (
                    session.query(Edge)
                    .filter(Edge.target_id == node.id, Edge.edge_type == "CONTAINS")
                    .first()
                )

                if session_edge:
                    session_id = session_edge.source_id

                    # Find chat_id from session edges
                    # Session nodes connect to Chat nodes via BELONGS_TO_SESSION
                    chat_edge = (
                        session.query(Edge)
                        .filter(
                            Edge.target_id == session_id,
                            Edge.edge_type == "BELONGS_TO_SESSION",
                        )
                        .first()
                    )

                    if chat_edge:
                        chat_id = chat_edge.source_id

                        # Create edge from chat to message if it doesn't exist
                        existing = (
                            session.query(Edge)
                            .filter(
                                Edge.source_id == chat_id,
                                Edge.target_id == node.id,
                                Edge.edge_type == "CONTAINS",
                            )
                            .first()
                        )

                        if not existing:
                            new_edge = Edge(
                                source_id=chat_id,
                                target_id=node.id,
                                edge_type="CONTAINS",
                            )
                            session.add(new_edge)
                            edges_created += 1

        session.commit()
        print(
            f"Migration complete: {updated_count} nodes updated, {edges_created} edges created"
        )
        return updated_count, edges_created


if __name__ == "__main__":
    print("Starting chat messages migration...")
    updated, created = migrate_chat_messages()
    print(f"Done! Updated {updated} message nodes and created {created} edges.")
