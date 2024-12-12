from mielenosoitukset_fi.utils.database import stringify_object_ids
from bson import ObjectId
from mielenosoitukset_fi.users.models import User


class BaseModel:
    """Mixin class for common methods like `to_dict` and `from_dict`."""

    @classmethod
    def from_dict(cls, data):
        """Create an instance from a dictionary.

        Parameters
        ----------
        data : dict


        Returns
        -------



        """
        return cls(**data)

    def to_dict(self, json=False):
        """Convert instance to dictionary.

        Parameters
        ----------
        json : bool, default=False
            If True, convert ObjectId to string.

        Returns
        -------


        """
        data = self.__dict__.copy()
        if json and "_id" in data:
            data["_id"] = str(data["_id"])
        if (
            json
            and any(isinstance(value, ObjectId) for value in data.values())
            or any(isinstance(value, User) for value in data.values())
        ):
            for key, value in data.items():
                if isinstance(value, ObjectId):
                    data[key] = str(value)

                if isinstance(value, User):
                    data[key] = value.to_dict()

        if json:
            # Replace None with None-equivalent in JSON format
            data = stringify_object_ids(data)

        return data
