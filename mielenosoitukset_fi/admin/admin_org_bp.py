"""
Changelog:
----------

v2.5.0:
- Removed gettext as it is not needed in create_organization.

v2.4.0:
- Added validation for organization fields.
- Added logging for organization creation.
- Modified code to use valid_email instead of deprecated is_valid_email.
- Admin action logging has been in use since V2.4.0, and it helps us keep track who did what.
"""

from datetime import datetime
from bson.objectid import ObjectId
from flask import Blueprint, abort, redirect, render_template, request, url_for, jsonify, Response, current_app
from flask_babel import gettext as _
from flask_login import current_user, login_required
from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.validators import valid_email
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from .utils import log_admin_action, mongo, get_org_name as get_organization_name
from mielenosoitukset_fi.utils.classes import Organization, MemberShip

from typing import Optional, Tuple, Any, Dict
from bson import ObjectId  # if using pymongo
from werkzeug.utils import secure_filename
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj

# Create a Blueprint for admin organization management
admin_org_bp = Blueprint("admin_org", __name__, url_prefix="/admin/organization")

from .utils import AdminActParser, log_admin_action_V2, _ADMIN_TEMPLATE_FOLDER


@admin_org_bp.before_request
def log_request_info():
    """Log request information before handling it."""
    log_admin_action_V2(
        AdminActParser().log_request_info(request.__dict__, current_user)
    )


from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.logger import logger

email_sender = EmailSender()




# Organization control panel
@admin_org_bp.route("/")
@login_required
@admin_required
@permission_required("LIST_ORGANIZATIONS")
def organization_control():
    """Render the organization control panel with a list of organizations."""
    log_admin_action(
        current_user, "View Organizations", "Accessed organization control panel"
    )  # Admin action logging has been in use since V2.4.0, and it helps us keep track who did what.

    org_limiter = (
        [ObjectId(org) for org in current_user.org_ids()]
        if not current_user.global_admin
        else None
    )

    search_query = request.args.get("search", "")
    page = max(int(request.args.get("page", 1)), 1)
    per_page = max(int(request.args.get("per_page", 20)), 1)

    query = construct_query(search_query, org_limiter)

    total_count = mongo.organizations.count_documents(query)
    total_pages = (total_count + per_page - 1) // per_page if total_count else 1
    if page > total_pages:
        page = total_pages

    organizations = list(
        mongo.organizations.find(query)
        .sort("name", 1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )

    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < total_pages else None

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}organizations/dashboard.html",
        organizations=organizations,
        search_query=search_query,
        per_page=per_page,
        current_page=page,
        total_pages=total_pages,
        prev_page=prev_page,
        next_page=next_page,
    )


def construct_query(search_query, org_limiter):
    """Construct the query for organizations based on search input.

    Parameters
    ----------
    search_query :
        param org_limiter:
    org_limiter :


    Returns
    -------


    """
    query = {}

    if search_query:
        query = {
            "$or": [
                {"name": {"$regex": search_query, "$options": "i"}},
                {"email": {"$regex": search_query, "$options": "i"}},
            ]
        }

    if org_limiter:
        query["_id"] = {"$in": org_limiter}

    return query


# Edit organization
@admin_org_bp.route("/edit/<org_id>", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("EDIT_ORGANIZATION")
def edit_organization(org_id):
    """Edit organization details.

    Parameters
    ----------
    org_id :


    Returns
    -------


    """
    if not current_user.has_permission("EDIT_ORGANIZATION", org_id):
        log_admin_action(
            current_user, "Edit Organization (insuffient permissions)", f"Tried editing organization {org_id}")
        abort(403)
        
        
    log_admin_action(
        current_user, "Edit Organization", f"Editing organization {org_id}"
    )

    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})

    if request.method == "POST":
        if update_organization(org_id):
            log_admin_action(
                current_user, "Update Organization", f"Updated organization {org_id}"
            )
            flash_message(_("Organisaatio päivitetty onnistuneesti."))
            return redirect(request.referrer)

    return render_template(f"{_ADMIN_TEMPLATE_FOLDER}organizations/form.html", organization=organization)


