import pyotp
import datetime
from mielenosoitukset_fi.utils.logger import logger

import warnings
from flask_login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from mielenosoitukset_fi.database_manager import DatabaseManager

db = DatabaseManager().get_instance()
mongo = db.get_db()

VALID_WINDOW = 5  # TODO: #226 Move this to a configuration file


class User(UserMixin):
    """User class represents a user in the system with various attributes and methods to manage user data and interactions."""

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
        """Create a User instance from a database document.

        Parameters
        ----------
        user_doc :


        Returns
        -------


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

    @staticmethod
    def from_OID(user_id: ObjectId):
        """Create a User instance from a database document.

        Parameters
        ----------
        user_id : ObjectId
            User ID to fetch from the database


        Returns
        -------
        User : User
            User instance created from the database document


        """
        if isinstance(user_id, str):
            # Convert the string to an ObjectId, and for security reasons, also redirect
            logger.warning("User ID is a string. Converting to ObjectId.")
            return User.from_OID(ObjectId(user_id))

        user_doc = mongo.users.find_one({"_id": user_id})
        # If the Cursor object has no data, return None
        if not user_doc:
            logger.error("User not found.")
            raise ValueError("User not found.")

        return User.from_db(user_doc)

    def check_password(self, password):
        """Verify the provided password against the stored password hash.

        Parameters
        ----------
        password :


        Returns
        -------


        """
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def create_user(
        username, password, email, displayname=None, profile_picture=None, bio=None
    ):
        """Create a new user dictionary with a hashed password.

        Parameters
        ----------
        username :
            param password:
        email :
            param displayname:  (Default value = None)
        profile_picture :
            Default value = None)
        bio :
            Default value = None)
        password :

        displayname :
            (Default value = None)

        Returns
        -------


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
        """Add or update an organization for the user, including role and permissions.

        Parameters
        ----------
        organization_id :
            Default value = None)
        role :
            Default value = "member")
        permissions :
            Default value = None)

        Returns
        -------


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
            )  # Add the organization to the user's organizations
            # TODO: #199 A class for representing organizations  and roles would be better

        else:
            existing_org["role"] = role
            existing_org["permissions"] = permissions or existing_org.get(
                "permissions", []
            )

        self.save()
        logger.info("Organization updated successfully.")

    def is_member_of_organization(self, organization_id):
        """Check if the user is a member of a specific organization.

        Parameters
        ----------
        organization_id :


        Returns
        -------


        """
        return any(org["org_id"] == str(organization_id) for org in self.organizations)

    def change_password(self, new_password):
        """Change the user's password and update the database.

        Parameters
        ----------
        new_password :


        Returns
        -------


        """
        new_password_hash = generate_password_hash(new_password)
        self.password_hash = new_password_hash

        self.save()
        logger.info("Password updated successfully.")

    def update_displayname(self, displayname):
        """Update the user's display name and database record.

        Parameters
        ----------
        displayname :


        Returns
        -------


        """
        self.displayname = displayname
        self.save()
        logger.info("Display name updated successfully.")

    def update_profile_picture(self, profile_picture):
        """Update the user's profile picture and database record.

        Parameters
        ----------
        profile_picture :


        Returns
        -------


        """
        self.profile_picture = profile_picture
        self.save()
        logger.info("Profile picture updated successfully.")

    def update_bio(self, bio):
        """Update the user's bio and database record.

        Parameters
        ----------
        bio :


        Returns
        -------


        """
        self.bio = bio
        self.save()
        logger.info("Bio updated successfully.")

    def save(self):
        """This method updates the user's information in the MongoDB collection.
        It finds the user by their unique ID and sets the user's data to the current state.

        Parameters
        ----------

        Returns
        -------


        """
        data = self.to_dict()
        del data["_id"]  # Remove the _id field from the data

        mongo.users.update_one({"_id": ObjectId(self._id)}, {"$set": data}, upsert=True)

    def to_dict(self, json=False):
        """Convert the User object to a dictionary for database storage.

        Parameters
        ----------
        json :
            Default value = False)

        Returns
        -------


        """
        data = self.__dict__.copy()
        if json and "_id" in data:
            data["_id"] = str(data["_id"])

        # If user organizations has ObjectId, stringiyf
        for org in data.get("organizations", []):
            if isinstance(org.get("org_id"), ObjectId):
                org["org_id"] = str(org["org_id"])

        # dont include the MFA in the dict
        del data["mfa"]

        return data

    def follow_user(self, user_id_to_follow):
        """Add a user to the followers list of this user.

        Parameters
        ----------
        user_id_to_follow :


        Returns
        -------


        """
        if isinstance(
            user_id_to_follow, User
        ):  # Check if the user_id_to_follow is a User object
            user_id_to_follow = user_id_to_follow.id

        if user_id_to_follow not in self.following:
            self.following.append(user_id_to_follow)
            self.save()
            logger.info("Started following user successfully.")

    def unfollow_user(self, user_id_to_unfollow):
        """Remove a user from the followers list of this user.

        Parameters
        ----------
        user_id_to_unfollow :


        Returns
        -------


        """
        if user_id_to_unfollow in self.following:
            self.following.remove(user_id_to_unfollow)
            self.save()
            logger.info("Stopped following user successfully.")

    def _permissions_for(self, organization_id=None):
        """Get the list of permissions for the user, optionally filtered by organization.

        Parameters
        ----------
        organization_id : str or None, optional
            The organization ID to filter permissions for. If None, returns all permissions.

        Returns
        -------
        list of str
            List of permissions for the user (global and/or organization-specific).
        """
        if not organization_id:
            permissions = set(self.global_permissions)
        else:
            permissions = set(self.permissions.get(str(organization_id), []))

        if organization_id:
            # Add permissions from organizations
            for org in self.organizations:
                if org["org_id"] == str(organization_id):
                    permissions.update(org.get("permissions", []))
            # Add permissions from permissions dict
            org_perms = self.permissions.get(str(organization_id), [])
            permissions.update(org_perms)
        else:
            # All org-specific permissions
            for org in self.organizations:
                permissions.update(org.get("permissions", []))
            for org_perms in self.permissions.values():
                permissions.update(org_perms)
        return list(permissions)
    
    def _perm_in(self, permission, organization_id=None):
        """Check if a specific permission exists for the user, optionally filtered by organization.

        Parameters
        ----------
        permission : str
            The permission to check for.
        organization_id : str or None, optional
            The organization ID to filter permissions for. If None, checks all permissions.

        Returns
        -------
        bool
            True if the permission exists, False otherwise.
        """
        if organization_id:
            return permission in self._permissions_for(organization_id)
        else:
            # ids of organizations, where the user has the permission
            org_ids = [
                org["org_id"]
                for org in self.organizations
                if permission in org.get("permissions", [])
            ]
            return org_ids
        return permission in self._permissions_for(organization_id)

    def all_permissions_with_organizations(self):
        """Get a mapping of all permissions the user has and the organizations for which they apply.

        Returns
        -------
        dict
            Dictionary where keys are permission names and values are lists of organization IDs (or 'global').
        """
        perm_map = {}
        # Global permissions
        for perm in self.global_permissions:
            perm_map.setdefault(perm, []).append("global")
        # Organization permissions from organizations list
        for org in self.organizations:
            for perm in org.get("permissions", []):
                perm_map.setdefault(perm, []).append(str(org["org_id"]))
        # Organization permissions from permissions dict
        for org_id, perms in self.permissions.items():
            for perm in perms:
                perm_map.setdefault(perm, []).append(str(org_id))
        # Remove duplicates in org lists
        for perm in perm_map:
            perm_map[perm] = list(set(perm_map[perm]))
        return perm_map
    
    def has_permission(self, permission, organization_id=None):
        """This method verifies if the user possesses a certain permission either on a global level or within a specified organization.
        It first checks the global permissions, then the organization-specific permissions if an organization ID is provided,
        and finally checks the permissions dictionary for organization-specific permissions.

        Parameters
        ----------
        permission : str
            The permission to check for.
        organization_id : str
            The ID of the organization to check the permission against. Defaults to None.

        Returns
        -------


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
        """Check if this user is following another user.

        Parameters
        ----------
        user_id :


        Returns
        -------


        """

        if isinstance(user_id, User):  # Check if the user_id is a User object
            return self.is_following(user_id.id)  # If it is, check the user_id's id

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

    def __str__(self):
        return self.displayname or self.username


