#!/usr/bin/env python
"""
Script to grant all permissions to a user.
"""

import json
from mielenosoitukset_fi.database_manager import DatabaseManager

def get_all_permissions():
    """Extract all permission names from permission_groups.json"""
    with open("mielenosoitukset_fi/utils/data/permission_groups.json", "r") as f:
        permission_groups = json.load(f)
    
    permissions = []
    for group_name, perms in permission_groups.items():
        for perm in perms:
            permissions.append(perm["name"])
    
    return sorted(permissions)

def grant_all_permissions(email):
    """Grant all permissions to a user."""
    db = DatabaseManager().get_instance().get_db()
    users_collection = db["users"]
    
    print(f"Looking for user with email: {email}")
    
    user = users_collection.find_one({"email": email})
    if not user:
        print(f"❌ User not found with email: {email}")
        return False
    
    print(f"✅ Found user: {user.get('username')} (ID: {user['_id']})")
    print(f"   Current role: {user.get('role', 'user')}")
    print(f"   Current global_admin: {user.get('global_admin', False)}")
    print(f"   Current permissions: {len(user.get('global_permissions', []))} permissions")
    
    # Get all available permissions
    all_permissions = get_all_permissions()
    print(f"\n📋 Available permissions: {len(all_permissions)}")
    for perm in all_permissions:
        print(f"   - {perm}")
    
    # Update the user with all permissions and admin rights
    update_data = {
        "role": "global_admin",
        "global_admin": True,
        "global_permissions": all_permissions,
    }
    
    print(f"\n🔄 Updating user...")
    result = users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        print(f"\n✅ Successfully granted all rights to {email}")
        print(f"   ✓ Role set to: global_admin")
        print(f"   ✓ global_admin set to: True")
        print(f"   ✓ Granted {len(all_permissions)} permissions")
        return True
    else:
        print(f"\n⚠️  No changes made")
        return False

if __name__ == "__main__":
    email = "verso@luova.club"
    success = grant_all_permissions(email)
