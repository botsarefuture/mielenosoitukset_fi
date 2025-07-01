from typing import List, Optional, Union
from bson import ObjectId
from .BaseModel import BaseModel
from mielenosoitukset_fi.utils.database import (
    stringify_object_ids,
    get_database_manager,
)

DB = get_database_manager()


class MemberShip(BaseModel):
    """
    Represents a user's membership in an organization.

    Attributes:
        _id: ObjectId of the membership.
        user_id: ObjectId of the user.
        organization_id: ObjectId of the organization.
        role: Role string ('member', 'admin', 'owner').
        permissions: Optional list of custom permissions.
    """

    VALID_ROLES = ["member", "admin", "owner"]

    DEFAULT_PERMISSIONS = {
        "member": [
            "INVITE_TO_ORGANIZATION",
            "VIEW_ORGANIZATION",
            "LIST_ORGANIZATIONS"
        ],
        "admin": [
            # ORG
            "INVITE_TO_ORGANIZATION",
            "VIEW_ORGANIZATION",
            "LIST_ORGANIZATIONS",
            "EDIT_ORGANIZATION",
            # DEMO
            "CREATE_DEMO",
            "EDIT_DEMO",
            "VIEW_DEMO",
            "LIST_DEMOS",
            "GENERATE_EDIT_LINK",
            # RECUDEMO
            "CREATE_RECURRING_DEMO",
            "EDIT_RECURRING_DEMO",
            "VIEW_RECURRING_DEMO",
            "LIST_RECURRING_DEMOS"
        ],
        "owner": [
            # ORG
            "INVITE_TO_ORGANIZATION",
            "VIEW_ORGANIZATION",
            "LIST_ORGANIZATIONS",
            "EDIT_ORGANIZATION",
            "DELETE_ORGANIZATION",
            # DEMO
            "CREATE_DEMO",
            "EDIT_DEMO",
            "VIEW_DEMO",
            "LIST_DEMOS",
            "GENERATE_EDIT_LINK",
            "DELETE_DEMO",
            # RECUDEMO
            "CREATE_RECURRING_DEMO",
            "EDIT_RECURRING_DEMO",
            "VIEW_RECURRING_DEMO",
            "LIST_RECURRING_DEMOS",
            "DELETE_RECURRING_DEMO"
        ]
    }

    def __init__(
        self,
        user_id: ObjectId,
        organization_id: ObjectId,
        role: str = "member",
        permissions: Optional[List[str]] = None,
        _id: Optional[ObjectId] = None,
    ):
        self.user_id = user_id
        self.organization_id = organization_id
        self.role = role if role in self.VALID_ROLES else "member"

        # Combine default + custom permissions
        default_perms = set(self.DEFAULT_PERMISSIONS[self.role])
        custom_perms = set(permissions or [])
        self.permissions = sorted(default_perms | custom_perms)

        # Prevent duplicate memberships
        if _id:
            self._id = _id
        else:
            existing = self._find_by_user_and_org(user_id, organization_id)
            self._id = existing._id if existing else ObjectId()

    def save(self):
        """Ensure unique user/org combo and upsert safely."""
        existing = DB["memberships"].find_one({
            "user_id": self.user_id,
            "organization_id": self.organization_id
        })

        if existing:
            self._id = existing["_id"]
            # Merge permissions in case previous entry missed any default
            existing_perms = set(existing.get("permissions", []))
            default_perms = set(self.DEFAULT_PERMISSIONS[self.role])
            merged = default_perms | existing_perms | set(self.permissions)
            self.permissions = sorted(merged)

        DB["memberships"].update_one(
            {
                "user_id": self.user_id,
                "organization_id": self.organization_id
            },
            {
                "$set": {
                    "role": self.role,
                    "permissions": self.permissions
                }
            },
            upsert=True
        )

    def insert_to_db(self):
        """Alias for save()."""
        self.save()

    @classmethod
    def from_dict(cls, data: dict) -> "MemberShip":
        """Create a Membership from dictionary data."""
        if data.get("_id") is None:
            result = cls._find_by_user_and_org(data["user_id"], data["organization_id"])
            if result is not None:
                return result

        return cls(
            _id=data.get("_id") or ObjectId(),
            user_id=data["user_id"],
            organization_id=data["organization_id"],
            role=data.get("role", "member"),
            permissions=data.get("permissions", []),
        )

    def to_dict(self, json: bool = False) -> dict:
        """Serialize membership to dict (optionally JSON-safe)."""
        data = {
            "_id": str(self._id) if json else self._id,
            "user_id": str(self.user_id) if json else self.user_id,
            "organization_id": str(self.organization_id) if json else self.organization_id,
            "role": self.role,
            "permissions": self.permissions,
        }

        if json:
            data = stringify_object_ids(data)

        return data

    @classmethod
    def _find_by_user_and_org(cls, user_id, org_id):
        """Find one membership for this user+org combo."""
        result = DB["memberships"].find_one({
            "user_id": ObjectId(user_id),
            "organization_id": ObjectId(org_id)
        })

        if result is not None:
            return cls.from_dict(result)
        return None

    @classmethod
    def all_in_organization(cls, organization_id: Union[str, ObjectId]) -> List["MemberShip"]:
        """Fetch all memberships in a specific organization."""
        organization_id = ObjectId(organization_id)
        return [cls.from_dict(doc) for doc in DB["memberships"].find({"organization_id": organization_id})]

    @classmethod
    def all_per_user(cls, user_id: Union[str, ObjectId]) -> List["MemberShip"]:
        """Fetch all memberships belonging to a user."""
        user_id = ObjectId(user_id)
        return [cls.from_dict(doc) for doc in DB["memberships"].find({"user_id": user_id})]
