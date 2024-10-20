from utils import PERMISSIONS_GROUPS
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from auth.models import User
from wrappers import admin_required, permission_required
from emailer.EmailSender import EmailSender

from .utils import mongo, get_org_name

email_sender = EmailSender()

admin_user_bp = Blueprint("admin_user", __name__, url_prefix="/admin/user")

def flash_message(message, category):
    """Flash a message with a specific category."""
    categories = {
        "info": "info",
        "approved": "success",
        "success": "success",
        "warning": "warning",
        "error": "danger",
    }
    flash(message, categories.get(category, "info"))


# User control panel with pagination
@admin_user_bp.route("/")
@login_required
@admin_required
@permission_required("LIST_USERS")
def user_control():
    """Render the user control panel with a list of users."""
    search_query = request.args.get("search", "")
    if search_query:
        users_cursor = mongo.users.find(
            {
                "$or": [
                    {"username": {"$regex": search_query, "$options": "i"}},
                    {"email": {"$regex": search_query, "$options": "i"}},
                ]
            }
        )
    else:
        users_cursor = mongo.users.find()

    return render_template(
        "admin/user/list.html", users=users_cursor, search_query=search_query
    )


def stringify_object_ids(data):
    """Recursively converts all ObjectId instances in the given data structure to strings."""
    if isinstance(data, dict):
        return {k: stringify_object_ids(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [stringify_object_ids(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, str):
        return data
    else:
        print(data)
        return data


@admin_user_bp.route("/edit_user/<user_id>", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("EDIT_USER")
def edit_user(user_id):
    """Edit user details."""
    user = User.from_db(mongo.users.find_one({"_id": ObjectId(user_id)}))

    organizations = stringify_object_ids(list(mongo.organizations.find()))

    if user is None:
        flash_message("Käyttäjää ei löytynyt.", "error")
        return redirect(url_for("admin_user.user_control"))

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        role = request.form.get("role")
        organization_ids = request.form.getlist("organizations")
        confirmed = (
            request.form.get("confirmed") == "on"
        )  # Correctly handle confirmation input

        # Validation for user input
        if not username or not email:
            flash_message("Käyttäjänimi ja sähköposti ovat pakollisia.", "error")
            return redirect(url_for("admin_user.edit_user", user_id=user_id))

        # Validate email format
        if not is_valid_email(email):
            flash_message("Virheellinen sähköpostimuoto.", "error")
            return redirect(url_for("admin_user.edit_user", user_id=user_id))

        # Collect organizations and permissions
        orgs = []
        permissions_data = request.form.getlist("permissions")
        for organization in organization_ids:
            org_perms = [
                perm.split("_")[-1]
                for perm in permissions_data
                if perm.startswith(organization)
            ]
            orgs.append(
                {"org_id": organization, "role": "admin", "permissions": org_perms}
            )

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
    user_orgs = [{"_id": org.get("org_id"), "role": org.get("role")} for org in user.organizations]
    org_ids = [org.get("org_id") for org in user_orgs]
    user_permissions = user.permissions  # Fetch user-specific permissions
    global_permissions = (
        user.global_permissions
    )  # Ensure global permissions are retrieved

    return render_template(
        "admin/user/edit.html",
        user=user,
        organizations=organizations,
        org_ids=org_ids,
        PERMISSIONS_GROUPS=PERMISSIONS_GROUPS,
        user_permissions=user_permissions,
        global_permissions=global_permissions,
        user_organizations=user_orgs
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

    # Get form data
    username = request.form.get("username")
    email = request.form.get("email")
    role = request.form.get("role")
    organization_ids = request.form.getlist("organizations")
    confirmed = request.form.get("confirmed") == "on"

    # Gather user permissions
    user_permissions = {
        org_id: request.form.getlist(f"permissions[{org_id}][]")
        for org_id in organization_ids
    }
    global_permissions = request.form.getlist(
        "permissions[global][]"
    )  # Changed from "global" to access global permissions

    # Validate mandatory fields
    if not username or not email:
        flash_message("Käyttäjänimi ja sähköposti ovat pakollisia.", "error")
        return redirect(url_for("admin_user.edit_user", user_id=user_id))

    if not is_valid_email(email):
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
                "permissions": user_permissions,
                "global_permissions": global_permissions,
            }
        },
    )

    # Prepare the email notification content
    permission_summary_html = "<p>Sinulla on seuraavat oikeudet:</p>"

    for org_id, perms in user_permissions.items():
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
            "user_name": user.get("displayname") or username,
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


def is_valid_email(email):
    """Utility function to validate email format."""
    return "@" in email and "." in email.split("@")[-1]


# Delete user
@admin_user_bp.route("/delete_user/<user_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("DELETE_USER")
def delete_user(user_id):
    """Delete a user from the database."""
    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    if user:
        mongo.users.delete_one({"_id": ObjectId(user_id)})
        flash_message("Käyttäjä poistettu onnistuneesti.", "approved")
    else:
        flash_message("Käyttäjää ei löydetty.", "error")
    return redirect(url_for("admin_user.user_control"))
