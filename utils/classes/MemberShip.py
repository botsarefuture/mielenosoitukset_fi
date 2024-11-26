from typing import List
from bson import ObjectId
from .BaseModel import BaseModel
from utils.database import stringify_object_ids, get_database_manager

DB = get_database_manager()


class MemberShip(BaseModel):
    """ """

    def __init__(
        self,
        user_id: ObjectId,
        organization_id: ObjectId,
        role: str,
        permissions: List[str] = None,
    ):
        self.user_id = user_id
        self.organization_id = organization_id
        self.role = role
        self.permissions = permissions or []

    def save(self):
        """Save the membership to MongoDB."""
        # Save to users info, as user["organizations"], and to organization["members"]
        user = DB["users"].find_one({"_id": self.user_id})
        organization = DB["organizations"].find_one({"_id": self.organization_id})

        if user and organization:
            # Update user's organizations
            if "organizations" not in user:
                user["organizations"] = []
            if self.organization_id not in user["organizations"]:
                user["organizations"].append(
                    {
                        "org_id": self.organization_id,
                        "role": self.role,
                        "permissions": self.permissions,
                    }
                )

            DB["users"].update_one(
                {"_id": ObjectId(self.user_id)},
                {"$set": {"organizations": user["organizations"]}},
            )

            # Update organization's members
            if "members" not in organization:
                organization["members"] = []
            if self.user_id not in [
                member["user_id"] for member in organization["members"]
            ]:
                organization["members"].append(
                    {
                        "user_id": self.user_id,
                        "role": self.role,
                        "permissions": self.permissions,
                    }
                )
            DB["organizations"].update_one(
                {"_id": self.organization_id},
                {"$set": {"members": organization["members"]}},
            )

    @classmethod
    def from_dict(cls, data: dict):
        """Create a Membership instance from a dictionary.

        Parameters
        ----------
        data :
            dict:
        data : dict :

        data : dict :

        data : dict :

        data : dict :

        data: dict :


        Returns
        -------


        """
        return cls(**data)

    def to_dict(self, json=False):
        """Convert instance to dictionary.

        Parameters
        ----------
        json : bool, default=False
            If True, the dictionary will be JSON serializable.

        Returns
        -------
        dict
            The instance as a dictionary.

        See Also
        --------
        utils.database.stringify_object_ids : Replace None with None-equivalent in JSON format.


        """
        data = self.__dict__.copy()
        if json and "_id" in data:
            data["_id"] = str(data["_id"])

        if json:
            # Replace None with None-equivalent in JSON format
            data = stringify_object_ids(data)

        return data

    def insert_to_db(self):
        """Insert the membership to the database."""
        # Same as in save method
        self.save()
