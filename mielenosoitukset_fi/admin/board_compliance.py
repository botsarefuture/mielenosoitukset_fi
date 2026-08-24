from flask import Blueprint, request, jsonify, redirect, url_for
from flask_login import current_user, login_required
from bson.objectid import ObjectId
from mielenosoitukset_fi.utils.time_utils import utcnow
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required

from .utils import mongo
from .board_audit import log_board_action

board_bp = Blueprint("board_compliance", __name__, url_prefix="/board")


def _serialize_clearance(clearance, iso_timestamp=True):
    if not clearance:
        return {"approved": False}
    timestamp = clearance.get("timestamp")
    return {
        "approved": bool(clearance.get("approved")),
        "granted_by": clearance.get("granted_by"),
        "timestamp": (
            timestamp.isoformat()
            if iso_timestamp and hasattr(timestamp, "isoformat")
            else timestamp
        ),
    }


def clearance_rows():
    """Return all users joined with their persistent board-clearance state."""
    clearances = {
        doc["user_id"]: doc
        for doc in mongo.board_clearances.find({}, {"_id": 0})
        if doc.get("user_id")
    }
    rows = []
    for user_doc in mongo.users.find().sort("username", 1):
        user_id = str(user_doc["_id"])
        clearance = _serialize_clearance(
            clearances.get(user_id),
            iso_timestamp=False,
        )
        rows.append(
            {
                "id": user_id,
                "username": user_doc.get("username"),
                "role": user_doc.get("role"),
                **clearance,
            }
        )
    return rows


# ────────────── GET CLEARANCE STATUS ──────────────
@board_bp.route("/api/clearance/<user_id>", methods=["GET"])
@login_required
@admin_required
@permission_required("MANAGE_CLEARANCE")
def get_clearance(user_id):
    """
    Get the board clearance status for a user.
    """
    clearance = mongo.board_clearances.find_one({"user_id": user_id})
    return jsonify(_serialize_clearance(clearance))

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
    data = request.get_json(silent=True) or {}
    approved = bool(data.get("approved", False))

    if not ObjectId.is_valid(user_id):
        return jsonify({"status": "ERROR", "message": "Virheellinen käyttäjätunniste."}), 400

    user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        return jsonify({"status": "ERROR", "message": "Käyttäjää ei löytynyt."}), 404

    timestamp = utcnow()
    mongo.board_clearances.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "approved": approved,
                "granted_by": current_user.username,
                "granted_by_id": str(current_user.id),
                "timestamp": timestamp,
            },
            "$setOnInsert": {"created_at": timestamp},
        },
        upsert=True,
    )

    action = "myönnetty" if approved else "peruttu"

    log_board_action(user_id, action, current_user.username)

    return jsonify(
        {
            "status": "OK",
            "message": (
                f"Hallinnollinen hyväksyntä {action} käyttäjälle "
                f"{user_doc.get('username')}."
            ),
        }
    )


# ────────────── LIST ALL CLEARANCES ──────────────
@board_bp.route("/api/clearances", methods=["GET"])
@login_required
@admin_required
@permission_required("MANAGE_CLEARANCE")
def list_clearances():
    """
    List all users with board clearance info.
    """
    return jsonify(
        [
            {
                **row,
                "timestamp": (
                    row["timestamp"].isoformat()
                    if hasattr(row.get("timestamp"), "isoformat")
                    else row.get("timestamp")
                ),
            }
            for row in clearance_rows()
        ]
    )


# ────────────── FRONTEND UTILITY ──────────────
def has_board_clearance(user_id):
    """Check if a user has board clearance."""
    clearance = mongo.board_clearances.find_one(
        {"user_id": str(user_id)},
        {"approved": 1},
    )
    return bool(clearance and clearance.get("approved"))


@board_bp.route("/ui")
@login_required
@admin_required
@permission_required("MANAGE_CLEARANCE")
def clearance_ui():
    """Redirect the legacy board UI into the unified admin panel."""
    return redirect(url_for("admin_governance.clearances"))