class TwoFAToken:
    """Class for handling 2FA tokens."""

    def __init__(self, token, user_id):
        self.token = token
        self.user_id = user_id

    def __repr__(self):
        return f"<TwoFAToken(user_id={self.user_id})>"

    def generate_token(self):
        """Generate a new 2FA token."""
        # Implementation for generating a new token
        pass

    def check_token(self, token):
        """Check if the provided token matches the stored token.

        Parameters
        ----------
        token : str
            The token to be checked.

        Returns
        -------
        bool
            True if the token matches, False otherwise.
        """
        # Implementation for checking the token
        pass


class MFAToken:
    """Class for handling MFA tokens.

    We have this kind of data structure for MFA tokens:

    {
        '_id': ObjectId('_id here'),
        'user_id': ObjectId('userid here'),
        'secret': 'secret here',
        'created_at': datetime.datetime(2022, 1, 1, 0, 0),
        'in_use': True
    }

    Parameters
    ----------
    user_id : str
        The user ID associated with the MFA token.
    secret : str
        The secret key for the MFA token.

    Returns
    -------
    MFAToken
        An instance of the MFAToken class.
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
        """Check if the provided token is valid.

        Parameters
        ----------
        token : str
            The token to be checked.

        Returns
        -------
        bool
            True if the token is valid, False otherwise.
        """
        return self.totp.verify(token, valid_window=VALID_WINDOW)


class UserMFA:
    """Class for handling user MFA (Multi-Factor Authentication)."""

    def __init__(self, user_id):
        self.user_id = user_id
        self.secrets = self.get_secrets()
        self.secrets_ = [MFAToken(user_id, secret) for secret in self.secrets]

    def get_secrets(self):
        """Retrieve the secrets associated with the user.

        Returns
        -------
        list
            A list of secrets associated with the user.
        """
        mfas = mongo.mfas.find({"user_id": ObjectId(self.user_id)})
        return [mfa["secret"] for mfa in mfas]

    def verify_token(self, token):
        """Verify the provided token.

        Parameters
        ----------
        token : str
            The token to be verified.

        Returns
        -------
        bool
            True if the token is valid, False otherwise.
        """
        for secret in self.secrets_:
            if secret.check_token(token):
                return True
        return False

    def get_qr_code_url(self):
        """Generate a QR code URL for the user.

        Returns
        -------
        str
            The URL for the QR code.
        """
        user = User.from_OID(self.user_id)
        return pyotp.totp.TOTP(self.secrets[0]).provisioning_uri(
            name=user.displayname or user.username, issuer_name="Mielenosoitukset.fi"
        )

    def add_secret(self, secret):
        """Add a new secret for the user.

        Parameters
        ----------
        secret : str
            The secret to be added.
        """
        mongo.mfas.insert_one({"user_id": ObjectId(self.user_id), "secret": secret})
        self.secrets.append(secret)
        self.secrets_.append(MFAToken(self.user_id, secret))

    def generate_secret(self):
        """Generate a new secret for the user.

        Returns
        -------
        str
            The generated secret.
        """
        secret = pyotp.random_base32()
        self.add_secret(secret)
        return secret

    def to_dict(self):
        """Convert the UserMFA object to a dictionary.

        Returns
        -------
        dict
            A dictionary representation of the UserMFA object.
        """
        return {"user_id": ObjectId(self.user_id), "secrets": self.secrets}


class AnonymousUser(AnonymousUserMixin):
    """ """

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

    # If any function is called, return an error message. Add a catch-all method to prevent errors.
    def __getattr__(self, name):
        logger.debug(f"Trying to access attribute {name} on AnonymousUser")
        return None

    def is_member_of_organization(self, organization_id):
        """Check if the user is a member of a specific organization.

        Parameters
        ----------
        organization_id :


        Returns
        -------


        """
        return False

    def has_permission(self, permission):
        """Check if the user has a specific permission in a given organization or globally.

        Parameters
        ----------
        organization_id :
            param permission:
        permission :


        Returns
        -------
        False : bool


        """
        return False

    def is_following(self, user_id):
        """Check if this user is following another user.

        Parameters
        ----------
        user_id :


        Returns
        -------


        """
        return False

    def __repr__(self):
        return f"<AnonymousUser(username={self.username})>"
