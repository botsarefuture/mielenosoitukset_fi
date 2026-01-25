from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from config import Config

from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from .utils import mongo, _ADMIN_TEMPLATE_FOLDER

admin_dev_bp = Blueprint("admin_dev", __name__, url_prefix="/admin/developer")


@admin_dev_bp.route("/requests", methods=["GET"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def list_requests():
    # Scope requests
    scope_reqs = list(mongo.developer_scope_requests.find().sort("requested_at", -1))
    app_ids = [r.get("app_id") for r in scope_reqs if r.get("app_id")]
    user_ids = [r.get("user_id") for r in scope_reqs if r.get("user_id")]
    apps = {a["_id"]: a for a in mongo.developer_apps.find({"_id": {"$in": app_ids}})} if app_ids else {}
    users = {u["_id"]: u for u in mongo.users.find({"_id": {"$in": user_ids}})} if user_ids else {}
    for r in scope_reqs:
        r["_id"] = str(r["_id"])
        r["app"] = apps.get(r.get("app_id"), {})
        r["user"] = users.get(r.get("user_id"), {})
        r["app_id"] = str(r.get("app_id")) if r.get("app_id") else None
        r["user_id"] = str(r.get("user_id")) if r.get("user_id") else None
        if r.get("requested_at"):
            r["requested_at"] = r["requested_at"].isoformat()

    # Developer access requests (API token unlock)
    dev_reqs = list(mongo.api_token_requests.find().sort("requested_at", -1))
    user_ids_dev = [r.get("user_id") for r in dev_reqs if r.get("user_id")]
    users_dev = {u["_id"]: u for u in mongo.users.find({"_id": {"$in": user_ids_dev}})} if user_ids_dev else {}
    for r in dev_reqs:
        r["_id"] = str(r["_id"])
        r["user"] = users_dev.get(r.get("user_id"), {})
        r["user_id"] = str(r.get("user_id")) if r.get("user_id") else None
        if r.get("requested_at"):
            r["requested_at"] = r["requested_at"]

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}developer/requests.html",
        scope_reqs=scope_reqs,
        dev_reqs=dev_reqs,
    )


@admin_dev_bp.route("/user/<user_id>/apps", methods=["GET"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def user_apps(user_id):
    apps = list(mongo.developer_apps.find({"owner_id": ObjectId(user_id)}))
    for app in apps:
        app["_id"] = str(app["_id"])
        app["owner_id"] = str(app.get("owner_id"))
        app["allowed_scopes"] = app.get("allowed_scopes", ["read"])
        if app.get("created_at"):
            app["created_at"] = app["created_at"].isoformat()
    user_doc = mongo.users.find_one({"_id": ObjectId(user_id)}) or {}
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}developer/user_apps.html",
        apps=apps,
        user=user_doc,
    )


def _update_app_scopes(app_id, scopes):
    if not scopes:
        return
    mongo.developer_apps.update_one(
        {"_id": app_id},
        {"$addToSet": {"allowed_scopes": {"$each": scopes}}},
    )


def _set_request_status(req_id, status):
    mongo.developer_scope_requests.update_one(
        {"_id": req_id},
        {"$set": {"status": status, "reviewed_at": datetime.utcnow(), "reviewed_by": current_user._id}},
    )


def _set_user_api_tokens(user_id, enabled: bool):
    update = {"$set": {"api_tokens_enabled": bool(enabled)}}
    if enabled:
        update["$unset"] = {"api_token_request": ""}
    else:
        update["$set"]["api_token_request"] = None
    mongo.users.update_one({"_id": user_id}, update)


@admin_dev_bp.route("/requests/<req_id>/approve", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def approve_request(req_id):
    req = mongo.developer_scope_requests.find_one({"_id": ObjectId(req_id)})
    if not req:
        return jsonify({"status": "error", "message": "Request not found"}), 404
    app_id = req.get("app_id")
    scopes = req.get("scopes", [])
    if app_id:
        _update_app_scopes(app_id, scopes)
    _set_request_status(req["_id"], "approved")
    return jsonify({"status": "success"})


@admin_dev_bp.route("/requests/<req_id>/deny", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def deny_request(req_id):
    req = mongo.developer_scope_requests.find_one({"_id": ObjectId(req_id)})
    if not req:
        return jsonify({"status": "error", "message": "Request not found"}), 404
    _set_request_status(req["_id"], "denied")
    return jsonify({"status": "success"})


@admin_dev_bp.route("/access/<req_id>/approve", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def approve_access(req_id):
    req_obj = mongo.api_token_requests.find_one({"_id": ObjectId(req_id)})
    if not req_obj:
        return jsonify({"status": "error", "message": "Request not found"}), 404
    user_id = req_obj.get("user_id")
    if user_id:
        _set_user_api_tokens(user_id, True)
        user_doc = mongo.users.find_one({"_id": user_id})
        if user_doc and user_doc.get("email"):
            try:
                msg = MIMEText("API-avainten käyttöoikeus on hyväksytty. Voit nyt käyttää kehittäjäpaneelia.", "plain", "utf-8")
                msg["Subject"] = "API-avaimet hyväksytty"
                msg["From"] = Config.MAIL_DEFAULT_SENDER
                msg["To"] = user_doc["email"]
                with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
                    if Config.MAIL_USE_TLS:
                        server.starttls()
                    if Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
                        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                    server.sendmail(Config.MAIL_DEFAULT_SENDER, [user_doc["email"]], msg.as_string())
            except Exception:
                pass
    mongo.api_token_requests.update_one(
        {"_id": req_obj["_id"]},
        {"$set": {"status": "approved", "reviewed_at": datetime.utcnow(), "reviewed_by": current_user._id}},
    )
    return jsonify({"status": "success"})


@admin_dev_bp.route("/access/<req_id>/deny", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def deny_access(req_id):
    req_obj = mongo.api_token_requests.find_one({"_id": ObjectId(req_id)})
    if not req_obj:
        return jsonify({"status": "error", "message": "Request not found"}), 404
    user_id = req_obj.get("user_id")
    if user_id:
        mongo.users.update_one({"_id": user_id}, {"$unset": {"api_token_request": ""}, "$set": {"api_tokens_enabled": False}})
    mongo.api_token_requests.update_one(
        {"_id": req_obj["_id"]},
        {"$set": {"status": "denied", "reviewed_at": datetime.utcnow(), "reviewed_by": current_user._id}},
    )
    return jsonify({"status": "success"})
