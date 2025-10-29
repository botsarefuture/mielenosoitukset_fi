from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user
from bson.objectid import ObjectId
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.classes import Organization

mongo = DatabaseManager().get_instance().get_db()

user_orgs_bp = Blueprint("user_orgs", __name__, url_prefix="/orgs")


def _get_invited_emails(org_inv):
    """
    Extract emails from an organization's invitations, handling both legacy and new formats.

    Parameters
    ----------
    org_inv : list
        List of invitations. Can be a list of strings (legacy) or a list of dicts (new format).

    Returns
    -------
    list[str]
        List of invited emails.
    """
    if not org_inv:
        return []

    emails = []
    for inv in org_inv:
        if isinstance(inv, str):
            emails.append(inv)
        elif isinstance(inv, dict) and "email" in inv:
            emails.append(inv["email"])
        # else ignore anything else (None, unexpected types)
    
    return emails

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

    invited_emails = _get_invited_emails(organization.get("invitations", []))

    if current_user.email in invited_emails:
        # Remove the user's email from invitations
        new_invitations = []
        for inv in organization.get("invitations", []):
            if isinstance(inv, str) and inv != current_user.email:
                new_invitations.append(inv)
            elif isinstance(inv, dict) and inv.get("email") != current_user.email:
                new_invitations.append(inv)

        mongo.organizations.update_one(
            {"_id": ObjectId(organization_id)},
            {"$set": {"invitations": new_invitations}},
        )

        org = Organization.from_dict(organization)
        org.add_member(current_user, role="member", permissions=[])
        flash_message(f"Liityit organisaatioon {organization.get('name')}.", "success")
    else:
        flash_message("Kutsua ei löytynyt.", "warning")
        return redirect(url_for("index"))

    return redirect(url_for("org", org_id=organization_id))

@user_orgs_bp.route("/accept_invite/<organization_id>", methods=["POST"])
def accept_invite_post(organization_id):
    """Accept an organization invite via POST using the organization_id URL parameter."""
    if not current_user.is_authenticated:
        flash_message("Kirjaudu sisään liittyäksesi organisaatioon.", "info")
        return redirect(url_for("users.auth.login", next=request.url))

    if not organization_id:
        flash_message("Organisaation tunnus puuttuu.", "warning")
        return redirect(url_for("index"))

    organization = mongo.organizations.find_one({"_id": ObjectId(organization_id)})
    if not organization:
        flash_message("Organisaatiota ei löytynyt.", "warning")
        return redirect(url_for("index"))

    invited_emails = _get_invited_emails(organization.get("invitations", []))

    if current_user.email in invited_emails:
        # Remove the user's email from invitations
        new_invitations = []
        for inv in organization.get("invitations", []):
            if isinstance(inv, str) and inv != current_user.email:
                new_invitations.append(inv)
            elif isinstance(inv, dict) and inv.get("email") != current_user.email:
                new_invitations.append(inv)

        mongo.organizations.update_one(
            {"_id": ObjectId(organization_id)},
            {"$set": {"invitations": new_invitations}},
        )

        org = Organization.from_dict(organization)
        org.add_member(current_user, role="member", permissions=[])
        flash_message(f"Liityit organisaatioon {organization.get('name')}.", "success")

    
        return redirect(request.referrer)
        # Render a success template or redirect
        return render_template(
            "orgs/accept_invite_success.html",
            organization=organization,
            user=current_user,
        )
    else:
        flash_message("Kutsua ei löytynyt.", "warning")
        return redirect(url_for("index"))

@user_orgs_bp.route("/decline_invite", methods=["POST"])
def decline_invite_post():
    """
    Decline an organization invitation. Removes the current user's email from the invitation list.
    """
    if not current_user.is_authenticated:
        flash_message("Kirjaudu sisään hylätäksesi kutsun.", "info")
        return redirect(url_for("users.auth.login", next=request.url))

    organization_id = request.args.get("organization_id")
    if not organization_id:
        flash_message("Organisaation tunnus puuttuu.", "warning")
        return redirect(url_for("index"))

    organization = mongo.organizations.find_one({"_id": ObjectId(organization_id)})
    if not organization:
        flash_message("Organisaatiota ei löytynyt.", "warning")
        return redirect(url_for("index"))

    # Remove the user's email from invitations
    invitations = organization.get("invitations", [])
    new_invitations = []
    for inv in invitations:
        if isinstance(inv, str) and inv != current_user.email:
            new_invitations.append(inv)
        elif isinstance(inv, dict) and inv.get("email") != current_user.email:
            new_invitations.append(inv)

    mongo.organizations.update_one(
        {"_id": ObjectId(organization_id)},
        {"$set": {"invitations": new_invitations}},
    )

    flash_message(f"Hylkäsit kutsun organisaatioon {organization.get('name')}.", "info")
    return redirect(url_for("index"))