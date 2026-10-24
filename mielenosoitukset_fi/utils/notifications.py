# utils/notifications.py
from mielenosoitukset_fi.utils.time_utils import utcnow
from datetime import datetime
from bson import ObjectId

from datetime import datetime

from bson import ObjectId
from flask_babel import _
from itertools import islice

from mielenosoitukset_fi.utils.database import get_database_manager

mongo = get_database_manager()


def create_notification(user_id: str | ObjectId, n_type: str, payload: dict, link: str):
    doc = {
        "user_id": ObjectId(user_id),
        "type": n_type,
        "payload": payload or {},
        "link": link,
        "created_at": utcnow(),
        "read": False,
    }
    mongo.notifications.insert_one(doc)


def fetch_notifications(user_id, limit: int = 20):
    cur = (
        mongo.notifications
        .find({"user_id": ObjectId(user_id)})
        .sort([("created_at", -1), ("_id", -1)])
        .batch_size(50)
        .max_time_ms(5000)
    )
    # Assignment notices are private moderation data, not permanent grants.
    # Recheck the current assignment and permission before every API/page read.
    # Stream rather than materializing historical notices; hidden entries must
    # not consume the visible inbox quota. The database cursor has a time limit.
    return list(islice((doc for doc in cur if _assignment_notice_visible(doc, user_id)), limit))


def _assignment_notice_visible(doc, user_id):
    if doc.get("type") != "city_review":
        return True
    demo_id = (doc.get("payload") or {}).get("demo_id")
    return ObjectId(user_id) in _city_review_recipients(mongo, demo_id)[1]


def _city_review_recipients(db, demo_id):
    """Use the same live assignment/scope check for delivery and inbox reads."""
    from mielenosoitukset_fi.utils.city_assignment import (
        active_city_admins_for_city, has_live_assignment,
    )
    from mielenosoitukset_fi.utils.cities import normalize_city_key

    demo = db.demonstrations.find_one({"_id": demo_id})
    if not demo or any(demo.get(key) for key in ("approved", "rejected", "cancelled", "in_past", "merged_into")):
        return demo, set()
    if not has_live_assignment(demo):
        return demo, set()
    assignment = demo["city_assignment"]
    # Match the review route: populated city_key is authoritative over the
    # legacy display name, including contradictory historical documents.
    city_key = demo.get("city_key") or normalize_city_key(demo.get("city") or "")
    if city_key != assignment.get("city_key"):
        return demo, set()
    assigned = set(assignment.get("city_admin_ids") or [])
    return demo, {
        admin["user_id"]
        for admin in active_city_admins_for_city(db, assignment["city_key"])
        if admin["user_id"] in assigned
    }


def notify_city_reviewers(db, demo_id):
    """Idempotent inbox delivery through the existing submission job/retry path.

    Store no submitter details or bearer URLs. A stable ID deduplicates retries
    without changing an already-read notice back to unread.
    """
    demo_id = ObjectId(demo_id)
    demo, recipients = _city_review_recipients(db, demo_id)
    for user_id in recipients:
        db.notifications.update_one(
            {"_id": f"city-review:{demo_id}:{user_id}"},
            {"$setOnInsert": {
                "user_id": user_id, "type": "city_review",
                "payload": {"demo_id": demo_id, "demo_title": demo.get("title") or ""},
                "link": f"/admin/demo/review/{demo_id}",
                "created_at": utcnow(), "read": False,
            }},
            upsert=True,
        )


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

    if n_type == "city_review":
        message = _("Odottaa hyväksyntää") + ": " + payload.get("demo_title", "")
        icon = "fa-solid fa-clipboard-check"
    elif n_type == "org_invite":
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
    elif n_type == "recurring_demo_update":
        message = _("Seuraamasi mielenosoitussarja päivittyi: ") + payload.get("demo_title", "")
        icon = "fa-solid fa-arrows-rotate"
    else:
        # Fallback: either explicit message field or generic info
        message = doc.get("message", "")
        icon = "fa-solid fa-info-circle"

    created_at = doc.get("created_at") or utcnow()

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
