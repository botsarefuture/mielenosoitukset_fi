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
from mielenosoitukset_fi.utils.demo_cancellation import cancel_demo

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
    """List all cases, newest first."""
    all_cases: list[Case] = []
    open_count = 0
    closed_count = 0
    escalated_count = 0
    auto_closed = 0

    def _auto_close(case_obj: Case):
        """Close cases that are clearly resolved (e.g., demo approved/rejected/cancelled)."""
        reason = None
        if case_obj.case_type == "new_demo" and case_obj.demo_id and case_obj.demo:
            demo_doc = case_obj.demo
            if demo_doc.get("accepted"):
                reason = "Demo hyväksytty"
            elif demo_doc.get("rejected"):
                reason = "Demo hylätty"
            elif demo_doc.get("cancelled"):
                reason = "Demo peruttu"
        if case_obj.case_type in {"demo_cancellation_request", "demo_cancelled"} and case_obj.demo:
            if case_obj.demo.get("cancelled"):
                reason = "Peruutus käsitelty"
        if reason:
            case_obj._add_history_entry(
                {
                    "timestamp": datetime.utcnow(),
                    "action": "Tapaus suljettu automaattisesti",
                    "user": getattr(current_user, "username", "system"),
                    "mech_action": "auto_close",
                    "metadata": {"reason": reason},
                    "meta_schema": {"reason": "string"},
                }
            )
            mongo.cases.update_one(
                {"_id": ObjectId(case_obj._id)},
                {
                    "$set": {
                        "meta.closed": True,
                        "meta.closed_reason": reason,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            return True
        return False

    for doc in mongo.cases.find({}, sort=[("created_at", -1)]):
        case = Case.from_dict(doc)

        # Attach related demo if this is a “new_demo” or cancellation case
        if case.case_type in {"new_demo", "demo_cancellation_request", "demo_cancelled"} and case.demo_id:
            demo_doc = mongo.demonstrations.find_one(
                {"_id": ObjectId(case.demo_id)},
                {"accepted": 1, "rejected": 1, "cancelled": 1, "title": 1, "date": 1, "city": 1}
            )
            case.demo = demo_doc or None
        else:
            case.demo = None

        if not (case.meta or {}).get("closed"):
            if _auto_close(case):
                case.meta = case.meta or {}
                case.meta["closed"] = True
                auto_closed += 1

        if (case.meta or {}).get("closed"):
            closed_count += 1
        else:
            open_count += 1
        if case.meta and case.meta.get("superior_needed"):
            escalated_count += 1

        all_cases.append(case)

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}cases/all.html",
        all_cases=all_cases,
        open_count=open_count,
        closed_count=closed_count,
        escalated_count=escalated_count,
        auto_closed=auto_closed,
    )

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
        suggestion = case.suggestion or {}
        organization = stringify_object_ids(org) if org else {}
        changes = []
        for key, new_val in suggestion.items():
            old_val = organization.get(key)
            if new_val != old_val:
                changes.append(
                    {
                        "field": key.replace("_", " ").capitalize(),
                        "old": old_val,
                        "new": new_val,
                    }
                )
        case_data["organization"] = organization
        case_data["suggestion"] = suggestion
        case_data["changes"] = changes

    elif case.case_type in {"demo_cancellation_request", "demo_cancelled"} and case.demo_id:
        demo = mongo.demonstrations.find_one({"_id": ObjectId(case.demo_id)})
        case_data["demo"] = stringify_object_ids(demo) if demo else {}
        case_data["cancellation"] = {
            "reason": (case.meta or {}).get("reason")
            or (demo or {}).get("cancellation_reason"),
            "requested_at": (demo or {}).get("cancellation_requested_at"),
            "requested_by": (demo or {}).get("cancellation_requested_by")
            or (case.meta or {}).get("requested_by"),
            "source": (demo or {}).get("cancellation_request_source")
            or (case.meta or {}).get("source"),
            "cancelled": bool((demo or {}).get("cancelled")),
            "cancelled_at": (demo or {}).get("cancelled_at"),
        }

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


@admin_case_bp.route("/<case_id>/approve_cancellation", methods=["POST"])
@login_required
@admin_required
def approve_cancellation(case_id):
    case = Case.get(case_id)
    if not case or case.case_type != "demo_cancellation_request" or not case.demo_id:
        abort(404)

    demo = mongo.demonstrations.find_one({"_id": ObjectId(case.demo_id)})
    if not demo:
        return jsonify({"success": False, "error": "Mielenosoitusta ei löydy."}), 404

    if demo.get("cancelled"):
        return jsonify({"success": True, "status": "already_cancelled"})

    payload = request.get_json(silent=True) or {}
    reason = (payload.get("reason") or demo.get("cancellation_reason") or case.meta.get("reason"))

    try:
        cancel_demo(
            demo,
            cancelled_by={
                "user": current_user.username,
                "source": "admin_case",
                "official_contact": True,
            },
            reason=reason,
            create_case=False,
        )
    except Exception:
        logger.exception("Failed to approve cancellation for case %s", case_id)
        return jsonify({"success": False, "error": "Peruutuksen hyväksyntä epäonnistui."}), 500

    timestamp = datetime.utcnow()
    mongo.cases.update_one(
        {"_id": case._id},
        {
            "$set": {
                "meta.closed": True,
                "meta.cancellation_status": "accepted",
                "meta.resolved_by": current_user.username,
                "updated_at": timestamp,
            },
            "$push": {
                "case_history": {
                    "timestamp": timestamp,
                    "action": "cancellation_accepted",
                    "mech_action": "approve_cancellation",
                    "user": current_user.username,
                    "metadata": {"reason": reason},
                },
                "action_logs": {
                    "user": current_user.username,
                    "action_type": "approve_cancellation",
                    "reason": reason or "Hyväksytty ilman erillistä perustetta",
                    "timestamp": timestamp,
                },
            },
        },
    )

    flash_message(_("Peruutus hyväksytty ja mielenosoitus merkitty perutuksi."), "success")
    return jsonify({"success": True, "status": "cancelled"})

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
