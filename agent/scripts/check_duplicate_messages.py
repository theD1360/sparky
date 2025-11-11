#!/usr/bin/env python3
"""Script to check for duplicate messages in task chats.

This helps diagnose whether messages are being saved twice to the database.
"""

import logging
from collections import defaultdict

from database.database import get_database_manager
from database.repository import KnowledgeRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_duplicate_messages():
    """Check for duplicate messages in task chats."""
    try:
        # Connect to database
        db_manager = get_database_manager()
        if not db_manager.engine:
            db_manager.connect()

        repository = KnowledgeRepository(db_manager)

        # Get all task chats (chats for the "agent" user)
        task_chats = repository.get_user_chats(
            user_id="agent",
            include_archived=False,
        )

        print(f"\nFound {len(task_chats)} task-related chats\n")
        print("=" * 80)

        total_duplicates = 0

        for chat_dict in task_chats:
            # get_user_chats returns dictionaries, not Node objects
            chat_id = chat_dict.get("chat_id", "")
            chat_name = chat_dict.get("chat_name", "")

            # Get all messages for this chat
            messages = repository.get_chat_messages(chat_id, limit=1000)

            if not messages:
                continue

            # Group messages by content and role
            messages_by_content = defaultdict(list)

            for msg in messages:
                props = msg.properties or {}
                role = props.get("role", "unknown")
                content = msg.content or ""

                # Skip internal messages
                if props.get("internal", False):
                    continue

                # Create a key from content + role
                key = f"{role}:{content}"
                messages_by_content[key].append(
                    {
                        "id": msg.id,
                        "created_at": msg.created_at,
                        "role": role,
                        "content": content[:100],  # First 100 chars for display
                    }
                )

            # Find duplicates
            duplicates_found = False
            for key, msg_list in messages_by_content.items():
                if len(msg_list) > 1:
                    if not duplicates_found:
                        print(f"\nChat: {chat_name}")
                        print(f"ID: {chat_id}")
                        print(f"Total messages: {len(messages)}")
                        print("-" * 80)
                        duplicates_found = True

                    role, _ = key.split(":", 1)
                    print(f"\n  Duplicate {role} message ({len(msg_list)} copies):")
                    print(f"  Content preview: {msg_list[0]['content']}...")
                    print(f"  Message IDs:")
                    for msg in msg_list:
                        created = (
                            msg["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                            if msg["created_at"]
                            else "Unknown"
                        )
                        print(f"    - {msg['id']} (created: {created})")

                    total_duplicates += len(msg_list) - 1  # Count extra copies

            if duplicates_found:
                print()

        print("=" * 80)
        if total_duplicates > 0:
            print(f"\n⚠️  Found {total_duplicates} duplicate message(s)")
            print(
                "\nThis indicates messages are being saved multiple times to the database."
            )
            print("Check the event subscription logic in task_server.py.")
        else:
            print("\n✓ No duplicate messages found in the database")
            print(
                "\nIf you're seeing duplicates in the UI, it's likely a frontend display issue."
            )

    except Exception as e:
        logger.error(f"Error checking duplicate messages: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit(check_duplicate_messages())
