from datetime import datetime
from typing import Any, Dict, Optional
from bson import ObjectId
from .BaseModel import BaseModel
from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.logger import logger


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
        self._user_id = user_id
        self._email = email
        self._action = action
        self._details = details
        self._timestamp = timestamp or datetime.utcnow()
        self._date_time = self._timestamp.strftime("%Y-%m-%d %H:%M:%S")
        self._id = _id or ObjectId()
        self._by = User.from_OID(user_id)

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
        try:
            data.update(
                {
                    "user_id": str(self._user_id),
                    "email": self._email,
                    "action": self._action,
                    "details": self._details,
                    "timestamp": (
                        self._timestamp.isoformat() if json else self._timestamp
                    ),
                    "_id": str(self._id),
                    "by": self._by.to_dict(json=json),
                }
            )
        except Exception as e:
            logger.error(e)
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
            user_id=ObjectId(data["user"]["id"]),
            email=data["user"]["email"],
            action=data["request"],
            details="",
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if data.get("timestamp") and isinstance(data.get("timestamp"), str)
                else None
            ),
            _id=ObjectId(data["_id"]) if data.get("_id") else None,
        )


class UserDataFormatter:
    def __init__(self, data):
        self.data = data

    def format_timestamp(self):
        timestamp = self.data.get("timestamp", {}).get("$date")
        if timestamp:
            return datetime.fromisoformat(timestamp[:-1]).strftime("%Y-%m-%d %H:%M:%S")
        return "Unknown"

    def format_request(self):
        request = self.data.get("request", {})
        formatted_request = {
            "Method": request.get("method", "Unknown"),
            "URL": request.get("url", "Unknown"),
            "Remote Address": request.get("remote_addr", "Unknown"),
            "User Agent": request.get("headers", "")
            .split("User-Agent: ")[-1]
            .split("\r\n")[0],
        }
        return formatted_request

    def format_user(self):
        user = self.data.get("user", {})
        formatted_user = {
            "Username": user.get("username", "Unknown"),
            "Display Name": user.get("displayname", "Unknown"),
            "Email": user.get("email", "Unknown"),
            "Bio": user.get("bio", "None"),
            "Profile Picture": user.get("profile_picture", "None"),
            "Role": user.get("role", "Unknown"),
            "Global Admin": "Yes" if user.get("global_admin") else "No",
            "Banned": "Yes" if user.get("banned") else "No",
        }
        return formatted_user

    def format_permissions(self):
        permissions = self.data.get("user", {}).get("global_permissions", [])
        return permissions if permissions else ["No permissions found"]

    def display(self):
        formatted_data = {
            "Timestamp": self.format_timestamp(),
            "Request": self.format_request(),
            "User": self.format_user(),
            "Permissions": self.format_permissions(),
        }
        return formatted_data
