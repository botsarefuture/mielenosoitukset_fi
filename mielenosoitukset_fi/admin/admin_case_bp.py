import sys
from datetime import datetime
import logging
from bson.objectid import ObjectId
from flask import Blueprint, jsonify, redirect, render_template, request, url_for, abort, current_app
from flask_login import current_user, login_required
from flask_babel import _

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from mielenosoitukset_fi.utils.classes import Demonstration, Organizer
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj
from mielenosoitukset_fi.utils.admin.demonstration import collect_tags
from mielenosoitukset_fi.utils.database import DEMO_FILTER, stringify_object_ids
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.variables import CITY_LIST
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from .utils import mongo, log_admin_action_V2, AdminActParser, _ADMIN_TEMPLATE_FOLDER

from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.logger import logger

# --- init ---
SECRET_KEY = "your_secret_key"
GEOCODE_API_KEY = "66df12ce96495339674278ivnc82595"
serializer = URLSafeTimedSerializer(SECRET_KEY)
email_sender = EmailSender()

admin_case_bp = Blueprint("admin_case", __name__, url_prefix="/admin/case")

# --- logging every admin action ---
@admin_case_bp.before_request
def log_request_info():
    log_admin_action_V2(AdminActParser().log_request_info(request.__dict__, current_user))


from mielenosoitukset_fi.utils.classes import Case

@admin_case_bp.route("/")
@login_required
def cases():
    all_cases_docs = mongo.cases.find({})
    all_cases = []

    for doc in all_cases_docs:
        case = Case.from_dict(doc)

        # Attach demo object if it's a new_demo case
        if case.case_type == "new_demo" and case.demo_id:
            demo_doc = mongo.demonstrations.find_one({"_id": ObjectId(case.demo_id)})
            case.demo = demo_doc if demo_doc else None
        else:
            case.demo = None

        all_cases.append(case)

    return render_template(f"{_ADMIN_TEMPLATE_FOLDER}cases/all.html", all_cases=all_cases)

@admin_case_bp.route("/<case_id>/")
@login_required
def single_case(case_id):
    case = Case.get(case_id)
    if not case:
        abort(404)

    case_data = {}

    # Handle different case types
    if case.case_type == "new_demo" and case.demo_id:
        demo = mongo.demonstrations.find_one({"_id": ObjectId(case.demo_id)})
        submitter = mongo.submitters.find_one({"demonstration_id": ObjectId(case.demo_id)})
        case_data["demo"] = stringify_object_ids(demo) if demo else {}
        case_data["submitter"] = stringify_object_ids(submitter) if submitter else {}

    elif case.case_type == "demo_error_report" and case.demo_id:
        demo = mongo.demonstrations.find_one({"_id": ObjectId(case.demo_id)})
        case_data["demo"] = stringify_object_ids(demo) if demo else {}
        case_data["error_report"] = case.error_report

    elif case.case_type == "organization_edit_suggestion" and case.organization_id:
        org = mongo.organizations.find_one({"_id": ObjectId(case.organization_id)})
        case_data["organization"] = stringify_object_ids(org) if org else {}
        case_data["suggestion"] = case.suggestion

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}cases/case.html",
        case=case,
        case_data=case_data
    )


# --- Add internal note/action ---
@admin_case_bp.route("/<case_id>/add_action/", methods=["POST"])
@login_required
@admin_required
def add_action(case_id):
    case = Case.get(case_id)
    if not case:
        abort(404)

    action_type = request.form.get("action_type")
    reason = request.form.get("reason", "").strip()

    if not action_type or not reason:
        flash_message(_("Täytä kaikki kentät."), "warning")
        return redirect(url_for("admin_case.single_case", case_id=case_id))

    # Append action log to the case
    action_entry = {
        "user": current_user.username,
        "action_type": action_type,
        "reason": reason,
        "timestamp": datetime.utcnow()
    }

    mongo.cases.update_one(
        {"_id": ObjectId(case_id)},
        {"$push": {"action_logs": action_entry}}
    )

    log_admin_action_V2(f"{current_user.username} lisäsi toimenpiteen: {action_type} ({reason})", case_id)
    flash_message(_("Merkintä lisätty!"), "success")
    return redirect(url_for("admin_case.single_case", case_id=case_id))


from flask import jsonify, request, abort
from flask_login import login_required, current_user
from bson import ObjectId
from datetime import datetime

