from flask import Blueprint, jsonify, redirect, url_for
from flask_login import login_required
from mielenosoitukset_fi.utils.time_utils import utcnow

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
    mongo.board_audit_logs.insert_one(
        {
            "user_id": str(user_id),
            "action": action,
            "granted_by": granted_by,
            "timestamp": utcnow(),
        }
    )


def audit_rows(limit=None):
    """Return board audit entries enriched with the affected username."""
    cursor = mongo.board_audit_logs.find().sort("timestamp", -1)
    if limit:
        cursor = cursor.limit(limit)
    logs = []
    for log in cursor:
        user_id = log.get("user_id")
        user_doc = (
            mongo.users.find_one({"_id": ObjectId(user_id)})
            if ObjectId.is_valid(user_id)
            else None
        )
        logs.append(
            {
                "user_id": user_id,
                "username": (
                    user_doc.get("username") if user_doc else "Tuntematon käyttäjä"
                ),
                "action": log.get("action"),
                "granted_by": log.get("granted_by"),
                "timestamp": log.get("timestamp"),
            }
        )
    return logs


@audit_bp.route("/logs", methods=["GET"])
@login_required
@admin_required
@permission_required("VIEW_CLEARANCE_AUDIT")
def get_logs():
    """Return all board compliance audit logs."""
    logs = audit_rows()
    return jsonify(
        [
            {
                **log,
                "timestamp": (
                    log["timestamp"].isoformat()
                    if hasattr(log.get("timestamp"), "isoformat")
                    else log.get("timestamp")
                ),
            }
            for log in logs
        ]
    )


@audit_bp.route("/ui")
@login_required
@admin_required
@permission_required("VIEW_CLEARANCE_AUDIT")
def audit_ui():
    """Redirect the legacy audit UI into the unified admin panel."""
    return redirect(url_for("admin_governance.audit_log"))
