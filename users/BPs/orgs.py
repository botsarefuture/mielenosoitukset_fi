from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from utils.flashing import flash_message
from classes import Organization

mongo = DatabaseManager().get_instance().get_db()

user_orgs_bp = Blueprint("user_orgs", __name__,  url_prefix="/orgs")

@user_orgs_bp.route("/accept_invite", methods=["GET"])
def accept_invite():
    """ """
    if not current_user.is_authenticated:
        flash_message("Kirjaudu sisään liittyäksesi organisaatioon.", "info")
        return redirect(url_for("users.auth.login", next=request.url))
    
    organization_id = request.args.get("organization_id")
    if not organization_id:
        flash_message("Organisaation tunnus puuttuu.", "warning")
        return redirect(url_for("index"))

    organization = mongo.organizations.find_one({"_id": ObjectId(organization_id)})
    if not organization:
        flash_message("Organisaatiota ei löytynyt.", "warning")
        return redirect(url_for("index"))

    if "invitations" in organization and current_user.email in organization["invitations"]:
        organization["invitations"].remove(current_user.email)
        mongo.organizations.update_one(
            {"_id": ObjectId(organization_id)},
            {"$set": {"invitations": organization["invitations"]}},
        )
        
        org = Organization.from_dict(organization)
        org.add_member(current_user, role="member", permissions=[])
        flash_message(f"Liityit organisaatioon {organization.get('name')}.", "success")
        
    else:
        flash_message("Kutsua ei löytynyt.", "warning")
        return redirect(url_for("index"))

    return redirect(url_for("org", org_id=organization_id))