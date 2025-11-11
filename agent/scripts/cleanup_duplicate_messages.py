#!/usr/bin/env python3
"""Script to clean up duplicate messages in task chats.

This removes duplicate messages that were created before the event
subscription fix was applied.
"""

import argparse
import logging
from collections import defaultdict

from database.database import get_database_manager
from database.repository import KnowledgeRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cleanup_duplicate_messages(dry_run: bool = True):
    """Clean up duplicate messages in task chats.
    
    Args:
        dry_run: If True, only show what would be deleted without actually deleting
    """
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

        print("\n" + "=" * 80)
        if dry_run:
            print("DRY RUN - Showing what would be deleted")
        else:
            print("CLEANING UP DUPLICATE MESSAGES")
        print("=" * 80)
        print(f"\nAnalyzing {len(task_chats)} task-related chats...\n")

        total_messages_deleted = 0
        chats_with_duplicates = 0

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
                messages_by_content[key].append(msg)

            # Find and clean up duplicates
            chat_has_duplicates = False
            messages_to_delete_in_chat = 0

            for key, msg_list in messages_by_content.items():
                if len(msg_list) > 1:
                    if not chat_has_duplicates:
                        print(f"\nChat: {chat_name}")
                        print(f"ID: {chat_id}")
                        chat_has_duplicates = True
                        chats_with_duplicates += 1

                    role, content = key.split(":", 1)
                    
                    # Sort by creation time (keep oldest, delete newer duplicates)
                    sorted_msgs = sorted(
                        msg_list,
                        key=lambda m: m.created_at if m.created_at else ""
                    )
                    
                    to_keep = sorted_msgs[0]
                    to_delete = sorted_msgs[1:]
                    
                    print(f"  - Duplicate {role} message ({len(msg_list)} copies)")
                    print(f"    Content: {content[:80]}...")
                    print(f"    Keeping: {to_keep.id} (created {to_keep.created_at})")
                    print(f"    Deleting {len(to_delete)} duplicate(s)")
                    
                    for msg in to_delete:
                        if not dry_run:
                            try:
                                repository.delete_node(msg.id)
                                logger.debug(f"Deleted message {msg.id}")
                            except Exception as e:
                                logger.error(f"Failed to delete message {msg.id}: {e}")
                        
                        messages_to_delete_in_chat += 1
                        total_messages_deleted += 1

            if chat_has_duplicates:
                print(f"  Total duplicates in this chat: {messages_to_delete_in_chat}")

        print("\n" + "=" * 80)
        print(f"\nSummary:")
        print(f"  Chats with duplicates: {chats_with_duplicates}")
        print(f"  Total duplicate messages: {total_messages_deleted}")

        if dry_run:
            print("\n⚠️  This was a dry run. Use --execute to actually delete these messages.")
        else:
            print("\n✅ Cleanup complete!")
            print("\nRecommendation: Restart your servers to ensure clean state.")

    except Exception as e:
        logger.error(f"Error cleaning up duplicate messages: {e}", exc_info=True)
        return 1

    return 0


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Clean up duplicate messages in task chats"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete duplicate messages (default is dry-run)",
    )

    args = parser.parse_args()

    try:
        return cleanup_duplicate_messages(dry_run=not args.execute)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        return 1


if __name__ == "__main__":
    exit(main())

