from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import current_user, login_required
from bson.objectid import ObjectId
from datetime import datetime

from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from mielenosoitukset_fi.utils.flashing import flash_message

from .utils import mongo
from .board_audit import log_board_action

board_bp = Blueprint("board_compliance", __name__, url_prefix="/board")

# In-memory storage for simplicity; can be a separate Mongo collection
BOARD_CLEARANCES = {}  # user_id -> {"approved": bool, "granted_by": str, "timestamp": datetime}


# ────────────── GET CLEARANCE STATUS ──────────────
@board_bp.route("/api/clearance/<user_id>", methods=["GET"])
@login_required
@admin_required
@permission_required("MANAGE_CLEARANCE")
def get_clearance(user_id):
    """
    Get the board clearance status for a user.
    """
    clearance = BOARD_CLEARANCES.get(user_id, {"approved": False})
    return jsonify(clearance)

# ────────────── SET CLEARANCE ──────────────
@board_bp.route("/api/clearance/<user_id>", methods=["POST"])
@login_required
@admin_required
@permission_required("MANAGE_CLEARANCE")
def set_clearance(user_id):
    """
    Grant or revoke board clearance for global_admin role.
    Expects JSON:
        { "approved": true/false }
    """
    data = request.get_json()
    approved = bool(data.get("approved", False))

    user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        return jsonify({"status": "ERROR", "message": "Käyttäjää ei löytynyt."}), 404

    user = User.from_db(user_doc)

    # Only allow board to approve users who aren't already global_admin
    #if user.role == "global_admin" and approved:
    #    return jsonify({"status": "ERROR", "message": "Käyttäjä on jo superkäyttäjä."}), 400

    BOARD_CLEARANCES[user_id] = {
        "approved": approved,
        "granted_by": current_user.username,
        "timestamp": datetime.utcnow().isoformat(),
    }

    action = "myönnetty" if approved else "peruttu"

    # 🔥 Log the action in the audit log
    log_board_action(user_id, action, current_user.username)

    return jsonify({"status": "OK", "message": f"Board clearance {action} käyttäjälle {user.username}."})


# ────────────── LIST ALL CLEARANCES ──────────────
@board_bp.route("/api/clearances", methods=["GET"])
@login_required
@admin_required
@permission_required("MANAGE_CLEARANCE")
def list_clearances():
    """
    List all users with board clearance info.
    """
    result = []
    for uid, info in BOARD_CLEARANCES.items():
        user_doc = mongo.users.find_one({"_id": ObjectId(uid)})
        if user_doc:
            result.append({
                "user_id": uid,
                "username": user_doc.get("username"),
                "approved": info["approved"],
                "granted_by": info["granted_by"],
                "timestamp": info["timestamp"],
            })
    return jsonify(result)


# ────────────── FRONTEND UTILITY ──────────────
def has_board_clearance(user_id):
    """Check if a user has board clearance."""
    clearance = BOARD_CLEARANCES.get(str(user_id))
    return clearance and clearance.get("approved", False)

@board_bp.route("/ui")
@login_required
@admin_required
@permission_required("MANAGE_CLEARANCE")
def clearance_ui():
    """
    Render the board clearance management UI.
    """
    # Fetch all users for the table
    users_cursor = mongo.users.find()
    users = []
    for user_doc in users_cursor:
        uid = str(user_doc["_id"])
        clearance = BOARD_CLEARANCES.get(uid, {"approved": False, "granted_by": None, "timestamp": None})
        users.append({
            "id": uid,
            "username": user_doc.get("username"),
            "role": user_doc.get("role"),
            "approved": clearance["approved"],
            "granted_by": clearance.get("granted_by"),
            "timestamp": clearance.get("timestamp"),
        })

    return render_template("board/clearances.html", users=users)
