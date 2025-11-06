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


# 🩶 main route: view a single support case
@admin_case_bp.route("/<case_id>/")
@login_required
def single_case(case_id):
    """Display a specific case (demo error, org edit suggestion, new demo, etc)."""
    case_doc = None
    case_type = "new_demo"
    case_data = {}

    try:
        
        # try to fetch from DB if exists
        case_doc = mongo.cases.find_one_or_404({"_id": ObjectId(case_id)})
        if case_doc:
            case_type = case_doc.get("type", "new_demo")

            if case_type == "new_demo":
                demo_id = case_doc.get("demo_id")
                demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
                submitter = mongo.submitters.find_one({"demonstration_id": ObjectId(demo_id)})
                if demo:
                    case_data["demo"] = stringify_object_ids(demo)
                if submitter:
                    case_data["submitter"] = stringify_object_ids(submitter)

            elif case_type == "demo_error_report":
                # example: fetch reported demo + error fields
                demo_id = case_doc.get("demo_id")
                demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
                case_data["demo"] = stringify_object_ids(demo) if demo else {}
                case_data["error_report"] = case_doc.get("error_report", {})

            elif case_type == "organization_edit_suggestion":
                org_id = case_doc.get("organization_id")
                org = mongo.organizations.find_one({"_id": ObjectId(org_id)})
                suggestion = case_doc.get("suggestion", {})
                case_data["organization"] = stringify_object_ids(org) if org else {}
                case_data["suggestion"] = suggestion

        else:
            abort(404)

    except Exception as e:
        abort(404)
        
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}cases/case.html",
        case_id=case_id,
        case_type=case_type,
        case_data=case_data,
    )