def invite_to_organization(invitee_email, organization_id):
    """Send an invitation email to a user to join an organization.

    Parameters
    ----------
    invitee_email : str
        The email address of the person being invited.
    organization_id : str
        The ID of the organization.

    Returns
    -------


    """
    try:
        organization = mongo.organizations.find_one({"_id": ObjectId(organization_id)})
        org = Organization.from_dict(organization)

        if invitee_email in org.invitations:
            flash_message("Kutsu on jo lähetetty tälle sähköpostiosoitteelle.", "error")
            return

        if org.is_member(invitee_email):
            flash_message("Käyttäjä on jo jäsen organisaatiossa.", "error")
            return

        invite_url = url_for(
            "users.user_orgs.accept_invite",
            organization_id=organization_id,
            _external=True,
        )
        email_sender.queue_email(
            template_name="invite_to_organization.html",
            subject=f"Kutsu liittyä organisaatioon {get_organization_name(organization_id)}",
            recipients=[invitee_email],
            context={
                "invite_url": invite_url,
                "inviter_name": current_user.displayname or current_user.username,
                "organization_name": get_organization_name(organization_id),
            },
        )

        # Add invitation into db
        mongo.organizations.update_one(
            {"_id": ObjectId(organization_id)},
            {"$addToSet": {"invitations": invitee_email}},
        )  # Add the email to the invitations list in the organization document.

        flash_message("Kutsu lähetetty onnistuneesti.", "success")
    except Exception as e:
        logger.error(f"Kutsun lähettäminen epäonnistui: {e}")
        flash_message(f"Kutsun lähettäminen epäonnistui: {e}", "error")


def update_organization(org_id):
    """Update organization details based on form input.

    Parameters
    ----------
    org_id :


    Returns
    -------


    """
    name = request.form.get("name")
    email = request.form.get("email")

    if not validate_organization_fields(name, email, org_id):
        return False

    description = request.form.get("description")
    website = request.form.get("website")
    social_media_links = get_social_media_links()
    current_logo_doc = mongo.organizations.find_one({"_id": ObjectId(org_id)}, {"logo": 1})
    current_logo = current_logo_doc.get("logo") if current_logo_doc else None
    logo_value, logo_changed = resolve_logo_value(current_logo)

    update_payload = {
        "name": name,
        "description": description,
        "email": email,
        "website": website,
        "social_media_links": social_media_links,
        "verified": request.form.get("verified") == "on",
    }
    if logo_changed:
        update_payload["logo"] = logo_value

    mongo.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {
            "$set": update_payload
        },
    )
    return True


def validate_organization_fields(name, email, org_id):
    """Validate required fields for organization.

    Changelog:
    ----------

    v2.4.0:
    - Modified code to use valid_email instead of depraced is_valid_email.

    Parameters
    ----------
    name :
        param email:
    org_id :

    email :


    Returns
    -------


    """

    if not name or not email:
        flash_message("Nimi ja sähköpostiosoite ovat pakollisia.", "error")
        return False

    if not valid_email(email):
        flash_message("Virheellinen sähköpostiosoite.", "error")
        return False

    return True


def get_social_media_links():
    """Retrieve social media links from form input."""
    platforms = request.form.getlist("social_media_platform[]")
    urls = request.form.getlist("social_media_url[]")
    return {platform: url for platform, url in zip(platforms, urls) if platform and url}


def resolve_logo_value(current_logo: Optional[str] = None) -> tuple[Optional[str], bool]:
    """
    Determine the desired logo value based on form inputs and uploads.

    Returns a tuple of (value, should_update) so callers can decide whether to include the field in DB writes.
    """
    file = request.files.get("logo_file")
    logo_field = request.form.get("logo_url")
    remove_logo = request.form.get("remove_logo") == "on"
    normalized_current = (current_logo or "").strip()

    if file and file.filename:
        bucket_name = current_app.config.get("S3_BUCKET")
        if not bucket_name:
            logger.error("S3 bucket missing, cannot upload organization logo.")
            flash_message(_("Logon lähetys epäonnistui, S3-asetukset puuttuvat."), "error")
            return current_logo, False

        filename = secure_filename(file.filename)
        try:
            uploaded_url = upload_image_fileobj(bucket_name, file.stream, filename, "organization_logos")
            if uploaded_url:
                return uploaded_url, True
            flash_message(_("Logon lähetys epäonnistui."), "error")
        except Exception:
            logger.exception("Failed to upload organization logo.")
            flash_message(_("Logon lähetys epäonnistui."), "error")
        return current_logo, False

    if remove_logo:
        return None, True

    if logo_field is None:
        return current_logo, False

    trimmed_logo = logo_field.strip()
    if trimmed_logo:
        if trimmed_logo != normalized_current:
            return trimmed_logo, True
        return current_logo, False

    # Field submitted empty
    if normalized_current:
        return None, True
    return None, False


