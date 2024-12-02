from bson import ObjectId
from .BaseModel import BaseModel
from mielenosoitukset_fi.utils.database import get_database_manager
from flask import url_for
from typing import Dict, List, Union
from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.classes.MemberShip import MemberShip as Membership

DB = get_database_manager()

class BaseEntity(BaseModel):
    """Base class for shared attributes and methods."""

    def __init__(self, name: str, email: str, website: str = None, _id: ObjectId = None):
        self.name = name
        self.email = email
        self.website = website
        self._id = _id or ObjectId()

    def to_dict(self, json=False):
        """
        Convert the entity to a dictionary.

        Parameters
        ----------
        json : bool, optional
            Whether to return a JSON-serializable dictionary (default is False).

        Returns
        -------
        dict
            The entity as a dictionary.
        """
        data = super().to_dict(json)
        return data

class Organizer(BaseEntity):
    """Class representing an individual organizer."""

    def __init__(
        self,
        name: str = None,
        email: str = None,
        organization_id: ObjectId = None,
        website: str = None,
        url: str = None,
    ):
        super().__init__(name, email, website)
        self.organization_id = organization_id or None
        self.url = url

        if organization_id:
            self.fetch_organization_details()

    def fetch_organization_details(self):
        """Fetch the organization details from the database using the organization_id."""
        if not self.organization_id:
            return

        organization = DB["organizations"].find_one({"_id": self.organization_id})

        if organization:
            self.name = organization.get("name")
            self.email = organization.get("email")
            self.website = organization.get("website")
            try:
                self.url = url_for("org", org_id=str(self.organization_id))
            except RuntimeError:
                self.url = f"/org/{self.organization_id}"

    def validate_organization_id(self):
        """Validate the existence of organization_id in the database."""
        if not self.organization_id:
            return False

        return bool(DB["organizations"].find_one({"_id": self.organization_id}))
