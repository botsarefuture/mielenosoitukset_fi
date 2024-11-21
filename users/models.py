import pyotp
import datetime
from utils.logger import logger

import warnings
from flask_login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from database_manager import DatabaseManager

db = DatabaseManager().get_instance()
mongo = db.get_db()

VALID_WINDOW = 5 # TODO: #226 Move this to a configuration file

class User(UserMixin):
    """
    User class represents a user in the system with various attributes and methods to manage user data and interactions.
    
    Attributes:
        id (str): Unique identifier for the user.
        username (str): Username of the user.
        email (str, optional): Email address of the user.
        password_hash (str): Hashed password of the user.
        displayname (str, optional): Display name of the user.
        profile_picture (str, optional): URL to the user's profile picture.
        bio (str, optional): Bio of the user.
        followers (list): List of user IDs who follow this user.
        following (list): List of user IDs this user is following.
        organizations (list): List of organizations the user is part of.
        global_admin (bool): Indicates if the user is a global admin.
        confirmed (bool): Indicates if the user's email is confirmed.
        permissions (dict): Dictionary of permissions for the user.
        global_permissions (list): List of global permissions for the user.
        role (str): Role of the user, default is "user".
        banned (bool): Indicates if the user is banned.
        mfa_enabled (bool): Indicates if MFA is enabled for the user.
        _id (str): Alias for id.
        
    Methods:
        from_db(user_doc): Create a User instance from a database document.
        check_password(password): Verify the provided password against the stored password hash.
        create_user(username, password, email, displayname=None, profile_picture=None, bio=None): Create a new user dictionary with a hashed password.
        add_organization(db, organization_id, role="member", permissions=None): Add or update an organization for the user, including role and permissions.
        is_member_of_organization(organization_id): Check if the user is a member of a specific organization.
        change_password(db, new_password): Change the user's password and update the database.
        update_displayname(db, displayname): Update the user's display name and database record.
        update_profile_picture(db, profile_picture): Update the user's profile picture and database record.
        update_bio(db, bio): Update the user's bio and database record.
        save(db): Save the current state of the user to the database.
        to_dict(): Convert the User object to a dictionary for database storage.
        follow_user(db, user_id_to_follow): Add a user to the followers list of this user.
        unfollow_user(db, user_id_to_unfollow): Remove a user from the followers list of this user.
        has_permission(permission, organization_id=None): Verify if the user possesses a certain permission either on a global level or within a specified organization.
        is_following(user_id): Check if this user is following another user.
        ban_user(): Ban the user.
        unban_user(): Unban the user.
        enable_mfa(): Enable MFA for the user.
        disable_mfa(): Disable MFA for the user.
        __repr__(): Return a string representation of the User object.
    """
    
    def __init__(
        self,
        user_id,
        username,
        password_hash,
        email=None,
        displayname=None,
        profile_picture=None,
        bio=None,
        followers=None,
        following=None,
        organizations=None,
        global_admin=False,
        confirmed=False,
        permissions=None,
        global_permissions=None,  # Added global permissions
        role=None,
        banned=False,  # Added banned attribute
        mfa_enabled=False,  # Added MFA attribute
    ):
        self.id = str(user_id)
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.displayname = displayname
        self.profile_picture = profile_picture
        self.bio = bio
        self.followers = followers or []
        self.following = following or []
        self.organizations = organizations or []
        self.global_admin = global_admin
        self.confirmed = confirmed
        self.permissions = permissions or {}
        self.global_permissions = global_permissions or []  # Ensure it's a list
        self.role = role or "user"
        self.banned = banned  # Initialize banned attribute
        self.mfa_enabled = mfa_enabled  # Initialize MFA attribute
        self._id = self.id  # Alias for id
        self.mfa = UserMFA(self.id)  # Initialize MFA for the user

    @staticmethod
    def from_db(user_doc):
        """
        Create a User instance from a database document.
        """
        global_admin = user_doc.get("global_admin", False)
        if user_doc.get("role") == "global_admin":
            global_admin = True

        return User(
            user_id=user_doc["_id"],
            username=user_doc["username"],
            email=user_doc.get("email", None),
            password_hash=user_doc["password_hash"],
            displayname=user_doc.get("displayname", None),
            profile_picture=user_doc.get("profile_picture", None),
            bio=user_doc.get("bio", None),
            followers=user_doc.get("followers", []),
            following=user_doc.get("following", []),
            organizations=user_doc.get("organizations", []),
            global_admin=global_admin,
            confirmed=user_doc.get("confirmed", False),
            permissions=user_doc.get("permissions", {}),
            global_permissions=user_doc.get(
                "global_permissions", []
            ),  # Fetch global permissions
            role=user_doc.get("role", "user"),
            banned=user_doc.get("banned", False),  # Fetch banned status
            mfa_enabled=user_doc.get("mfa_enabled", False),  # Fetch MFA status
        )

    def check_password(self, password):
        """
        Verify the provided password against the stored password hash.
        """
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def create_user(
        username, password, email, displayname=None, profile_picture=None, bio=None
    ):
        """
        Create a new user dictionary with a hashed password.
        """
        password_hash = generate_password_hash(password)
        return {
            "username": username,
            "password_hash": password_hash,
            "email": email,
            "displayname": displayname,
            "profile_picture": profile_picture,
            "bio": bio,
            "followers": [],
            "organizations": [],
            "global_admin": False,
            "confirmed": False,
            "permissions": [],
            "global_permissions": [],  # Initialize global permissions
            "following": [],
            "banned": False,  # Initialize banned status
            "mfa_enabled": False,  # Initialize MFA status
        }

    def add_organization(self, organization_id=None, role="member", permissions=None):
        """
        Add or update an organization for the user, including role and permissions.
        """
        if organization_id is None:
            logger.error("Organization ID is required to add organization.")
            return
        
        # Check if the organization already exists in the user's organizations
        existing_org = next(
            (org for org in self.organizations if org["org_id"] == organization_id),
            None,
        )

        if not existing_org:
            self.organizations.append(
                {
                    "org_id": organization_id,
                    "role": role,
                    "permissions": permissions or [],
                }
            ) # Add the organization to the user's organizations
            # TODO: #199 A class for representing organizations  and roles would be better
            
            
        else:
            existing_org["role"] = role
            existing_org["permissions"] = permissions or existing_org.get(
                "permissions", []
            )

        self.save()
        logger.info("Organization updated successfully.")

    def is_member_of_organization(self, organization_id):
        """
        Check if the user is a member of a specific organization.
        """
        return any(org["org_id"] == str(organization_id) for org in self.organizations)

    def change_password(self, new_password):
        """
        Change the user's password and update the database.
        """
        new_password_hash = generate_password_hash(new_password)
        self.password_hash = new_password_hash

        self.save()
        logger.info("Password updated successfully.")

    def update_displayname(self, displayname):
        """
        Update the user's display name and database record.
        """
        self.displayname = displayname
        self.save()
        logger.info("Display name updated successfully.")

    def update_profile_picture(self, profile_picture):
        """
        Update the user's profile picture and database record.
        """
        self.profile_picture = profile_picture
        self.save()
        logger.info("Profile picture updated successfully.")

    def update_bio(self, bio):
        """
        Update the user's bio and database record.
        """
        self.bio = bio
        self.save()
        logger.info("Bio updated successfully.")

    def save(self):
        """
        This method updates the user's information in the MongoDB collection.
        It finds the user by their unique ID and sets the user's data to the current state.
        Returns:
            None
        """
        data = self.to_dict()
        del data["_id"]  # Remove the _id field from the data
        
        mongo.users.update_one(
            {"_id": ObjectId(self._id)}, {"$set": data}, upsert=True
        )

    def to_dict(self, json=False):
        """
        Convert the User object to a dictionary for database storage.
        """
        data = self.__dict__.copy()
        if json and "_id" in data:
            data["_id"] = str(data["_id"])
        return data

    def follow_user(self, user_id_to_follow):
        """
        Add a user to the followers list of this user.
        """
        if isinstance(user_id_to_follow, User): # Check if the user_id_to_follow is a User object
            user_id_to_follow = user_id_to_follow.id
            
        if user_id_to_follow not in self.following:
            self.following.append(user_id_to_follow)
            self.save()
            logger.info("Started following user successfully.")

    def unfollow_user(self, user_id_to_unfollow):
        """
        Remove a user from the followers list of this user.
        """
        if user_id_to_unfollow in self.following:
            self.following.remove(user_id_to_unfollow)
            self.save()
            logger.info("Stopped following user successfully.")

    def has_permission(self, permission, organization_id=None):
        """
        This method verifies if the user possesses a certain permission either on a global level or within a specified organization.
        It first checks the global permissions, then the organization-specific permissions if an organization ID is provided,
        and finally checks the permissions dictionary for organization-specific permissions.

        Args:
            permission (str): The permission to check for.
            organization_id (str, optional): The ID of the organization to check the permission against. Defaults to None.

        Returns:
            bool: True if the user has the specified permission, either globally or within the given organization; False otherwise.

        Global Permissions:
            The method first checks if the specified permission exists in the user's global permissions.
            If it does, the method returns True.

        Organization-specific Permissions:
            If an organization ID is provided, the method iterates through the user's organizations to find a match with the given ID.
            If a match is found and the specified permission exists in the organization's permissions, the method returns True.

        Permissions Dictionary:
            If the permission is not found in the global or organization-specific permissions, the method checks the permissions dictionary.
            It iterates through the dictionary to see if the specified permission exists in any of the organization's permissions.
            If found, the method returns True.

        Example:
            ```python
            user = User(global_permissions=['read'], organizations=[{'org_id': '1', 'permissions': ['write']}], permissions={'2': ['delete']})
            user.has_permission('write', '1')  # Returns True
            user.has_permission('delete', '2')  # Returns True
            user.has_permission('read')  # Returns True
            user.has_permission('update')  # Returns False
            ```
        """
        
        # Check global permissions first
        if permission in self.global_permissions:
            return True

        # If organization_id is provided, check organization-specific permissions
        if organization_id:
            for org in self.organizations:
                if org["org_id"] == str(organization_id):
                    if permission in org.get("permissions", []):
                        return True

        # Check organization-specific permissions in the permissions dictionary
        for org in self.permissions:
            if permission in self.permissions.get(org, []):
                return True

        return False

    def is_following(self, user_id):
        """Check if this user is following another user."""
        
        if isinstance(user_id, User): # Check if the user_id is a User object
            return self.is_following(user_id.id) # If it is, check the user_id's id

        print(self.following, user_id, user_id in self.following)
        
        return user_id in self.following

    def ban_user(self):
        """Ban the user."""
        self.banned = True
        self.save()
        logger.info("User banned successfully.")

    def unban_user(self):
        """Unban the user."""
        self.banned = False
        self.save()
        logger.info("User unbanned successfully.")

    def enable_mfa(self):
        """Enable MFA for the user."""
        self.mfa_enabled = True
        self.save()
        logger.info("MFA enabled successfully.")

    def disable_mfa(self):
        """Disable MFA for the user."""
        self.mfa_enabled = False
        self.save()
        logger.info("MFA disabled successfully.")

    def __repr__(self):
        return f"<User(username={self.username}, email={self.email}, global_admin={self.global_admin}, banned={self.banned}, mfa_enabled={self.mfa_enabled})>"