# Create organization
@admin_org_bp.route("/create", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("CREATE_ORGANIZATION")
def create_organization():
    """Create a new organization.

    Changelog:
    ----------
    v2.5.0:
    - Removed gettext as it is not needed here.

    v2.4.0:
    - Added validation for organization fields.
    - Added logging for organization creation.

    Parameters
    ----------

    Returns
    -------


    """
    if request.method == "POST":
        if insert_organization()[0]:
            flash_message(
                "Organisaatio luotu onnistuneesti."
            )  # Removed gettext as it is not needed here.
            return redirect(request.referrer or url_for("admin_org.organization_control"))

    return render_template(f"{_ADMIN_TEMPLATE_FOLDER}organizations/form.html")

def insert_organization(org_data: Optional[dict] = None) -> Tuple[bool, Optional[ObjectId]]:
    """
    Insert a new organization into the database.

    Parameters
    ----------
    org_data : dict, optional
        A dictionary containing organization data. Expected keys are:
        - "name" : str
            The name of the organization.
        - "email" : str
            Contact email of the organization.
        - "description" : str, optional
            Description of the organization.
        - "website" : str, optional
            Website URL of the organization.
        If not provided, data will be extracted from the Flask `request.form`.

    Returns
    -------
    tuple of (bool, ObjectId or None)
        A tuple containing:
        - success : bool
            Whether the organization was successfully inserted.
        - inserted_id : bson.ObjectId or None
            The ID of the newly created organization if successful, otherwise ``None``.

    Notes
    -----
    - If `org_data` is provided, social media links will be initialized as an
      empty dictionary. Otherwise, they are retrieved using
      `get_social_media_links()`.
    - The function validates required fields (`name`, `email`) only when
      `org_data` is not provided.
    - On successful insertion, an admin action is logged with the current user.
    """
    if org_data:
        data_source = org_data
    else:
        data_source = request.form

    name = data_source.get("name")
    email = data_source.get("email")

    if not validate_organization_fields(name, email, None) and not org_data:
        return False, None

    description = data_source.get("description")
    website = data_source.get("website")

    if not org_data:
        social_media_links = get_social_media_links()
    else:
        social_media_links = {}

    if org_data:
        logo_value = org_data.get("logo")
        logo_should_set = "logo" in org_data and logo_value is not None
    else:
        logo_value, logo_should_set = resolve_logo_value()

    result = mongo.organizations.insert_one(
        {
            "name": name,
            "description": description,
            "email": email,
            "website": website,
            "social_media_links": social_media_links,
            "members": [],
            **({"logo": logo_value} if logo_should_set and logo_value else {}),
        }
    )

    if result.inserted_id:
        log_admin_action(
            current_user,
            "Create Organization",
            f"Created organization {result.inserted_id}",
        )
        return True, result.inserted_id

    return False, None



# Delete organization
@admin_org_bp.route("/delete/<org_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("DELETE_ORGANIZATION")
def delete_organization(org_id):
    """Delete an organization.

    Parameters
    ----------
    org_id :


    Returns
    -------


    """
    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})

    if not organization:
        log_admin_action(
            current_user, "Delete Organization", f"Failed to find organization {org_id}"
        )
        flash_message("Organisatiota ei löytynyt.", "error")
        return redirect(request.referrer or url_for("admin_org.organization_control"))

    if "confirm_delete" in request.form:
        mongo.organizations.delete_one({"_id": ObjectId(org_id)})
        flash_message(_("Organisaatio poistettu onnistuneesti."))
        log_admin_action(
            current_user, "Delete Organization", f"Deleted organization {org_id}"
        )

    else:
        flash_message("Organisaation poistoa ei vahvistettu.", "warning")

    return redirect(request.referrer or url_for("admin_org.organization_control"))


