"""
Step-up ("sudo") authentication state.

Elevation is a lightweight server-side session flag with a hard timeout.
Expiring the elevated state never logs the user out — the normal authenticated
session stays untouched. The flag is bound to the user id so it cannot be
replayed across accounts.
"""

import time
from functools import wraps
from typing import Optional

from flask import jsonify, session
from flask_login import current_user

SUDO_SESSION_KEY = "sudo"


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