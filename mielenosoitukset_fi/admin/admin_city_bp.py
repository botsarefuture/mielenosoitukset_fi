from flask import Blueprint, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from mielenosoitukset_fi.utils.cities import CITY_KEY_TO_NAME, normalize_city_key
from mielenosoitukset_fi.utils.city_settings import enabled_city_keys, upsert_city_setting
from mielenosoitukset_fi.utils.flashing import flash_message
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
    city_rows = [
        {
            "key": city_key,
            "name": name,
            "enabled": city_key in active_keys,
            "demo_count": demo_counts.get(city_key, 0),
            "grant_count": grant_counts.get(city_key, 0),
        }
        for city_key, name in sorted(CITY_KEY_TO_NAME.items(), key=lambda item: item[1])
    ]
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}cities/index.html",
        city_rows=city_rows,
        active_count=sum(1 for row in city_rows if row["enabled"]),
        demo_count=sum(row["demo_count"] for row in city_rows),
        grant_count=sum(row["grant_count"] for row in city_rows),
    )
