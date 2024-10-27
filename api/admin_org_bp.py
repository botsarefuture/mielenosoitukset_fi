from flask import Blueprint, request, jsonify, abort
from flask_login import login_required
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from flask_login import current_user
from wrappers import admin_required, permission_required
from utils import is_valid_email
from .utils import mongo

# Create a Blueprint for admin organization management
admin_org_bp = Blueprint("admin_org", __name__, url_prefix="/api/admin/organizations")


# List organizations
@admin_org_bp.route("/", methods=["GET"])
@login_required
@admin_required
@permission_required("LIST_ORGANIZATIONS")
def list_organizations():
    """List organizations with optional search query."""
    org_limiter = None
    if not current_user.global_admin:
        org_limiter = [ObjectId(org.get("org_id")) for org in current_user.organizations]

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

    organizations = list(mongo.organizations.find(query))
    for org in organizations:
        org["_id"] = str(org["_id"])  # Convert ObjectId to string for JSON serialization

    return jsonify(organizations), 200


# Create organization
@admin_org_bp.route("/", methods=["POST"])
@login_required
@admin_required
@permission_required("CREATE_ORGANIZATION")
def create_organization():
    """Create a new organization."""
    data = request.json
    name = data.get("name")
    email = data.get("email")
    description = data.get("description")
    website = data.get("website")
    social_media_links = data.get("social_media_links", {})

    # Validate required fields
    if not name or not email:
        return jsonify({"error": "Nimi ja sähköpostiosoite ovat pakollisia."}), 400

    if not is_valid_email(email):
        return jsonify({"error": "Virheellinen sähköpostiosoite."}), 400

    # Insert new organization into the database
    new_org = {
        "name": name,
        "description": description,
        "email": email,
        "website": website,
        "social_media_links": social_media_links,
        "members": [],
    }
    mongo.organizations.insert_one(new_org)

    return jsonify({"message": "Organisaatio luotu onnistuneesti."}), 201


# Edit organization
@admin_org_bp.route("/<org_id>", methods=["PUT"])
@login_required
@admin_required
@permission_required("EDIT_ORGANIZATION")
def edit_organization(org_id):
    """Edit organization details."""
    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})

    if not organization:
        return jsonify({"error": "Organisaatiota ei löytynyt."}), 404

    data = request.json
    name = data.get("name")
    email = data.get("email")
    description = data.get("description")
    website = data.get("website")
    social_media_links = data.get("social_media_links", {})
    verified = data.get("verified", False)

    # Validate required fields
    if not name or not email:
        return jsonify({"error": "Nimi ja sähköpostiosoite ovat pakollisia."}), 400

    if not is_valid_email(email):
        return jsonify({"error": "Virheellinen sähköpostiosoite."}), 400

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

    return jsonify({"message": "Organisaatio päivitetty onnistuneesti."}), 200


# Delete organization
@admin_org_bp.route("/<org_id>", methods=["DELETE"])
@login_required
@admin_required
@permission_required("DELETE_ORGANIZATION")
def delete_organization(org_id):
    """Delete an organization."""
    organization = mongo.organizations.find_one({"_id": ObjectId(org_id)})

    if not organization:
        return jsonify({"error": "Organisatiota ei löytynyt."}), 404

    mongo.organizations.delete_one({"_id": ObjectId(org_id)})
    return jsonify({"message": "Organisaatio poistettu onnistuneesti."}), 204
