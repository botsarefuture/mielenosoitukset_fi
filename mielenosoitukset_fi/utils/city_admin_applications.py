"""City admin applications stored by the Go API (docs/city-admin-applications.md).

Go accepts and stores the application in ``city_admin_applications``. This
module turns each stored application into a ``city_admin_application`` case,
tells the national team through the site inbox, and records review decisions.
Granting the role itself stays in the accounts dashboard, so approving an
application never changes permissions on its own.
"""
from bson import ObjectId

from mielenosoitukset_fi.utils.classes import Case
from mielenosoitukset_fi.utils.cities import CITY_KEY_TO_NAME
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.system_teams import national_recipients
from mielenosoitukset_fi.utils.time_utils import utcnow

CASE_TYPE = "city_admin_application"
STATUSES = ("received", "in_review", "approved", "declined", "withdrawn")
DECISION_STATUSES = ("in_review", "approved", "declined")
STATUS_LABELS = {
    "received": "Vastaanotettu",
    "in_review": "Käsittelyssä",
    "approved": "Hyväksytty",
    "declined": "Hylätty",
    "withdrawn": "Peruttu",
}
EXPERIENCE_LABELS = {"none": "Ei kokemusta", "some": "Jonkin verran", "lot": "Paljon"}


def city_names(keys):
    return [CITY_KEY_TO_NAME.get(key, key) for key in keys or []]


def _notify_national_team(db, application, case_id):
    """Idempotent inbox notices; a stable ID never re-marks a read notice unread."""
    try:
        recipients = national_recipients(db)
    except RuntimeError:
        logger.warning("No national team recipients for city admin application %s", application["_id"])
        return
    payload = {"case_id": case_id, "cities": city_names(application.get("city_keys"))}
    for recipient in recipients:
        user_id = recipient.get("user_id")
        if not user_id:
            continue
        db.notifications.update_one(
            {"_id": f"city-admin-application:{application['_id']}:{user_id}"},
            {"$setOnInsert": {
                "user_id": ObjectId(user_id), "type": "city_admin_application",
                "payload": payload, "link": f"/admin/case/{case_id}/",
                "created_at": utcnow(), "read": False,
            }},
            upsert=True,
        )


def deliver_pending(db, limit=50):
    """Create the review case for stored applications. Safe to rerun after a crash."""
    delivered = 0
    for application in db.city_admin_applications.find({"case_pending": True}).limit(limit):
        case_id = application["_id"]
        if not db.cases.find_one({"_id": case_id}, {"_id": 1}):
            user = db.users.find_one({"_id": application.get("user_id")}, {"username": 1, "displayname": 1}) or {}
            case = Case(
                case_type=CASE_TYPE,
                submitter_id=application.get("user_id"),
                # The username identifies the account; the email stays on the
                # user record and the application text stays on the application.
                submitter={"submitter_name": user.get("displayname") or user.get("username") or ""},
                meta={"application_id": application["_id"], "city_keys": application.get("city_keys") or [],
                      "urgency": "normal"},
                _id=case_id,
            )
            db.cases.update_one({"_id": case_id}, {"$setOnInsert": case.to_dict()}, upsert=True)
        _notify_national_team(db, application, case_id)
        db.city_admin_applications.update_one(
            {"_id": application["_id"]},
            {"$set": {"case_pending": False, "case_id": case_id, "updated_at": utcnow()}},
        )
        delivered += 1
    return delivered


def set_status(db, application_id, status, actor):
    """Record a review decision on the application and its case history."""
    if status not in DECISION_STATUSES:
        raise ValueError("unknown status")
    now = utcnow()
    result = db.city_admin_applications.update_one(
        {"_id": application_id, "status": {"$nin": ["withdrawn"]}},
        {"$set": {"status": status, "updated_at": now, "decided_by": actor if status != "in_review" else None}},
    )
    if not result.matched_count:
        return False
    update = {"$push": {"case_history": {
        "timestamp": now, "action": f"Hakemuksen tila: {STATUS_LABELS[status]}", "user": actor,
        "mech_action": "application_status", "metadata": {"status": status},
        "meta_schema": {"status": "string"},
    }}, "$set": {"updated_at": now}}
    if status in ("approved", "declined"):
        update["$set"].update({"meta.closed": True, "meta.closed_reason": STATUS_LABELS[status], "meta.closed_at": now})
    db.cases.update_one({"_id": application_id}, update)
    return True
