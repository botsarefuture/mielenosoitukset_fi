from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

class User(UserMixin):
        self.id = str(user_id)
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.organizations = organizations or []  # List of dictionaries with org_id and role/permissions
        self.global_admin = global_admin
        self.org_ids = org_ids or []
        self.confirmed = confirmed

    @staticmethod
    def from_db(user_doc):
        """
        Create a User instance from a database document.
        """
        return User(
            user_id=user_doc['_id'],
            username=user_doc['username'],
            email=user_doc.get("email", None),
            password_hash=user_doc['password_hash'],
            organizations=user_doc.get('organizations', []),
        )

    def check_password(self, password):
        """
        Verify the provided password against the stored password hash.
        """
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def create_user(username, password, email):
        """
        Create a new user dictionary with a hashed password.
        """
        password_hash = generate_password_hash(password)
        return {
            'username': username,
            'password_hash': password_hash,
            'email': email,
            'organizations': [],
            'global_admin': False,
            'confirmed': False
        }

    def add_organization(self, db, organization_id, role='member', permissions=None):
        """
        Add or update an organization for the user, including role and permissions.
        """
        existing_org = next((org for org in self.organizations if org['org_id'] == organization_id), None)

        if not existing_org:
            self.organizations.append({
                'org_id': organization_id,
                'role': role,
                'permissions': permissions or []
            })
            # Ensure atomicity during the database update
            db.users.update_one(
                {'_id': ObjectId(self.id)},
                {'$set': {'organizations': self.organizations}}
            )
        else:
            existing_org['role'] = role
            existing_org['permissions'] = permissions or existing_org.get('permissions', [])
            db.users.update_one(
                {'_id': ObjectId(self.id), 'organizations.org_id': organization_id},
                {'$set': {'organizations.$': existing_org}}
            )

    def is_member_of_organization(self, organization_id):
        """
        Check if the user is a member of a specific organization.
        """
