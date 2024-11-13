from bson.objectid import ObjectId
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from auth.models import User
from emailer.EmailSender import EmailSender
from wrappers import admin_required, permission_required
from utils.variables import PERMISSIONS_GROUPS
from utils.validators import valid_email
from utils.database import stringify_object_ids
from utils.flashing import flash_message

from .utils import get_org_name, mongo
from flask_babel import _


email_sender = EmailSender()
admin_user_bp = Blueprint("admin_user", __name__, url_prefix="/admin/user")


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
        "admin/user/list.html", users=users_cursor, search_query=search_query
    )


@admin_user_bp.route("/edit_user/<user_id>", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def edit_user(user_id):
    """Edit user details.

    Changelog:
    ----------

    v2.4.0:
    - Modified to use valid_email instead of depraced is_valid_email
    """
    user = User.from_db(mongo.users.find_one({"_id": ObjectId(user_id)}))
    organizations = stringify_object_ids(list(mongo.organizations.find()))

    if user is None:
        flash_message("Käyttäjää ei löytynyt.", "error")
        return redirect(url_for("admin_user.user_control"))

    # Check if the current user is trying to edit a higher-level user
    if user.role == "global_admin" and current_user.role != "global_admin":
        flash_message("Et voi muokata globaalin ylläpitäjän tietoja.", "error")
        return redirect(url_for("admin_user.user_control"))

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        role = request.form.get("role")
        organization_ids = request.form.getlist("organizations")
        confirmed = request.form.get("confirmed") == "on"

        # Validate user input
        if not username or not email:
            flash_message("Käyttäjänimi ja sähköposti ovat pakollisia.", "error")
            return redirect(url_for("admin_user.edit_user", user_id=user_id))

        if not valid_email(email):
            flash_message("Virheellinen sähköpostimuoto.", "error")
            return redirect(url_for("admin_user.edit_user", user_id=user_id))

        # Prevent role escalation
        if current_user._id == user_id and role != current_user.role:
            flash_message("Et voi muuttaa omaa rooliasi.", "error")
            return redirect(url_for("admin_user.edit_user", user_id=user_id))

        # Ensure global admins cannot lower their role
        if (
            user.role == "global_admin"
            and current_user._id == user_id
            and role != "global_admin"
        ):
            flash_message(
                "Et voi alentaa omaa rooliasi globaalina ylläpitäjänä.", "error"
            )
            return redirect(url_for("admin_user.edit_user", user_id=user_id))

        # Collect organizations and permissions
        orgs = [
            {
                "org_id": org_id,
                "role": "admin",
                "permissions": request.form.getlist(f"permissions_{org_id}"),
            }
            for org_id in organization_ids
        ]

        # Update user in the database
        mongo.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "username": username,
                    "email": email,
                    "role": role,
                    "organizations": orgs,
                    "confirmed": confirmed,
                }
            },
        )

        flash_message("Käyttäjä päivitetty onnistuneesti.", "approved")
        return redirect(url_for("admin_user.user_control"))

    # Prepare to render the edit user form
    user_orgs = [
        {"_id": org.get("org_id"), "role": org.get("role")}
        for org in user.organizations
    ]
    org_ids = [org.get("org_id") for org in user_orgs]
    user_permissions = user.permissions
    global_permissions = user.global_permissions

    return render_template(
        "admin/user/edit.html",
        user=user,
        organizations=organizations,
        org_ids=org_ids,
        PERMISSIONS_GROUPS=PERMISSIONS_GROUPS,
        user_permissions=user_permissions,
        global_permissions=global_permissions,
        user_organizations=user_orgs,
    )


@admin_user_bp.route("/save_user/<user_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def save_user(user_id):
    """Save updated user details, permissions, and send email notification.

    Changelog:
    ----------

    v2.4.0:
    - Modified to use valid_email instead of depraced is_valid_email
    """
    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash_message("Käyttäjää ei löydy.", "error")
        return redirect(url_for("admin_user.user_control"))

    user = User.from_db(user)

    # Get form data
    username = request.form.get("username")
    email = request.form.get("email")
    role = request.form.get("role")
    organization_ids = request.form.getlist("organizations")
    confirmed = request.form.get("confirmed") == "on"

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
        # If user that's the target of this edit, is a global_admin and you're the user that's being edited, and you're trying to lower your role, we will deny it.
        flash_message("Et voi alentaa omaa rooliasi globaalina ylläpitäjänä.", "error")
        return redirect(url_for("admin_user.edit_user", user_id=user_id))

    # Validate mandatory fields
    if not username or not email:
        flash_message("Käyttäjänimi ja sähköposti ovat pakollisia.", "error")
        return redirect(url_for("admin_user.edit_user", user_id=user_id))

    if not valid_email(email):
        flash_message("Virheellinen sähköpostimuoto.", "error")
        return redirect(url_for("admin_user.edit_user", user_id=user_id))

    # Fetch organization names for notification
    organizations = mongo.organizations.find(
        {"_id": {"$in": [ObjectId(org_id) for org_id in organization_ids]}}
    )
    org_names = [org["name"] for org in organizations]

    # Update user information in the database
    mongo.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "username": username,
                "email": email,
                "role": role,
                "organizations": [
                    {"org_id": org_id, "role": "admin"} for org_id in organization_ids
                ],
                "confirmed": confirmed,
            }
        },
    )

    # Prepare the email notification content
    permission_summary_html = "<p>Sinulla on seuraavat oikeudet:</p>"
    for org_id, perms in user.permissions.items():
        org_name = get_org_name(org_id)
        permission_summary_html += f"<h3>{org_name}:</h3><ul>"

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
            "user_name": user.displayname or username,
            "role": role,
            "organization_names": ", ".join(org_names),
            "action": "päivitetty",
            "updated_email": email,
            "permissions_summary": permission_summary_html,
            "login_link": url_for("auth.login", _external=True),
            "support_contact": "tuki@mielenosoitukset.fi",
        },
    )

    flash_message("Käyttäjä päivitetty onnistuneesti.", "approved")
    return redirect(url_for("admin_user.user_control"))


import warnings


def is_valid_email(email):
    """
    Deprecated: This function is deprecated and will be removed in future versions.
    Please use `valid_email` from `utils.py` instead.

    Usage:
        from utils import valid_email
        is_valid = valid_email(email)

    Utility function to validate email format.
    """
    warnings.warn(
        "is_valid_email is deprecated; use valid_email from ../utils.py instead.",
        DeprecationWarning,
    )

    return "@" in email and "." in email.split("@")[-1]


# Delete user
@admin_user_bp.route("/delete_user/<user_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("DELETE_USER")
def delete_user(user_id):
    """Delete a user from the system."""
    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    if user:
        mongo.users.delete_one({"_id": ObjectId(user_id)})
        flash_message("Käyttäjä poistettu onnistuneesti.", "approved")
    else:
        flash_message("Käyttäjää ei löydy.", "error")
    return redirect(url_for("admin_user.user_control"))
