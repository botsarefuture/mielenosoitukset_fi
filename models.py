from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

class User(UserMixin):
    def __init__(self, user_id, username, password_hash, organizations=None, global_admin=False, email=None, org_ids=None):
        self.id = str(user_id)
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.organizations = organizations or []  # List of organization IDs the user belongs to
        self.global_admin = global_admin
        self.org_ids = org_ids or []

    @staticmethod
    def from_db(user_doc):
        """
        Create a User instance from a database document.
        """
        
        global_admin = False
        if user_doc.get('role', '') == 'global_admin':
            global_admin = True
        
        global_admin_user = user_doc.get('global_admin', global_admin)
        
        org_ids = [organization["org_id"] for organization in user_doc.get("organizations", [])]
        
        return User(
            user_id=user_doc['_id'],
            username=user_doc['username'],
            email=user_doc.get("email", None),
            password_hash=user_doc['password_hash'],
            organizations=user_doc.get('organizations', []),
            global_admin=global_admin_user,
            org_ids=org_ids
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
        return any(org['org_id'] == str(organization_id) for org in self.organizations)
    
    def change_password(self, db, new_password):
        """
        Change the user's password and update the database.
        
        :param db: The database connection
        :param new_password: The new password to be set
        """
        new_password_hash = generate_password_hash(new_password)
        self.password_hash = new_password_hash

        # Update the password hash in the database
        db.users.update_one(
            {'_id': ObjectId(self.id)},
            {'$set': {'password_hash': self.password_hash}}
        )
        print('Password updated successfully.')