"""Permission-scoped, bounded city review queue; reads never reset deadlines."""

from datetime import UTC
from math import ceil
from zoneinfo import ZoneInfo

from mielenosoitukset_fi.utils.cities import CITY_KEY_TO_NAME, normalize_city_key
from mielenosoitukset_fi.utils.city_assignment import city_review_deadline, city_review_hours

PAGE_SIZE = 20


def city_review_queue(db, user, page, now):
    keys = set()
    for permission in ("LIST_DEMOS", "VIEW_DEMO", "ACCEPT_DEMO"):
        keys.update(user.scoped_city_keys_for(permission))
    # A populated city_key is authoritative, just as in has_demo_permission.
    # Do not let a contradictory legacy city name widen another city's scope.
    city_scope = {"$or": [
        {"city_key": {"$in": sorted(keys)}},
        {"$and": [
            {"$or": [{"city_key": {"$exists": False}}, {"city_key": None}, {"city_key": ""}]},
            {"city": {"$in": [CITY_KEY_TO_NAME[key] for key in keys if key in CITY_KEY_TO_NAME]}},
        ]},
    ]}
    query = {"$and": [city_scope, {
        "city_assignment": {"$type": "object"}, "approved": {"$ne": True},
        "rejected": {"$ne": True}, "cancelled": {"$ne": True},
    }]}
    total = db.demonstrations.count_documents(query, maxTimeMS=5000)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    try:
        page = min(max(int(page), 1), pages)
    except (ValueError, TypeError):
        page = 1
    hours = city_review_hours()
    # Mirror the shared reader: explicit null/malformed stored deadlines do not
    # fall back; only truly absent legacy fields use assigned_at + current hours.
    deadline = {"$cond": [
        {"$eq": [{"$type": "$city_assignment.review_deadline_at"}, "missing"]},
        {"$cond": [
            {"$eq": [{"$type": "$city_assignment.assigned_at"}, "date"]},
            {"$add": ["$city_assignment.assigned_at", hours * 3600000]}, None,
        ]},
        {"$cond": [
            {"$eq": [{"$type": "$city_assignment.review_deadline_at"}, "date"]},
            "$city_assignment.review_deadline_at", None,
        ]},
    ]}
    pipeline = [
        {"$match": query}, {"$addFields": {"_review_deadline": deadline}},
        {"$addFields": {"_review_unknown": {"$eq": ["$_review_deadline", None]}}},
        {"$sort": {"_review_unknown": 1, "_review_deadline": 1, "_id": 1}},
        {"$skip": (page - 1) * PAGE_SIZE}, {"$limit": PAGE_SIZE},
        {"$project": {"title": 1, "city": 1, "city_key": 1, "city_assignment": 1}},
    ]
    rows = []
    for demo in db.demonstrations.aggregate(pipeline, maxTimeMS=5000):
        value = city_review_deadline(demo, escalate_after_hours=hours)
        deadline_utc = value.replace(tzinfo=UTC) if value and value.tzinfo is None else value
        key = demo.get("city_key") or normalize_city_key(demo.get("city"))
        assignment = demo.get("city_assignment") or {}
        rows.append({
            "id": str(demo["_id"]), "title": demo.get("title") or "", "city": demo.get("city") or "",
            "deadline_iso": deadline_utc.isoformat() if deadline_utc else None,
            "deadline_label": deadline_utc.astimezone(ZoneInfo("Europe/Helsinki")).strftime("%d.%m.%Y %H.%M %Z") if deadline_utc else None,
            "remaining_minutes": max(0, ceil((deadline_utc - now).total_seconds() / 60)) if deadline_utc else None,
            "state": "escalated" if assignment.get("escalated") else (
                "unknown" if deadline_utc is None else "overdue" if deadline_utc <= now else "pending"
            ),
            "can_review": user.has_scoped_permission("ACCEPT_DEMO", scope_type="city", scope_key=key),
            "can_view": user.has_scoped_permission("VIEW_DEMO", scope_type="city", scope_key=key),
        })
    return {"rows": rows, "total": total, "page": page, "pages": pages,
            "first": (page - 1) * PAGE_SIZE + 1 if rows else 0,
            "last": (page - 1) * PAGE_SIZE + len(rows) if rows else 0}
