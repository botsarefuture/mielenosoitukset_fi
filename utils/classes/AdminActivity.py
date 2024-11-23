from datetime import datetime
from typing import Any, Dict, Optional
from bson import ObjectId
from .BaseModel import BaseModel
from users.models import User

class AdminActivity(BaseModel):
    """Class to represent an admin activity."""

    def __init__(
        self,
        user_id: ObjectId,
        email: str,
        action: str,
        details: str,
        timestamp: Optional[datetime] = None,
        _id: Optional[ObjectId] = None,
    ):
        """
        Initialize an AdminActivity instance.

        Parameters
        ----------
        user_id : ObjectId
            The ID of the user performing the action.
        email : str
            The email of the user performing the action.
        action : str
            The action performed by the user.
        details : str
            Additional details about the action.
        timestamp : datetime, optional
            The timestamp of the action. Defaults to the current time.
        _id : ObjectId, optional
            The unique identifier for the activity. Defaults to None.
        """
        self.user_id = user_id
        self.email = email
        self.action = action
        self.details = details
        self.timestamp = timestamp or datetime.utcnow()
        self.date_time = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        self._id = _id or ObjectId()
        self.by = User.from_OID(user_id)

    def to_dict(self, json=False) -> Dict[str, Any]:
        """
        Convert the AdminActivity instance to a dictionary.

        Parameters
        ----------
        json : bool, optional
            If True, convert the instance to a JSON-compatible dictionary. Defaults to False.

        Returns
        -------
        dict
            A dictionary representation of the AdminActivity instance.
        """
        data = super().to_dict(json=json)
               
        data["by"] = self.by.to_dict(json=json)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdminActivity":
        """
        Create an AdminActivity instance from a dictionary.

        Parameters
        ----------
        data : dict
            A dictionary containing the data to initialize the instance.

        Returns
        -------
        AdminActivity
            An instance of the AdminActivity class.
        """
        return cls(
            user_id=ObjectId(data["user_id"]),
            email=data["email"],
            action=data["action"],
            details=data["details"],
            timestamp=data.get("timestamp"),
            _id=ObjectId(data["_id"]) if data.get("_id") else None,
        )