class _2faToken:
    def __init__(self, token, user_id):
        self.token = token
        self.user_id = user_id
    
    def __repr__(self):
        return f"<2faToken(user_id={self.user_id})>"

    def generate_token(self):
        """Generate a new 2FA token."""
        ...
    
    def check_token(self, token):
        """Check if the provided token matches the stored token."""
        ...

class MFAToken:
    """We have this kind of data sctructure for MFA tokens.
    
    {
        '_id': ObjectId('_id here'),
        'user_id': ObjectId('userid here'),
        'secret': 'secret here',
        'created_at': datetime.datetime(2022, 1, 1, 0, 0),
        'in_use': True
        
    }
    """
    def __init__(self, user_id, secret):
        self.user_id = user_id
        self.secret = secret
        self.created_at = datetime.datetime.now()
        self.in_use = True
        self.totp = pyotp.TOTP(secret)
    
    def __repr__(self):
        return f"<MFAToken(user_id={self.user_id})>"

    def check_token(self, token):
        return self.totp.verify(token, valid_window=VALID_WINDOW)
    
class UserMFA:
    def __init__(self, user_id) -> None:
        self.user_id = user_id
        self.secrets = self.get_secrets()
        self.secrets_ = [MFAToken(user_id, secret) for secret in self.secrets]
    
    def get_secrets(self):
        mfas = mongo.mfas.find({"user_id": ObjectId(self.user_id)})
        return [mfa["secret"] for mfa in mfas]

    def verify_token(self, token):
        for secret in self.secrets_:
            if secret.check_token(token):
                return True
        
        return False
    
    def add_secret(self, secret):
        mongo.mfas.insert_one({"user_id": ObjectId(self.user_id), "secret": secret})
        self.secrets.append(secret)
        self.secrets_.append(MFAToken(self.user_id, secret))
    
    def generate_secret(self):
        secret = pyotp.random_base32()
        self.add_secret(secret)
        return secret
    
    

