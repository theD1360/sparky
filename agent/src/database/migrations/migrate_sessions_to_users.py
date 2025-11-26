"""
Migration script to migrate chats from session-based to user-based relationships.

This script:
1. Finds all chats with BELONGS_TO_SESSION edges
2. Traverses to find the user that owns the session
3. Creates new BELONGS_TO edge from chat directly to user
4. Removes old BELONGS_TO_SESSION edges
5. Optionally cleans up orphaned session nodes
"""

from database.database import get_database_manager
from database.models import Edge, Node


def migrate_sessions_to_users(cleanup_sessions: bool = False):
    """Migrate existing chats from session-based to user-based relationships.

    Args:
        cleanup_sessions: If True, delete orphaned session nodes after migration
    """
    db_manager = get_database_manager()
    if not db_manager.engine:
        db_manager.connect()

    with db_manager.get_session() as session:
        # Find all chats with BELONGS_TO_SESSION edges
        chat_to_session_edges = (
            session.query(Edge).filter(Edge.edge_type == "BELONGS_TO_SESSION").all()
        )

        migrated_count = 0
        edges_created = 0
        edges_removed = 0
        errors = []

        for edge in chat_to_session_edges:
            chat_id = edge.source_id
            session_id = edge.target_id

            try:
                # Find the user that owns this session
                # Session -[:BELONGS_TO]-> User
                session_to_user_edge = (
                    session.query(Edge)
                    .filter(
                        Edge.source_id == session_id,
                        Edge.edge_type == "BELONGS_TO",
                    )
                    .first()
                )

                if not session_to_user_edge:
                    errors.append(
                        f"Chat {chat_id} has session {session_id} with no user link"
                    )
                    continue

                user_id = session_to_user_edge.target_id

                # Check if direct user-chat edge already exists
                existing_user_chat_edge = (
                    session.query(Edge)
                    .filter(
                        Edge.source_id == chat_id,
                        Edge.target_id == user_id,
                        Edge.edge_type == "BELONGS_TO",
                    )
                    .first()
                )

                if not existing_user_chat_edge:
                    # Create new BELONGS_TO edge from chat to user
                    new_edge = Edge(
                        source_id=chat_id,
                        target_id=user_id,
                        edge_type="BELONGS_TO",
                    )
                    session.add(new_edge)
                    edges_created += 1

                # Remove old BELONGS_TO_SESSION edge
                session.delete(edge)
                edges_removed += 1

                # Update chat node properties to remove session_id and add user_id
                chat_node = session.query(Node).filter(Node.id == chat_id).first()
                if chat_node and chat_node.properties:
                    if "session_id" in chat_node.properties:
                        del chat_node.properties["session_id"]
                    if "user_id" not in chat_node.properties:
                        chat_node.properties["user_id"] = user_id.replace("user:", "")
                    from sqlalchemy.orm.attributes import flag_modified

                    flag_modified(chat_node, "properties")

                migrated_count += 1

            except Exception as e:
                errors.append(f"Error migrating chat {chat_id}: {e}")

        # Commit all changes
        session.commit()

        print(f"Migration complete:")
        print(f"  - Migrated {migrated_count} chats")
        print(f"  - Created {edges_created} new user-chat edges")
        print(f"  - Removed {edges_removed} session-chat edges")

        if errors:
            print(f"  - {len(errors)} errors occurred:")
            for error in errors[:10]:  # Show first 10 errors
                print(f"    {error}")
            if len(errors) > 10:
                print(f"    ... and {len(errors) - 10} more errors")

        # Optional: Clean up orphaned session nodes
        if cleanup_sessions:
            # Find session nodes that have no chats linked to them
            session_nodes = (
                session.query(Node).filter(Node.node_type == "Session").all()
            )

            orphaned_sessions = []
            for session_node in session_nodes:
                # Check if any chats still link to this session
                remaining_edges = (
                    session.query(Edge)
                    .filter(
                        Edge.target_id == session_node.id,
                        Edge.edge_type == "BELONGS_TO_SESSION",
                    )
                    .count()
                )

                if remaining_edges == 0:
                    # Check if session has any other important edges
                    # (like CONTAINS for messages - but those should be on chats now)
                    other_edges = (
                        session.query(Edge)
                        .filter(
                            Edge.source_id == session_node.id,
                            Edge.edge_type != "BELONGS_TO",
                        )
                        .count()
                    )

                    if other_edges == 0:
                        orphaned_sessions.append(session_node.id)

            if orphaned_sessions:
                print(
                    f"\nCleaning up {len(orphaned_sessions)} orphaned session nodes..."
                )
                for session_id in orphaned_sessions:
                    # Remove BELONGS_TO edge from session to user
                    session_to_user_edges = (
                        session.query(Edge)
                        .filter(
                            Edge.source_id == session_id,
                            Edge.edge_type == "BELONGS_TO",
                        )
                        .all()
                    )
                    for edge in session_to_user_edges:
                        session.delete(edge)

                    # Delete session node
                    session_node = (
                        session.query(Node).filter(Node.id == session_id).first()
                    )
                    if session_node:
                        session.delete(session_node)

                session.commit()
                print(f"  - Removed {len(orphaned_sessions)} orphaned session nodes")


if __name__ == "__main__":
    import sys

    cleanup = "--cleanup" in sys.argv
    migrate_sessions_to_users(cleanup_sessions=cleanup)
