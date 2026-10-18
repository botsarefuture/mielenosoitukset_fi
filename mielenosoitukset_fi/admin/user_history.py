"""Allowlisted user-management history; never snapshot credentials or sessions."""

from datetime import datetime, timezone

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
