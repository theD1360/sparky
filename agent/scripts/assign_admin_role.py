"""Script to assign admin role to a user.

Usage:
    python scripts/assign_admin_role.py <username_or_email>
    
Or to assign to the first user:
    python scripts/assign_admin_role.py --first
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.database import get_database_manager
from services.user_management_service import UserManagementService


def assign_admin(username_or_email=None, first_user=False):
    """Assign admin role to a user."""
    
    # Get database connection
    db_url = os.getenv("SPARKY_DB_URL")
    if not db_url:
        print("Error: SPARKY_DB_URL environment variable not set")
        return
    
    db_manager = get_database_manager(db_url=db_url)
    db_manager.connect()
    db_session = db_manager.SessionLocal()
    user_service = UserManagementService(db_session)
    
    try:
        if first_user:
            # Get the first user
            users = user_service.list_users(limit=1)
            if not users:
                print("Error: No users found in database")
                return
            user = users[0]
            username_or_email = user.username
        else:
            if not username_or_email:
                print("Error: Please provide username/email or use --first flag")
                print("\nUsage:")
                print("  python scripts/assign_admin_role.py <username_or_email>")
                print("  python scripts/assign_admin_role.py --first")
                return
            
            # Find user by username or email
            user = user_service.get_user_by_username(username_or_email)
            if not user:
                user = user_service.get_user_by_email(username_or_email)
            
            if not user:
                print(f"Error: User '{username_or_email}' not found")
                return
        
        # Check if user already has admin role
        roles = user_service.get_user_roles(user.id)
        if 'admin' in roles:
            print(f"User '{user.username}' already has admin role")
            return
        
        # Assign admin role
        success = user_service.assign_role(user.id, 'admin')
        
        if success:
            print(f"✓ Successfully assigned admin role to user: {user.username} ({user.email})")
            print(f"  User ID: {user.id}")
        else:
            print(f"Error: Failed to assign admin role to user: {user.username}")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db_session.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--first":
            assign_admin(first_user=True)
        else:
            assign_admin(username_or_email=sys.argv[1])
    else:
        print("Error: Please provide username/email or use --first flag")
        print("\nUsage:")
        print("  python scripts/assign_admin_role.py <username_or_email>")
        print("  python scripts/assign_admin_role.py --first")

