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

from bson.objectid import ObjectId
from flask import Blueprint, abort, redirect, render_template, request, url_for, jsonify
from flask_babel import gettext as _
from flask_login import current_user, login_required
from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.validators import valid_email
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from .utils import log_admin_action, mongo, get_org_name as get_organization_name
from mielenosoitukset_fi.utils.classes import Organization, MemberShip


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

    print(org_email)

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

    if _ and _id:
        return {"message": "Organisaatio luotu onnistuneesti.", "id": str(_id)}

    return {"message": "Virhe organisaation luonnissa."}


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
    query = construct_query(search_query, org_limiter)

    organizations = mongo.organizations.find(query)

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}organizations/dashboard.html",
        organizations=organizations,
        search_query=search_query,
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

    mongo.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {
            "$set": {
                "name": name,
                "description": description,
                "email": email,
                "website": website,
                "social_media_links": social_media_links,
                "verified": request.form.get("verified") == "on",
            }
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
            return redirect(url_for("admin_org.organization_control"))

    return render_template(f"{_ADMIN_TEMPLATE_FOLDER}organizations/form.html")


def insert_organization(org_data=None):
    """Insert a new organization into the database."""
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

    result = mongo.organizations.insert_one(
        {
            "name": name,
            "description": description,
            "email": email,
            "website": website,
            "social_media_links": social_media_links,
            "members": [],
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
        return redirect(url_for("admin_org.organization_control"))

    if "confirm_delete" in request.form:
        mongo.organizations.delete_one({"_id": ObjectId(org_id)})
        flash_message(_("Organisaatio poistettu onnistuneesti."))
        log_admin_action(
            current_user, "Delete Organization", f"Deleted organization {org_id}"
        )

    else:
        flash_message("Organisaation poistoa ei vahvistettu.", "warning")

    return redirect(url_for("admin_org.organization_control"))


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

        return redirect(url_for("admin_org.organization_control"))

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
    print(invitee_email, organization_id)
    invite_to_organization(invitee_email, ObjectId(organization_id))
    return redirect(url_for("admin_org.organization_control"))


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
    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})
    organization = Organization.from_dict(organization)
    
    
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
        memberships=members
    )

@admin_org_bp.route("/api/change_access_level/", methods=["POST"])
@admin_required
def change_access_level():
    data = request.json

    user_id = data.get("user_id")
    organization_id = data.get("organization_id")
    role = data.get("role")
    
    if not role in ["member", "admin", "owner"]:
        return jsonify({"error": "Invalid role. Role must be one of these: \n'member', 'admin', 'owner'"}), 400
        
    
    
    organization = mongo.organizations.find_one({"_id": ObjectId(organization_id)})
    organization = Organization.from_dict(organization)
    
    if organization.is_member(None, user_id):
        organization.update_member(user_id, role)
    
    else:
        flash_message("Ei käyttäjää.", "error")
    

    
    return jsonify({"status": "OK"}), 200

@admin_org_bp.route("/api/delete_membership/", methods=["POST"])
@login_required
@admin_required
@permission_required("EDIT_ORGANIZATION")
def delete_membership():
    # TODO: #342 require admin or owner level access to the organization, or global level edit_organization access, or superuser status.
    
    data = request.get_json()
    membership_id = data.get("membership_id")

    if not membership_id:
        return jsonify({"error": "Membership ID puuttuu"}), 400

    result = mongo.memberships.delete_one({"_id": ObjectId(membership_id)})
    
    if result.deleted_count == 1:
        return jsonify({"message": "Käyttäjä poistettu organisaatiosta"}), 200
    else:
        return jsonify({"error": "Poisto epäonnistui"}), 500
