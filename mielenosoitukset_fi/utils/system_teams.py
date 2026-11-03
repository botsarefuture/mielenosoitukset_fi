"""Server-owned team identity and live membership, independent of org roles."""
from bson import ObjectId
from flask import abort, current_app, has_app_context, has_request_context
from config import Config

BOARD_PERMISSIONS = frozenset({"MANAGE_CLEARANCE", "VIEW_CLEARANCE_AUDIT"})
SUPER_ROLES = frozenset({"global_admin", "god", "superuser"})


def olivia_user_id():
    value = current_app.config.get("OVERRIDE_OLIVIA_USER_ID") if has_app_context() else getattr(Config, "OVERRIDE_OLIVIA_USER_ID", None)
    return str(ObjectId(str(value))) if value and ObjectId.is_valid(str(value)) else None


def team_ids():
    result = {}
    for team, key in (("national", "NATIONAL_ADMIN_ORG_ID"), ("board", "BOARD_ORG_ID")):
        value = current_app.config.get(key) if has_app_context() else getattr(Config, key, None)
        if value:
            if not ObjectId.is_valid(str(value)):
                raise ValueError("Invalid system team configuration")
            result[team] = ObjectId(str(value))
    if len(set(result.values())) != len(result):
        raise ValueError("System teams must have distinct organizations")
    return result


def protected_organization(organization_id):
    return str(organization_id) in {str(value) for value in team_ids().values()}


def forbid_ordinary_team_write(organization_id):
    if protected_organization(organization_id):
        if has_request_context():
            abort(403, "Tämän organisaation jäsenyyttä hallitaan hallinnon hyväksyntöjen kautta.")
        raise PermissionError("Protected team requires governance approval")


def active_account(doc):
    return bool(doc and doc.get("active", True) is True and doc.get("banned", False) is False and doc.get("confirmed") is True)


def approved_members(db, team, *, include_inactive=False):
    organization = team_ids().get(team)
    if not organization or not db.organizations.find_one({"_id": organization}, {"_id": 1}):
        return []
    rows = list(db.memberships.find({"organization_id": {"$in": [organization, str(organization)]}, "governance_approved": True}))
    ids = {ObjectId(str(row["user_id"])) for row in rows if ObjectId.is_valid(str(row.get("user_id", "")))}
    if not ids:
        return []
    users = db.users.find({"_id": {"$in": list(ids)}}, {"username": 1, "email": 1, "active": 1, "banned": 1, "confirmed": 1})
    return sorted((doc for doc in users if include_inactive or active_account(doc)), key=lambda doc: str(doc["_id"]))


def board_ids(db):
    # Disabling a board member's login must not silently reduce the quorum.
    return {str(doc["_id"]) for doc in approved_members(db, "board", include_inactive=True)}


def clearance_approved(db, user_id):
    record = db.board_clearances.find_one({"user_id": str(user_id)}) or {}
    return clearance_record_approved(record)


def clearance_record_approved(record):
    emergency = ((record.get("team_requests") or {}).get("god_emergency") or {})
    if (record.get("approved") is True and emergency.get("approved") is True
            and emergency.get("method") == "usb_and_god"
            and emergency.get("id") == record.get("god_appointment_emergency_id")
            and emergency.get("candidate_id") == record.get("user_id")
            and ObjectId.is_valid(str(emergency.get("god_user_id", "")))
            and emergency.get("usb_key_id") and emergency.get("god_proof_id") and emergency.get("usb_proof")):
        # Durable evidence from the dedicated, signature-verified appointment
        # workflow. It is not a second fictitious board member or a generic
        # override of national-admin membership rules.
        return True
    approvals = record.get("approvals") or {}
    if not isinstance(approvals, dict):
        return False
    voters = set(approvals) - {str(record.get("user_id"))}
    return record.get("approved") is True and len(voters) >= 2


def user_team_access(db, user_id):
    ids = team_ids()
    if not ids:
        return frozenset()
    oid = ObjectId(str(user_id))
    rows = db.memberships.find({"user_id": {"$in": [oid, str(oid)]}, "organization_id": {"$in": [*ids.values(), *(str(value) for value in ids.values())]}, "governance_approved": True})
    access = set()
    for row in rows:
        team = next((key for key, value in ids.items() if str(value) == str(row.get("organization_id"))), None)
        if team and db.organizations.find_one({"_id": ids[team]}, {"_id": 1}):
            if team == "board" or row.get("grant_source") == "maintainer_bootstrap" or clearance_approved(db, oid):
                access.add(team)
    return frozenset(access)


def national_recipients(db):
    if "national" not in team_ids():
        # Compatibility until the approved team IDs are provisioned.
        return [{"email": "tuki@mielenosoitukset.fi"}]
    result, seen = [], set()
    for user in approved_members(db, "national"):
        if "national" not in user_team_access(db, user["_id"]):
            continue
        email = (user.get("email") or "").strip()
        if email and email.casefold() not in seen:
            result.append({"user_id": str(user["_id"]), "username": user.get("username"), "email": email})
            seen.add(email.casefold())
    if not result:
        raise RuntimeError("National administration team has no eligible recipients")
    return result
