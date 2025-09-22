# mielenosoitukset_fi/campaign/routes.py
from flask import render_template, jsonify, request
from . import campaign_bp

from mielenosoitukset_fi.database_manager import DatabaseManager

# Initialize MongoDB and Flask-Login
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

# === PAGE ROUTE ===
@campaign_bp.route("/")
def index():
    """
    Serve the main campaign page.
    """
    return render_template("kampanja/index.html")


# === API ROUTES ===

# Example: get campaign partners
@campaign_bp.route("/api/partners", methods=["GET"])
def get_partners():
    """
    Return a list of campaign partners as JSON.
    """
    partners = [
        {"name": "Partner 1", "url": "https://partner1.fi"},
        {"name": "Partner 2", "url": "https://partner2.fi"},
    ]
    return jsonify({"success": True, "partners": partners})


# Example: add a new campaign partner (POST)
@campaign_bp.route("/api/partners", methods=["POST"])
def add_partner():
    """
    Add a new partner from JSON payload.
    Expects: {"name": "Partner Name", "url": "https://..."}
    """
    data = request.get_json()
    if not data or "name" not in data or "url" not in data:
        return jsonify({"success": False, "error": "Invalid payload"}), 400

    # Here you would normally save it to your DB
    new_partner = {"name": data["name"], "url": data["url"]}

    return jsonify({"success": True, "partner": new_partner}), 201


# Example: get campaign statistics
@campaign_bp.route("/api/stats", methods=["GET"])
def get_stats():
    """
    Return mock campaign stats (can be replaced with DB queries)
    """
    stats = {
        "total_visits": 1024,
        "signups": 256,
        "shares": 512,
    }
    return jsonify({"success": True, "stats": stats})

# === API route for volunteer signups ===
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
email_sender = EmailSender()

import secrets
from datetime import datetime, timedelta

@campaign_bp.route("/api/volunteers", methods=["POST"])
def add_volunteer():
    data = request.get_json()
    if not data or "name" not in data or "email" not in data:
        return jsonify({"success": False, "error": "Name and email are required"}), 400

    token = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(days=1)  # 1 day to confirm

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

# === API route for confirming volunteer email ===
@campaign_bp.route("/confirm/<token>", methods=["GET"])
def confirm_volunteer(token):
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