# Confirmation before deleting an organization
@admin_org_bp.route("/confirm_delete/<org_id>", methods=["GET"])
@login_required
@admin_required
@permission_required("DELETE_ORGANIZATION")
def confirm_delete_organization(org_id):
    """Render a confirmation page before deleting an organization.

    Parameters
    ----------
    org_id :


    Returns
    -------


    """
    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})

    if not organization:
        flash_message("Organisaatiota ei löytynyt.", "error")

        return redirect(request.referrer or url_for("admin_org.organization_control"))

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}organizations/confirm_delete.html", organization=organization
    )


# TODO: #174 Add unit tests for all routes and functions.
# TODO: #175 Implement pagination for the organization control panel.
# TODO: #176 Add error handling for database operations.
# TODO: #177 Refactor common code into utility functions.
# TODO: #179 #178 Improve the user interface for organization forms.


@admin_org_bp.route("/invite", methods=["POST"])
@login_required
@admin_required
@permission_required("INVITE_TO_ORGANIZATION")
def invite():
    """ """
    invitee_email = request.form.get("invitee_email")
    organization_id = request.form.get("organization_id")
    logger.debug(f"Inviting {invitee_email} to organization {organization_id}")
    invite_to_organization(invitee_email, ObjectId(organization_id))
    return redirect(request.referrer or url_for("admin_org.organization_control"))


@admin_org_bp.route("/view/<org_id>")
@login_required
@admin_required
@permission_required("VIEW_ORGANIZATION")
def view_organization(org_id):
    """

    Parameters
    ----------
    org_id :


    Returns
    -------


    """
    organization_doc = mongo.organizations.find_one({"_id": ObjectId(org_id)})
    organization = Organization.from_dict(organization_doc)

    # Get invited users (emails or dicts) from the organization document
    invited_users_raw = organization_doc.get("invitations", [])
    invited_users = []
    for invite in invited_users_raw:
        if isinstance(invite, dict):
            # Ensure both email and role keys exist
            invited_users.append({
                "email": invite.get("email", ""),
                "role": invite.get("role", "member")
            })
        elif isinstance(invite, str):
            invited_users.append({"email": invite, "role": "member"})
    # Now invited_users is always a list of dicts with email and role

    memberships = MemberShip.all_in_organization(organization_id=ObjectId(org_id))
    members = []
    for m in memberships:
        user = User.from_OID(m.user_id)
        user.role = m.role
        user.permissions = m.permissions
        user._ship_id = m._id
        members.append(user)

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}organizations/view.html",
        organization=organization,
        memberships=members,
        invited_users=invited_users
    )


# API STUFF

