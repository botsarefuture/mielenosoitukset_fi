import hashlib
import hmac
import json
from datetime import datetime

from bson.objectid import ObjectId
from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from config import Config
from mielenosoitukset_fi.utils.wrappers import permission_required

from .board_audit import log_board_action
from .utils import mongo

board_bp = Blueprint("board_compliance", __name__, url_prefix="/board")

BOARD_MEMBER_ROLE = "board_member"
BOARD_MANAGED_ROLES = {"god", "global_admin"}
BOARD_REQUEST_TYPES = {"assign_role", "revoke_god"}
DEFAULT_GOD_FALLBACK_ROLE = "admin"
BOARD_REQUEST_INTEGRITY_VERSION = "board-request-v1"


def _requests_collection():
    return mongo.board_clearance_requests


def _now():
    return datetime.utcnow()


def _board_request_signing_key() -> bytes:
    key = getattr(Config, "BOARD_APPROVAL_SIGNING_KEY", None) or Config.SECRET_KEY
    return str(key).encode("utf-8")


def _mongo_datetime_iso(value) -> str | None:
    if not value:
        return None
    normalized = value.replace(microsecond=(value.microsecond // 1000) * 1000)
    return normalized.isoformat()


def _integrity_approvals(doc: dict) -> list[dict]:
    approvals = []
    for vote in doc.get("approvals", []):
        approvals.append(
            {
                "board_member_id": vote.get("board_member_id"),
                "username": vote.get("username"),
                "decision": vote.get("decision"),
                "note": vote.get("note"),
                "decided_at": _mongo_datetime_iso(vote.get("decided_at")),
            }
        )
    return sorted(approvals, key=lambda vote: (vote.get("board_member_id") or "", vote.get("decided_at") or ""))


def _request_integrity_payload(doc: dict) -> dict:
    return {
        "version": BOARD_REQUEST_INTEGRITY_VERSION,
        "user_id": doc.get("user_id"),
        "username": doc.get("username"),
        "current_role": doc.get("current_role"),
        "requested_role": doc.get("requested_role"),
        "request_type": doc.get("request_type"),
        "fallback_role": doc.get("fallback_role"),
        "status": doc.get("status"),
        "requested_by": doc.get("requested_by"),
        "requested_by_user_id": doc.get("requested_by_user_id"),
        "reason": doc.get("reason"),
        "approval_document_url": doc.get("approval_document_url"),
        "approval_document_sha256": doc.get("approval_document_sha256"),
        "required_approver_ids": sorted(doc.get("required_approver_ids", [])),
        "approvals": _integrity_approvals(doc),
        "created_at": _mongo_datetime_iso(doc.get("created_at")),
        "resolved_at": _mongo_datetime_iso(doc.get("resolved_at")),
        "active_role_grant": bool(doc.get("active_role_grant", False)),
    }


def _request_integrity_signature(doc: dict) -> str:
    payload = json.dumps(
        _request_integrity_payload(doc),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hmac.new(
        _board_request_signing_key(),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _stamp_request_integrity(doc: dict) -> dict:
    doc["integrity_version"] = BOARD_REQUEST_INTEGRITY_VERSION
    doc["integrity_signature"] = _request_integrity_signature(doc)
    return doc


def _request_integrity_ok(doc: dict) -> bool:
    if not doc:
        return False
    if doc.get("integrity_version") != BOARD_REQUEST_INTEGRITY_VERSION:
        return False
    signature = doc.get("integrity_signature")
    if not signature:
        return False
    return hmac.compare_digest(signature, _request_integrity_signature(doc))


def _is_board_member(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return getattr(user, "role", None) == BOARD_MEMBER_ROLE or user.has_permission("MANAGE_CLEARANCE")


def _board_members():
    return list(
        mongo.users.find(
            {
                "role": BOARD_MEMBER_ROLE,
                "active": {"$ne": False},
                "confirmed": True,
            }
        )
    )


def _required_board_member_ids():
    return [str(doc["_id"]) for doc in _board_members()]


def _serialize_vote(vote: dict) -> dict:
    return {
        "board_member_id": vote.get("board_member_id"),
        "username": vote.get("username"),
        "decision": vote.get("decision"),
        "note": vote.get("note"),
        "decided_at": vote.get("decided_at").isoformat() if vote.get("decided_at") else None,
    }


def _serialize_request(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id")),
        "user_id": doc.get("user_id"),
        "username": doc.get("username"),
        "current_role": doc.get("current_role"),
        "requested_role": doc.get("requested_role"),
        "request_type": doc.get("request_type"),
        "fallback_role": doc.get("fallback_role"),
        "status": doc.get("status"),
        "requested_by": doc.get("requested_by"),
        "reason": doc.get("reason"),
        "approval_document_url": doc.get("approval_document_url"),
        "approval_document_sha256": doc.get("approval_document_sha256"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "resolved_at": doc.get("resolved_at").isoformat() if doc.get("resolved_at") else None,
        "approvals": [_serialize_vote(vote) for vote in doc.get("approvals", [])],
        "required_approver_ids": doc.get("required_approver_ids", []),
        "active_role_grant": bool(doc.get("active_role_grant", False)),
        "integrity_valid": _request_integrity_ok(doc),
    }


def _active_role_request(user_id: str, role: str):
    return _requests_collection().find_one(
        {
            "user_id": str(user_id),
            "requested_role": role,
            "request_type": "assign_role",
            "status": "approved",
            "active_role_grant": True,
        },
        sort=[("resolved_at", -1), ("_id", -1)],
    )


def has_board_clearance(user_id):
    """Return True when the user has an active approved god request."""
    request_doc = _active_role_request(str(user_id), "god")
    return bool(request_doc and _request_integrity_ok(request_doc))


def has_global_admin_clearance(user_id):
    """Return True when the user has an active approved global_admin request."""
    request_doc = _active_role_request(str(user_id), "global_admin")
    return bool(request_doc and _request_integrity_ok(request_doc))


def _apply_request_resolution(request_doc: dict):
    user_oid = ObjectId(request_doc["user_id"])
    user_doc = mongo.users.find_one({"_id": user_oid})
    if not user_doc:
        raise ValueError("Target user no longer exists.")

    if request_doc["request_type"] == "assign_role":
        new_role = request_doc["requested_role"]
        update = {"role": new_role, "global_admin": new_role == "global_admin"}
        if new_role == "global_admin":
            update["global_admin"] = True
        mongo.users.update_one({"_id": user_oid}, {"$set": update})

        if new_role == "god":
            _requests_collection().update_many(
                {
                    "user_id": request_doc["user_id"],
                    "requested_role": "god",
                    "request_type": "assign_role",
                    "_id": {"$ne": request_doc["_id"]},
                },
                {"$set": {"active_role_grant": False}},
            )
        if new_role == "global_admin":
            _requests_collection().update_many(
                {
                    "user_id": request_doc["user_id"],
                    "requested_role": "global_admin",
                    "request_type": "assign_role",
                    "_id": {"$ne": request_doc["_id"]},
                },
                {"$set": {"active_role_grant": False}},
            )

    elif request_doc["request_type"] == "revoke_god":
        fallback_role = request_doc.get("fallback_role") or DEFAULT_GOD_FALLBACK_ROLE
        mongo.users.update_one(
            {"_id": user_oid},
            {"$set": {"role": fallback_role, "global_admin": False}},
        )
        _requests_collection().update_many(
            {
                "user_id": request_doc["user_id"],
                "requested_role": "god",
                "request_type": "assign_role",
                "status": "approved",
                "active_role_grant": True,
            },
            {"$set": {"active_role_grant": False}},
        )
    else:
        raise ValueError(f"Unknown board request type: {request_doc['request_type']}")


def _resolve_request_if_ready(request_doc: dict) -> dict:
    required_approver_ids = set(request_doc.get("required_approver_ids", []))
    votes = request_doc.get("approvals", [])
    if not required_approver_ids:
        raise ValueError("No active board members are configured.")

    decisions = {vote["board_member_id"]: vote["decision"] for vote in votes}
    if any(decision == "reject" for decision in decisions.values()):
        update = {
            "status": "rejected",
            "resolved_at": _now(),
            "updated_at": _now(),
            "active_role_grant": False,
        }
        request_doc = _stamp_request_integrity({**request_doc, **update})
        _requests_collection().update_one(
            {"_id": request_doc["_id"]},
            {
                "$set": {
                    "status": request_doc["status"],
                    "resolved_at": request_doc["resolved_at"],
                    "updated_at": request_doc["updated_at"],
                    "active_role_grant": request_doc["active_role_grant"],
                    "integrity_version": request_doc["integrity_version"],
                    "integrity_signature": request_doc["integrity_signature"],
                }
            },
        )
        return request_doc

    approved_ids = {
        vote["board_member_id"]
        for vote in votes
        if vote.get("decision") == "approve"
    }
    if required_approver_ids.issubset(approved_ids):
        update = {
            "status": "approved",
            "resolved_at": _now(),
            "updated_at": _now(),
            "active_role_grant": request_doc["request_type"] == "assign_role",
        }
        request_doc = _stamp_request_integrity({**request_doc, **update})
        _requests_collection().update_one(
            {"_id": request_doc["_id"]},
            {
                "$set": {
                    "status": request_doc["status"],
                    "resolved_at": request_doc["resolved_at"],
                    "updated_at": request_doc["updated_at"],
                    "active_role_grant": request_doc["active_role_grant"],
                    "integrity_version": request_doc["integrity_version"],
                    "integrity_signature": request_doc["integrity_signature"],
                }
            },
        )
        _apply_request_resolution(request_doc)
        log_board_action(
            request_doc["user_id"],
            f"request:{request_doc['request_type']}:{request_doc['requested_role']}:approved",
            "board-system",
        )
    return request_doc


def _latest_request_for_user(user_id: str):
    return _requests_collection().find_one(
        {"user_id": str(user_id)},
        sort=[("created_at", -1), ("_id", -1)],
    )


@board_bp.route("/api/clearance/<user_id>", methods=["GET"])
@login_required
@permission_required("MANAGE_CLEARANCE")
def get_clearance(user_id):
    """Return current board-managed role state and latest request for a user."""
    try:
        user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        user_doc = None
    if not user_doc:
        return jsonify({"status": "ERROR", "message": "Käyttäjää ei löytynyt."}), 404

    latest = _latest_request_for_user(user_id)
    return jsonify(
        {
            "user_id": str(user_id),
            "role": user_doc.get("role"),
            "has_god_clearance": has_board_clearance(user_id),
            "has_global_admin_clearance": has_global_admin_clearance(user_id),
            "latest_request": _serialize_request(latest) if latest else None,
        }
    )


@board_bp.route("/api/clearance/<user_id>", methods=["POST"])
@login_required
@permission_required("MANAGE_CLEARANCE")
def create_request(user_id):
    """Create a board request to grant global_admin/god or revoke god."""
    data = request.get_json(silent=True) or {}

    try:
        user_oid = ObjectId(user_id)
    except Exception:
        return jsonify({"status": "ERROR", "message": "Virheellinen käyttäjän tunniste."}), 400

    user_doc = mongo.users.find_one({"_id": user_oid})
    if not user_doc:
        return jsonify({"status": "ERROR", "message": "Käyttäjää ei löytynyt."}), 404

    requested_role = (data.get("requested_role") or "").strip()
    request_type = (data.get("request_type") or "assign_role").strip()
    fallback_role = (data.get("fallback_role") or DEFAULT_GOD_FALLBACK_ROLE).strip()
    approval_document_url = (data.get("approval_document_url") or "").strip()
    approval_document_sha256 = (data.get("approval_document_sha256") or "").strip().lower()
    reason = (data.get("reason") or "").strip()

    if request_type not in BOARD_REQUEST_TYPES:
        return jsonify({"status": "ERROR", "message": "Virheellinen board request type."}), 400

    if request_type == "assign_role" and requested_role not in BOARD_MANAGED_ROLES:
        return jsonify({"status": "ERROR", "message": "Voit pyytää vain god- tai global_admin-roolia."}), 400

    if request_type == "revoke_god":
        requested_role = "god"
        if user_doc.get("role") != "god":
            return jsonify({"status": "ERROR", "message": "Vain god-roolin poisto tarvitsee tämän prosessin."}), 400
        if fallback_role in BOARD_MANAGED_ROLES:
            return jsonify({"status": "ERROR", "message": "God-roolin poiston kohderooli ei voi olla board-managed role."}), 400

    if not approval_document_url or not approval_document_sha256:
        return jsonify(
            {
                "status": "ERROR",
                "message": "Board request vaatii dokumentin URL:n ja SHA256-hashin.",
            }
        ), 400

    existing_pending = _requests_collection().find_one(
        {
            "user_id": str(user_id),
            "requested_role": requested_role,
            "request_type": request_type,
            "status": "pending",
        }
    )
    if existing_pending:
        return jsonify({"status": "ERROR", "message": "Tälle käyttäjälle on jo avoin board request."}), 409

    required_approver_ids = _required_board_member_ids()
    if not required_approver_ids:
        return jsonify({"status": "ERROR", "message": "Yhtään aktiivista board_member-käyttäjää ei ole määritelty."}), 400

    now = _now()
    request_doc = {
        "user_id": str(user_id),
        "username": user_doc.get("username"),
        "current_role": user_doc.get("role"),
        "requested_role": requested_role,
        "request_type": request_type,
        "fallback_role": fallback_role if request_type == "revoke_god" else None,
        "status": "pending",
        "requested_by": getattr(current_user, "username", "unknown"),
        "requested_by_user_id": getattr(current_user, "id", None),
        "reason": reason,
        "approval_document_url": approval_document_url,
        "approval_document_sha256": approval_document_sha256,
        "required_approver_ids": required_approver_ids,
        "approvals": [],
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
        "active_role_grant": False,
    }
    _stamp_request_integrity(request_doc)
    result = _requests_collection().insert_one(request_doc)
    request_doc["_id"] = result.inserted_id
    log_board_action(
        user_id,
        f"request:{request_type}:{requested_role}:created",
        getattr(current_user, "username", "unknown"),
    )
    return jsonify({"status": "OK", "request": _serialize_request(request_doc)})


@board_bp.route("/api/clearance/request/<request_id>/decision", methods=["POST"])
@login_required
@permission_required("MANAGE_CLEARANCE")
def decide_request(request_id):
    """Allow board members to approve or reject a request while logged in."""
    if not _is_board_member(current_user):
        return jsonify({"status": "ERROR", "message": "Vain board_member voi vahvistaa tai hylätä board requestin."}), 403

    data = request.get_json(silent=True) or {}
    decision = (data.get("decision") or "").strip().lower()
    note = (data.get("note") or "").strip()
    if decision not in {"approve", "reject"}:
        return jsonify({"status": "ERROR", "message": "Paatoksen tulee olla approve tai reject."}), 400

    try:
        request_oid = ObjectId(request_id)
    except Exception:
        return jsonify({"status": "ERROR", "message": "Virheellinen board request ID."}), 400

    request_doc = _requests_collection().find_one({"_id": request_oid})
    if not request_doc:
        return jsonify({"status": "ERROR", "message": "Board requestia ei löytynyt."}), 404
    if not _request_integrity_ok(request_doc):
        return jsonify({"status": "ERROR", "message": "Board requestin eheystarkistus epaonnistui. Ratkaise tilanne auditin kautta ennen jatkoa."}), 409
    if request_doc.get("status") != "pending":
        return jsonify({"status": "ERROR", "message": "Board request on jo ratkaistu."}), 409

    board_member_id = str(current_user.id)
    if board_member_id not in request_doc.get("required_approver_ids", []):
        return jsonify({"status": "ERROR", "message": "Et kuulu tämän requestin vaadittuihin board approvereihin."}), 403

    approvals = [vote for vote in request_doc.get("approvals", []) if vote.get("board_member_id") != board_member_id]
    approvals.append(
        {
            "board_member_id": board_member_id,
            "username": getattr(current_user, "username", "unknown"),
            "decision": decision,
            "note": note,
            "decided_at": _now(),
        }
    )
    request_doc = _stamp_request_integrity(
        {
            **request_doc,
            "approvals": approvals,
            "updated_at": _now(),
        }
    )
    _requests_collection().update_one(
        {"_id": request_oid},
        {
            "$set": {
                "approvals": request_doc["approvals"],
                "updated_at": request_doc["updated_at"],
                "integrity_version": request_doc["integrity_version"],
                "integrity_signature": request_doc["integrity_signature"],
            }
        },
    )
    request_doc = _resolve_request_if_ready(request_doc)
    log_board_action(
        request_doc["user_id"],
        f"request:{request_doc['request_type']}:{request_doc['requested_role']}:{decision}",
        getattr(current_user, "username", "unknown"),
    )
    return jsonify({"status": "OK", "request": _serialize_request(request_doc)})


@board_bp.route("/api/clearances", methods=["GET"])
@login_required
@permission_required("MANAGE_CLEARANCE")
def list_clearances():
    """List board requests with current user roles for the board UI."""
    requests_payload = [
        _serialize_request(doc)
        for doc in _requests_collection().find().sort("created_at", -1)
    ]
    users_payload = []
    for user_doc in mongo.users.find().sort("username", 1):
        users_payload.append(
            {
                "id": str(user_doc["_id"]),
                "username": user_doc.get("username"),
                "role": user_doc.get("role"),
                "is_board_member": user_doc.get("role") == BOARD_MEMBER_ROLE,
                "has_god_clearance": has_board_clearance(user_doc["_id"]),
                "has_global_admin_clearance": has_global_admin_clearance(user_doc["_id"]),
            }
        )
    return jsonify({"users": users_payload, "requests": requests_payload})


@board_bp.route("/ui")
@login_required
@permission_required("MANAGE_CLEARANCE")
def clearance_ui():
    """Render the board request UI."""
    users = []
    for user_doc in mongo.users.find().sort("username", 1):
        users.append(
            {
                "id": str(user_doc["_id"]),
                "username": user_doc.get("username"),
                "role": user_doc.get("role"),
                "is_board_member": user_doc.get("role") == BOARD_MEMBER_ROLE,
                "has_god_clearance": has_board_clearance(user_doc["_id"]),
                "has_global_admin_clearance": has_global_admin_clearance(user_doc["_id"]),
            }
        )
    requests = [
        _serialize_request(doc)
        for doc in _requests_collection().find().sort("created_at", -1)
    ]
    return render_template(
        "board/clearances.html",
        users=users,
        requests=requests,
        is_board_member=_is_board_member(current_user),
        board_member_count=len(_required_board_member_ids()),
    )
