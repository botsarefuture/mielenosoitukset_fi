from mielenosoitukset_fi.utils.database import stringify_object_ids
from bson import ObjectId


class BaseModel:
    """Mixin class for common methods like `to_dict` and `from_dict`."""

    @classmethod
    def from_dict(cls, data):
        """Create an instance from a dictionary.

        Converts string `_id` to :class:`bson.ObjectId` so the model's `_id`
        is never left as a string.

        Parameters
        ----------
        data : dict
            Input dictionary used to construct the instance.

        Returns
        -------
        instance
        """
        data = data.copy()
        if "_id" in data and isinstance(data["_id"], str):
            data["_id"] = ObjectId(data["_id"])
        return cls(**data)

    def to_dict(self, json=False):
        """Convert instance to dictionary.

        When json is False (saving to DB), ensure the top-level `_id` is a
        :class:`bson.ObjectId` (not a string). When json is True, convert
        ObjectIds to strings for JSON serialization.

        Parameters
        ----------
        json : bool, default=False
            If True, convert ObjectId to string and handle nested models.

        Returns
        -------
        dict
        """
        data = self.__dict__.copy()

        if not json:
            # Ensure top-level _id is an ObjectId when preparing for save
            if "_id" in data and isinstance(data["_id"], str):
                data["_id"] = ObjectId(data["_id"])
            return data

        # json=True branch: convert ObjectId => str and nested models => dict
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
