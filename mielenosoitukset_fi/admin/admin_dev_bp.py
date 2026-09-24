from bson.objectid import ObjectId
from flask import Blueprint, abort, jsonify, render_template, request, url_for
from flask_login import login_required, current_user
from flask_babel import _
from mielenosoitukset_fi.utils.time_utils import utcnow
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from config import Config

from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from .pagination import build_admin_pagination, parse_admin_pagination
from .utils import mongo, _ADMIN_TEMPLATE_FOLDER

admin_dev_bp = Blueprint("admin_dev", __name__, url_prefix="/admin/developer")


@admin_dev_bp.route("/requests", methods=["GET"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def list_requests():
    kind = (request.args.get("kind") or "access").strip().lower()
    if kind not in {"access", "scope"}:
        kind = "access"
    status = (request.args.get("status") or "").strip().lower()
    if status not in {"", "pending", "approved", "denied"}:
        status = ""
    page, per_page = parse_admin_pagination(request.args)

    collection = (
        mongo.api_token_requests
        if kind == "access"
        else mongo.developer_scope_requests
    )
    if status == "pending":
        query = {
            "$or": [
                {"status": "pending"},
                {"status": {"$exists": False}},
                {"status": None},
            ]
        }
    else:
        query = {"status": status} if status else {}
    filtered_count = collection.count_documents(query)
    total_count = collection.count_documents({})
    pagination = build_admin_pagination(
        "admin_dev.list_requests",
        total_count=filtered_count,
        page=page,
        per_page=per_page,
        query_args={"kind": kind, "status": status},
    )
    rows = list(
        collection.find(query)
        .sort([("requested_at", -1), ("_id", -1)])
        .skip(pagination["slice_start"])
        .limit(per_page)
    )

    user_ids = [row.get("user_id") for row in rows if row.get("user_id")]
    users = (
        {user["_id"]: user for user in mongo.users.find({"_id": {"$in": user_ids}})}
        if user_ids
        else {}
    )
    apps = {}
    if kind == "scope":
        app_ids = [row.get("app_id") for row in rows if row.get("app_id")]
        apps = (
            {app["_id"]: app for app in mongo.developer_apps.find({"_id": {"$in": app_ids}})}
            if app_ids
            else {}
        )

    for row in rows:
        row["_id"] = str(row["_id"])
        row["user"] = users.get(row.get("user_id"), {})
        row["user_id"] = str(row.get("user_id")) if row.get("user_id") else None
        if kind == "scope":
            row["app"] = apps.get(row.get("app_id"), {})
            row["app_id"] = str(row.get("app_id")) if row.get("app_id") else None
        if row.get("requested_at"):
            row["requested_at"] = row["requested_at"].isoformat()

    active_filters = []
    if status:
        status_labels = {
            "pending": _("Odottaa"),
            "approved": _("Hyväksytty"),
            "denied": _("Hylätty"),
        }
        active_filters.append(
            {
                "label": _("Tila"),
                "value": status_labels[status],
                "remove_url": url_for(
                    "admin_dev.list_requests",
                    kind=kind,
                    per_page=per_page,
                    page=1,
                ),
            }
        )

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}developer/requests.html",
        rows=rows,
        kind=kind,
        status=status,
        access_count=mongo.api_token_requests.count_documents({}),
        scope_count=mongo.developer_scope_requests.count_documents({}),
        total_count=total_count,
        filtered_count=filtered_count,
        filters_active=bool(active_filters),
        active_filters=active_filters,
        clear_filters_url=url_for(
            "admin_dev.list_requests", kind=kind, per_page=per_page
        ),
        **pagination,
    )


@admin_dev_bp.route("/user/<user_id>/apps", methods=["GET"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def user_apps(user_id):
    if not ObjectId.is_valid(user_id):
        abort(404)
    owner_id = ObjectId(user_id)
    page, per_page = parse_admin_pagination(request.args)
    total_count = mongo.developer_apps.count_documents({"owner_id": owner_id})
    pagination = build_admin_pagination(
        "admin_dev.user_apps",
        total_count=total_count,
        page=page,
        per_page=per_page,
        query_args={"user_id": user_id},
    )
    apps = list(
        mongo.developer_apps.find({"owner_id": owner_id})
        .sort([("created_at", -1), ("_id", -1)])
        .skip(pagination["slice_start"])
        .limit(per_page)
    )
    for app in apps:
        app["_id"] = str(app["_id"])
        app["owner_id"] = str(app.get("owner_id"))
        app["allowed_scopes"] = app.get("allowed_scopes", ["read"])
        if app.get("created_at"):
            app["created_at"] = app["created_at"].isoformat()
    user_doc = mongo.users.find_one({"_id": owner_id}) or {}
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}developer/user_apps.html",
        apps=apps,
        user=user_doc,
        total_count=total_count,
        **pagination,
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
        {"$set": {"status": status, "reviewed_at": utcnow(), "reviewed_by": current_user._id}},
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
        {"$set": {"status": "approved", "reviewed_at": utcnow(), "reviewed_by": current_user._id}},
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
        {"$set": {"status": "denied", "reviewed_at": utcnow(), "reviewed_by": current_user._id}},
    )
    return jsonify({"status": "success"})