@admin_org_bp.route("/api/delete_membership/", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_ORGANIZATION")
def delete_membership() -> Tuple[Response, int]:
    """
    Delete a user's membership from an organization.

    API Endpoint
    ------------
    POST /api/delete_membership/

    Request JSON
    ------------
    {
        "membership_id": str,
            The MongoDB ObjectId of the membership document as a string.
    }

    Returns
    -------
    (flask.Response, int)
        JSON response with status code:
        
        - 200 OK:
            {"message": "Käyttäjä poistettu organisaatiosta"}
        - 400 Bad Request:
            {"error": "Membership ID puuttuu"}
        - 500 Internal Server Error:
            {"error": "Poisto epäonnistui"}

    Notes
    -----
    - TODO (#342): Require organization-level admin/owner access,
      global `edit_organization` access, or superuser status before deletion.
    """
    # --- Parse input ---
    data: Dict[str, Any] = request.get_json() or {}
    membership_id: str | None = data.get("membership_id")

    if not membership_id:
        return jsonify({"error": "Membership ID puuttuu"}), 400

    # --- Delete membership ---
    result = mongo.memberships.delete_one({"_id": ObjectId(membership_id)})

    if result.deleted_count == 1:
        return jsonify({"message": "Käyttäjä poistettu organisaatiosta"}), 200

    return jsonify({"error": "Poisto epäonnistui"}), 500

@admin_org_bp.route("/<org_id>/suggestion/<suggestion_id>")
@login_required
@admin_required
def review_suggestion(org_id, suggestion_id):
    suggestion = get_suggestion_with_expiry_check(suggestion_id)
    
    if suggestion and str(suggestion.get("organization_id")) != org_id:
        flash_message("Ehdotus kuuluu toiselle organisaatiolle. Uudelleenohjataan oikeaan paikkaan.", "warning")
        return redirect(url_for(
            "admin_org.review_suggestion",
            org_id=str(suggestion.get("organization_id")),
            suggestion_id=suggestion_id
        ))

    org = mongo.organizations.find_one({"_id": ObjectId(org_id)})
    

    if not org or not suggestion:
        flash_message("Ehdotusta tai organisaatiota ei löytynyt.", "error")
        return redirect(url_for("index"))

    org = Organization.from_dict(org)

    # --- 🪄 Mark as viewed ---
    update_ops = {
        "$set": {
            "status.updated_at": datetime.utcnow(),
        },
        "$push": {
            "audit_log": {
                "action": "viewed",
                "timestamp": datetime.utcnow(),
                "user": getattr(current_user, "username", None),  # if you have Flask-Login
            }
        }
    }

    # If still pending, mark as "in_review" when opened
    if suggestion.get("status", {}).get("state") == "pending":
        update_ops["$set"]["status.state"] = "in_review"
        update_ops["$set"]["status.updated_by"] = getattr(current_user, "username", None)

    mongo.org_edit_suggestions.update_one(
        {"_id": ObjectId(suggestion_id)},
        update_ops
    )

    # Reload suggestion so we render fresh data
    suggestion = mongo.org_edit_suggestions.find_one({"_id": ObjectId(suggestion_id)})

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}organizations/review_suggestion.html",
        org=org,
        suggestion=suggestion,
    )

from datetime import datetime
from bson import ObjectId
from flask import request, redirect, url_for
from flask_login import current_user

@admin_org_bp.route("/<org_id>/suggestion/<suggestion_id>/apply", methods=["POST"])
@login_required
@admin_required
def apply_suggestion(org_id, suggestion_id):
    suggestion = mongo.org_edit_suggestions.find_one({"_id": ObjectId(suggestion_id)})
    if not suggestion:
        flash_message("Ehdotusta ei löytynyt.", "error")
        return redirect(url_for("admin_org.review_suggestion", org_id=org_id, suggestion_id=suggestion_id))

    selected_fields = request.form.getlist("apply_fields")
    if not selected_fields:
        flash_message("Et valinnut yhtään kenttää päivitettäväksi.", "info")
        return redirect(url_for("admin_org.review_suggestion", org_id=org_id, suggestion_id=suggestion_id))

    update_data = {}
    for f in selected_fields:
        if f in suggestion.get("fields", {}):
            update_data[f] = suggestion["fields"][f]

    # Handle nested socials
    if "social_media_links" in selected_fields and isinstance(suggestion["fields"].get("social_media_links"), dict):
        update_data["social_media_links"] = suggestion["fields"]["social_media_links"]

    applied_successfully = False

    if update_data:
        mongo.organizations.update_one(
            {"_id": ObjectId(org_id)},
            {"$set": update_data}
        )
        applied_successfully = True
        flash_message("Organisaation tiedot päivitettiin valittujen kenttien osalta 💖", "success")
    else:
        flash_message("Ei mitään päivitettävää.", "info")

    # --- 🪄 Update suggestion status + audit log ---
    new_state = "applied" if applied_successfully else "in_review"
    if applied_successfully and len(selected_fields) < len(suggestion.get("fields", {})):
        new_state = "partially_applied"

    update_ops = {
        "$set": {
            "status.state": new_state,
            "status.updated_at": datetime.utcnow(),
            "status.updated_by": getattr(current_user, "username", None),
        },
        "$push": {
            "audit_log": {
                "action": "apply_fields",
                "fields": selected_fields,
                "timestamp": datetime.utcnow(),
                "user": getattr(current_user, "username", None),
            }
        }
    }

    mongo.org_edit_suggestions.update_one(
        {"_id": ObjectId(suggestion_id)},
        update_ops
    )

    # Optional: auto-hide from todo list if fully applied
    if new_state == "applied":
        mongo.org_edit_suggestions.update_one(
            {"_id": ObjectId(suggestion_id)},
            {"$set": {"status.completed_at": datetime.utcnow()}}
        )

    return redirect(url_for("admin_org.review_suggestion", org_id=org_id, suggestion_id=suggestion_id))



