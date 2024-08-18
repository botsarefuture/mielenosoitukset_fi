from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

class User(UserMixin):
    def __init__(self, user_id, username, password_hash, organizations=None, global_admin=False):
        self.id = str(user_id)
        self.username = username
        self.password_hash = password_hash
        self.organizations = organizations or []  # List of organization IDs the user belongs to
        self.global_admin = global_admin

    @staticmethod
    def from_db(user_doc):
        """
        Create a User instance from a database document.
        """
        return User(
            user_id=user_doc['_id'],
            username=user_doc['username'],
            password_hash=user_doc['password_hash'],
            organizations=user_doc.get('organizations', []),
            global_admin=user_doc.get('global_admin', False)
        )

    def check_password(self, password):
        """
        Verify the provided password against the stored password hash.
        """
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def create_user(username, password):
        """
        Create a new user dictionary with a hashed password.
        """
        password_hash = generate_password_hash(password)
        return {
            'username': username,
            'password_hash': password_hash,
            'organizations': [],
            'global_admin': False
        }

    def add_organization(self, db, organization_id, role=None):
        """
        Add or update an organization for the user.
        """
        existing_org = next((org for org in self.organizations if org['org_id'] == organization_id), None)

        if not existing_org:
            self.organizations.append({
                'org_id': organization_id,
                'role': role or 'member'
            })

            # Ensure atomicity during the database update
            db.users.update_one(
                {'_id': ObjectId(self.id)},
                {'$set': {'organizations': self.organizations}}
            )
        else:
            db.users.update_one(
                {'_id': ObjectId(self.id), 'organizations.org_id': organization_id},
                {'$set': {'organizations.$.role': role or 'member'}}
            )

    def is_member_of_organization(self, organization_id):
        """
        Check if the user is a member of a specific organization.
        """
        return any(org['org_id'] == organization_id for org in self.organizations)