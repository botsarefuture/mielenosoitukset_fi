# Standard library
import secrets
from datetime import datetime, timedelta

# Third-party
from flask import render_template, jsonify, request

# Local imports
from . import campaign_bp
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailSender import EmailSender

# Initialize email sender and database
email_sender = EmailSender()
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()


@campaign_bp.route("/")
def index():
    """Serve the main campaign page."""
    return render_template("kampanja/index.html")


@campaign_bp.route("/api/volunteers", methods=["POST"])
def add_volunteer():
    """Handle volunteer signups."""
    data = request.get_json()
    if not data or "name" not in data or "email" not in data:
        return jsonify({"success": False, "error": "Name and email are required"}), 400

    token = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(days=1)

    volunteer = {
        "name": data["name"],
        "email": data["email"],
        "phone": data.get("phone", ""),
        "city": data.get("city", ""),
        "notes": data.get("notes", ""),
        "confirmed": False,
        "confirmation_token": token,
        "confirmation_expires": expires_at,
    }

    mongo.volunteers.insert_one(volunteer)

    confirm_link = f"https://mielenosoitukset.fi/kampanja/confirm/{token}"

    email_sender.queue_email(
        template_name="kampanja/welcome.html",
        subject="Kiitos ilmoittautumisesta! Vahvista sähköpostisi",
        recipients=[volunteer["email"]],
        context={"name": volunteer["name"], "confirm_link": confirm_link},
    )

    return jsonify({"success": True}), 201


@campaign_bp.route("/confirm/<token>", methods=["GET"])
def confirm_volunteer(token):
    """Confirm volunteer email using token."""
    volunteer = mongo.volunteers.find_one({"confirmation_token": token})
    if not volunteer:
        return "Virheellinen tai vanhentunut vahvistuslinkki.", 400

    if volunteer["confirmation_expires"] < datetime.utcnow():
        return "Vahvistusaika on umpeutunut.", 400

    mongo.volunteers.update_one(
        {"_id": volunteer["_id"]},
        {"$set": {"confirmed": True}, "$unset": {"confirmation_token": "", "confirmation_expires": ""}}
    )

    return render_template("kampanja/confirm_success.html", name=volunteer["name"])
