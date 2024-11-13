from bson.objectid import ObjectId
from flask import Blueprint, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required
from utils.flashing import flash_message
from utils.validators import valid_email
from wrappers import admin_required, permission_required
from .utils import log_admin_action, mongo

# Create a Blueprint for admin organization management
admin_org_bp = Blueprint("admin_org", __name__, url_prefix="/admin/organization")


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
        [ObjectId(org.get("org_id")) for org in current_user.organizations]
        if not current_user.global_admin
        else None
    )

    search_query = request.args.get("search", "")
    query = construct_query(search_query, org_limiter)

    organizations = mongo.organizations.find(query)

    return render_template(
        "admin/organizations/dashboard.html",
        organizations=organizations,
        search_query=search_query,
    )


def construct_query(search_query, org_limiter):
    """Construct the query for organizations based on search input."""
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
    """Edit organization details."""
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
            return redirect(url_for("admin_org.organization_control"))

    return render_template("admin/organizations/form.html", organization=organization)


def update_organization(org_id):
    """Update organization details based on form input."""
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
    
    """
    if request.method == "POST":
        if insert_organization():
            flash_message("Organisaatio luotu onnistuneesti.") # Removed gettext as it is not needed here.
            return redirect(url_for("admin_org.organization_control"))

    return render_template("admin/organizations/form.html")


def insert_organization():
    """Insert a new organization into the database."""
    name = request.form.get("name")
    email = request.form.get("email")

    if not validate_organization_fields(name, email, None):
        return False

    description = request.form.get("description")
    website = request.form.get("website")
    social_media_links = get_social_media_links()

    mongo.organizations.insert_one(
        {
            "name": name,
            "description": description,
            "email": email,
            "website": website,
            "social_media_links": social_media_links,
            "members": [],
        }
    )
    return True


# Delete organization
@admin_org_bp.route("/delete/<org_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("DELETE_ORGANIZATION")
def delete_organization(org_id):
    """Delete an organization."""
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
    """Render a confirmation page before deleting an organization."""
    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})

    if not organization:
        flash_message("Organisaatiota ei löytynyt.", "error")

        return redirect(url_for("admin_org.organization_control"))

    return render_template(
        "admin/organizations/confirm_delete.html", organization=organization
    )
