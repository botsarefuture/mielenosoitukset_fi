from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user
from datetime import datetime

from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required
from .utils import mongo
from bson.objectid import ObjectId

audit_bp = Blueprint("board_audit", __name__, url_prefix="/board/audit")

# Mongo collection: board_audit_logs
# Schema:
# {
#   "_id": ObjectId,
#   "user_id": str,
#   "action": str,        # e.g., "approved", "revoked"
#   "granted_by": str,    # username of board member
#   "timestamp": datetime
# }

def log_board_action(user_id, action, granted_by):
    """Log an action to the board audit log."""
    mongo.board_audit_logs.insert_one({
        "user_id": str(user_id),
        "action": action,
        "granted_by": granted_by,
        "timestamp": datetime.utcnow()
    })


@audit_bp.route("/logs", methods=["GET"])
@login_required
@admin_required
@permission_required("VIEW_CLEARANCE_AUDIT")
def get_logs():
    """Return all board compliance audit logs."""
    logs_cursor = mongo.board_audit_logs.find().sort("timestamp", -1)
    logs = []
    for log in logs_cursor:
        user_doc = mongo.users.find_one({"_id": ObjectId(log["user_id"])})
        username = user_doc.get("username") if user_doc else "Unknown"
        logs.append({
            "user_id": log["user_id"],
            "username": username,
            "action": log["action"],
            "granted_by": log["granted_by"],
            "timestamp": log["timestamp"].isoformat()
        })
    return jsonify(logs)


@audit_bp.route("/ui")
@login_required
@admin_required
@permission_required("VIEW_CLEARANCE_AUDIT")
def audit_ui():
    """Render the audit log UI for the board."""
    return render_template("board/audit_logs.html")
