from typing import Dict, List, Union
from bson import ObjectId
from mielenosoitukset_fi.utils.classes.BaseModel import BaseModel
from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.classes.MemberShip import MemberShip as Membership
from mielenosoitukset_fi.utils.database import get_database_manager

DB = get_database_manager()

from mielenosoitukset_fi.utils.classes.Organizer import BaseEntity

class Organization(BaseEntity):
    """Class representing an organization."""

    def __init__(
        self,
        name: str,
        description: str,
        email: str,
        website: str = "",
        social_media_links: Dict[str, str] = None,
        members: List[User] = None,
        verified: bool = False,
        _id=None,
        invitations=None,
    ):
        super().__init__(name, email, website, _id)
        self.description = description
        self.social_media_links = social_media_links or {}
        self.members = members or []
        self.verified = verified
        self.invitations = invitations or []

        self.init_members()

    def init_members(self):
        """Initialize the members list."""
        self.members = [
            User.from_OID(ObjectId(member["user_id"]))
            for member in self.members
        ]

    def save(self):
        """Save the organization to MongoDB."""
        DB["organizations"].update_one(
            {"_id": self._id}, {"$set": self.to_dict()}, upsert=True
        )

    @classmethod
    def from_dict(cls, data: dict):
        """
        Create an instance of the class from a dictionary.

        Parameters
        ----------
        data : dict
            A dictionary containing the data to initialize the instance.

        Returns
        -------
        Organization : Organization
            An instance of the Organization class.
        """
        # Remove any deprecated or unnecessary keys
        data.pop("social_medias", None)  # Remove 'social_medias' if it exists
        return cls(**data)

    def is_member(self, email):
        """Check if a user with the given email is a member of the organization.

        Parameters
        ----------
        email : str
            The email address of the user to check.

        Returns
        -------
        bool
            True if the user is a member, False otherwise.

        Raises
        ------
        TypeError
            If the email is not a string.
        """
        if not isinstance(email, str):
            raise TypeError("Email must be a string.")

        return any(member.email == email for member in self.members)

    def add_member(self, member: Union[ObjectId, User], role="member", permissions=[]):
        """Add a member to the organization.

        Parameters
        ----------
        member : Union[ObjectId, User]
            The member to add, either as an ObjectId or User instance.
        role : str, optional
            The role of the member in the organization (default is "member").
        permissions : list, optional
            The permissions of the member (default is []).

        Returns
        -------
        None
        """
        if isinstance(member, User):
            member = ObjectId(member._id)

        elif isinstance(member, str):
            member = ObjectId(member)

        Membership(member, self._id, role, permissions).save()
