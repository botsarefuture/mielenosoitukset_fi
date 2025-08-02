from datetime import datetime
from typing import Any, Dict, Optional
from bson import ObjectId
from .BaseModel import BaseModel
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
        self._user_id = user_id
        self._email = email
        self._action = action
        self._details = details
        self._timestamp = timestamp or datetime.utcnow()
        self._date_time = self._timestamp.strftime("%Y-%m-%d %H:%M:%S")
        self._id = _id or ObjectId()

        # 🧠 Lazy import to avoid circular import
        from mielenosoitukset_fi.users.models import User
        self._by = User.from_OID(user_id)

    def to_dict(self, json: bool = False) -> Dict[str, Any]:
        data = super().to_dict(json=json)
        try:
            data.update({
                "user_id": str(self._user_id),
                "email": self._email,
                "action": self._action,
                "details": self._details,
                "timestamp": (
                    self._timestamp.isoformat() if json else self._timestamp
                ),
                "_id": str(self._id),
                "by": self._by.to_dict(json=json),
            })
        except Exception as e:
            logger.error(f"Error serializing AdminActivity: {e}")
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdminActivity":
        user_data = data.get("user", {})
        return cls(
            user_id=ObjectId(user_data.get("_id")) if user_data.get("_id") else ObjectId(),
            email=user_data.get("email", ""),
            action=data.get("request", ""),
            details=data.get("details", ""),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if isinstance(data.get("timestamp"), str)
                else None
            ),
            _id=ObjectId(data["_id"]) if data.get("_id") else None,
        )


class UserDataFormatter:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def format_timestamp(self) -> str:
        timestamp_raw = self.data.get("timestamp", {}).get("$date")
        try:
            if timestamp_raw:
                return datetime.fromisoformat(timestamp_raw.rstrip("Z")).strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.warning(f"Invalid timestamp format: {e}")
        return "Unknown"

    def format_request(self) -> Dict[str, str]:
        request_data = self.data.get("request", {})
        headers = request_data.get("headers", "")

        user_agent = "Unknown"
        if isinstance(headers, str):
            try:
                user_agent = headers.split("User-Agent: ")[-1].split("\r\n")[0]
            except IndexError:
                pass

        return {
            "Method": request_data.get("method", "Unknown"),
            "URL": request_data.get("url", "Unknown"),
            "Remote Address": request_data.get("remote_addr", "Unknown"),
            "User Agent": user_agent,
        }

    def format_user(self) -> Dict[str, str]:
        user = self.data.get("user", {})
        return {
            "Username": user.get("username", "Unknown"),
            "Display Name": user.get("displayname", "Unknown"),
            "Email": user.get("email", "Unknown"),
            "Bio": user.get("bio", "None"),
            "Profile Picture": user.get("profile_picture", "None"),
            "Role": user.get("role", "Unknown"),
            "Global Admin": "Yes" if user.get("global_admin") else "No",
            "Banned": "Yes" if user.get("banned") else "No",
        }

    def format_permissions(self) -> list:
        permissions = self.data.get("user", {}).get("global_permissions", [])
        return permissions if permissions else ["No permissions found"]

    def display(self) -> Dict[str, Any]:
        return {
            "Timestamp": self.format_timestamp(),
            "Request": self.format_request(),
            "User": self.format_user(),
            "Permissions": self.format_permissions(),
        }
