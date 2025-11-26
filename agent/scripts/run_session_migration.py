#!/usr/bin/env python3
"""
Script to run the session-to-user migration.

This migrates existing chats from being linked via sessions to being directly linked to users.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.migrations.migrate_sessions_to_users import migrate_sessions_to_users

if __name__ == "__main__":
    cleanup = "--cleanup" in sys.argv
    print(f"Running session-to-user migration (cleanup={cleanup})...")
    migrate_sessions_to_users(cleanup_sessions=cleanup)
    print("Migration complete!")

