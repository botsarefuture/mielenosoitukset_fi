from bson.objectid import ObjectId
from flask import Blueprint, redirect, render_template, request, url_for, jsonify
from flask_login import current_user, login_required

from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from mielenosoitukset_fi.utils.variables import PERMISSIONS_GROUPS
from mielenosoitukset_fi.utils.validators import valid_email
from mielenosoitukset_fi.utils.database import stringify_object_ids
from mielenosoitukset_fi.utils.flashing import flash_message

from .utils import get_org_name, mongo, _ADMIN_TEMPLATE_FOLDER
from flask_babel import _


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
    search_query = request.args.get("search", "")
    users_cursor = mongo.users.find(
        {
            "$or": [
                {"username": {"$regex": search_query, "$options": "i"}},
                {"email": {"$regex": search_query, "$options": "i"}},
            ]
        }
        if search_query
        else {}
    )
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}user/list.html", users=users_cursor, search_query=search_query
    )


USER_ACCESS_LEVELS = {"global_admin": 3, "admin": 2, "user": 1}


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
        raise ValueError("Invalid user role")

    return USER_ACCESS_LEVELS[user1.role] > USER_ACCESS_LEVELS[user2.role]

@admin_user_bp.route("/edit_user/<user_id>", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def edit_user(user_id):
    """Edit a user's profile + global permissions."""
    user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        flash_message("Käyttäjää ei löytynyt.", "error")
        return redirect(url_for("admin_user.user_control"))

    user = User.from_db(user_doc)

    # ────────────────────────────── permission gate ─────────────────────────────
    if user != current_user and not compare_user_levels(current_user, user):
        flash_message("Et voi muokata käyttäjää, jolla on korkeampi käyttöoikeustaso kuin sinulla.", "error")
        return redirect(url_for("admin_user.user_control"))
    # ────────────────────────────────────────────────────────────────────────────

    if request.method == "POST":
        username  = request.form.get("username")
        email     = request.form.get("email")
        role      = request.form.get("role")
        confirmed = request.form.get("confirmed") == "on"

        # NEW  ➜  collect global perms from the template’s
        # <input name="permissions[global][]" ...>
        global_permissions = request.form.getlist("permissions[global][]")
        
        print(global_permissions)

        # ───── validation ─────
        if not username or not email:
            flash_message("Käyttäjänimi ja sähköposti ovat pakollisia.", "error")
            return redirect(url_for("admin_user.edit_user", user_id=user_id))

        if not valid_email(email):
            flash_message("Virheellinen sähköpostimuoto.", "error")
            return redirect(url_for("admin_user.edit_user", user_id=user_id))

        # role‑escalation / downgrade checks
        if current_user._id == user_id and role != current_user.role:
            flash_message("Et voi muuttaa omaa rooliasi.", "error")
            return redirect(url_for("admin_user.edit_user", user_id=user_id))

        if USER_ACCESS_LEVELS.get(role, 0) > USER_ACCESS_LEVELS.get(current_user.role, 0):
            flash_message("Et voi korottaa omaa tai toisen käyttäjän roolia korkeammalle kuin oma roolisi.", "error")
            return redirect(url_for("admin_user.edit_user", user_id=user_id))

        if user.role == "global_admin" and current_user._id == user_id and role != "global_admin":
            flash_message("Superkäyttäjät eivät voi alentaa itseään.", "error")
            return redirect(url_for("admin_user.edit_user", user_id=user_id))

        # ───── apply changes ─────
        mongo.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "username":          username,
                    "email":             email,
                    "role":              role,
                    "confirmed":         confirmed,
                    "global_permissions": global_permissions,   # ⭐ NEW ⭐
                }
            },
        )

        flash_message("Käyttäjä päivitetty onnistuneesti.", "approved")
        return redirect(url_for("admin_user.user_control"))

    # ───── GET: render form ─────
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}user/edit.html",
        user=user,
        PERMISSIONS_GROUPS=PERMISSIONS_GROUPS,
        global_permissions=user.global_permissions,
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
        return redirect(url_for("admin_user.user_control"))

    user = User.from_db(user)

    # Get form data
    print(request.form)
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
    return redirect(url_for("admin_user.user_control"))

import warnings


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
            else redirect(url_for("admin_user.user_control"))
        )

    # Fetch the user from the database
    user_data = mongo.users.find_one({"_id": ObjectId(user_id)})

    if not user_data:
        error_message = "Käyttäjää ei löydy."
        if json_mode:
            return jsonify({"status": "ERROR", "message": error_message})
        else:
            flash_message(error_message, "error")
            return redirect(url_for("admin_user.user_control"))

    # Check if the current user has the right to delete the target user
    target_user = User.from_db(user_data)
    if compare_user_levels(current_user, target_user) is False:
        error_message = "Et voi poistaa käyttäjää, jolla on korkeampi käyttöoikeustaso kuin sinulla."
        if json_mode:
            return jsonify({"status": "ERROR", "message": error_message})
        else:
            flash_message(error_message, "error")
            return redirect(url_for("admin_user.user_control"))

    # Perform deletion
    mongo.users.delete_one({"_id": ObjectId(user_id)})

    success_message = "Käyttäjä poistettu onnistuneesti."
    if json_mode:
        return jsonify({"status": "OK", "message": success_message})
    else:
        flash_message(success_message, "approved")
        return redirect(url_for("admin_user.user_control"))
