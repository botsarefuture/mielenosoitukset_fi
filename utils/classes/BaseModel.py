from utils.database import stringify_object_ids

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

        if json:
            # Replace None with None-equivalent in JSON format
            data = stringify_object_ids(data)

        return data