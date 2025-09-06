# mielenosoitukset_fi/campaign/routes.py
from flask import render_template, jsonify, request
from . import campaign_bp

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
