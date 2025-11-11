"""User service for handling user-related operations.

Handles user CRUD operations, preferences management, and user-session relationships.
"""

import logging
from typing import Any, Dict, Optional

from database.models import Node
from database.repository import KnowledgeRepository

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing users in the knowledge graph.

    Provides methods for creating, retrieving, and updating users,
    as well as managing user preferences and session relationships.
    """

    def __init__(self, repository: KnowledgeRepository):
        """Initialize the user service.

        Args:
            repository: Knowledge graph repository instance
        """
        self.repository = repository

    def create_user(
        self, user_id: str, **properties: Any
    ) -> Optional[str]:
        """Create a new user node in the knowledge graph.

        Args:
            user_id: Unique user identifier
            **properties: Additional properties to store with the user

        Returns:
            The node ID of the created user, or None if failed
        """
        user_node_id = f"user:{user_id}"

        try:
            # Check if user already exists
            existing_user = self.repository.get_node(user_node_id)
            if existing_user:
                logger.info(f"User {user_node_id} already exists, skipping creation")
                return user_node_id

            # Build properties
            user_properties = {"user_id": user_id}
            user_properties.update(properties)

            # Create user node
            self.repository.add_node(
                node_id=user_node_id,
                node_type="User",
                label=f"User {user_id}",
                content=f"User with ID {user_id}",
                properties=user_properties,
            )

            logger.info(f"Created User node: {user_node_id}")
            return user_node_id

        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {e}", exc_info=True)
            return None

    def get_user(self, user_id: str) -> Optional[Node]:
        """Retrieve a user node from the knowledge graph.

        Args:
            user_id: User identifier

        Returns:
            User Node object, or None if not found
        """
        user_node_id = f"user:{user_id}"

        try:
            user_node = self.repository.get_node(user_node_id)
            if user_node:
                logger.debug(f"Retrieved user: {user_node_id}")
            else:
                logger.debug(f"User not found: {user_node_id}")
            return user_node

        except Exception as e:
            logger.error(f"Failed to retrieve user {user_id}: {e}", exc_info=True)
            return None

    def update_user(
        self, user_id: str, **properties: Any
    ) -> bool:
        """Update a user node's properties.

        Args:
            user_id: User identifier
            **properties: Properties to update

        Returns:
            True if successful, False otherwise
        """
        user_node_id = f"user:{user_id}"

        try:
            # Get existing user
            user_node = self.repository.get_node(user_node_id)
            if not user_node:
                logger.warning(f"User {user_node_id} not found, cannot update")
                return False

            # Update properties
            existing_properties = user_node.properties or {}
            existing_properties.update(properties)

            # Update node
            self.repository.update_node(
                node_id=user_node_id,
                properties=existing_properties,
            )

            logger.info(f"Updated user {user_node_id} with properties: {properties}")
            return True

        except Exception as e:
            logger.error(f"Failed to update user {user_id}: {e}", exc_info=True)
            return False

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get all preferences for a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary of user preferences (empty dict if user not found or no preferences)
        """
        user_node = self.get_user(user_id)
        if not user_node:
            return {}

        properties = user_node.properties or {}
        preferences = properties.get("preferences", {})

        logger.debug(f"Retrieved preferences for user {user_id}: {preferences}")
        return preferences

    def set_user_preference(
        self, user_id: str, key: str, value: Any
    ) -> bool:
        """Set a single preference for a user.

        Args:
            user_id: User identifier
            key: Preference key
            value: Preference value

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get existing preferences
            preferences = self.get_user_preferences(user_id)

            # Update preference
            preferences[key] = value

            # Save back to user node
            success = self.update_user(user_id, preferences=preferences)

            if success:
                logger.info(f"Set preference for user {user_id}: {key}={value}")
            else:
                logger.warning(f"Failed to set preference for user {user_id}")

            return success

        except Exception as e:
            logger.error(
                f"Failed to set preference for user {user_id}: {e}", exc_info=True
            )
            return False

    def get_user_preference(
        self, user_id: str, key: str, default: Any = None
    ) -> Any:
        """Get a single preference for a user.

        Args:
            user_id: User identifier
            key: Preference key
            default: Default value if preference not found

        Returns:
            Preference value, or default if not found
        """
        preferences = self.get_user_preferences(user_id)
        return preferences.get(key, default)

    def link_user_to_session(
        self, user_id: str, session_id: str
    ) -> bool:
        """Create a relationship between a user and a session.

        Args:
            user_id: User identifier
            session_id: Session identifier

        Returns:
            True if successful, False otherwise
        """
        user_node_id = f"user:{user_id}"

        try:
            # Verify user exists
            user_node = self.repository.get_node(user_node_id)
            if not user_node:
                logger.warning(
                    f"User {user_node_id} not found, cannot link to session"
                )
                return False

            # Create BELONGS_TO edge between session and user
            self.repository.add_edge(
                source_id=session_id, target_id=user_node_id, edge_type="BELONGS_TO"
            )

            logger.info(f"Created BELONGS_TO edge: {session_id} -> {user_node_id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to link user {user_id} to session {session_id}: {e}",
                exc_info=True,
            )
            return False

    def get_user_sessions(self, user_id: str, limit: Optional[int] = None) -> list:
        """Get all sessions belonging to a user.

        Args:
            user_id: User identifier
            limit: Optional limit on number of sessions to return

        Returns:
            List of session nodes
        """
        user_node_id = f"user:{user_id}"

        try:
            # Get incoming BELONGS_TO edges (sessions that belong to this user)
            edges = self.repository.get_edges(
                target_id=user_node_id, edge_type="BELONGS_TO"
            )

            sessions = []
            for edge in edges:
                session_node = self.repository.get_node(edge.source_id)
                if session_node:
                    sessions.append(session_node)

                if limit and len(sessions) >= limit:
                    break

            logger.debug(f"Found {len(sessions)} sessions for user {user_id}")
            return sessions

        except Exception as e:
            logger.error(
                f"Failed to get sessions for user {user_id}: {e}", exc_info=True
            )
            return []

    def delete_user(self, user_id: str) -> bool:
        """Delete a user node from the knowledge graph.

        Warning: This will also delete all relationships involving this user.

        Args:
            user_id: User identifier

        Returns:
            True if successful, False otherwise
        """
        user_node_id = f"user:{user_id}"

        try:
            # Delete the node (cascade will delete edges)
            self.repository.delete_node(user_node_id)

            logger.info(f"Deleted user: {user_node_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete user {user_id}: {e}", exc_info=True)
            return False