@admin_case_bp.route("/<case_id>/close/", methods=["POST"])
@login_required
@admin_required
def close_case(case_id):
    case = Case.get(case_id)
    if not case:
        return jsonify({"success": False, "error": "Tapausta ei löydy."}), 404

    reason = (request.json.get("reason") or "").strip()
    if case.meta.get("closed", False):
        return jsonify({"success": False, "error": "Tapaus on jo suljettu."}), 400
    if not reason:
        return jsonify({"success": False, "error": "Syytä ei annettu."}), 400

    case._add_history_entry({
        "timestamp": datetime.utcnow(),
        "action": "Tapaus suljettu",
        "user": current_user.username,
        "mech_action": "close_case",
        "metadata": {
            "reason": reason,
            "permitted_by": current_user.username
        },
        "meta_schema": {"reason": "string", "permitted_by": "string"}
    })

    mongo.cases.update_one(
        {"_id": ObjectId(case_id)},
        {"$set": {"meta.closed": True, "updated_at": datetime.utcnow()}}
    )

    flash_message(_("Tapaus suljettu."), "success")

    return jsonify({"success": True, "message": "Tapaus suljettu onnistuneesti."})


@admin_case_bp.route("/<case_id>/reopen/", methods=["POST"])
@login_required
@admin_required
def reopen_case(case_id):
    case = Case.get(case_id)
    if not case:
        return jsonify({"success": False, "error": "Tapausta ei löydy."}), 404

    reason = (request.json.get("reason") or "").strip()
    if not case.meta.get("closed", False):
        return jsonify({"success": False, "error": "Tapaus ei ole suljettu."}), 400
    if not reason:
        return jsonify({"success": False, "error": "Syytä ei annettu."}), 400

    case._add_history_entry({
        "timestamp": datetime.utcnow(),
        "action": "Tapaus avattu uudelleen",
        "user": current_user.username,
        "mech_action": "reopen_case",
        "metadata": {
            "reason": reason,
            "permitted_by": current_user.username
        },
        "meta_schema": {"reason": "string", "permitted_by": "string"}
    })

    mongo.cases.update_one(
        {"_id": ObjectId(case_id)},
        {"$set": {"meta.closed": False, "updated_at": datetime.utcnow()}}
    )

    flash_message(_("Tapaus avattu uudelleen."), "success")

    return jsonify({"success": True, "message": "Tapaus avattu uudelleen onnistuneesti."})



# --- Update demo info ---
@admin_case_bp.route("/<case_id>/update_demo/", methods=["POST"])
@login_required
@admin_required
def update_demo(case_id):
    case = Case.get(case_id)
    if not case or case.case_type != "new_demo" or not case.demo_id:
        abort(404)

    demo = mongo.demonstrations.find_one({"_id": ObjectId(case.demo_id)})
    if not demo:
        flash_message(_("Demoa ei löytynyt."), "danger")
        return redirect(url_for("admin_case.single_case", case_id=case_id))

    name = request.form.get("name", demo.get("name", ""))
    date = request.form.get("date", demo.get("date", ""))
    description = request.form.get("description", demo.get("description", ""))

    mongo.demonstrations.update_one(
        {"_id": ObjectId(case.demo_id)},
        {"$set": {"name": name, "date": date, "description": description}}
    )

    log_admin_action_V2(f"{current_user.username} päivitti demoa: {demo['_id']}", case_id)
    flash_message(_("Demo päivitetty!"), "success")
    return redirect(url_for("admin_case.single_case", case_id=case_id))


# --- Update organization suggestion ---
@admin_case_bp.route("/<case_id>/update_org_suggestion/", methods=["POST"])
@login_required
@admin_required
def update_org_suggestion(case_id):
    case = Case.get(case_id)
    if not case or case.case_type != "organization_edit_suggestion" or not case.organization_id:
        abort(404)

    suggestion = request.form.get("suggestion", "").strip()
    if not suggestion:
        flash_message(_("Täytä muutosluonnos."), "warning")
        return redirect(url_for("admin_case.single_case", case_id=case_id))

    mongo.cases.update_one(
        {"_id": ObjectId(case_id)},
        {"$set": {"suggestion": suggestion}}
    )

    log_admin_action_V2(f"{current_user.username} päivitti organisaation muutosluonnosta", case_id)
    flash_message(_("Muutosluonnos päivitetty!"), "success")
    return redirect(url_for("admin_case.single_case", case_id=case_id))


# --- Delete an action note ---
@admin_case_bp.route("/<case_id>/delete_action/<action_idx>/", methods=["POST"])
@login_required
@admin_required
def delete_action(case_id, action_idx):
    case = Case.get(case_id)
    if not case or not case.action_logs:
        abort(404)

    try:
        action_idx = int(action_idx)
        if 0 <= action_idx < len(case.action_logs):
            removed = case.action_logs[action_idx]
            mongo.cases.update_one(
                {"_id": ObjectId(case_id)},
                {"$pull": {"action_logs": removed}}
            )
            log_admin_action_V2(f"{current_user.username} poisti merkinnän: {removed}", case_id)
            flash_message(_("Merkintä poistettu."), "success")
    except (ValueError, IndexError):
        flash_message(_("Virheellinen indeksi."), "danger")

    return redirect(url_for("admin_case.single_case", case_id=case_id))


