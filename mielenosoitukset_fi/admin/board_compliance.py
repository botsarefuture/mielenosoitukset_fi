import hmac
import secrets
from datetime import timedelta

from flask import Blueprint, request, jsonify, redirect, session, url_for
from flask_login import current_user, login_required
from bson.objectid import ObjectId
from mielenosoitukset_fi.utils.time_utils import utcnow
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required, global_permission_required

from .utils import mongo
from .board_audit import log_board_action
from mielenosoitukset_fi.utils.system_teams import board_ids, clearance_approved, clearance_record_approved
from mielenosoitukset_fi.utils.team_governance import cast_vote, cast_joint_override, request_state, GovernanceConflict
from mielenosoitukset_fi.utils.god_appointments import appointment_roster, required_voters, can_vote, cast_appointment_vote

board_bp = Blueprint("board_compliance", __name__, url_prefix="/board")
GOVERNANCE_CSRF_SESSION_KEY = "governance_csrf_token"


def governance_csrf_token():
    token = session.get(GOVERNANCE_CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[GOVERNANCE_CSRF_SESSION_KEY] = token
    return token


def _valid_governance_csrf_token():
    expected = session.get(GOVERNANCE_CSRF_SESSION_KEY, "")
    provided = request.headers.get("X-CSRF-Token", "")
    return bool(expected and provided and hmac.compare_digest(expected, provided))


def _serialize_clearance(clearance, iso_timestamp=True):
    if not clearance:
        return {"approved": False}
    timestamp = clearance.get("timestamp")
    return {
        "approved": clearance_record_approved(clearance),
        "approval_count": len(clearance.get("approvals") or {}),
        "approvers": [value.get("username", "") for value in (clearance.get("approvals") or {}).values()],
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
    board = board_ids(mongo)
    def visible_request(record, kind):
        state = dict(request_state(record, kind))
        state['override_votes'] = {key: value for key, value in (state.get('override_votes') or {}).items()
                                   if value.get('at') and value['at'] > utcnow() - timedelta(minutes=10)}
        return state
    for user_doc in mongo.users.find().sort([("username", 1), ("_id", 1)]):
        user_id = str(user_doc["_id"])
        clearance = _serialize_clearance(
            clearances.get(user_id),
            iso_timestamp=False,
        )
        god_request = request_state(clearances.get(user_id), "god")
        god_roster = appointment_roster(mongo, user_id) if user_doc.get("god_candidate") else {}
        god_votes = (god_request.get("votes") or {}) if god_request.get("roster") == god_roster else {}
        rows.append(
            {
                "id": user_id,
                "username": user_doc.get("username"),
                "role": user_doc.get("role"),
                **clearance,
                "approval_count": clearance.get("approval_count",0),
                "my_vote": str(current_user.id) in ((clearances.get(user_id) or {}).get("approvals") or {}),
                "board_member": user_id in board,
                "board_request": visible_request(clearances.get(user_id),"board"),
                "national_request": visible_request(clearances.get(user_id),"national"),
                "god_candidate": user_doc.get("god_candidate") is True,
                "god_approval_count": len(god_votes),
                "god_required": len(required_voters(god_roster)),
                "my_god_vote": str(current_user.id) in god_votes,
                "can_god_vote": can_vote(mongo, current_user, user_id) if user_doc.get("god_candidate") else False,
            }
        )
    return rows


# ────────────── GET CLEARANCE STATUS ──────────────
@board_bp.route("/api/clearance/<user_id>", methods=["GET"])
@login_required
@admin_required
@permission_required("MANAGE_CLEARANCE")
@global_permission_required("MANAGE_CLEARANCE")
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
@global_permission_required("MANAGE_CLEARANCE")
def set_clearance(user_id):
    """
    Grant or revoke board clearance for global_admin role.
    Expects JSON:
        { "approved": true/false }
    """
    if not _valid_governance_csrf_token():
        return jsonify({"status": "ERROR", "message": "Istunnon turvatarkistus epäonnistui."}), 403

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify(status="ERROR", message="Virheellinen pyyntö."), 400
    approved = data.get("approved", False)

    if not ObjectId.is_valid(user_id):
        return jsonify({"status": "ERROR", "message": "Virheellinen käyttäjätunniste."}), 400

    user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        return jsonify({"status": "ERROR", "message": "Käyttäjää ei löytynyt."}), 404

    try:
        kind = data.get("kind","national")
        if kind == "god":
            if data.get("override"):
                raise PermissionError("Tavallinen yhteinen ohitus ei korvaa god-tilin kaikkia hyväksyntöjä.")
            result = cast_appointment_vote(mongo, user_id, current_user, approved)
        else:
            result = cast_joint_override(mongo,user_id,current_user,kind) if data.get("override") is True else cast_vote(mongo,user_id,current_user.id,kind,approved)
    except PermissionError as exc:
        return jsonify(status="ERROR",message=str(exc)),403
    except GovernanceConflict as exc:
        return jsonify(status="ERROR",message=str(exc)),409
    except ValueError as exc:
        return jsonify(status="ERROR",message=str(exc)),400
    count = len(result.get("votes") or {})
    return jsonify(status="OK",approved=result["approved"],approval_count=count,required=result["required"],
                   message="Hyväksyntä valmis." if result["approved"] else "Hyväksyntä kirjattu. Muut hyväksynnät tarvitaan vielä.")


# ────────────── LIST ALL CLEARANCES ──────────────
@board_bp.route("/api/clearances", methods=["GET"])
@login_required
@admin_required
@permission_required("MANAGE_CLEARANCE")
@global_permission_required("MANAGE_CLEARANCE")
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
    return clearance_approved(mongo,user_id)


@board_bp.route("/ui")
@login_required
@admin_required
@permission_required("MANAGE_CLEARANCE")
@global_permission_required("MANAGE_CLEARANCE")
def clearance_ui():
    """Redirect the legacy board UI into the unified admin panel."""
    return redirect(url_for("admin_governance.clearances"))
