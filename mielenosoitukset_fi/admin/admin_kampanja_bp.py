from datetime import datetime, date

from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
from mielenosoitukset_fi.utils.flashing import flash_message

from mielenosoitukset_fi.utils.classes import RecurringDemonstration, Organizer
from mielenosoitukset_fi.utils.variables import CITY_LIST
from mielenosoitukset_fi.utils.wrappers import permission_required, admin_required

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
    log_admin_action_V2(
        AdminActParser().log_request_info(request.__dict__, current_user)
    )

@admin_kampanja_bp.route("/")
@login_required
def index():
    # hae kaikki vapaaehtoiset listana
    volunteers = list(mongo.volunteers.find({}))
    volunteer_count = len(volunteers)

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}kampanja/list.html",
        volunteers=volunteers,
        volunteer_count=volunteer_count
    )

from flask import jsonify

# --- Volunteers API ---

@admin_kampanja_bp.route("/api/volunteers/<vol_id>", methods=["PUT"])
@login_required
@admin_required
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
        "updated_at": datetime.utcnow(),
    }

    mongo.volunteers.update_one({"_id": ObjectId(vol_id)}, {"$set": update})
    return jsonify({"status": "ok"})


@admin_kampanja_bp.route("/api/volunteers/<vol_id>", methods=["DELETE"])
@login_required
@admin_required
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
        {"$set": {"confirmed": True, "updated_at": datetime.utcnow()}}
    )
    return jsonify({"status": "ok"})


@admin_kampanja_bp.route("/api/volunteers/confirm_all", methods=["POST"])
@login_required
@admin_required
def confirm_all_volunteers():
    """Confirm all volunteers that are still pending."""
    mongo.volunteers.update_many(
        {"confirmed": {"$ne": True}},
        {"$set": {"confirmed": True, "updated_at": datetime.utcnow()}}
    )
    return jsonify({"status": "ok"})


# --- Export routes (CSV/Excel) ---
# (optional if you want server-side instead of JS-only)

import io, csv
from flask import Response

@admin_kampanja_bp.route("/api/volunteers/export/csv")
@login_required
@admin_required
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


