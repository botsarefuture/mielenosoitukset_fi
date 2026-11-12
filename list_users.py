#!/usr/bin/env python
"""
Script to list all users in the database.
"""

from mielenosoitukset_fi.database_manager import DatabaseManager

def list_users():
    """List all users in the database."""
    db = DatabaseManager().get_instance().get_db()
    users_collection = db["users"]
    
    users = list(users_collection.find({}, {"_id": 1, "username": 1, "email": 1, "role": 1, "global_admin": 1}))
    
    if not users:
        print("No users found in database")
        return
    
    print(f"Found {len(users)} users in database:\n")
    print(f"{'Username':<20} {'Email':<30} {'Role':<15} {'Global Admin':<12}")
    print("-" * 77)
    
    for user in users:
        username = user.get("username", "N/A")
        email = user.get("email", "N/A")
        role = user.get("role", "user")
        global_admin = user.get("global_admin", False)
        print(f"{username:<20} {email:<30} {role:<15} {str(global_admin):<12}")

if __name__ == "__main__":
    list_users()
