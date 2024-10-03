from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from wrappers import (
    admin_required,
    permission_required,
)  # Consider adding permission handling here
from utils import is_valid_email

# Create a Blueprint for admin organization management
admin_org_bp = Blueprint("admin_org", __name__, url_prefix="/admin/organization")

# Initialize MongoDB
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()


# Organization control panel
@admin_org_bp.route("/")
@login_required
@admin_required  #
@permission_required(
    "LIST_ORGANIZATIONS"
)  # or @permissions_required(['EDIT_ORGANIZATION', 'MANAGE_ORGANIZATIONS'])
def organization_control():
    """Render the organization control panel with a list of organizations."""
    search_query = request.args.get("search", "")

    # Query organizations based on search input
    query = {}
    if search_query:
        query = {
            "$or": [
                {"name": {"$regex": search_query, "$options": "i"}},
                {"email": {"$regex": search_query, "$options": "i"}},
            ]
        }

    organizations = mongo.organizations.find(query)

    return render_template(
        "admin/organizations/dashboard.html",
        organizations=organizations,
        search_query=search_query,
    )


# Edit organization
@admin_org_bp.route("/edit/<org_id>", methods=["GET", "POST"])
@login_required
@admin_required  #
@permission_required(
    "EDIT_ORGANIZATION"
)  # or @permissions_required(['MANAGE_ORGANIZATIONS'])
def edit_organization(org_id):
    """Edit organization details."""
    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})

    if request.method == "POST":
        # Get form data
        name = request.form.get("name")
        description = request.form.get("description")
        email = request.form.get("email")
        website = request.form.get("website")
        verified = request.form.get("verified") == "on"  # Convert checkbox to boolean

        # Validate required fields
        if not name or not email:
            flash("Nimi ja sähköpostiosoite ovat pakollisia.")
            return redirect(url_for("admin_org.edit_organization", org_id=org_id))

        if not is_valid_email(email):
            flash("Virheellinen sähköpostiosoite.")
            return redirect(url_for("admin_org.edit_organization", org_id=org_id))

        mongo.organizations.update_one(
            {"_id": ObjectId(org_id)},
            {
                "$set": {
                    "name": name,
                    "description": description,
                    "email": email,
                    "website": website,
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
@admin_required  #
@permission_required(
    "CREATE_ORGANIZATION"
)  # or @permissions_required(['MANAGE_ORGANIZATIONS'])
def create_organization():
    """Create a new organization."""
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        email = request.form.get("email")
        website = request.form.get("website")

        if not name or not email:
            flash("Nimi ja sähköpostiosoite ovat pakollisia.")
            return redirect(url_for("admin_org.create_organization"))

        if not is_valid_email(email):
            flash("Virheellinen sähköpostiosoite.")
            return redirect(url_for("admin_org.create_organization"))

        mongo.organizations.insert_one(
            {
                "name": name,
                "description": description,
                "email": email,
                "website": website,
                "members": [],
            }
        )

        flash("Organisaatio luotu onnistuneesti.")
        return redirect(url_for("admin_org.organization_control"))

    return render_template("admin/organizations/form.html")


# Delete organization
@admin_org_bp.route("/delete/<org_id>", methods=["POST"])
@login_required
@admin_required  #
@permission_required(
    "DELETE_ORGANIZATION"
)  # or @permissions_required(['MANAGE_ORGANIZATIONS'])
def delete_organization(org_id):
    """Delete an organization."""
    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})

    if not organization:
        flash("Organisatiota ei löytynyt.")
        return redirect(url_for("admin_org.organization_control"))

    if "confirm_delete" in request.form:
        mongo.organizations.delete_one({"_id": ObjectId(org_id)})
        flash("Organisaatio poistettu onnistuneesti.")
    else:
        flash("Organisaation poistoa ei vahvistettu.")

    return redirect(url_for("admin_org.organization_control"))


# Confirmation before deleting an organization
@admin_org_bp.route("/confirm_delete/<org_id>", methods=["GET"])
@login_required
@admin_required  #
@permission_required(
    "DELETE_ORGANIZATION"
)  # or @permissions_required(['MANAGE_ORGANIZATIONS'])
def confirm_delete_organization(org_id):
    """Render a confirmation page before deleting an organization."""
    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})

    if not organization:
        flash("Organisaatiota ei löytynyt.")
        return redirect(url_for("admin_org.organization_control"))

    return render_template(
        "admin/organizations/confirm_delete.html", organization=organization
    )
