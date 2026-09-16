"""City-admin assignment for newly submitted demonstrations.

When a demonstration is submitted for a city that has active city admins, the
demonstration is assigned to those admins: they receive the moderation email and
the national admin queue is skipped. If nobody acts within 24 hours a background
job (``scripts/escalate_city_assignments``) escalates the demonstration back to
the national team, which then receives the notification instead.

The assignment is stored on the demonstration document under the
``city_assignment`` sub-document:

.. code-block:: python

    {
        "assigned_at": <naive UTC datetime>,      # set at assignment; reset on city action
        "city_key": "helsinki",
        "city_admin_ids": [ObjectId, ...],        # snapshot of the assigned admins
        "escalated": False,
        "escalated_at": None,                     # set when escalated to national team
        "escalation_notified_at": None,           # guards double notification
    }

The field is removed once the demonstration is approved or rejected.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional

from bson import ObjectId

from mielenosoitukset_fi.utils.cities import normalize_city_key
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.time_utils import utcnow

CITY_ASSIGNMENT_FIELD = "city_assignment"
ESCALATION_PERMISSION = "ACCEPT_DEMO"
DEFAULT_ESCALATION_HOURS = 24

# Mongo filter clause that matches demonstrations NOT currently owned by city admins.
# Used by the national pending views and the national reminder job: assigned but
# not-yet-escalated demonstrations belong to the city admins.
NOT_ESCALATED_ASSIGNMENT_CLAUSE = {
    "$or": [
        {CITY_ASSIGNMENT_FIELD: {"$exists": False}},
        {"city_assignment.escalated": True},
    ]
}


def _as_object_id(value) -> Optional[ObjectId]:
    if value is None:
        return None
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def active_city_admins_for_city(db, city_key: str) -> List[Dict[str, Any]]:
    """Return active city admins able to approve demonstrations in ``city_key``.

    A user counts as a city admin for a city when there is a live (non-revoked)
    ``admin_scope_grants`` entry for that city carrying the ``ACCEPT_DEMO``
    permission and the user account is not deactivated or banned.
    """
    city_key = normalize_city_key(city_key)
    if not city_key:
        return []

    grants = list(
        db.admin_scope_grants.find(
            {
                "scope_type": "city",
                "$or": [
                    {"scope_keys": city_key},
                    {"scope_key": city_key},
                ],
                "permissions": ESCALATION_PERMISSION,
                "$or": [
                    {"revoked_at": {"$exists": False}},
                    {"revoked_at": None},
                ],
            }
        )
    )

    user_ids: List[Any] = []
    for grant in grants:
        keys = [normalize_city_key(k) for k in (grant.get("scope_keys") or [])]
        if grant.get("scope_key"):
            keys.append(normalize_city_key(grant["scope_key"]))
        if city_key not in keys:
            continue
        user_id = grant.get("user_id")
        if user_id:
            user_ids.append(user_id)

    oids = [_as_object_id(uid) for uid in user_ids]
    oids = [oid for oid in oids if oid is not None]
    if not oids:
        return []

    users = list(
        db.users.find(
            {
                "_id": {"$in": oids},
                "active": {"$ne": False},
                "banned": {"$ne": True},
            },
            {"_id": 1, "email": 1, "displayname": 1, "username": 1},
        )
    )

    admins: List[Dict[str, Any]] = []
    for user in users:
        email = (user.get("email") or "").strip()
        if not email:
            continue
        admins.append(
            {
                "user_id": user["_id"],
                "email": email,
                "displayname": user.get("displayname") or user.get("username"),
            }
        )
    return admins


def assign_demo_to_city(
    db,
    demo_id,
    city_key: str,
    city_admins: List[Dict[str, Any]],
    *,
    template_name: str,
    subject: str,
    context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Assign ``demo_id`` to ``city_admins`` and return the email message.

    Writes the ``city_assignment`` sub-document on the demonstration and returns
    the ``demo_notifications_queue`` message payload the caller should enqueue.
    Returns ``None`` when there is nothing to assign so the caller can fall back
    to the national queue.
    """
    demo_oid = _as_object_id(demo_id)
    if demo_oid is None or not city_key or not city_admins:
        return None

    now = utcnow()
    db.demonstrations.update_one(
        {"_id": demo_oid},
        {
            "$set": {
                CITY_ASSIGNMENT_FIELD: {
                    "assigned_at": now,
                    "city_key": normalize_city_key(city_key),
                    "city_admin_ids": [admin["user_id"] for admin in city_admins],
                    "escalated": False,
                    "escalated_at": None,
                    "escalation_notified_at": None,
                }
            }
        },
    )
    logger.info(
        "Demo %s assigned to %d city admin(s) for %s.",
        demo_oid,
        len(city_admins),
        city_key,
    )

    return {
        "template_name": template_name,
        "subject": subject,
        "recipients": [admin["email"] for admin in city_admins if admin.get("email")],
        "context": context,
    }


