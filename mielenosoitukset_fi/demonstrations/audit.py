from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional

from flask import has_app_context, has_request_context, request
from flask_login import current_user

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.logger import logger

mongo = DatabaseManager().get_instance().get_db()


def _resolve_actor(actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if actor:
        return actor
    if has_app_context():
        try:
            user_id = getattr(current_user, "id", None)
            return {
                "user_id": str(user_id) if user_id else None,
                "username": getattr(current_user, "username", None),
                "email": getattr(current_user, "email", None),
            }
        except Exception:  # pragma: no cover - defensive
            logger.debug("Failed to resolve current_user for audit logging.", exc_info=True)
    return {
        "user_id": None,
        "username": "system",
        "email": None,
    }


def _summarize_changes(old_data: Optional[Dict[str, Any]], new_data: Optional[Dict[str, Any]]):
    if not isinstance(old_data, dict) or not isinstance(new_data, dict):
        return []
    changed = []
    keys = set(old_data.keys()) | set(new_data.keys())
    for key in keys:
        if old_data.get(key) != new_data.get(key):
            changed.append(key)
    return changed


def save_demo_history(demo_id, old_data, new_data, case_id=None, actor: Optional[Dict[str, Any]] = None):
    actor_data = _resolve_actor(actor)
    try:
        result = mongo.demo_edit_history.insert_one({
            "demo_id": str(demo_id),
            "edited_by": actor_data.get("user_id") or "unknown",
            "edited_at": datetime.utcnow(),
            "old_demo": deepcopy(old_data),
            "new_demo": deepcopy(new_data),
            "diff": None,  # placeholder for future rollups
            "rollbacked_from": None,
            "case_id": case_id or None,
            "actor": actor_data,
        })
        return result.inserted_id
    except Exception:  # pragma: no cover - persistence safeguard
        logger.exception("Failed to write demo_edit_history for %s", demo_id)
        return None


def log_demo_audit_entry(
    demo_id,
    action,
    message=None,
    details: Optional[Dict[str, Any]] = None,
    actor: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
):
    actor_data = _resolve_actor(actor)
    ip = ip_address
    if ip is None and has_request_context():
        try:
            ip = request.remote_addr
        except RuntimeError:
            ip = None

    entry = {
        "demo_id": str(demo_id),
        "action": action,
        "message": message or action,
        "details": details or {},
        "timestamp": datetime.utcnow(),
        "user_id": actor_data.get("user_id"),
        "username": actor_data.get("username"),
        "email": actor_data.get("email"),
        "ip_address": ip,
        "actor": actor_data,
    }
    try:
        mongo.demo_audit_logs.insert_one(entry)
    except Exception:  # pragma: no cover - persistence safeguard
        logger.exception("Failed to write demo audit log entry for %s", demo_id)


def record_demo_change(
    demo_id,
    old_data,
    new_data,
    action,
    message=None,
    case_id=None,
    extra_details: Optional[Dict[str, Any]] = None,
    actor: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
):
    hist_id = save_demo_history(demo_id, old_data, new_data, case_id=case_id, actor=actor)
    details = {
        "history_id": str(hist_id) if hist_id else None,
        "changed_fields": _summarize_changes(old_data or {}, new_data or {}),
    }
    if extra_details:
        details.update(extra_details)

    log_demo_audit_entry(
        demo_id,
        action,
        message=message,
        details=details,
        actor=actor,
        ip_address=ip_address,
    )
    return hist_id
