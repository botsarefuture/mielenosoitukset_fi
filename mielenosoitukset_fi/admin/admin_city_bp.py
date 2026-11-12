from bson import ObjectId
from flask import Blueprint, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from mielenosoitukset_fi.utils.cities import CITY_KEY_TO_NAME, normalize_city_key
from mielenosoitukset_fi.utils.city_assignment import ESCALATION_PERMISSION
from mielenosoitukset_fi.utils.city_settings import enabled_city_keys, upsert_city_setting
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.system_teams import active_account
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required

from .utils import _ADMIN_TEMPLATE_FOLDER, mongo


admin_city_bp = Blueprint("admin_city", __name__, url_prefix="/admin/cities")


def _demonstration_counts_by_city():
    counts = {}
    pipeline = [
        {
            "$group": {
                "_id": {
                    "city_key": "$city_key",
                    "city": "$city",
                },
                "count": {"$sum": 1},
            }
        }
    ]
    for group in mongo.demonstrations.aggregate(pipeline):
        identity = group.get("_id") or {}
        city_key = normalize_city_key(identity.get("city_key") or identity.get("city"))
        if city_key in CITY_KEY_TO_NAME:
            counts[city_key] = counts.get(city_key, 0) + group["count"]
    return counts


def _grant_counts_by_city():
    pipeline = [
        {
            "$match": {
                "scope_type": "city",
                "$or": [
                    {"revoked_at": {"$exists": False}},
                    {"revoked_at": None},
                ],
            }
        },
        {"$unwind": "$scope_keys"},
        {"$group": {"_id": "$scope_keys", "count": {"$sum": 1}}},
    ]
    counts = {}
    for group in mongo.admin_scope_grants.aggregate(pipeline):
        city_key = normalize_city_key(group.get("_id"))
        if city_key in CITY_KEY_TO_NAME:
            counts[city_key] = counts.get(city_key, 0) + group["count"]
    return counts

# The organisational target: at least two active city admins per city. It is a
# goal shown to administrators, never an enforced limit.
CITY_ADMIN_TARGET = 2
# Cities moderated by the national admin team rather than local city admins
# (Helsinki: very high volume and a fragmented local scene). They are never
# counted as needing admins. Keep in sync with nationallyManagedCities in
# go-api/city_admin_status.go.
NATIONALLY_MANAGED_CITIES = frozenset({"helsinki"})


def _active_admin_counts_by_city():
    """Count distinct users who can approve demonstrations in each city.

    Same rule as ``active_city_admins_for_city``: an unrevoked city grant that
    carries ``ACCEPT_DEMO``, held by an account that can act. View-only or
    case-only grants are not moderation coverage.
    """
    grants = list(mongo.admin_scope_grants.find(
        {"scope_type": "city", "permissions": ESCALATION_PERMISSION,
         "$or": [{"revoked_at": {"$exists": False}}, {"revoked_at": None}]},
        {"user_id": 1, "scope_keys": 1, "scope_key": 1},
    ))
    user_ids = {grant.get("user_id") for grant in grants if grant.get("user_id")}
    object_ids = [value for value in user_ids if not isinstance(value, str)]
    string_ids = [value for value in user_ids if isinstance(value, str)]
    lookup = [ObjectId(value) for value in string_ids if ObjectId.is_valid(value)] + object_ids
    active = {
        str(doc["_id"])
        for doc in mongo.users.find(
            {"_id": {"$in": lookup}},
            {"active": 1, "banned": 1, "confirmed": 1, "security_suspension": 1},
        )
        if active_account(doc)
    }
    admins = {}
    for grant in grants:
        user = str(grant.get("user_id"))
        if user not in active:
            continue
        # Grants may store a list or a single string, in either field.
        keys = grant.get("scope_keys") or []
        keys = [keys] if isinstance(keys, str) else list(keys)
        if grant.get("scope_key"):
            keys.append(grant["scope_key"])
        for raw in keys:
            city_key = normalize_city_key(raw)
            if city_key in CITY_KEY_TO_NAME:
                admins.setdefault(city_key, set()).add(user)
    return {city_key: len(users) for city_key, users in admins.items()}


def _coverage(city_key, admin_count):
    if city_key in NATIONALLY_MANAGED_CITIES:
        return "national"
    if admin_count <= 0:
        return "none"
    return "single" if admin_count < CITY_ADMIN_TARGET else "team"


@admin_city_bp.route("/", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("MANAGE_CITIES")
def city_control():
    if request.method == "POST":
        selected_keys = {
            normalize_city_key(city_key)
            for city_key in request.form.getlist("enabled_cities[]")
        }
        selected_keys = {city_key for city_key in selected_keys if city_key in CITY_KEY_TO_NAME}

        current_keys = enabled_city_keys(mongo)
        for city_key in sorted(current_keys | selected_keys):
            upsert_city_setting(
                mongo,
                city_key,
                city_key in selected_keys,
                actor_id=getattr(current_user, "_id", None),
            )

        flash_message(_("Kaupunkihallinta päivitetty."), "approved")
        return redirect(url_for("admin_city.city_control"))

    active_keys = enabled_city_keys(mongo)
    demo_counts = _demonstration_counts_by_city()
    grant_counts = _grant_counts_by_city()
    admin_counts = _active_admin_counts_by_city()
    city_rows = [
        {
            "key": city_key,
            "name": name,
            "enabled": city_key in active_keys,
            "demo_count": demo_counts.get(city_key, 0),
            "grant_count": grant_counts.get(city_key, 0),
            "admin_count": admin_counts.get(city_key, 0),
            "coverage": _coverage(city_key, admin_counts.get(city_key, 0)),
        }
        for city_key, name in sorted(CITY_KEY_TO_NAME.items(), key=lambda item: item[1])
    ]
    # Recruiting matters where the service is in use or has content.
    relevant = [row for row in city_rows if row["enabled"] or row["demo_count"]]
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}cities/index.html",
        city_rows=city_rows,
        active_count=sum(1 for row in city_rows if row["enabled"]),
        demo_count=sum(row["demo_count"] for row in city_rows),
        grant_count=sum(row["grant_count"] for row in city_rows),
        no_admin_count=sum(1 for row in relevant if row["coverage"] == "none"),
        single_admin_count=sum(1 for row in relevant if row["coverage"] == "single"),
        admin_target=CITY_ADMIN_TARGET,
    )
