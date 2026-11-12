from mielenosoitukset_fi.utils.time_utils import utcnow
from datetime import datetime, date
import hmac
import secrets

from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, session, abort, current_app
from flask_login import login_required
from pymongo.errors import PyMongoError
from mielenosoitukset_fi.utils.flashing import flash_message

from mielenosoitukset_fi.utils.classes import RecurringDemonstration, Organizer
from mielenosoitukset_fi.utils.variables import CITY_LIST
from mielenosoitukset_fi.utils.wrappers import (
    permission_required, admin_required, global_permission_required,
    has_admin_access, has_global_permission,
)
from mielenosoitukset_fi.utils.campaign_publication import campaign_pages_public, PUBLICATION_ID

from mielenosoitukset_fi.utils.admin.demonstration import collect_tags
from .utils import mongo, _ADMIN_TEMPLATE_FOLDER

from mielenosoitukset_fi.utils.classes import RecurringDemonstration

admin_kampanja_bp = Blueprint(
    "admin_kampanja", __name__, url_prefix="/admin/kampanja"
)

from .utils import AdminActParser, log_admin_action_V2
from flask_login import current_user


@admin_kampanja_bp.before_request
def log_request_info():
    """Log request information before handling it."""
    if request.endpoint == "admin_kampanja.update_publication":
        return  # The action audit below deliberately excludes session/CSRF material.
    log_admin_action_V2(
        AdminActParser().log_request_info(request.__dict__, current_user)
    )

@admin_kampanja_bp.after_request
def private_admin_response(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@admin_kampanja_bp.route("/")
@login_required
@permission_required("KAMPANJA")
def index():
    # hae kaikki vapaaehtoiset listana
    volunteers = list(mongo.volunteers.find({}))
    volunteer_count = len(volunteers)

    can_publish = has_admin_access(current_user) and has_global_permission(current_user, "KAMPANJA")
    token = None
    if can_publish:
        token = session.setdefault("campaign_publication_csrf", secrets.token_urlsafe(32))

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}kampanja/list.html",
        volunteers=volunteers,
        volunteer_count=volunteer_count,
        pages_public=campaign_pages_public(),
        can_publish=can_publish,
        publication_csrf=token,
    )

@admin_kampanja_bp.route("/publication", methods=["POST"])
@login_required
@admin_required
@global_permission_required("KAMPANJA")
def update_publication():
    """Publish or withdraw pages without enabling fundraising payments."""
    expected = session.get("campaign_publication_csrf", "")
    supplied = request.form.get("csrf_token", "")
    if not expected or not supplied or not hmac.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8")):
        abort(400)
    action = request.form.get("publication")
    if action not in {"publish", "private"}:
        abort(400)
    published = action == "publish"
    try:
        mongo.campaign_settings.update_one(
            {"_id": PUBLICATION_ID},
            {"$set": {"published": published, "updated_at": utcnow(), "updated_by": str(current_user.id)}},
            upsert=True,
        )
    except PyMongoError:
        current_app.logger.exception("Could not save campaign publication state")
        flash_message("Tallennusta ei voitu varmistaa. Tarkista sivujen näkyvyys ja yritä tarvittaessa uudelleen.", "error")
        return redirect(url_for("admin_kampanja.index"), code=303)
    log_admin_action_V2({
        "action": "campaign_publication_changed", "published": published,
        "actor": str(current_user.id), "entity_type": "campaign_settings", "entity_id": PUBLICATION_ID,
    })
    flash_message(
        "Kampanja- ja keräyssivut on julkaistu kaikille." if published
        else "Kampanja- ja keräyssivut näkyvät vain kirjautuneille.",
        "success",
    )
    return redirect(url_for("admin_kampanja.index"), code=303)


from flask import jsonify

# --- Volunteers API ---

@admin_kampanja_bp.route("/api/volunteers/<vol_id>", methods=["PUT"])
@login_required
@admin_required
@permission_required("KAMPANJA")
def update_volunteer(vol_id):
    """Update volunteer details (edit modal)."""
    data = request.get_json() or {}
    update = {
        "name": data.get("name", "").strip(),
        "email": data.get("email", "").strip(),
        "phone": data.get("phone", "").strip(),
        "city": data.get("city", "").strip(),
        "notes": data.get("notes", "").strip(),
        "confirmed": bool(data.get("confirmed", False)),
        "updated_at": utcnow(),
    }

    mongo.volunteers.update_one({"_id": ObjectId(vol_id)}, {"$set": update})
    return jsonify({"status": "ok"})


@admin_kampanja_bp.route("/api/volunteers/<vol_id>", methods=["DELETE"])
@login_required
@admin_required
@permission_required("KAMPANJA")
def delete_volunteer(vol_id):
    """Delete volunteer."""
    mongo.volunteers.delete_one({"_id": ObjectId(vol_id)})
    return jsonify({"status": "ok"})


@admin_kampanja_bp.route("/api/volunteers/<vol_id>/confirm", methods=["POST"])
@login_required
@admin_required
def confirm_volunteer(vol_id):
    """Mark volunteer as confirmed."""
    mongo.volunteers.update_one(
        {"_id": ObjectId(vol_id)},
        {"$set": {"confirmed": True, "updated_at": utcnow()}}
    )
    return jsonify({"status": "ok"})


@admin_kampanja_bp.route("/api/volunteers/confirm_all", methods=["POST"])
@login_required
@admin_required
@permission_required("KAMPANJA")
def confirm_all_volunteers():
    """Confirm all volunteers that are still pending."""
    mongo.volunteers.update_many(
        {"confirmed": {"$ne": True}},
        {"$set": {"confirmed": True, "updated_at": utcnow()}}
    )
    return jsonify({"status": "ok"})


# --- Export routes (CSV/Excel) ---
# (optional if you want server-side instead of JS-only)

import io, csv
from flask import Response

@admin_kampanja_bp.route("/api/volunteers/export/csv")
@login_required
@admin_required
@permission_required("KAMPANJA")
def export_volunteers_csv():
    """Export all volunteers to CSV."""
    volunteers = list(mongo.volunteers.find({}))
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Name","Email","Phone","City","Notes","Confirmed"])
    for v in volunteers:
        cw.writerow([
            v.get("name",""),
            v.get("email",""),
            v.get("phone",""),
            v.get("city",""),
            v.get("notes",""),
            "Vahvistettu" if v.get("confirmed") else "Odottaa"
        ])
    output = si.getvalue().encode("utf-8")
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition":"attachment;filename=vapaaehtoiset.csv"})


