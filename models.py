from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

class User(UserMixin):
    def __init__(self, user_id, username, password_hash, organizations=None, global_admin = False):
        self.id = str(user_id)
        self.username = username
        self.password_hash = password_hash
        self.organizations = organizations or []  # List of organization IDs the user belongs to
        self.global_admin = global_admin

    @staticmethod
    def from_db(user_doc):
        return User(
            user_id=user_doc['_id'],
            username=user_doc['username'],
            password_hash=user_doc['password_hash'],
            organizations=user_doc.get('organizations', []),
            global_admin=user_doc.get("global_admin", False)
        )

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def create_user(username, password):
        password_hash = generate_password_hash(password)
        return {
            "username": username,
            "password_hash": password_hash
        }

    def add_organization(self, db, organization_id, level=None):
        # Check if the user already has access to this organization
        existing_org = next((org for org in self.organizations if org['organization_id'] == organization_id), None)
        
        if not existing_org:
            # Append the new organization with the specified access level
            self.organizations.append({
                "org_id": organization_id,
                "role": level or "member"  # Default to "member" if no level is provided
            })

            # Update the user's organizations in the database
            db.users.update_one(
                {"_id": ObjectId(self.id)},
                {"$set": {"organizations": self.organizations}}
            )
        else:
            # If the user already has access, update the access level
            db.users.update_one(
                {"_id": ObjectId(self.id), "organizations.organization_id": organization_id},
                {"$set": {"organizations.$.level": level or "member"}}
            )
            
    def is_member_of_organization(self, organization_id):
        """Check if the user is a member of a specific organization."""
        for org in self.organizations:
            if org["org_id"] == organization_id:
                return True

        return False