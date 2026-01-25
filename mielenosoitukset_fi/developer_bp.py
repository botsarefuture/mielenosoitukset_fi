from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import secrets
from datetime import datetime

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.tokens import create_token
from mielenosoitukset_fi.utils.flashing import flash_message
from config import Config
import smtplib
from email.mime.text import MIMEText

mongo = DatabaseManager().get_instance().get_db()

developer_bp = Blueprint("developer", __name__, url_prefix="/developer")


def _require_dev_access():
    user = mongo.users.find_one({"_id": current_user._id}) or {}
    return bool(user.get("api_tokens_enabled", False))


def _email_admin(subject, body, to=None):
    to = to or ["tuki@mielenosoitukset.fi"]
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = Config.MAIL_DEFAULT_SENDER
        msg["To"] = ", ".join(to)
        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
            if Config.MAIL_USE_TLS:
                server.starttls()
            if Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.sendmail(Config.MAIL_DEFAULT_SENDER, to, msg.as_string())
    except Exception:
        current_app.logger.exception("Failed to send admin email")


@developer_bp.before_request
@login_required
def guard_dev_panel():
    allowed_endpoints = {"developer.dev_docs", "developer.request_access"}
    if request.endpoint in allowed_endpoints:
        return
    if not _require_dev_access():
        return render_template("developer/locked.html")


@developer_bp.route("/", methods=["GET"])
def dashboard():
    apps = list(mongo.developer_apps.find({"owner_id": current_user._id}))
    tokens = list(mongo.api_tokens.find({"user_id": current_user._id, "category": "user"}))
    for app in apps:
        app["_id"] = str(app["_id"])
    for t in tokens:
        t["_id"] = str(t["_id"])
        if t.get("expires_at"):
            t["expires_at"] = t["expires_at"].isoformat()
    return render_template("developer/dashboard.html", apps=apps, tokens=tokens)


@developer_bp.route("/apps", methods=["GET"])
def apps_home():
    apps = list(mongo.developer_apps.find({"owner_id": current_user._id}))
    for app in apps:
        app["_id"] = str(app["_id"])
    return render_template("developer/apps.html", apps=apps)


@developer_bp.route("/apps/<app_id>", methods=["GET"])
def app_detail(app_id):
    app = mongo.developer_apps.find_one({"_id": ObjectId(app_id), "owner_id": current_user._id})
    if not app:
        flash_message("Sovellusta ei löytynyt", "error")
        return redirect(url_for("developer.dashboard"))
    app["_id"] = str(app["_id"])
    app["owner_id"] = str(app.get("owner_id"))
    # Gather basic token metadata for this app
    tokens = list(mongo.api_tokens.find({"app_id": ObjectId(app_id)}))
    for t in tokens:
        t["_id"] = str(t["_id"])
        if t.get("expires_at"):
            t["expires_at"] = t["expires_at"].isoformat()
    # Placeholder rate-limit info
    rate_info = {
        "limit": "100/min",
        "remaining": "N/A",
        "reset": "N/A",
    }
    current_scopes = sorted(list(set(app.get("allowed_scopes", ["read"]))))
    return render_template("developer/app_detail.html", app=app, tokens=tokens, rate_info=rate_info, current_scopes=current_scopes)


@developer_bp.route("/apps/<app_id>/request_scopes", methods=["POST"])
def request_scopes(app_id):
    app = mongo.developer_apps.find_one({"_id": ObjectId(app_id), "owner_id": current_user._id})
    if not app:
        return jsonify({"status": "error", "message": "Sovellusta ei löytynyt"}), 404
    data = request.get_json(silent=True) or {}
    scopes = data.get("scopes") or []
    reason = (data.get("reason") or "").strip()
    if not scopes:
        return jsonify({"status": "error", "message": "Valitse vähintään yksi scope"}), 400
    if not reason:
        return jsonify({"status": "error", "message": "Perustelu vaaditaan"}), 400
    doc = {
        "app_id": app["_id"],
        "user_id": current_user._id,
        "scopes": scopes,
        "reason": reason,
        "status": "pending",
        "requested_at": datetime.utcnow(),
        "current_scopes": app.get("allowed_scopes", ["read"]),
    }
    mongo.developer_scope_requests.insert_one(doc)
    _email_admin(
        subject=f"Scope-pyyntö sovellukselle {app.get('name')}",
        body=f"Käyttäjä {current_user.username} pyytää scopet {', '.join(scopes)} sovellukselle {app.get('name')}.\nPerustelu: {reason}",
        to=["emilia@mielenosoitukset.fi"],
    )
    return jsonify({"status": "success", "message": "Pyyntö lähetetty. Ylläpitäjä käsittelee sen."})


@developer_bp.route("/docs", methods=["GET"])
def dev_docs():
    return redirect(url_for("api_docs"))


@developer_bp.route("/request_access", methods=["POST"])
def request_access():
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash_message("Perustelu vaaditaan.", "error")
        return redirect(url_for("developer.dashboard"))

    timestamp = datetime.utcnow().isoformat()
    mongo.users.update_one(
        {"_id": current_user._id},
        {"$set": {"api_token_request": timestamp, "api_token_request_reason": reason}},
    )
    mongo.api_token_requests.insert_one({
        "user_id": current_user._id,
        "username": current_user.username,
        "requested_at": timestamp,
        "status": "pending",
        "reason": reason,
    })
    _email_admin(
        "Kehittäjäpaneelin avauspyyntö",
        f"Käyttäjä {current_user.username} pyytää kehittäjäpaneelin/APIt käyttöön.\nPerustelu: {reason}\nAika: {timestamp}",
        to=["emilia@mielenosoitukset.fi"],
    )
    flash_message("Pyyntö lähetetty. Ylläpitäjä käsittelee sen.", "info")
    return redirect(url_for("developer.dashboard"))


def _gen_credentials():
    return secrets.token_urlsafe(12), secrets.token_urlsafe(24)


@developer_bp.route("/apps", methods=["POST"])
def create_app():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    if not name:
        return jsonify({"status": "error", "message": "Nimi vaaditaan"}), 400
    client_id, client_secret = _gen_credentials()
    owner_id = current_user._id
    doc = {
        "name": name,
        "description": description,
        "owner_id": owner_id,
        "client_id": client_id,
        "client_secret": client_secret,
        "created_at": datetime.utcnow(),
        "allowed_scopes": ["read"],
    }
    inserted = mongo.developer_apps.insert_one(doc)
    safe_doc = {
        "_id": str(inserted.inserted_id),
        "name": doc["name"],
        "description": doc["description"],
        "owner_id": str(owner_id),
        "client_id": client_id,
        "client_secret": client_secret,
        "created_at": doc["created_at"].isoformat(),
    }
    return jsonify({"status": "success", "app": safe_doc})


@developer_bp.route("/apps/<app_id>/token", methods=["POST"])
def create_app_token(app_id):
    app = mongo.developer_apps.find_one({"_id": ObjectId(app_id), "owner_id": current_user._id})
    if not app:
        return jsonify({"status": "error", "message": "Sovellusta ei löytynyt"}), 404

    data = request.get_json(silent=True) or {}
    token_type = data.get("type", "short")  # short (48h) or long (90d via exchange if desired)
    scopes = data.get("scopes", ["read"])

    allowed_scopes = app.get("allowed_scopes", ["read"])

    # enforce allowed scopes
    scopes = [s for s in scopes if s in allowed_scopes]
    if not scopes:
        return jsonify({"status": "error", "message": "Valitut scopet eivät ole sallittuja tälle sovellukselle."}), 403

    try:
        token, expires_at = create_token(
            user_id=current_user._id,
            token_type=token_type,
            scopes=scopes,
            category="app",
            app_id=app["_id"],
        )
        return jsonify({
            "status": "success",
            "token": token,
            "expires_at": expires_at.isoformat(),
            "scopes": scopes,
            "type": token_type,
            "app_id": str(app["_id"])
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@developer_bp.route("/apps/<app_id>/rotate", methods=["POST"])
def rotate_secret(app_id):
    app = mongo.developer_apps.find_one({"_id": ObjectId(app_id), "owner_id": current_user._id})
    if not app:
        return jsonify({"status": "error", "message": "Sovellusta ei löytynyt"}), 404
    cid, csecret = _gen_credentials()
    mongo.developer_apps.update_one(
        {"_id": app["_id"]},
        {"$set": {"client_id": cid, "client_secret": csecret, "rotated_at": datetime.utcnow()}}
    )
    return jsonify({"status": "success", "client_id": cid, "client_secret": csecret})