def touch_city_assignment(db, demo_id) -> bool:
    """Reset the 24 h escalation window for a demo with a live assignment."""
    demo_oid = _as_object_id(demo_id)
    if demo_oid is None:
        return False
    result = db.demonstrations.update_one(
        {
            "_id": demo_oid,
            CITY_ASSIGNMENT_FIELD: {"$exists": True},
            "city_assignment.escalated": {"$ne": True},
        },
        {"$set": {"city_assignment.assigned_at": utcnow()}},
    )
    return result.modified_count > 0


def clear_city_assignment(db, demo_id) -> bool:
    """Remove the assignment (used when a decision resolves the demo)."""
    demo_oid = _as_object_id(demo_id)
    if demo_oid is None:
        return False
    result = db.demonstrations.update_one(
        {"_id": demo_oid}, {"$unset": {CITY_ASSIGNMENT_FIELD: ""}}
    )
    return result.modified_count > 0


def has_live_assignment(demo_doc: Dict[str, Any]) -> bool:
    """True when the demo is still owned by city admins (not escalated)."""
    if not isinstance(demo_doc, dict):
        demo_doc = getattr(demo_doc, "to_dict", lambda: {})() or {}
    assignment = demo_doc.get(CITY_ASSIGNMENT_FIELD) or {}
    return bool(assignment) and not bool(assignment.get("escalated"))


def escalate_overdue(
    db,
    *,
    escalate_after_hours: int = DEFAULT_ESCALATION_HOURS,
    max_to_process: int = 50,
) -> List[Dict[str, Any]]:
    """Return assigned demos whose 24 h window has elapsed and await escalation.

    This is read-only; the caller is responsible for emailing the national team
    and flipping ``city_assignment.escalated`` (see the escalation script).
    """
    cutoff = utcnow() - timedelta(hours=escalate_after_hours)
    query = {
        CITY_ASSIGNMENT_FIELD: {"$exists": True},
        "city_assignment.escalated": {"$ne": True},
        "city_assignment.assigned_at": {"$lte": cutoff},
        "approved": {"$ne": True},
        "$or": [{"rejected": {"$exists": False}}, {"rejected": False}],
        "cancelled": {"$ne": True},
    }
    demos = list(db.demonstrations.find(query).limit(max_to_process))
    logger.info("Found %d city-assigned demo(s) awaiting escalation.", len(demos))
    return demos


def mark_escalated(db, demo_id, *, notified: bool = True) -> bool:
    """Flip an active assignment to escalated (guard against double escalation)."""
    demo_oid = _as_object_id(demo_id)
    if demo_oid is None:
        return False
    now = utcnow()
    payload: Dict[str, Any] = {
        "city_assignment.escalated": True,
        "city_assignment.escalated_at": now,
    }
    if notified:
        payload["city_assignment.escalation_notified_at"] = now
    result = db.demonstrations.update_one(
        {
            "_id": demo_oid,
            CITY_ASSIGNMENT_FIELD: {"$exists": True},
            "city_assignment.escalated": {"$ne": True},
        },
        {"$set": payload},
    )
    return result.modified_count > 0