class AnonymousUser(AnonymousUserMixin):
    def __init__(self):
        self.id = None
        self.username = "Anonymous"
        self.email = None
        self.displayname = None
        self.profile_picture = None
        self.bio = None
        self.followers = []
        self.following = []
        self.organizations = []
        self.global_admin = False
        self.confirmed = False
        self.permissions = {}
        self.global_permissions = []
        self.role = "anonymous"
        self.banned = False
        self.mfa_enabled = False

    def add_organization(self, db, organization_id, role="member", permissions=None):
        """
        Add or update an organization for the user, including role and permissions.
        """
        logger.critical(
            f"Trying to add organization to AnonymousUser"
        )  # TODO: Handle this case more gracefully

    def is_member_of_organization(self, organization_id):
        """
        Check if the user is a member of a specific organization.
        """
        return False

    def change_password(self, db, new_password):
        """
        Change the user's password and update the database.
        """
        # FIXME: This method should not be implemented for AnonymousUser
        ...

    def update_displayname(self, db, displayname):
        """
        Update the user's display name and database record.
        """
        # FIXME: This method should not be implemented for AnonymousUser
        ...

    def update_profile_picture(self, db, profile_picture):
        """
        Update the user's profile picture and database record.
        """
        # FIXME: This method should not be implemented for AnonymousUser
        ...

    def update_bio(self, db, bio):
        """
        Update the user's bio and database record.
        """
        # FIXME: This method should not be implemented for AnonymousUser
        ...

    def follow_user(self, db, user_id_to_follow):
        """
        Add a user to the followers list of this user.
        """
        # FIXME: This method should not be implemented for AnonymousUser
        ...

    def unfollow_user(self, db, user_id_to_unfollow):
        """
        Remove a user from the followers list of this user.
        """
        # FIXME: This method should not be implemented for AnonymousUser
        ...

    def has_permission(self, organization_id, permission):
        """
        Check if the user has a specific permission in a given organization or globally.
        """
        return False

    def can_use(self, permission):
        """
        DEPRECATED: Use has_permission instead.
        """
        warnings.warn(
            "can_use is deprecated and will be removed in a future release. "
            "Use has_permission instead.",
            DeprecationWarning,
        )
        # Check global permissions first
        if permission in self.global_permissions:
            return True

        # Check organization-specific permissions
        for org in self.permissions:
            if permission in self.permissions.get(org, []):
                return True

        for org in self.organizations:
            if permission in org.get("permissions", []):
                return True

        return False

    def is_following(self, user_id):
        """Check if this user is following another user."""
        return False

    def __repr__(self):
        return f"<AnonymousUser(username={self.username})>"
