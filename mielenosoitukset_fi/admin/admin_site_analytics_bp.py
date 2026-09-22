"""Admin dashboard for the built-in first-party site analytics.

Reads only pre-aggregated counters (see ``utils/site_analytics.py``) and
renders the site-wide overview plus per-demonstration analytics pages. All
routes are restricted to the existing ``VIEW_ANALYTICS`` permission.
"""

from datetime import timedelta

from bson.objectid import ObjectId
from flask import Blueprint, abort, render_template, request
from flask_babel import _
from flask_login import login_required

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.site_analytics import (
    DEVICE_LABELS,
    LANGUAGE_LABELS,
    REFERRER_LABELS,
    get_breakdown,
    get_demonstration_analytics,
    get_demonstration_identifiers,
    get_overview,
    get_top_pages,
    get_traffic_series,
)
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from mielenosoitukset_fi.admin.utils import _ADMIN_TEMPLATE_FOLDER, log_admin_action_V2

admin_site_analytics_bp = Blueprint(
    "admin_site_analytics",
    __name__,
    url_prefix="/admin/analytics",
)

_VALID_RANGES = {"7", "14", "30", "90"}


def _parse_range():
    """Read the ?range=days query parameter (default 30 days)."""
    raw = str(request.args.get("range", "30"))
    if raw not in _VALID_RANGES:
        return 30
    return int(raw)


def _parse_days(requested):
    return max(1, min(int(requested or 30), 365))


def _demo_title(page_type, resource_id):
    """Resolve a demonstration id/slug to its title for top-page listings."""
    if page_type != "demonstration" or not resource_id:
        return None
    identifiers = list(get_demonstration_identifiers(resource_id))
    object_id_candidates = [value for value in identifiers if ObjectId.is_valid(value)]
    query = {"$or": [{"slug": {"$in": identifiers}}]}
    if object_id_candidates:
        from bson import ObjectId as _ObjectId

        query["$or"].append({"_id": {"$in": [_ObjectId(v) for v in object_id_candidates]}})
    doc = (
        DatabaseManager().get_instance().get_db().demonstrations.find_one(
            query, {"title": 1}
        )
    )
    return doc.get("title") if doc else None


def _org_title(page_type, resource_id):
    if page_type != "organization" or not resource_id:
        return None
    if not ObjectId.is_valid(str(resource_id)):
        return None
    doc = (
        DatabaseManager().get_instance().get_db().organizations.find_one(
            {"_id": ObjectId(str(resource_id))}, {"name": 1}
        )
    )
    return doc.get("name") if doc else None


def _resolve_titles(rows):
    """Attach friendly titles to demonstration/organization top-page rows."""
    for row in rows:
        page_type = row.get("page_type")
        resource_id = row.get("resource_id")
        if page_type == "demonstration":
            row["title"] = _demo_title(page_type, resource_id) or row["title"]
        elif page_type == "organization":
            row["title"] = _org_title(page_type, resource_id) or row["title"]
    return rows


def _page_views_endpoint(page_type, resource_id):
    """Public URL for a top-page row, when it can be built safely."""
    from flask import url_for

    if not resource_id:
        return None
    try:
        if page_type == "demonstration":
            return url_for("demonstration_detail", demo_id=resource_id)
        if page_type == "organization":
            return url_for("org", org_id=resource_id)
    except Exception:
        return None
    return None


@admin_site_analytics_bp.route("/")
@login_required
@admin_required
@permission_required("VIEW_ANALYTICS")
def site_overview():
    """Site-wide analytics dashboard built from aggregate counters."""
    days = _parse_range()
    try:
        overview = get_overview(days=days)
        series = get_traffic_series(days=days)
        top_pages = _resolve_titles(
            get_top_pages(days=days, limit=10, title_resolver=lambda t, r: None)
        )
        top_demos = _resolve_titles(
            get_top_pages(page_type="demonstration", days=days, limit=10, title_resolver=lambda t, r: None)
        )
        languages = get_breakdown("language", days=days)
        devices = get_breakdown("device", days=days)
        referrers = get_breakdown("referrer", days=days)
    except Exception:
        logger.exception("Failed to build site analytics overview")
        abort(503)

    rows = [
        {**row, "url": _page_views_endpoint(row["page_type"], row["resource_id"])}
        for row in top_pages
    ]
    demo_rows = [
        {**row, "url": _page_views_endpoint("demonstration", row["resource_id"])}
        for row in top_demos
    ]

    log_admin_action_V2(
        "VIEW_SITE_ANALYTICS",
        None,
    )

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}site_analytics.html",
        range_days=days,
        overview=overview,
        series=series,
        top_pages=rows,
        top_demos=demo_rows,
        languages=languages,
        devices=devices,
        referrers=referrers,
        language_labels=LANGUAGE_LABELS,
        device_labels=DEVICE_LABELS,
        referrer_labels=REFERRER_LABELS,
    )


@admin_site_analytics_bp.route("/demonstration/<demo_id>")
@login_required
@admin_required
@permission_required("VIEW_ANALYTICS", _type="DEMONSTRATION")
def site_demo_analytics(demo_id):
    """Analytics for a single demonstration (built-in counters)."""
    days = _parse_range()
    mongo = DatabaseManager().get_instance().get_db()
    identifiers = get_demonstration_identifiers(demo_id)
    demo_doc = None
    for value in identifiers:
        if ObjectId.is_valid(value):
            demo_doc = mongo.demonstrations.find_one({"_id": ObjectId(value)})
            if demo_doc:
                break
    if not demo_doc:
        abort(404)

    from mielenosoitukset_fi.utils.classes import Demonstration

    try:
        data = get_demonstration_analytics(demo_id, days=days)
    except Exception:
        logger.exception("Failed to build demonstration analytics for %s", demo_id)
        abort(503)

    demo = Demonstration.from_dict(demo_doc)
    log_admin_action_V2(
        "VIEW_DEMO_SITE_ANALYTICS",
        str(demo_doc["_id"]),
    )

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}site_demo_analytics.html",
        range_days=days,
        demo=demo,
        demo_id=str(demo_doc["_id"]),
        data=data,
        language_labels=LANGUAGE_LABELS,
        device_labels=DEVICE_LABELS,
        referrer_labels=REFERRER_LABELS,
    )
