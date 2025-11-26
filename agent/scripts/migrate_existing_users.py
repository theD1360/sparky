"""Migration script to migrate existing knowledge graph users to the new user management system.

This script is optional and should be run after the user management tables are created.
It will:
1. Find all user nodes in the knowledge graph
2. Create corresponding entries in the users table (with random passwords)
3. Link knowledge graph nodes to user table via external_id property

Usage:
    python -m scripts.migrate_existing_users
"""

import os
import sys
import uuid
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.database import get_database_manager
from database.repository import KnowledgeRepository
from services.auth_service import get_password_hash
from services.user_management_service import UserManagementService


def migrate_users():
    """Migrate existing knowledge graph users to new user management system."""

    # Get database connection
    db_url = os.getenv("SPARKY_DB_URL")
    if not db_url:
        print("Error: SPARKY_DB_URL environment variable not set")
        return

    db_manager = get_database_manager(db_url=db_url)
    db_manager.connect()

    repository = KnowledgeRepository(db_manager)
    db_session = db_manager.SessionLocal()
    user_service = UserManagementService(db_session)

    try:
        # Find all user nodes in knowledge graph
        # User nodes have node_type="User" and id starting with "user:"
        all_nodes = repository.get_nodes(node_type="User")

        print(f"Found {len(all_nodes)} user nodes in knowledge graph")

        migrated_count = 0
        skipped_count = 0

        for node in all_nodes:
            user_id = node.id.replace("user:", "")

            # Check if user already exists in user table
            existing_user = user_service.get_user_by_id(user_id)
            if existing_user:
                print(f"Skipping {user_id} - already exists in user table")
                skipped_count += 1
                continue

            # Extract username and email from node properties
            properties = node.properties or {}
            username = properties.get("username") or f"user_{user_id[:8]}"
            email = properties.get("email") or f"{username}@migrated.local"

            # Generate a random password (user will need to reset)
            temp_password = str(uuid.uuid4())

            # Create user in user table
            new_user = user_service.create_user(
                username=username,
                email=email,
                password=temp_password,
                is_active=True,
                is_verified=False,
            )

            if new_user:
                # Update knowledge graph node to link to user table
                properties["external_id"] = new_user.id
                repository.update_node(node.id, properties=properties)

                print(f"Migrated user: {username} (id: {new_user.id})")
                print(f"  Temporary password: {temp_password}")
                print(f"  User must reset password on first login")
                migrated_count += 1
            else:
                print(f"Failed to migrate user: {user_id}")

        print(f"\nMigration complete:")
        print(f"  Migrated: {migrated_count}")
        print(f"  Skipped: {skipped_count}")
        print(
            f"\nNote: All migrated users have temporary passwords and must reset on first login."
        )

    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db_session.close()


if __name__ == "__main__":
    migrate_users()
