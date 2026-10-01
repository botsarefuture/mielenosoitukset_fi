"""
Step-up ("sudo") authentication state.

Elevation is a lightweight server-side session flag with a hard timeout.
Expiring the elevated state never logs the user out — the normal authenticated
session stays untouched. The flag is bound to the user id so it cannot be
replayed across accounts.

Fresh step-up tokens provide single-use, action-bound authentication for
highly sensitive operations (e.g., user deletion). Unlike session elevation,
fresh tokens cannot be reused and must be obtained through a new authentication
ceremony for each action.
"""

import secrets
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional

from bson import ObjectId
from flask import current_app, jsonify, session
from flask_login import current_user

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.time_utils import utcnow

SUDO_SESSION_KEY = "sudo"
FRESH_STEP_UP_COLLECTION = "fresh_step_up_tokens"
FRESH_STEP_UP_TTL_SECONDS = 60


def _configured_timeout() -> float:
    from flask import current_app

    try:
        return float(current_app.config.get("SUDO_DEFAULT_TIMEOUT", 900))
    except (TypeError, ValueError):
        return 900.0


def grant_elevation(method: str) -> None:
    """Mark the current user as recently step-up authenticated."""
    session[SUDO_SESSION_KEY] = {
        "authenticated_at": time.time(),
        "method": method,
        "user_id": str(current_user._id),
    }
    session.modified = True


def clear_elevation() -> None:
    """Drop any step-up elevation for the current session."""
    if SUDO_SESSION_KEY in session:
        session.pop(SUDO_SESSION_KEY, None)
        session.modified = True


def elevation_method() -> Optional[str]:
    """Return the method used for the current elevation (stale or not)."""
    sudo = session.get(SUDO_SESSION_KEY)
    if not sudo or str(sudo.get("user_id", "")) != str(current_user._id):
        return None
    return sudo.get("method")


def has_elevation(timeout_seconds: Optional[float] = None) -> bool:
    """Return whether the current session is still elevated."""
    sudo = session.get(SUDO_SESSION_KEY)
    if not sudo:
        return False
    if str(sudo.get("user_id", "")) != str(current_user._id):
        clear_elevation()
        return False

    window = timeout_seconds if timeout_seconds is not None else _configured_timeout()
    age = time.time() - sudo.get("authenticated_at", 0)
    if age < 0 or age > window:
        clear_elevation()
        return False
    return True


def is_elevated(timeout_seconds: Optional[float] = None) -> bool:
    """Alias for callers that read better with a positive name."""
    return has_elevation(timeout_seconds=timeout_seconds)


def sudo_required(timeout_seconds: Optional[float] = None):
    """
    Guard a route behind recent step-up authentication.

    Returns ``403 {"error": "step_up_required"}`` when the session is not
    elevated (the frontend re-authenticates and retries the request) and
    ``401`` when no user is logged in.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return (
                    jsonify(
                        {
                            "error": "authentication_required",
                            "message": "Kirjaudu sisään ennen tätä toimintoa.",
                        }
                    ),
                    401,
                )
            if is_elevated(timeout_seconds=timeout_seconds):
                return func(*args, **kwargs)
            return (
                jsonify(
                    {
                        "error": "step_up_required",
                        "message": "Vahvista henkilöllisyytesi uudelleen ennen tätä toimintoa.",
                    }
                ),
                403,
            )
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Fresh step-up tokens (single-use, action-bound)
# ---------------------------------------------------------------------------


def _get_mongo():
    """Return the active database handle."""
    return DatabaseManager().get_instance().get_db()


def create_fresh_step_up_token(action: str, target_id: Optional[str] = None) -> str:
    """
    Create a single-use fresh step-up token for a specific action.

    The token is bound to the current user, the action, and optionally a target ID.
    It expires after FRESH_STEP_UP_TTL_SECONDS and can only be used once.

    Returns the token string.
    """
    if not current_user.is_authenticated:
        raise RuntimeError("Cannot create fresh step-up token for anonymous user")

    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)

    doc = {
        "token_hash": token_hash,
        "user_id": ObjectId(current_user._id),
        "action": action,
        "target_id": target_id,
        "created_at": utcnow(),
        "expires_at": utcnow() + timedelta(seconds=FRESH_STEP_UP_TTL_SECONDS),
        "used": False,
    }
    _get_mongo()[FRESH_STEP_UP_COLLECTION].insert_one(doc)

    # Also create a TTL index if not exists (idempotent)
    try:
        _get_mongo()[FRESH_STEP_UP_COLLECTION].create_index(
            "expires_at", expireAfterSeconds=0, name="fresh_step_up_ttl"
        )
    except Exception:
        pass

    return token


def _hash_token(token: str) -> str:
    """Hash a token for storage."""
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()


def consume_fresh_step_up_token(token: str, action: str, target_id: Optional[str] = None) -> bool:
    """
    Atomically consume a fresh step-up token.

    Returns True if the token was valid, unused, unexpired, and matched the
    action and target_id. Returns False otherwise.
    """
    if not current_user.is_authenticated:
        return False

    token_hash = _hash_token(token)

    query = {
        "token_hash": token_hash,
        "user_id": ObjectId(current_user._id),
        "action": action,
        "used": False,
        "expires_at": {"$gt": utcnow()},
    }
    if target_id is not None:
        query["target_id"] = target_id

    result = _get_mongo()[FRESH_STEP_UP_COLLECTION].find_one_and_update(
        query,
        {"$set": {"used": True, "used_at": utcnow()}},
    )
    return result is not None


def require_fresh_step_up(action: str, target_id_param: str = "user_id"):
    """
    Decorator that requires a valid fresh step-up token for the given action.

    The token must be provided in the request JSON body or form data under
    the key "fresh_step_up_token". The target_id is extracted from the
    request using target_id_param.

    Returns 403 with error "fresh_step_up_required" if the token is missing,
    invalid, or already used.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return (
                    jsonify(
                        {
                            "error": "authentication_required",
                            "message": "Kirjaudu sisään ennen tätä toimintoa.",
                        }
                    ),
                    401,
                )

            # Get token from JSON body or form data
            data = None
            if hasattr(func, "__wrapped__"):
                # Try to get from request context
                from flask import request

                if request.is_json:
                    data = request.get_json(silent=True) or {}
                else:
                    data = request.form.to_dict()
            else:
                from flask import request

                if request.is_json:
                    data = request.get_json(silent=True) or {}
                else:
                    data = request.form.to_dict()

            token = data.get("fresh_step_up_token") if data else None
            target_id = data.get(target_id_param) if data else None

            if not token:
                return (
                    jsonify(
                        {
                            "error": "fresh_step_up_required",
                            "message": "Tämä toiminto vaatii tuoreen vahvistuksen. Vahvista henkilöllisyytesi uudelleen.",
                        }
                    ),
                    403,
                )

            if not consume_fresh_step_up_token(token, action, target_id):
                return (
                    jsonify(
                        {
                            "error": "fresh_step_up_required",
                            "message": "Vahvistus on virheellinen, vanhentunut tai jo käytetty. Vahvista henkilöllisyytesi uudelleen.",
                        }
                    ),
                    403,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator