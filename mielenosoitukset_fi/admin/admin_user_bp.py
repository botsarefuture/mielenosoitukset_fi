from bson.objectid import ObjectId
from flask import Blueprint, redirect, render_template, request, session, url_for, jsonify
from flask_login import current_user, login_required
import math
import re

from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from mielenosoitukset_fi.utils.variables import CITY_LIST, PERMISSIONS_GROUPS
from mielenosoitukset_fi.utils.cities import CITY_KEY_TO_NAME, CITY_NAME_TO_KEY, normalize_city_key
from mielenosoitukset_fi.utils.validators import valid_email
from mielenosoitukset_fi.utils.database import stringify_object_ids
from mielenosoitukset_fi.utils.flashing import flash_message

from .utils import get_org_name, mongo, _ADMIN_TEMPLATE_FOLDER
from flask_babel import _
from mielenosoitukset_fi.utils.time_utils import utcnow
from datetime import datetime


email_sender = EmailSender()
admin_user_bp = Blueprint("admin_user", __name__, url_prefix="/admin/user")

from .utils import AdminActParser, log_admin_action_V2
from flask_login import current_user


@admin_user_bp.before_request
def log_request_info():
    """Log request information before handling it."""
    log_admin_action_V2(
        AdminActParser().log_request_info(request.__dict__, current_user)
    )


# User control panel with pagination
@admin_user_bp.route("/")
@login_required
@admin_required
@permission_required("LIST_USERS")
def user_control():
    """Render the user control panel with a list of users."""
    search_query = (request.args.get("search", "") or "").strip()
    page = max(request.args.get("page", default=1, type=int) or 1, 1)
    per_page = request.args.get("per_page", default=20, type=int) or 20
    per_page = min(max(per_page, 1), 100)
    pending_token_requests = mongo.api_token_requests.count_documents({"status": "pending"})
    search_filter = {}
    if search_query:
        escaped_query = re.escape(search_query)
        search_filter = {
            "$or": [
                {"username": {"$regex": escaped_query, "$options": "i"}},
                {"email": {"$regex": escaped_query, "$options": "i"}},
                {"displayname": {"$regex": escaped_query, "$options": "i"}},
            ]
        }

    total_users = mongo.users.count_documents(search_filter)
    total_pages = max(math.ceil(total_users / per_page), 1)
    page = min(page, total_pages)
    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < total_pages else None
    users_cursor = (
        mongo.users.find(search_filter)
        .sort("username", 1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}user/list.html",
        users=list(users_cursor),
        search_query=search_query,
        current_page=page,
        per_page=per_page,
        total_pages=total_pages,
        prev_page=prev_page,
        next_page=next_page,
        pending_token_requests=pending_token_requests,
        total_users=total_users,
    )


USER_ACCESS_LEVELS = {"god": 4, "global_admin": 3, "admin": 2, "user": 1}

CITY_ADMIN_PERMISSIONS = [
    "LIST_DEMOS",
    "VIEW_DEMO",
    "EDIT_DEMO",
    "ACCEPT_DEMO",
    "CREATE_DEMO",
    "GENERATE_EDIT_LINK",
]


def _can_manage_scope_grants(actor) -> bool:
    return bool(getattr(actor, "global_admin", False)) or getattr(actor, "role", None) in {
        "global_admin",
        "god",
    }


def _city_scope_grant_for_user(user_id: ObjectId) -> dict:
    grant = mongo.admin_scope_grants.find_one(
        {
            "user_id": {"$in": [user_id, str(user_id)]},
            "scope_type": "city",
            "$or": [{"revoked_at": {"$exists": False}}, {"revoked_at": None}],
        }
    )
    if not grant:
        return {"scope_keys": [], "permissions": []}

    scope_keys = grant.get("scope_keys")
    if scope_keys is None and grant.get("scope_key"):
        scope_keys = [grant.get("scope_key")]
    grant["scope_keys"] = [normalize_city_key(key) for key in scope_keys or [] if normalize_city_key(key)]
    grant["permissions"] = [
        permission for permission in grant.get("permissions", []) if permission in CITY_ADMIN_PERMISSIONS
    ]
    return grant


def _sync_city_scope_grant(user_id: ObjectId, city_keys: list[str], permissions: list[str]) -> None:
    city_keys = sorted({normalize_city_key(key) for key in city_keys if normalize_city_key(key) in CITY_KEY_TO_NAME})
    permissions = sorted({permission for permission in permissions if permission in CITY_ADMIN_PERMISSIONS})

    query = {
        "user_id": {"$in": [user_id, str(user_id)]},
        "scope_type": "city",
        "$or": [{"revoked_at": {"$exists": False}}, {"revoked_at": None}],
    }

    if not city_keys or not permissions:
        mongo.admin_scope_grants.update_many(
            query,
            {"$set": {"revoked_at": utcnow(), "revoked_by": str(current_user._id)}},
        )
        return

    existing = mongo.admin_scope_grants.find_one(query)
    payload = {
        "user_id": user_id,
        "scope_type": "city",
        "scope_keys": city_keys,
        "role": "city_reviewer",
        "permissions": permissions,
        "updated_at": utcnow(),
        "updated_by": str(current_user._id),
        "revoked_at": None,
    }
    if existing:
        mongo.admin_scope_grants.update_one({"_id": existing["_id"]}, {"$set": payload})
    else:
        payload["created_at"] = utcnow()
        payload["granted_by"] = str(current_user._id)
        mongo.admin_scope_grants.insert_one(payload)


def compare_user_levels(user1, user2):  # Check if the user1 is higher than user2
    """Compare the access levels of two users.

    Parameters
    ----------
    user1 :
        An object representing the first user, which must have a 'role' attribute.
    user2 :
        raises ValueError: If either user1 or user2 has an invalid role not present in USER_ACCESS_LEVELS.

    Returns
    -------


    """
    if user1.role not in USER_ACCESS_LEVELS or user2.role not in USER_ACCESS_LEVELS:
        if user2.role not in USER_ACCESS_LEVELS:
            user2.role = "user"
        else:
            raise ValueError("Invalid user role")
    
    if user1._id == ObjectId("66c25768dad432ad39ce38d5"):
        return True

    if user1.role == user2.role and not user1._id == ObjectId("66c25768dad432ad39ce38d5"): # HARD CODED EXCEPTION FOR EMILIA
        return False

    return USER_ACCESS_LEVELS[user1.role] > USER_ACCESS_LEVELS[user2.role]

def safe_redirect(target):
    """Redirect safely with redi_count check to prevent loops."""
    session["redi_count"] = session.get("redi_count", 0) + 1
    session.modified = True
    if session["redi_count"] > 2:
        session["redi_count"] = 0
        flash_message("Liian monta uudelleenohjausta, palaa käyttäjälistaukseen.", "error")
        return redirect(url_for("admin_user.user_control"))
    return redirect(target)


@admin_user_bp.route("/edit_user/<user_id>", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def edit_user(user_id):
    """Edit a user's profile + global permissions."""
    user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        flash_message("Käyttäjää ei löytynyt.", "error")
        return safe_redirect(request.referrer or url_for("admin_user.user_control"))

    user = User.from_db(user_doc)

    # ─── permission gate ───────────────────────────────────────────────────────
    if user != current_user and not compare_user_levels(current_user, user):
        flash_message("Et voi muokata käyttäjää, jolla on korkeampi käyttöoikeustaso kuin sinulla.", "error")
        return safe_redirect(request.referrer or url_for("admin_user.user_control"))
    # ───────────────────────────────────────────────────────────────────────────

    if request.method == "POST":
        # 1️⃣ Nykytila
        current = {
            "username":           user.username,
            "email":              user.email,
            "role":               user.role,
            "confirmed":          bool(user.confirmed),
            "global_permissions": list(user.global_permissions or []),
        }

        # 2️⃣ Lomakkeelta saapuvat arvot
        incoming = {
            "username":  request.form.get("username", "").strip(),
            "email":     request.form.get("email", "").strip(),
            "role":      request.form.get("role") or user.role,
            "confirmed": request.form.get("confirmed") == "on",
            "global_permissions": request.form.getlist("permissions[global][]")
                                   or current["global_permissions"],
        }

        # ─── validoinnit ────────────────────────────────────────────────────────
        if not incoming["username"] or not incoming["email"]:
            flash_message("Käyttäjänimi ja sähköposti ovat pakollisia.", "error")
            return safe_redirect(url_for("admin_user.edit_user", user_id=user_id))

        if not valid_email(incoming["email"]):
            flash_message("Virheellinen sähköpostimuoto.", "error")
            return safe_redirect(url_for("admin_user.edit_user", user_id=user_id))

        # estä oman roolin muutos
        if current_user._id == user._id and incoming["role"] != current_user.role:
            flash_message("Et voi muuttaa omaa rooliasi.", "error")
            return safe_redirect(url_for("admin_user.edit_user", user_id=user_id))

        # estä ylennys yli oman tason
        if USER_ACCESS_LEVELS.get(incoming["role"], 0) > USER_ACCESS_LEVELS.get(current_user.role, 0):
            flash_message("Et voi korottaa omaa tai toisen käyttäjän roolia korkeammalle kuin oma roolisi.", "error")
            return safe_redirect(url_for("admin_user.edit_user", user_id=user_id))

        # estä super-käyttäjän itse-alennus
        if (user.role == "global_admin" and current_user._id == user._id
                and incoming["role"] != "global_admin"):
            flash_message("Superkäyttäjät eivät voi alentaa itseään.", "error")
            return safe_redirect(url_for("admin_user.edit_user", user_id=user_id))

        # 3️⃣ Muutosdiff
        changes = {k: v for k, v in incoming.items() if v != current[k]}

        # 4️⃣ Päivitä vain jos on muutoksia
        if changes:
            mongo.users.update_one({"_id": ObjectId(user_id)}, {"$set": changes})
            flash_message("Käyttäjä päivitetty onnistuneesti.", "approved")
        else:
            flash_message("Mitään ei muutettu.", "info")

        if _can_manage_scope_grants(current_user):
            city_scope_keys = request.form.getlist("admin_scope_cities[]")
            city_scope_permissions = request.form.getlist("admin_scope_permissions[city][]")
            _sync_city_scope_grant(user._id, city_scope_keys, city_scope_permissions)

        return safe_redirect(request.referrer or url_for("admin_user.user_control"))

    # ─── GET → lomake ──────────────────────────────────────────────────────────
    city_scope_grant = _city_scope_grant_for_user(user._id)
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}user/edit.html",
        user=user,
        PERMISSIONS_GROUPS=PERMISSIONS_GROUPS,
        global_permissions=user.global_permissions,
        can_manage_scope_grants=_can_manage_scope_grants(current_user),
        city_list=CITY_LIST,
        city_name_to_key=CITY_NAME_TO_KEY,
        city_scope_grant=city_scope_grant,
        city_admin_permissions=CITY_ADMIN_PERMISSIONS,
    )




class UserOrg:
    """ """

    def __init__(self, org_id, user, role, permissions):
        self.org_id = org_id
        self.user = user
        self.role = role
        self.permissions = permissions  # Validate permissions

    def __str__(self):
        return f"UserOrg({self.org_id}, {self.user}, {self.role}, {self.permissions})"

    def to_dict(self):
        """ """
        return {
            "org_id": ObjectId(self.org_id),
            "role": (
                self.role if self.role in ["global_admin", "admin", "user"] else "user"
            ),
            "permissions": self.permissions,
        }

    @staticmethod
    def from_dict(data):
        """

        Parameters
        ----------
        data :


        Returns
        -------


        """
        return UserOrg(
            data.get("org_id"),
            data.get("user"),
            data.get("role"),
            data.get("permissions"),
        )


@admin_user_bp.route("/save_user/<user_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def save_user(user_id):
    """Save updated user details, permissions, and send email notification."""

    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash_message("Käyttäjää ei löydy.", "error")
        return redirect(request.referrer or url_for("admin_user.user_control"))

    user = User.from_db(user)

    # Get form data
    username = request.form.get("username")
    email = request.form.get("email")
    role = request.form.get("role")
    confirmed = request.form.get("confirmed") == "on"
    global_permissions = request.form.getlist("permissions[global][]")  # ← 🔥 this line

    # Prevent role escalation
    if current_user._id == user_id and role != current_user.role:
        flash_message("Et voi muuttaa omaa rooliasi.", "error")
        return redirect(url_for("admin_user.edit_user", user_id=user_id))

    # Prevent global admins from lowering their role
    if (
        user.role == "global_admin"
        and current_user._id == user_id
        and role != "global_admin"
    ):
        flash_message("Et voi alentaa omaa rooliasi globaalina ylläpitäjänä.", "error")
        return redirect(url_for("admin_user.edit_user", user_id=user_id))

    # Validate required fields
    if not username or not email:
        flash_message("Käyttäjänimi ja sähköposti ovat pakollisia.", "error")
        return redirect(url_for("admin_user.edit_user", user_id=user_id))

    if not valid_email(email):
        flash_message("Virheellinen sähköpostimuoto.", "error")
        return redirect(url_for("admin_user.edit_user", user_id=user_id))

    
    # Assign values
    user.username = username
    user.email = email
    user.role = role
    user.confirmed = confirmed
    user.global_permissions = global_permissions  # ← 🔥 this line


    user.save()

    if _can_manage_scope_grants(current_user):
        city_scope_keys = request.form.getlist("admin_scope_cities[]")
        city_scope_permissions = request.form.getlist("admin_scope_permissions[city][]")
        _sync_city_scope_grant(user._id, city_scope_keys, city_scope_permissions)

    # Build email summary
    permission_summary_html = "<p>Sinulla on seuraavat oikeudet:</p>"

    for perms in user.global_permissions:

        for group_name, group_perms in PERMISSIONS_GROUPS.items():
            permission_summary_html += f"<h4>{group_name}</h4><ul>"
            for perm in group_perms:
                if perm["name"] in perms:
                    permission_summary_html += f"<li><strong>{perm['name']}:</strong> {perm['description']}</li>"
            permission_summary_html += "</ul>"
        permission_summary_html += "</ul>"

    # Send email notification
    email_sender.queue_email(
        template_name="user_update_notification.html",
        subject="Tilisi tiedot on päivitetty",
        recipients=[email],
        context={
            "user_name": user.displayname or user.username,
            "role": role,
            "action": "päivitetty",
            "updated_email": email,
            "permissions_summary": permission_summary_html,
            "login_link": url_for("users.auth.login", _external=True),
            "support_contact": "tuki@mielenosoitukset.fi",
        },
    )

    flash_message("Käyttäjä päivitetty onnistuneesti.", "approved")
    return redirect(request.referrer or url_for("admin_user.user_control"))

import warnings




@admin_user_bp.route("/api/check_clearance/<user_id>")
def check_clearance(user_id):
    """
    Temporary endpoint to check if the board has approved the user for global_admin role.
    Currently always returns False.
    """
    return jsonify({
        "has_clearance": False
    })


def is_valid_email(email):
    """Deprecated: This function is deprecated and will be removed in future versions.
    Please use `valid_email` from `utils.py` instead.

    Usage:
        from mielenosoitukset_fi.utils import valid_email
        is_valid = valid_email(email)

    Utility function to validate email format.

    Parameters
    ----------
    email :


    Returns
    -------


    """
    warnings.warn(
        "is_valid_email is deprecated; use valid_email from ../utils.py instead.",
        DeprecationWarning,
    )

    return "@" in email and "." in email.split("@")[-1]


# Delete user
@admin_user_bp.route("/delete_user", methods=["POST"])
@login_required
@admin_required
@permission_required("DELETE_USER")
def delete_user():
    """Delete a user from the system.

    Returns
    -------
    response : flask.Response
        A JSON response or a redirect to the user control panel.
    """
    json_mode = request.headers.get("Content-Type") == "application/json"

    # Extract user_id from either form data or JSON body
    user_id = request.form.get("user_id") or (
        request.json.get("user_id") if json_mode else None
    )

    if not user_id:
        error_message = "Käyttäjän tunniste puuttuu."
        return (
            jsonify({"status": "ERROR", "message": error_message})
            if json_mode
            else redirect(request.referrer or url_for("admin_user.user_control"))
        )

    # Fetch the user from the database
    user_data = mongo.users.find_one({"_id": ObjectId(user_id)})

    if not user_data:
        error_message = "Käyttäjää ei löydy."
        if json_mode:
            return jsonify({"status": "ERROR", "message": error_message})
        else:
            flash_message(error_message, "error")
            return redirect(request.referrer or url_for("admin_user.user_control"))

    # Check if the current user has the right to delete the target user
    target_user = User.from_db(user_data)
    if compare_user_levels(current_user, target_user) is False:
        error_message = "Et voi poistaa käyttäjää, jolla on korkeampi käyttöoikeustaso kuin sinulla."
        if json_mode:
            return jsonify({"status": "ERROR", "message": error_message})
        else:
            flash_message(error_message, "error")
            return redirect(request.referrer or url_for("admin_user.user_control"))

    # Perform deletion
    mongo.users.delete_one({"_id": ObjectId(user_id)})

    success_message = "Käyttäjä poistettu onnistuneesti."
    if json_mode:
        return jsonify({"status": "OK", "message": success_message})
    else:
        flash_message(success_message, "approved")
        return redirect(request.referrer or url_for("admin_user.user_control"))

import random
import string
from werkzeug.security import generate_password_hash

@admin_user_bp.route("/create_user", methods=["POST"])
@login_required
@admin_required
@permission_required("CREATE_USER")
def create_user():
    """
    Create a new user with access credentials and send them an email notification.

    Expects form or JSON data:
        - email (required)
        - username (optional; defaults to email prefix)
        - displayname (optional; defaults to username)
        - role (optional; defaults to "user")

    Returns
    -------
    flask.Response
        JSON response with status or redirect with flash messages if failure.
    """
    data = request.get_json() if request.is_json else request.form

    email = data.get("email")
    username = data.get("username") or email.split("@")[0]
    displayname = data.get("displayname") or username
    role = data.get("role") or "user"

    # Basic validation
    if not email:
        flash_message("Sähköposti on pakollinen.", "error")
        return redirect(request.referrer or url_for("admin_user.user_control"))
    if not valid_email(email):
        flash_message("Virheellinen sähköpostimuoto.", "error")
        return redirect(request.referrer or url_for("admin_user.user_control"))
    if role not in ["user", "admin", "global_admin"]:
        flash_message("Rooli ei ole kelvollinen.", "error")
        return redirect(request.referrer or url_for("admin_user.user_control"))

    # Check if email already exists
    if mongo.users.find_one({"email": email}):
        flash_message("Käyttäjä tällä sähköpostilla on jo olemassa.", "error")
        return redirect(request.referrer or url_for("admin_user.user_control"))

    # Generate a random password
    raw_password = "".join(random.choices(string.ascii_letters + string.digits, k=12))
    password_hash = generate_password_hash(raw_password)

    # Create user document
    user_doc = {
        "email": email,
        "username": username,
        "displayname": displayname,
        "role": role,
        "confirmed": True,
        "password_hash": password_hash,
        "global_permissions": [],
    }
    
    result = mongo.users.insert_one(user_doc)
    if not result.inserted_id:
        flash_message("Käyttäjän luominen epäonnistui.", "error")
        return redirect(request.referrer or url_for("admin_user.user_control"))
    
    inserted_user = mongo.users.find_one({"_id": result.inserted_id})
    user = User.from_db(inserted_user)

    user.forced_pwd_reset = True # We want to force password reset on first login
    user.save()

    # Send credentials via email
    email_sender.queue_email(
        template_name="new_user_credentials.html",
        subject="Tilisi on luotu",
        recipients=[email],
        context={
            "user_name": displayname,
            "username": username,
            "email": email,
            "role": role,
            "password": raw_password,
            "login_link": url_for("users.auth.login", _external=True),
            "support_contact": "tuki@mielenosoitukset.fi",
        },
        extra_headers={"reply-to": "tuki@mielenosoitukset.fi"}
    )

    flash_message(f"Käyttäjä {displayname} luotu ja tunnukset lähetetty sähköpostiin.", "approved")
    return redirect(request.referrer or url_for("admin_user.user_control"))

@admin_user_bp.route("/api/force_password_change/", methods=["POST"])
@login_required
@admin_required
@permission_required("FORCE_PASSWORD_CHANGE")
def api_force_password_change():
    """
    API endpoint to force a password change for a user.

    Expects JSON data:
        - user_id (required)

    Returns
    -------
    flask.Response
        JSON response indicating success or failure.
    """
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"status": "ERROR", "message": "Käyttäjä ID puuttuu."}), 400

    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"status": "ERROR", "message": "Käyttäjää ei löytynyt."}), 404

    user_ = User.from_db(user)
    
    user_.forced_pwd_reset = True
    user_.save()
    
    return jsonify({"status": "OK", "message": "Salasanan vaihto pakotettu onnistuneesti."})


def _serialize_login_log(doc):
    ts = doc.get("timestamp")
    return {
        "id": str(doc.get("_id")),
        "timestamp": ts.isoformat() if ts else None,
        "timestamp_display": ts.strftime("%d.%m.%Y %H:%M") if ts else None,
        "ip": doc.get("ip"),
        "success": bool(doc.get("success")),
        "reason": doc.get("reason"),
        "user_agent": doc.get("user_agent"),
    }


@admin_user_bp.route("/api/login_history/<user_id>")
@login_required
@admin_required
@permission_required("VIEW_USER")
def api_user_login_history(user_id):
    """Return login attempts for the requested user (admin use only)."""
    try:
        object_id = ObjectId(user_id)
    except Exception:
        return jsonify({"status": "ERROR", "message": "Virheellinen käyttäjän tunniste."}), 400

    user_doc = mongo.users.find_one({"_id": object_id})
    if not user_doc:
        return jsonify({"status": "ERROR", "message": "Käyttäjää ei löytynyt."}), 404

    raw_limit = request.args.get("limit", 25)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = 25
    limit = max(1, min(limit, 200))

    query = {
        "$or": [
            {"user_id": object_id},
            {"user_id": None, "username": user_doc.get("username")},
        ]
    }
    cursor = (
        mongo.login_logs.find(query)
        .sort("timestamp", -1)
        .limit(limit)
    )
    logs = [_serialize_login_log(doc) for doc in cursor]
    return jsonify(
        {
            "status": "OK",
            "user": {
                "id": str(user_doc.get("_id")),
                "username": user_doc.get("username"),
                "displayname": user_doc.get("displayname"),
                "email": user_doc.get("email"),
            },
            "logins": logs,
            "limit": limit,
        }
    )