@admin_case_bp.route("/<case_id>/demo_action", methods=["POST"])
@login_required
@admin_required
def demo_action(case_id):
    from mielenosoitukset_fi.admin.admin_demo_bp import approve_demo, reject_demo
    
    case = Case.get(case_id)
    if not case or case.case_type != "new_demo" or not case.demo_id:
        abort(404)

    data = request.get_json()
    if not data or "action" not in data:
        return jsonify({"error": "Invalid request"}), 400

    demo = mongo.demonstrations.find_one({"_id": ObjectId(case.demo_id)})
    if not demo:
        return jsonify({"error": "Demo not found"}), 404

    action_type = ""
    action_reason = ""
    response_status = ""

    if data["action"] == "accept":
        approve_demo(demo_id=case.demo_id)
        
        action_type = "accept_demo"
        action_reason = "Mielenosoitus hyväksytty"
        response_status = "accepted"

    elif data["action"] == "reject":
        reason = data.get("reason", "").strip()
        if not reason:
            return jsonify({"error": "Rejection reason required"}), 400

        reject_demo(case.demo_id)
        
        action_type = "reject_demo"
        action_reason = f"Mielenosoitus hylätty: {reason}"
        response_status = "rejected"

    else:
        return jsonify({"error": "Unknown action"}), 400

    # Update case action logs
    action_entry = {
        "user": current_user.username,
        "action_type": action_type,
        "reason": action_reason,
        "timestamp": datetime.utcnow()
    }
    mongo.cases.update_one(
        {"_id": ObjectId(case_id)},
        {"$push": {"action_logs": action_entry}}
    )

    # Log for internal tracking
    #log_admin_action_V2(f"{current_user.username} suoritti '{action_type}' demolle {demo['_id']}: {action_reason}", case_id)

    

    flash_message(_(action_reason), "success")
    return jsonify({"success": True, "status": response_status})

@admin_case_bp.route("/<case_id>/demo_escalate", methods=["POST"])
@login_required
@admin_required
def demo_escalate(case_id):
    case = Case.get(case_id)
    if not case or case.case_type != "new_demo" or not case.demo_id:
        abort(404)

    demo = mongo.demonstrations.find_one({"_id": ObjectId(case.demo_id)})
    if not demo:
        return jsonify({"error": "Demo not found"}), 404

    # Reset demo status
    mongo.demonstrations.update_one(
        {"_id": ObjectId(case.demo_id)},
        {"$set": {"accepted": False, "rejected": False}}
    )

    # Set meta flag
    mongo.cases.update_one(
        {"_id": ObjectId(case_id)},
        {"$set": {"meta.superior_needed": True}}
    )

    # Log escalation
    action_entry = {
        "user": current_user.username,
        "action_type": "escalate_demo",
        "reason": "Demo status needs superior review",
        "timestamp": datetime.utcnow()
    }
    mongo.cases.update_one(
        {"_id": ObjectId(case_id)},
        {"$push": {"action_logs": action_entry}}
    )

    flash_message(_("Demo status reset – requires superior review."), "warning")
    return jsonify({"success": True})

@admin_case_bp.route("/<case_id>/deescalate", methods=["POST"])
@login_required
@admin_required
def deescalate_case(case_id):
    """De-escalate a case back to normal processing with proper action log."""

    case = mongo.cases.find_one({"_id": ObjectId(case_id)})
    if not case:
        return jsonify({"success": False, "error": "Case not found."}), 404

    try:
        timestamp = datetime.utcnow()

        # Update the case: remove superior_needed and append logs
        mongo.cases.update_one(
            {"_id": ObjectId(case_id)},
            {
                "$set": {"meta.superior_needed": False},
                "$push": {
                    "history": {
                        "timestamp": timestamp,
                        "action": "Eskalointi poistettu",
                        "user": current_user.username
                    },
                    "action_logs": {
                        "user": current_user.username,
                        "action_type": "deescalate",
                        "reason": "Case de-escalated by superior",
                        "timestamp": timestamp
                    }
                }
            }
        )

        #log_admin_action_V2(
        #    f"{current_user.username} de-escalated case {case_id}", case_id
        #)

        return jsonify({"success": True, "message": "Case de-escalated successfully."}), 200

    except Exception as e:
        logger.error(f"De-escalation failed for case {case_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error."}), 500
