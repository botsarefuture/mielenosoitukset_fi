# utils/notifications.py
from datetime import datetime
from bson import ObjectId

from datetime import datetime

from bson import ObjectId
from flask_babel import _

from mielenosoitukset_fi.utils.database import get_database_manager

mongo = get_database_manager()


def create_notification(user_id: str | ObjectId, n_type: str, payload: dict, link: str):
    doc = {
        "user_id": ObjectId(user_id),
        "type": n_type,
        "payload": payload or {},
        "link": link,
        "created_at": datetime.utcnow(),
        "read": False,
    }
    mongo.notifications.insert_one(doc)


def fetch_notifications(user_id, limit: int = 20):
    cur = (
        mongo.notifications
        .find({"user_id": ObjectId(user_id)})
        .sort("created_at", -1)
        .limit(limit)
    )
    return list(cur)


def mark_all_read(user_id):
    mongo.notifications.update_many(
        {"user_id": ObjectId(user_id), "read": False},
        {"$set": {"read": True}},
    )


def serialize_notification(doc: dict) -> dict:
    """
    Turn a raw Mongo notification document into a dict that:
    - is used by the JSON API (/api/notifications/)
    - is used in Jinja (user_notifications, full list page)

    Shape:
      {
        "id": str,
        "type": str,
        "message": str,
        "icon": str,        # ONLY icon classes, no colour classes
        "link": str,
        "time": iso-string,
        "created_at": datetime,
        "read": bool,
      }
    """
    payload = doc.get("payload") or {}
    n_type = doc.get("type")

    if n_type == "org_invite":
        message = _("Kutsu organisaatioon: ") + payload.get("organization_name", "")
        icon = "fa-solid fa-building-circle-check"
    elif n_type == "friend_request":
        message = _("Kaveripyyntö käyttäjältä ") + payload.get("sender_name", "")
        icon = "fa-solid fa-user-plus"
    elif n_type == "demo_invite":
        message = _("Kutsu mielenosoitukseen: ") + payload.get("demo_title", "")
        icon = "fa-solid fa-bullhorn"
    elif n_type == "demo_cancelled":
        message = _("Mielenosoitus peruttu: ") + payload.get("demo_title", "")
        icon = "fa-solid fa-ban"
    else:
        # Fallback: either explicit message field or generic info
        message = doc.get("message", "")
        icon = "fa-solid fa-info-circle"

    created_at = doc.get("created_at") or datetime.utcnow()

    return {
        "id": str(doc["_id"]),
        "type": n_type,
        "message": message,
        "icon": icon,                          # colour is added in templates/JS
        "link": doc.get("link") or "#",
        "time": created_at.isoformat(),
        "created_at": created_at,
        "read": bool(doc.get("read", False)),
    }
