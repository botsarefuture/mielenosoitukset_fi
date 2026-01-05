import os
import threading
from datetime import datetime
from typing import Any

from bson.objectid import ObjectId
from pymongo.errors import PyMongoError
from flask import has_request_context, request
from flask_login import current_user

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.classes import Organization
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.demonstrations.audit import log_super_audit

db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()


def get_org_name(org_id: str) -> str:
    """
    Retrieve the name of the organization.

    Parameters
    ----------
    org_id : str
        The organization ID.

    Returns
    -------
    str
        The organization name if found; otherwise "Unknown Organization".
    """
    try:
        result = mongo.organizations.find_one({"_id": ObjectId(org_id)})
        if not result:
            logger.warning(f"Organization with ID {org_id} not found.")
            return "Unknown Organization"
        org = Organization.from_dict(result)
        return org.name
    except PyMongoError as e:
        logger.error(f"Error retrieving organization name: {e}")
        return "Unknown Organization"


def get_org_details(org_id: str) -> Organization:
    """
    Retrieve detailed information about an organization.

    Parameters
    ----------
    org_id : str
        The organization ID.

    Returns
    -------
    Organization
        An Organization object containing detailed information.

    Raises
    ------
    ValueError
        If the organization is not found or retrieval fails.
    """
    try:
        result = mongo.organizations.find_one({"_id": ObjectId(org_id)})
        if not result:
            logger.warning(f"Organization with ID {org_id} not found.")
            raise ValueError("Organization not found")
        return Organization.from_dict(result)
    except PyMongoError as e:
        logger.error(f"Error retrieving organization details: {e}")
        raise ValueError("Failed to retrieve organization details")


def log_admin_action(user, action: str, details: str):
    """
    Log an admin action to MongoDB.

    Parameters
    ----------
    user : User
        The user performing the action.
    action : str
        The action performed.
    details : str
        Additional details about the action.

    Returns
    -------
    None
    """
    try:
        mongo.admin_logs.insert_one(
            {
                "user_id": user.get_id(),
                "email": user.email,
                "action": action,
                "details": details,
                "timestamp": datetime.utcnow(),  # using UTC time
            }
        )
        logger.info(f"Admin action logged: {action} by user {user.email}")
    except PyMongoError as e:
        logger.error(f"Error logging admin action: {e}")


# TODO: Transfer organization-related functions to utils.organizations


def dictify_object(obj):
    """
    Convert an object to a dictionary.

    Parameters
    ----------
    obj : any
        The object to be converted.

    Returns
    -------
    dict or equivalent
        The dictionary representation of the object.
    """
    if isinstance(obj, dict):
        return {k: dictify_object(v) for k, v in obj.items()}
    elif hasattr(obj, "__dict__"):
        return {k: dictify_object(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, (list, tuple, set)):
        return type(obj)(dictify_object(v) for v in obj)
    return obj


def capture_actor_context() -> dict:
    if not has_request_context():
        return {
            "user_id": None,
            "username": "system",
            "email": None,
            "role": None,
            "global_admin": False,
            "global_permissions": [],
        }
    try:
        user_id = getattr(current_user, "id", None)
        membership_ids = []
        for membership in getattr(current_user, "memberships", []) or []:
            org_id = getattr(membership, "organization_id", None)
            if org_id:
                membership_ids.append(str(org_id))
        return {
            "user_id": str(user_id) if user_id else None,
            "username": getattr(current_user, "username", None),
            "email": getattr(current_user, "email", None),
            "role": getattr(current_user, "role", None),
            "global_admin": getattr(current_user, "global_admin", False),
            "global_permissions": list(getattr(current_user, "global_permissions", []) or []),
            "membership_org_ids": membership_ids,
        }
    except Exception:
        logger.debug("Failed to capture actor context", exc_info=True)
        return {
            "user_id": None,
            "username": "unknown",
            "email": None,
            "role": None,
            "global_admin": False,
            "global_permissions": [],
        }


def capture_request_context() -> dict | None:
    if not has_request_context():
        return None
    try:
        return {
            "path": request.path,
            "method": request.method,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "ip": request.remote_addr,
            "args": request.args.to_dict(flat=False),
            "form_keys": list(request.form.keys()),
            "json_keys": list((request.get_json(silent=True) or {}).keys()),
            "user_agent": getattr(request.user_agent, "string", str(request.user_agent)),
            "endpoint": request.endpoint,
            "blueprint": request.blueprint,
        }
    except Exception:
        logger.debug("Failed to capture request context", exc_info=True)
        return None


def capture_process_context() -> dict:
    return {
        "pid": os.getpid(),
        "thread": threading.current_thread().name,
        "module": __name__,
    }


def _prepare_log_payload(entry: Any, related_id=None) -> dict:
    payload: dict = {}
    if isinstance(entry, dict):
        payload.update(entry)
    elif entry is not None:
        payload["message"] = str(entry)

    if related_id is not None:
        payload.setdefault("related_id", str(related_id))

    actor = capture_actor_context()
    payload.setdefault("actor", actor)

    request_ctx = capture_request_context()
    if request_ctx:
        payload.setdefault("request", request_ctx)

    payload.setdefault("process", capture_process_context())
    payload.setdefault("timestamp", datetime.utcnow())
    return dictify_object(payload)


def log_admin_action_V2(aact: Any = None, related_id=None):
    """
    Log an admin action (version 2) to MongoDB.

    Parameters
    ----------
    aact : dict
        A dictionary containing the admin action details.

    Returns
    -------
    None
    """
    try:
        payload = _prepare_log_payload(aact, related_id)
        mongo.admin_logs.insert_one(payload)
        event_name = payload.get("event") or payload.get("action") or payload.get("message") or "action"
        entity_id = payload.get("entity_id") or payload.get("demo_id") or payload.get("related_id")
        entity_type = payload.get("entity_type") or "admin_log"
        log_super_audit(
            event_type=f"admin:{event_name}",
            payload=payload,
            actor=payload.get("actor"),
            entity={"type": entity_type, "id": entity_id},
            tags=["admin", "audit"],
        )
    except PyMongoError as e:
        logger.error(f"Error logging admin action: {e}")
    except Exception:
        logger.exception("Unexpected failure while logging admin action")


class AdminActParser:
    """
    Parse admin activity logs and handle request data.
    """

    def __init__(self):
        pass

    def log_request_info(self, request, user):
        """
        Log request and user information.

        Parameters
        ----------
        request : dict
            The HTTP request data.
        user : User
            The user object.

        Returns
        -------
        dict
            A dictionary with parsed request and user data.
        """
        try:
            import json

            request_data = json.loads(json.dumps({**request}, skipkeys=True, default=str))
            user_data = user.to_dict() if hasattr(user, "to_dict") else dictify_object(user)
            return {"request": request_data, "user": user_data}
        except Exception as e:
            logger.exception(f"Error parsing request info: {e}")
            return {}


_ADMIN_TEMPLATE_FOLDER = "admin_V2/" # if we want to go back to the previous ones, use "admin/"