from datetime import datetime, timedelta

def get_suggestion_with_expiry_check(suggestion_id):
    suggestion = mongo.org_edit_suggestions.find_one({"_id": ObjectId(suggestion_id)})
    if not suggestion:
        return None

    # auto-expire review state after 30 minutes
    status = suggestion.get("status", {})
    if status.get("state") == "in_review":
        updated_at = status.get("updated_at")
        if updated_at and datetime.utcnow() - updated_at > timedelta(minutes=30):
            mongo.org_edit_suggestions.update_one(
                {"_id": ObjectId(suggestion_id)},
                {"$set": {"status.state": "pending"}}
            )
            suggestion["status"]["state"] = "pending"  # keep local copy consistent

    return suggestion

def get_pending_suggestions(org_id):
    return list(mongo.org_edit_suggestions.find({
        "organization_id": ObjectId(org_id),
        "status.state": {"$in": ["pending", "in_review", "partially_applied"]}
    }))


@admin_org_bp.route("/api/new", methods=["POST"])
@login_required
@admin_required
@permission_required("CREATE_ORGANIZATION")
def create_organization_api():
    """Create a new organization using an API endpoint.

    Parameters
    ----------

    Returns
    -------


    """
    org_name = request.json.get("name")
    org_email = request.json.get("email", "no@email.example")
    org_website = request.json.get("website")


    if not org_name and not org_email:
        return {"message": "Nimi ja sähköpostiosoite ovat pakollisia."}

    # if org_email is not None and not valid_email(org_email):
    # return {"message": "Virheellinen sähköpostiosoite."}

    org_description = request.json.get("description", "Kuvaus tulossa")

    org_data = {
        "name": org_name,
        "email": org_email,
        "website": org_website,
        "description": org_description,
    }

    # insert

    _, _id = insert_organization(org_data)

    if not _id is None:
        return {"message": "Organisaatio luotu onnistuneesti.", "id": str(_id)}

    return {"message": "Virhe organisaation luonnissa."}


