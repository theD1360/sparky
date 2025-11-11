#!/usr/bin/env python3
"""Script to identify and clean up duplicate task-related chats.

This script helps identify duplicate chats created for scheduled tasks
before the fix that ensures scheduled_task_name is included in metadata.
"""

import argparse
import logging
from collections import defaultdict
from datetime import datetime

from database.database import get_database_manager
from database.repository import KnowledgeRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_all_task_chats(repository: KnowledgeRepository) -> list:
    """Get all chats that appear to be task-related.
    
    Args:
        repository: Knowledge repository instance
        
    Returns:
        List of chat nodes that are task-related
    """
    # Get chats for the "agent" user (the task server user)
    task_chats = repository.get_user_chats(
        user_id="agent",
        include_archived=False,
    )
    
    return task_chats


def analyze_duplicate_chats(chats: list, repository: KnowledgeRepository) -> dict:
    """Analyze chats to find potential duplicates.
    
    Args:
        chats: List of chat dictionaries from get_user_chats
        repository: Knowledge repository instance
        
    Returns:
        Dictionary with analysis results
    """
    # Group chats by name prefix (e.g., "Task: smart_maintenance")
    chats_by_name = defaultdict(list)
    
    for chat_dict in chats:
        # Extract chat name from dictionary
        chat_name = chat_dict.get("chat_name", "")
        chat_id = chat_dict.get("chat_id", "")
        
        if chat_name and chat_name.startswith("Task:"):
            # Get the actual Node object for this chat
            chat_node = repository.get_chat(chat_id)
            if chat_node:
                chats_by_name[chat_name].append(chat_node)
    
    # Find groups with duplicates
    duplicates = {
        name: chats
        for name, chats in chats_by_name.items()
        if len(chats) > 1
    }
    
    return {
        "total_task_chats": len(chats),
        "unique_task_names": len(chats_by_name),
        "duplicate_groups": duplicates,
    }


def display_analysis(analysis: dict):
    """Display the analysis results.
    
    Args:
        analysis: Analysis results dictionary
    """
    print("\n" + "=" * 80)
    print("Task Chat Analysis")
    print("=" * 80)
    print(f"Total task-related chats: {analysis['total_task_chats']}")
    print(f"Unique task names: {analysis['unique_task_names']}")
    print(f"Duplicate groups: {len(analysis['duplicate_groups'])}")
    print()
    
    if analysis['duplicate_groups']:
        print("Duplicate Task Chats:")
        print("-" * 80)
        
        for task_name, chats in analysis['duplicate_groups'].items():
            print(f"\n{task_name} ({len(chats)} instances):")
            
            # Sort by creation time
            sorted_chats = sorted(
                chats,
                key=lambda c: c.created_at if c.created_at else datetime.min
            )
            
            for i, chat in enumerate(sorted_chats, 1):
                created = chat.created_at.strftime("%Y-%m-%d %H:%M:%S") if chat.created_at else "Unknown"
                # Display chat_id without prefix for readability
                chat_display_id = chat.id.replace("chat:", "") if chat.id.startswith("chat:") else chat.id
                print(f"  {i}. ID: {chat_display_id}")
                print(f"     Created: {created}")
                
                # Get message count
                try:
                    from database.database import get_database_manager
                    db_manager = get_database_manager()
                    if not db_manager.engine:
                        db_manager.connect()
                    repository = KnowledgeRepository(db_manager)
                    # get_chat_messages expects chat_id without prefix
                    chat_id_clean = chat.id.replace("chat:", "") if chat.id.startswith("chat:") else chat.id
                    messages = repository.get_chat_messages(chat_id_clean, limit=1000)
                    print(f"     Messages: {len(messages)}")
                except Exception as e:
                    print(f"     Messages: Error loading ({e})")
    else:
        print("\nNo duplicate task chats found! ✓")


def cleanup_old_duplicates(analysis: dict, dry_run: bool = True):
    """Clean up old duplicate chats, keeping the most recent one.
    
    Args:
        analysis: Analysis results dictionary
        dry_run: If True, only show what would be deleted without actually deleting
    """
    if not analysis['duplicate_groups']:
        print("\nNo duplicates to clean up.")
        return
    
    print("\n" + "=" * 80)
    if dry_run:
        print("DRY RUN - Showing what would be deleted")
    else:
        print("CLEANING UP DUPLICATE CHATS")
    print("=" * 80)
    
    db_manager = get_database_manager()
    if not db_manager.engine:
        db_manager.connect()
    repository = KnowledgeRepository(db_manager)
    
    total_to_delete = 0
    
    for task_name, chats in analysis['duplicate_groups'].items():
        # Sort by creation time (newest first)
        sorted_chats = sorted(
            chats,
            key=lambda c: c.created_at if c.created_at else datetime.min,
            reverse=True
        )
        
        # Keep the newest, delete the rest
        to_keep = sorted_chats[0]
        to_delete = sorted_chats[1:]
        
        print(f"\n{task_name}:")
        # Display IDs without prefix for readability
        keep_display_id = to_keep.id.replace("chat:", "") if to_keep.id.startswith("chat:") else to_keep.id
        print(f"  Keeping: {keep_display_id} (created {to_keep.created_at})")
        print(f"  Deleting {len(to_delete)} old chat(s):")
        
        for chat in to_delete:
            # Extract chat_id without prefix for display
            chat_display_id = chat.id.replace("chat:", "") if chat.id.startswith("chat:") else chat.id
            print(f"    - {chat_display_id} (created {chat.created_at})")
            total_to_delete += 1
            
            if not dry_run:
                try:
                    # Delete the chat and its messages (delete_node expects full node id with prefix)
                    repository.delete_node(chat.id)
                    logger.info(f"Deleted chat {chat.id}")
                except Exception as e:
                    logger.error(f"Failed to delete chat {chat.id}: {e}")
    
    print(f"\nTotal chats to delete: {total_to_delete}")
    
    if dry_run:
        print("\nThis was a dry run. Use --execute to actually delete these chats.")
    else:
        print("\nCleanup complete!")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Analyze and clean up duplicate task chats"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete duplicate chats (default is dry-run)",
    )
    
    args = parser.parse_args()
    
    try:
        # Connect to database
        db_manager = get_database_manager()
        if not db_manager.engine:
            db_manager.connect()
        
        repository = KnowledgeRepository(db_manager)
        
        # Get all task chats
        logger.info("Fetching task-related chats...")
        chats = get_all_task_chats(repository)
        
        # Analyze for duplicates
        logger.info("Analyzing for duplicates...")
        analysis = analyze_duplicate_chats(chats, repository)
        
        # Display results
        display_analysis(analysis)
        
        # Clean up if requested
        if analysis['duplicate_groups']:
            cleanup_old_duplicates(analysis, dry_run=not args.execute)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

