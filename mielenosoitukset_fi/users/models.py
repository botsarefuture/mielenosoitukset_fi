from typing import List, Dict, Union, Optional
from bson import ObjectId
from flask_login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import pyotp, datetime

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.classes.MemberShip import MemberShip
#from mielenosoitukset_fi.utils.classes.BaseModel import BaseModel  # if still needed

db  = DatabaseManager().get_instance()
mongo = db.get_db()

VALID_WINDOW = 5          # TODO → move to config
DEFAULT_ROLE = "user"

class User(UserMixin):
    @classmethod
    def create_user(cls, username: str, password: str, email: str = None, displayname: str = None) -> dict:
        """
        Create a new user document for registration.

        Parameters
        ----------
        username : str
            The username for the new user.
        password : str
            The plaintext password (will be hashed).
        email : str, optional
            The user's email address.
        displayname : str, optional
            The user's display name.

        Returns
        -------
        dict
            The user document ready for insertion into the database.
        """
        password_hash = generate_password_hash(password)
        user_doc = {
            "username": username,
            "password_hash": password_hash,
            "email": email,
            "displayname": displayname,
            "global_admin": False,
            "confirmed": False,
            "global_permissions": [],
            "role": DEFAULT_ROLE,
            "banned": False,
            "mfa_enabled": False,
            "followers": [],
            "following": [],
        }
        return user_doc
    """
    MongoDB‑backed application user.
    Memberships live in the `memberships` collection – we derive org/role data on‑demand.
    """

    # ---------- INIT / FACTORIES -------------------------------------------------

    def __init__(
        self,
        user_id: ObjectId,
        username: str,
        password_hash: str,
        *,
        email: Optional[str] = None,
        displayname: Optional[str] = None,
        profile_picture: Optional[str] = None,
        bio: Optional[str] = None,
        followers: Optional[List[str]] = None,
        following: Optional[List[str]] = None,
        global_admin: bool = False,
        confirmed: bool = False,
        global_permissions: Optional[List[str]] = None,
        role: str = DEFAULT_ROLE,
        banned: bool = False,
        mfa_enabled: bool = False,
    ):
        self.id                = str(user_id)  # flask‑login expects .id str
        self._id               = ObjectId(user_id)
        self.username          = username
        self.email             = email
        self.password_hash     = password_hash
        self.displayname       = displayname
        self.profile_picture   = profile_picture
        self.bio               = bio
        self.followers         = followers or []
        self.following         = following or []
        self.global_admin      = global_admin
        self.confirmed         = confirmed
        self.global_permissions= global_permissions or []
        self.role              = role
        self.banned            = banned
        self.mfa_enabled       = mfa_enabled
        self.mfa               = UserMFA(self._id)  # see helper class below

        # CACHED memberships (lazy)  --------------------------------------------
        self._memberships: Optional[List[MemberShip]] = None

    # ---------- CLASS HELPERS ----------------------------------------------------

    @classmethod
    def from_db(cls, doc: dict) -> "User":
        return cls(
            user_id         = doc["_id"],
            username        = doc["username"],
            password_hash   = doc["password_hash"],
            email           = doc.get("email"),
            displayname     = doc.get("displayname"),
            profile_picture = doc.get("profile_picture"),
            bio             = doc.get("bio"),
            followers       = doc.get("followers", []),
            following       = doc.get("following", []),
            global_admin    = doc.get("global_admin", False) or doc.get("role")=="global_admin",
            confirmed       = doc.get("confirmed", False),
            global_permissions = doc.get("global_permissions", []),
            role            = doc.get("role", DEFAULT_ROLE),
            banned          = doc.get("banned", False),
            mfa_enabled     = doc.get("mfa_enabled", False),
        )

    @classmethod
    def from_OID(cls, oid: Union[str, ObjectId]) -> "User":
        if isinstance(oid, str):
            oid = ObjectId(oid)
        doc = mongo.users.find_one({"_id": oid})
        if not doc:
            raise ValueError("User not found")
        return cls.from_db(doc)

    # ---------- MEMBERSHIP / ORG / PERMS ----------------------------------------

    @property
    def memberships(self) -> List[MemberShip]:
        """Lazy‑load & cache MemberShip rows for this user."""
        if self._memberships is None:
            self._memberships = MemberShip.all_per_user(self._id)
        return self._memberships

    def org_ids(self) -> List[ObjectId]:
        return [m.organization_id for m in self.memberships]
    
    def _permission_in(self, permission: str) -> List[Union[str, ObjectId]]:
        """
        Return a list of scopes (organization IDs or the literal string "global")
        in which this user has *permission*.

        • If the permission is in the user’s global_permissions,
          the list will contain the string "global".
        • For every membership that contains the permission,
          the organization_id of that membership is included.
        The list is deduplicated and keeps a predictable order.
        """
        scopes: List[Union[str, ObjectId]] = []

        # 1️⃣ global scope
        if permission in self.global_permissions:
            scopes.append("global")

        # 2️⃣ per‑organization scope
        scopes.extend(
            m.organization_id
            for m in self.memberships
            if permission in m.permissions
        )

        # remove duplicates while preserving order (Python 3.7+ keeps dict order)
        return list(dict.fromkeys(scopes))
    
    def membership_for(self, organization_id: Union[str, ObjectId]) -> Optional[MemberShip]:
        oid = ObjectId(organization_id)
        return next((m for m in self.memberships if m.organization_id == oid), None)

    def role_in(self, organization_id: Union[str, ObjectId]) -> Optional[str]:
        m = self.membership_for(organization_id)
        return m.role if m else None

    # ---------- PASSWORD / LOGIN -------------------------------------------------

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # ---------- PERMISSION HANDLING ---------------------------------------------

    def permissions_for(self, organization_id: Optional[Union[str, ObjectId]] = None) -> List[str]:
        if organization_id is None:
            # global scope
            perms = set(self.global_permissions)
        else:
            ms = self.membership_for(organization_id)
            perms = set(ms.permissions) if ms else set()
        return list(perms)

    def has_permission(self, perm: str, organization_id: Optional[Union[str, ObjectId]]=None, strict=False) -> bool:
        if perm in self.global_permissions:
            return True
        
        if organization_id:
            ms = self.membership_for(organization_id)
            if ms:
                print(ms.permissions)
                print(ms.organization_id)
            
            return bool(ms and perm in ms.permissions)
        # if org not specified, check all org memberships
        return any(perm in m.permissions for m in self.memberships)

    # ---------- FOLLOW / BAN / MFA ----------------------------------------------

    def follow_user(self, other_id: Union[str, "User"]):
        oid = str(other_id._id) if isinstance(other_id, User) else str(other_id)
        if oid not in self.following:
            self.following.append(oid)
            self.save()

    def unfollow_user(self, other_id: Union[str, "User"]):
        oid = str(other_id._id) if isinstance(other_id, User) else str(other_id)
        if oid in self.following:
            self.following.remove(oid)
            self.save()

    def ban_user(self):
        self.banned = True
        self.save()

    def unban_user(self):
        self.banned = False
        self.save()

    # ---------- CRUD -------------------------------------------------------------

    def save(self):
        """Persist user (does **not** touch memberships)."""
        doc = self.to_dict()
        doc.pop("_id", None)
        mongo.users.update_one({"_id": self._id}, {"$set": doc}, upsert=True)
        # invalidate cache after save
        self._memberships = None

    # ---------- SERIALISATION ----------------------------------------------------

    def to_dict(self, json: bool = False) -> Dict:
        d = {
            "_id": str(self._id) if json else self._id,
            "username": self.username,
            "password_hash": self.password_hash,
            "email": self.email,
            "displayname": self.displayname,
            "profile_picture": self.profile_picture,
            "bio": self.bio,
            "followers": self.followers,
            "following": self.following,
            "global_admin": self.global_admin,
            "confirmed": self.confirmed,
            "global_permissions": self.global_permissions,
            "role": self.role,
            "banned": self.banned,
            "mfa_enabled": self.mfa_enabled,
        }
        return d

    # ---------- STRING MAGIC -----------------------------------------------------

    def __repr__(self):
        return f"<User {self.username} ({self._id})>"

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

    def has_permission(self, permission, strict=False):
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