@admin_org_bp.route("/api/force_accept_invite/", methods=["POST"])
@login_required
@admin_required
def force_accept_invite() -> Tuple[Response, int]:
    """
    Force-accept an organization invitation on behalf of a user (superuser only).

    This endpoint allows a superuser (`global_admin`) to accept an invitation
    for a user into an organization. The invitation is removed from the
    organization's `invitations` list, and the user is added as a member with
    the specified role (default: "member").

    API Endpoint
    ------------
    POST /api/force_accept_invite/

    Request JSON
    ------------
    {
        "email": str,
            Email address of the invited user.
        "organization_id": str,
            The MongoDB ObjectId of the organization as a string.
    }

    Returns
    -------
    (flask.Response, int)
        JSON response with appropriate status code:
        
        - 200 OK:
            {"status": "OK"}
        - 400 Bad Request:
            {"status": "error", "error": "..."}
            If required fields are missing or user is already a member.
        - 403 Forbidden:
            {"status": "error", "error": "..."}
            If the current user is not a superuser.
        - 404 Not Found:
            {"status": "error", "error": "..."}
            If the organization or user is not found.

    Notes
    -----
    - Only users with `global_admin = True` can perform this action.
    - If the invite includes a `role`, that role is applied to the user.
      Otherwise, the role defaults to `"member"`.
    - If the role is `"admin"` or `"owner"` and the user does not already have
      a global admin/owner role, the user's role is elevated to `"admin"`.
    - Invitations can be stored either as dicts (with "email" and optional
      "role") or as plain strings (email only).
    - After acceptance, the user's invitation is removed from the organization's
      `invitations` list and the user is added to `members`.
    """

    # --- Permission check ---
    if not getattr(current_user, "global_admin", False):
        return (
            jsonify({
                "status": "error",
                "error": "Vain superkäyttäjä voi hyväksyä kutsun puolesta."
            }),
            403,
        )

    # --- Parse input ---
    data: Dict[str, Any] = request.get_json() or {}
    email: str | None = data.get("email")
    org_id: str | None = data.get("organization_id")

    if not email or not org_id:
        return (
            jsonify({"status": "error", "error": "Missing required fields."}),
            400,
        )

    # --- Fetch organization ---
    org = mongo.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        return (
            jsonify({"status": "error", "error": "Organization not found."}),
            404,
        )

    # --- Prepare invitations ---
    invitations = org.get("invitations", [])
    new_invitations = [
        invite
        for invite in invitations
        if not (
            (isinstance(invite, dict) and invite.get("email") == email)
            or (isinstance(invite, str) and invite == email)
        )
    ]

    # --- Fetch user ---
    from mielenosoitukset_fi.users.models import User

    user_doc = mongo.users.find_one({"email": email})
    if not user_doc:
        return (
            jsonify({"status": "error", "error": "Käyttäjää ei löydy annetulla sähköpostilla."}),
            404,
        ) # TODO: #387 Add user creation, so this automatically creates the user and accepts the invite for them

    user = User.from_db(user_doc)

    # --- Determine role ---
    role = "member"
    for invite in invitations:
        if (
            isinstance(invite, dict)
            and invite.get("email") == email
            and invite.get("role")
        ):
            role = invite.get("role")
            break

    # --- Membership check ---
    org_obj = Organization.from_dict(org)
    if org_obj.is_member(email):
        return (
            jsonify({"status": "error", "error": "Käyttäjä on jo jäsen."}),
            400,
        )

    # --- Add member ---
    org_obj.add_member(user, role=role)

    # --- Elevate role if needed ---
    if (
        role in ["admin", "owner"]
        and user.role not in ["admin", "owner", "global_admin", "superuser"]
    ):
        user.role = "admin"
        user.save()

    # --- Update organization ---
    mongo.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {"invitations": new_invitations}},
    )

    return jsonify({"status": "OK"}), 200


@admin_org_bp.route("/api/cancel_invite/", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_ORGANIZATION")
def cancel_invite() -> Tuple[Response, int]:
    """
    Cancel (remove) a pending invitation for an organization.

    API Endpoint
    ------------
    POST /api/cancel_invite/

    Request JSON
    ------------
    {
        "email": str,
            Email address of the invited user.
        "organization_id": str,
            The MongoDB ObjectId of the organization as a string.
    }

    Returns
    -------
    (flask.Response, int)
        JSON response with status code:
        
        - 200 OK:
            {"status": "OK"}
        - 400 Bad Request:
            {"status": "error", "error": "Missing required fields."}
        - 404 Not Found:
            {"status": "error", "error": "Organization not found."}
            or {"status": "error", "error": "Invitation not found."}
    """
    # --- Parse input ---
    data: Dict[str, Any] = request.get_json() or {}
    email: str | None = data.get("email")
    org_id: str | None = data.get("organization_id")

    if not email or not org_id:
        return jsonify({"status": "error", "error": "Missing required fields."}), 400

    # --- Fetch organization ---
    org = mongo.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        return jsonify({"status": "error", "error": "Organization not found."}), 404

    # --- Process invitations ---
    invitations = org.get("invitations", [])
    new_invitations = []
    removed = False

    for invite in invitations:
        if (
            (isinstance(invite, dict) and invite.get("email") == email)
            or (isinstance(invite, str) and invite == email)
        ):
            removed = True
            continue
        new_invitations.append(invite)

    if not removed:
        return jsonify({"status": "error", "error": "Invitation not found."}), 404

    # --- Update organization ---
    mongo.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {"invitations": new_invitations}},
    )
    return jsonify({"status": "OK"}), 200


