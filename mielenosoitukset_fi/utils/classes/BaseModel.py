from mielenosoitukset_fi.utils.database import stringify_object_ids
from bson import ObjectId


class BaseModel:
    """Mixin class for common methods like `to_dict` and `from_dict`."""

    @classmethod
    def from_dict(cls, data):
        """Create an instance from a dictionary."""
        return cls(**data)

    def to_dict(self, json=False):
        """Convert instance to dictionary.

        Parameters
        ----------
        json : bool, default=False
            If True, convert ObjectId to string and handle nested models.

        Returns
        -------
        dict
        """
        data = self.__dict__.copy()

        if json:
            if "_id" in data:
                data["_id"] = str(data["_id"])

            for key, value in data.items():
                if isinstance(value, ObjectId):
                    data[key] = str(value)
                elif (
                    isinstance(value, object)
                    and value.__class__.__name__ == "User"
                ):
                    data[key] = value.to_dict(True)

            data = stringify_object_ids(data)

        return data
