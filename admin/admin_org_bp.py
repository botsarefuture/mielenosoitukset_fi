from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from flask_login import current_user
from wrappers import admin_required, permission_required
from utils import is_valid_email
from .utils import mongo

# Create a Blueprint for admin organization management
admin_org_bp = Blueprint("admin_org", __name__, url_prefix="/admin/organization")


# Organization control panel
@admin_org_bp.route("/")
@login_required
@admin_required
@permission_required("LIST_ORGANIZATIONS")
def organization_control():
    """Render the organization control panel with a list of organizations."""
    if not current_user.global_admin:
        org_limiter = [
            ObjectId(org.get("org_id")) for org in current_user.organizations
        ]
        print(org_limiter)
    else:
        org_limiter = None
    search_query = request.args.get("search", "")
    query = {}

    # Query organizations based on search input
    if search_query:
        query = {
            "$or": [
                {"name": {"$regex": search_query, "$options": "i"}},
                {"email": {"$regex": search_query, "$options": "i"}},
            ]
        }
    if org_limiter:
        query["_id"] = {"$in": org_limiter}

    organizations = mongo.organizations.find(query)

    return render_template(
        "admin/organizations/dashboard.html",
        organizations=organizations,
        search_query=search_query,
    )


# Edit organization
@admin_org_bp.route("/edit/<org_id>", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("EDIT_ORGANIZATION")
def edit_organization(org_id):
    """Edit organization details."""
    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})

    if request.method == "POST":
        # Get form data
        name = request.form.get("name")
        description = request.form.get("description")
        email = request.form.get("email")
        website = request.form.get("website")
        social_media_platforms = request.form.getlist(
            "social_media_platform[]"
        )  # Get the platforms
        social_media_urls = request.form.getlist("social_media_url[]")  # Get the URLs
        verified = request.form.get("verified") == "on"

        # Validate required fields
        if not name or not email:
            flash("Nimi ja sähköpostiosoite ovat pakollisia.", "error")
            return redirect(url_for("admin_org.edit_organization", org_id=org_id))

        if not is_valid_email(email):
            flash("Virheellinen sähköpostiosoite.", "error")
            return redirect(url_for("admin_org.edit_organization", org_id=org_id))

        # Prepare social media links
        social_media_links = {
            platform: url
            for platform, url in zip(social_media_platforms, social_media_urls)
            if platform and url
        }

        # Update organization in the database
        mongo.organizations.update_one(
            {"_id": ObjectId(org_id)},
            {
                "$set": {
                    "name": name,
                    "description": description,
                    "email": email,
                    "website": website,
                    "social_media_links": social_media_links,
                    "verified": verified,
                }
            },
        )

        flash("Organisaatio päivitetty onnistuneesti.")
        return redirect(url_for("admin_org.organization_control"))

    return render_template("admin/organizations/form.html", organization=organization)


# Create organization
@admin_org_bp.route("/create", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("CREATE_ORGANIZATION")
def create_organization():
    """Create a new organization."""
    if request.method == "POST":
        # Get form data
        name = request.form.get("name")
        description = request.form.get("description")
        email = request.form.get("email")
        website = request.form.get("website")
        social_media_platforms = request.form.getlist(
            "social_media_platform[]"
        )  # Get the platforms
        social_media_urls = request.form.getlist("social_media_url[]")  # Get the URLs

        # Validate required fields
        if not name or not email:
            flash("Nimi ja sähköpostiosoite ovat pakollisia.", "error")
            return redirect(url_for("admin_org.create_organization"))

        if not is_valid_email(email):
            flash("Virheellinen sähköpostiosoite.", "error")
            return redirect(url_for("admin_org.create_organization"))

        # Prepare social media links
        social_media_links = {
            platform: url
            for platform, url in zip(social_media_platforms, social_media_urls)
            if platform and url
        }

        # Insert new organization into the database
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

        flash("Organisaatio luotu onnistuneesti.")
        return redirect(url_for("admin_org.organization_control"))

    return render_template("admin/organizations/form.html")


# Delete organization
@admin_org_bp.route("/delete/<org_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("DELETE_ORGANIZATION")
def delete_organization(org_id):
    """Delete an organization."""
    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})

    if not organization:
        flash("Organisatiota ei löytynyt.", "error")
        return redirect(url_for("admin_org.organization_control"))

    if "confirm_delete" in request.form:
        mongo.organizations.delete_one({"_id": ObjectId(org_id)})
        flash("Organisaatio poistettu onnistuneesti.")
    else:
        flash("Organisaation poistoa ei vahvistettu.", "warning")

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
        flash("Organisaatiota ei löytynyt.", "error")
        return redirect(url_for("admin_org.organization_control"))

    return render_template(
        "admin/organizations/confirm_delete.html", organization=organization
    )