@admin_org_bp.route("/api/set_invite_role/", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_ORGANIZATION")
def set_invite_role() -> Tuple[Response, int]:
    """
    Set or update the role for a pending invitation (by email) for an organization.

    API Endpoint
    ------------
    POST /api/set_invite_role/

    Request JSON
    ------------
    {
        "email": str,
            Email address of the invited user.
        "organization_id": str,
            The MongoDB ObjectId of the organization as a string.
        "role": str,
            Role assigned to the invited user. One of: "owner", "admin", "member".
    }

    Returns
    -------
    (flask.Response, int)
        JSON response with status code:
        
        - 200 OK:
            {"status": "OK"}
        - 400 Bad Request:
            {"status": "error", "error": "Missing required fields."}
            or {"status": "error", "error": "Invalid role."}
        - 404 Not Found:
            {"status": "error", "error": "Organization not found."}

    Notes
    -----
    - Invitations may be stored as:
        - dict: {"email": ..., "role": ...}
        - str: legacy format (email only)
    - If an invite already exists, its role is updated.
    - If no invite exists for the email, a new one is created.
    """
    # --- Parse input ---
    data: Dict[str, Any] = request.get_json() or {}
    email: str | None = data.get("email")
    org_id: str | None = data.get("organization_id")
    role: str | None = data.get("role")

    if not email or not org_id or not role:
        return jsonify({"status": "error", "error": "Missing required fields."}), 400

    if role not in ["owner", "admin", "member"]:
        return jsonify({"status": "error", "error": "Invalid role."}), 400

    # --- Fetch organization ---
    org = mongo.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        return jsonify({"status": "error", "error": "Organization not found."}), 404

    # --- Process invitations ---
    invitations = org.get("invitations", [])
    updated = False

    for invite in invitations:
        if isinstance(invite, dict) and invite.get("email") == email:
            invite["role"] = role
            updated = True
            break

        # Legacy format: invite stored as just email string
        if isinstance(invite, str) and invite == email:
            invitations[invitations.index(invite)] = {"email": email, "role": role}
            updated = True
            break

    if not updated:
        # No existing invite → add a new one
        invitations.append({"email": email, "role": role})

    # --- Update organization ---
    mongo.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {"invitations": invitations}},
    )
    return jsonify({"status": "OK"}), 200


@admin_org_bp.route("/api/change_access_level/", methods=["POST"])
@admin_required
def change_access_level() -> Tuple[Response, int]:
    """
    Change a user's access level (role) within an organization.

    API Endpoint
    ------------
    POST /api/change_access_level/

    Request JSON
    ------------
    {
        "user_id": str,
            The ID of the user whose role is being updated.
        "organization_id": str,
            The MongoDB ObjectId of the organization.
        "role": str,
            The new role to assign. Must be one of: "member", "admin", "owner".
    }

    Returns
    -------
    (flask.Response, int)
        JSON response with status code:
        
        - 200 OK:
            {"status": "OK"}
        - 400 Bad Request:
            {"error": "Invalid role. Role must be one of these: 'member', 'admin', 'owner'"}
        - 404 / flash message:
            Flash message displayed if the user is not found in the organization.

    Notes
    -----
    - If the new role is "admin" or "owner" and the user's current global role
      is "user" or "member", their global role is elevated to "admin".
    - Silently ignores errors during user global role update, but organization
      update always proceeds.
    - Requires `@admin_required` decorator; only admins can change access levels.
    """

    # --- Parse input ---
    data: Dict[str, Any] = request.json or {}
    user_id: str | None = data.get("user_id")
    organization_id: str | None = data.get("organization_id")
    role: str | None = data.get("role")

    # --- Validate role ---
    if role not in ["member", "admin", "owner"]:
        return (
            jsonify({
                "error": "Invalid role. Role must be one of these: 'member', 'admin', 'owner'"
            }),
            400,
        )

    # --- Fetch organization ---
    org_doc = mongo.organizations.find_one({"_id": ObjectId(organization_id)})
    if not org_doc:
        flash_message("Organisaatiota ei löydy.", "error")
        return jsonify({"status": "error"}), 404

    organization = Organization.from_dict(org_doc)

    # --- Update member in organization ---
    if organization.is_member(None, user_id):
        organization.update_member(user_id, role)

        # --- Update global role if elevated ---
        if role in ["admin", "owner"]:
            try:
                from mielenosoitukset_fi.users.models import User

                user = User.from_OID(user_id)
                if user.role in ["user", "member"]:
                    user.role = "admin"
                    user.save()
                    
            except Exception:
                # Silently ignore errors; org update is more important
                pass
    else:
        flash_message("Ei käyttäjää.", "error")

    return jsonify({"status": "OK"}), 200
