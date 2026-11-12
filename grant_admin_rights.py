#!/usr/bin/env python
"""
Script to grant admin/superuser rights to a user in MongoDB.
Usage: python grant_admin_rights.py <email> [--role admin|superuser]
"""

import sys
from mielenosoitukset_fi.database_manager import DatabaseManager
from bson import ObjectId

def grant_admin_rights(email, role="superuser"):
    """
    Grant admin/superuser rights to a user by email.
    
    Parameters
    ----------
    email : str
        The email of the user to grant rights to.
    role : str, optional
        The role to assign ("admin" or "superuser"), default is "superuser".
    """
    db = DatabaseManager().get_instance().get_db()
    users_collection = db["users"]
    
    print(f"Looking for user with email: {email}")
    
    user = users_collection.find_one({"email": email})
    if not user:
        print(f"❌ User not found with email: {email}")
        return False
    
    print(f"Found user: {user.get('username')} (ID: {user['_id']})")
    print(f"Current role: {user.get('role', 'user')}")
    print(f"Current global_admin: {user.get('global_admin', False)}")
    
    # Update the user with admin rights
    update_data = {
        "role": role,
        "global_admin": True,
    }
    
    result = users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        print(f"✅ Successfully granted {role} rights to {email}")
        print(f"   Role set to: {role}")
        print(f"   global_admin set to: True")
        return True
    else:
        print(f"⚠️  No changes made (user may already have these rights)")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python grant_admin_rights.py <email> [--role admin|superuser]")
        print("Example: python grant_admin_rights.py verso@luova.club --role superuser")
        sys.exit(1)
    
    email = sys.argv[1]
    role = "superuser"  # default
    
    if len(sys.argv) > 2 and sys.argv[2] == "--role" and len(sys.argv) > 3:
        role = sys.argv[3]
    
    if role not in ["admin", "superuser"]:
        print(f"Invalid role: {role}. Must be 'admin' or 'superuser'")
        sys.exit(1)
    
    success = grant_admin_rights(email, role)
    sys.exit(0 if success else 1)
