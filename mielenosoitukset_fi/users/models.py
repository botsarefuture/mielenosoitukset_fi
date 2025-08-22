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
    def _perm_in(self, permission: str) -> List[Union[str, ObjectId]]:
        """
        Return a list of scopes (organization IDs or the literal string "global")
        in which this user has the given permission.

        Parameters
        ----------
        permission : str
            The permission to check.

        Returns
        -------
        list of str or ObjectId
            List of organization IDs or "global" where the user has the permission.
        """
        scopes = []
        if permission in self.global_permissions:
            scopes.append("global")
        scopes.extend(
            m.organization_id for m in self.memberships if permission in m.permissions
        )
        # Remove duplicates while preserving order
        return list(dict.fromkeys(scopes))
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

from typing import List, Dict
import pyotp
import datetime
from bson import ObjectId

class PendingMFA:
    """Pending MFA setup before verification (can handle multiple secrets)."""
    COLLECTION = "pending_mfa"

    @staticmethod
    def create(user_id: ObjectId) -> str:
        """Create a new pending MFA secret."""
        secret = pyotp.random_base32()
        mongo[PendingMFA.COLLECTION].insert_one({
            "user_id": user_id,
            "secret": secret,
            "created_at": datetime.datetime.utcnow()
        })
        return secret

    @staticmethod
    def get(user_id: ObjectId, secret: str = None) -> List[str]:
        """Return pending secrets for a user or a specific secret."""
        query = {"user_id": user_id}
        if secret:
            query["secret"] = secret
        docs = mongo[PendingMFA.COLLECTION].find(query)
        return [doc["secret"] for doc in docs]

    @staticmethod
    def delete(user_id: ObjectId, secret: str = None):
        """Delete pending MFA secrets (all or specific)."""
        query = {"user_id": user_id}
        if secret:
            query["secret"] = secret
        mongo[PendingMFA.COLLECTION].delete_many(query)


class MFAToken:
    """Active MFA token with verification."""
    def __init__(self, secret: str):
        self.secret = secret
        self.totp = pyotp.TOTP(secret)

    def verify(self, token: str, window: int = 5) -> bool:
        return self.totp.verify(token, valid_window=window)


class UserMFA:
    """Handles all active MFA secrets for a user."""

    def __init__(self, user_id: ObjectId):
        self.user_id = user_id

    def list_devices(self) -> List[Dict]:
        """Return metadata for all active MFA secrets/devices."""
        docs = mongo.mfas.find({"user_id": self.user_id})
        return [
            {
                "id": str(doc["_id"]),
                "secret": doc["secret"],
                "device_name": doc.get("device_name", "Unknown device"),
                "created_at": doc.get("created_at")
            }
            for doc in docs
        ]

    def active_tokens(self) -> List[MFAToken]:
        """Return MFAToken objects for all active secrets."""
        return [MFAToken(dev["secret"]) for dev in self.list_devices()]

    def verify_token(self, token: str) -> bool:
        """Verify token against all active secrets."""
        return any(tok.verify(token) for tok in self.active_tokens())

    def add_device(self, device_name: str = "New device") -> str:
        """Generate a new secret and store it as a device."""
        secret = pyotp.random_base32()
        mongo.mfas.insert_one({
            "user_id": self.user_id,
            "secret": secret,
            "device_name": device_name,
            "created_at": datetime.datetime.utcnow()
        })
        return secret

    def remove_device(self, device_id: str):
        """Remove a specific device by Mongo _id."""
        result = mongo.mfas.delete_one({"_id": ObjectId(device_id), "user_id": self.user_id})
        return result.deleted_count > 0

    def get_qr_code_url(self, secret: str) -> str:
        """Generate QR for a given secret."""
        user = User.from_OID(self.user_id)
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.displayname or user.username,
            issuer_name="Mielenosoitukset.fi"
        )

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
