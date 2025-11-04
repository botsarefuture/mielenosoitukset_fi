from typing import Dict, List, Union
from bson import ObjectId

from mielenosoitukset_fi.utils.classes.BaseModel   import BaseModel
from mielenosoitukset_fi.utils.classes.MemberShip  import MemberShip as Membership
from mielenosoitukset_fi.utils.database            import get_database_manager
from mielenosoitukset_fi.utils.classes.Organizer   import BaseEntity

DB = get_database_manager()


class Organization(BaseEntity):
    """Represents an organization and bridges to the `memberships` collection."""

    def __init__(
        self,
        name: str,
        description: str,
        email: str,
        website: str = "",
        social_media_links: Dict[str, str] = None,
        members: List[object] = None,          # kept for legacy compatibility – ignored
        verified: bool = False,
        _id: ObjectId = None,
        invitations: List[dict] = None,
        fill_url: str = None,          # ✨ added param
    ):
        super().__init__(name, email, website, _id)
        self.description        = description
        self.social_media_links = social_media_links or {}
        self.verified           = verified
        self.invitations        = invitations or []

        # if org is not verified → autogenerate /organization/<id>/fill
        self.fill_url = fill_url or (f"/organization/{self._id}/fill" if not verified and self._id else None)


        self.members: List["User"] = []        # populated below
        self.init_members()

    # ------------------------------------------------------------------ members

    def init_members(self):
        """Refresh `self.members` from the memberships collection."""
        memberships = Membership.all_in_organization(self._id)
        self.members.clear()

        # Lazy import (avoids circular import with users.models)
        from mielenosoitukset_fi.users.models import User

        for m in memberships:
            user = User.from_OID(m.user_id)
            user.role        = m.role
            user.permissions = m.permissions
            self.members.append(user)

    def is_member(self,  email: str = None, user_id: ObjectId = None) -> bool:
        if not email and not user_id:
            raise TypeError("Pass either email or user_id")

        for u in self.members:
            if email and u.email == email:
                return True
            if user_id and str(u._id) == str(user_id):
                return True
        return False

    # --------------------------- mutate memberships (add / update)

    def add_member(
        self,
        member: Union[str, ObjectId, "User"],
        role: str = "member",
        permissions: List[str] | None = None,
    ):
        from mielenosoitukset_fi.users.models import User   # lazy import

        if isinstance(member, User):
            member = member._id
        if isinstance(member, str):
            member = ObjectId(member)

        if self.is_member(user_id=member):
            return  # already there

        Membership(user_id=member,
                   organization_id=self._id,
                   role=role,
                   permissions=permissions or []).save()
        self.init_members()

    def update_member(
        self,
        member: Union[str, ObjectId, "User"],
        role: str = "member",
        permissions: List[str] | None = None,
    ):
        from mielenosoitukset_fi.users.models import User   # lazy import

        if isinstance(member, User):
            member = member._id
        if isinstance(member, str):
            member = ObjectId(member)

        Membership(user_id=member,
                   organization_id=self._id,
                   role=role,
                   permissions=permissions or []).save()
        self.init_members()

    def get_member(self, user_id: Union[str, ObjectId]):
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        return next((u for u in self.members if u._id == user_id), None)

    # ------------------------------------------------------------------ storage

    def save(self):
        DB["organizations"].update_one(
            {"_id": self._id}, {"$set": self.to_dict()}, upsert=True
        )

    @classmethod
    def from_dict(cls, data: dict):
        data.pop("social_medias", None)  # prune legacy keys
        data.pop("members", None)

        # Ensure fill_url auto-assigns if org isn't verified
        org = cls(**data)
        if not org.verified and org._id:
            org.fill_url = f"/organization/{org._id}/fill"
        return org
