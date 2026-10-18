"""Allowlisted user-management history; never snapshot credentials or sessions."""

from datetime import datetime, timezone
from copy import deepcopy

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from flask_babel import _, format_datetime, lazy_gettext as N_

from mielenosoitukset_fi.utils.cities import CITY_KEY_TO_NAME


FIELDS = {
    "username": N_("Käyttäjänimi"), "displayname": N_("Näyttönimi"),
    "email": N_("Sähköpostiosoite"), "role": N_("Rooli"),
    "confirmed": N_("Sähköpostiosoite on vahvistettu"), "active": N_("Aktiivinen"),
    "banned": N_("Estetty"), "global_permissions": N_("Globaalit oikeudet"),
    "forced_identity_change": N_("Pakota käyttäjänimen ja näyttönimen vaihto"),
    "forced_pwd_reset": N_("Salasanan vaihto vaaditaan"),
    "city_scope_keys": N_("Kaupungit"), "city_scope_permissions": N_("Kaupunkiadminin oikeudet"),
}
EVENTS = {
    "user_details_changed": N_("Käyttäjän tiedot päivitetty"),
    "user_account_status_changed": N_("Käyttötila muutettu"),
    "user_created": N_("Käyttäjä luotu"),
    "user_password_reset_required": N_("Salasanan vaihto vaaditaan"),
}

PENDING_HISTORY = "_admin_history_pending"
MAX_PENDING_HISTORY = 100


def history_event(user_id, before, after, actor, event="user_details_changed", *, always_record=False):
    """Build a credential-free event from this mutation's explicit states."""
    old, new = changed_states(before, after)
    if not new and not always_record:
        return None
    from .utils import capture_request_context, capture_process_context

    return {
        "_id": ObjectId(), "timestamp": datetime.now(timezone.utc),
        "event": event, "entity_type": "user", "entity_id": str(user_id),
        "related_id": str(user_id), "actor_id": str(actor["id"]),
        "actor": deepcopy(actor), "old_state": old, "new_state": new,
        "state_changed": bool(new),
        "request": capture_request_context(), "process": capture_process_context(),
    }


def commit_history_change(collection, document, updates, event, guard_fields):
    """Atomically store a state change and its bounded durable audit outbox.

    No replica-set transaction is required. An event is never inferred from a
    later document reload. Returning None means a stale or saturated write.
    """
    guard = [
        {key: {"$eq": document[key]}} if key in document else {key: {"$exists": False}}
        for key in guard_fields
    ]
    mutation = {"$set": updates}
    if event is not None:
        guard.append({f"{PENDING_HISTORY}.{MAX_PENDING_HISTORY - 1}": {"$exists": False}})
        mutation["$push"] = {PENDING_HISTORY: event}
    return collection.find_one_and_update(
        {"_id": document["_id"], "$and": guard}, mutation,
        return_document=ReturnDocument.AFTER,
    )


def flush_user_history(db, user_id):
    """Idempotently project pending events, retaining them on delivery failure.

    Authorized history reads and subsequent changes retry projection. Each
    source mutation already persisted its event in the same document write.
    """
    sources = (
        (db.users, {"_id": user_id}),
        (db.admin_scope_grants, {"user_id": {"$in": [user_id, str(user_id)]}}),
    )
    for collection, query in sources:
        for document in collection.find({**query, f"{PENDING_HISTORY}.0": {"$exists": True}}).limit(MAX_PENDING_HISTORY):
            for event in document.get(PENDING_HISTORY, [])[:MAX_PENDING_HISTORY]:
                try:
                    db.admin_logs.update_one({"_id": event["_id"]}, {"$setOnInsert": event}, upsert=True)
                    db.super_audit_logs.update_one({"_id": event["_id"]}, {"$setOnInsert": {
                        "event": f"admin:{event['event']}", "payload": event,
                        "timestamp": event["timestamp"], "actor": event["actor"],
                        "request": event.get("request"), "process": event.get("process"),
                        "entity": {"type": "user", "id": event["entity_id"]},
                        "tags": ["admin", "audit"],
                    }}, upsert=True)
                    collection.update_one({"_id": document["_id"]}, {
                        "$pull": {PENDING_HISTORY: {"_id": event["_id"]}},
                    })
                except PyMongoError:
                    # Delivery is best-effort, durability is not: retry the
                    # original event (same id, actor, states and timestamp).
                    return False
    return True


def user_snapshot(document, grant):
    """Normalize only editable, non-secret fields for meaningful comparisons."""
    result = {key: document.get(key, "") for key in ("username", "displayname", "email", "role")}
    for key in ("confirmed", "active", "banned", "forced_identity_change", "forced_pwd_reset"):
        result[key] = bool(document.get(key, key == "active"))
    result["global_permissions"] = sorted(set(document.get("global_permissions") or []))
    result["city_scope_keys"] = sorted(set(grant.get("scope_keys") or []))
    result["city_scope_permissions"] = sorted(set(grant.get("permissions") or []))
    return result


def changed_states(before, after):
    keys = [key for key in FIELDS if before.get(key) != after.get(key)]
    return ({key: before.get(key) for key in keys}, {key: after.get(key) for key in keys})


def history_query(user_id):
    return {"entity_type": "user", "entity_id": str(user_id), "event": {"$in": list(EVENTS)}}


def _display_value(field, value):
    if value is None or value == "" or value == []:
        return "—"
    if isinstance(value, bool):
        return _("Kyllä") if value else _("Ei")
    if isinstance(value, list):
        return ", ".join(CITY_KEY_TO_NAME.get(item, item) if field == "city_scope_keys" else item
                         for item in value if isinstance(item, str)) or "—"
    return str(value) if isinstance(value, (str, int)) else "—"


def present_history(entry):
    """Do not send raw audit/request payloads to the template, even for legacy logs."""
    before = entry.get("old_state") or {}
    after = entry.get("new_state") or {}
    changes = [
        {"label": str(label), "before": _display_value(key, before.get(key)),
         "after": _display_value(key, after.get(key))}
        for key, label in FIELDS.items()
        if (key in before or key in after) and before.get(key) != after.get(key)
    ]
    timestamp = entry.get("timestamp")
    if isinstance(timestamp, datetime):
        timestamp = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp
    else:
        timestamp = None
    actor = entry.get("actor") or {}
    return {
        "title": str(EVENTS[entry["event"]]), "changes": changes,
        "unchanged": entry.get("state_changed") is False,
        "actor": actor.get("username") or entry.get("actor_id") or _("Tuntematon tekijä"),
        "timestamp": timestamp.isoformat() if timestamp else "",
        "timestamp_display": format_datetime(timestamp, rebase=False) + " UTC" if timestamp else _("Aika ei saatavilla"),
    }
