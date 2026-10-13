"""Case permissions inherit city scope only from the linked demonstration."""

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.cities import CITY_KEY_TO_NAME

CASE_PERMISSIONS = {"LIST_CASES", "VIEW_CASE", "EDIT_CASE", "DELETE_CASE"}


def global_case_permission(user, permission):
    """Distinguish global grants from navigation-level scoped permission."""
    return user.has_full_permissions() or permission in user.global_permissions


def case_scope_query(user, permission):
    """Return the permission scope, or None when no case capability is granted."""
    if global_case_permission(user, permission):
        return {}
    keys = user.scoped_city_keys_for(permission)
    if not keys:
        return None
    db = DatabaseManager.get_instance().get_db()
    demo_ids = list(db.demonstrations.distinct("_id", {"$or": [
        {"city_key": {"$in": keys}},
        {"city_key": {"$in": [None, ""]},
         "city": {"$in": [CITY_KEY_TO_NAME[key] for key in keys if key in CITY_KEY_TO_NAME]}},
    ]}))
    return {
        "demo_id": {"$in": demo_ids + [str(value) for value in demo_ids]},
        "type": {"$in": [
            "new_demo", "demo_error_report", "demo_cancellation_request",
            "demo_cancelled", "support_ticket",
        ]},
    }


def can_access_case(user, permission, case_id):
    """Apply the same scope to an individual record before any action."""
    query = case_scope_query(user, permission)
    if query is None:
        return False
    db = DatabaseManager.get_instance().get_db()
    return db.cases.find_one({"$and": [query, {"_id": case_id}]}, {"_id": 1}) is not None
