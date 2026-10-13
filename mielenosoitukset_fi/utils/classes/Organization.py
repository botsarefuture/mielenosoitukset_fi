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
        logo: str | None = None,
        social_media_links: Dict[str, str] = None,
        members: List[object] = None,          # kept for legacy compatibility – ignored
        verified: bool = False,
        _id: ObjectId = None,
        invitations: List[dict] = None,
        fill_url: str = None,
    ):
        super().__init__(name=name, email=email, website=website, _id=_id, logo=logo)
        self.description        = description
        self.social_media_links = social_media_links or {}
        self.verified           = verified
        self.invitations        = invitations or []

        # if org is not verified → autogenerate /organization/<id>/fill
        self.fill_url = fill_url or (f"/organization/{self._id}/fill" if not verified and self._id else None)


        # Public organization pages do not need membership/user records.
        self._members = None

    # ------------------------------------------------------------------ members

    @property
    def members(self):
        """Load members on demand, retaining the existing member API."""
        if self._members is None:
            self.init_members()
        return self._members

    def init_members(self):
        """Refresh members in one batch; missing legacy users grant no access."""
        memberships = Membership.all_in_organization(self._id)

        # Lazy import (avoids circular import with users.models)
        from mielenosoitukset_fi.users.models import User

        user_ids = [ObjectId(m.user_id) if isinstance(m.user_id, str) else m.user_id
                    for m in memberships]
        documents = {doc["_id"]: doc for doc in DB["users"].find(
            {"_id": {"$in": user_ids}}
        )} if user_ids else {}
        members = []
        for m, user_id in zip(memberships, user_ids):
            document = documents.get(user_id)
            if document is None:
                continue
            # Invalid persisted user data still raises rather than hiding errors.
            user = User.from_db(document)
            user.role        = m.role
            user.permissions = m.permissions
            user._ship_id    = m._id
            members.append(user)
        self._members = members

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

    def to_dict(self, json=False):
        """Serialize organization fields, never cached member credentials."""
        data = super().to_dict(json=json)
        data.pop("_members", None)
        return data

    def save(self):
        DB["organizations"].update_one(
            {"_id": self._id}, {"$set": self.to_dict()}, upsert=True
        )

    @classmethod
    def from_dict(cls, data: dict):
        data = data.copy()
        data.pop("social_medias", None)  # prune legacy keys
        data.pop("members", None)

        # Ensure fill_url auto-assigns if org isn't verified
        org = cls(**data)
        if not org.verified and org._id:
            org.fill_url = f"/organization/{org._id}/fill"
            
        return org
