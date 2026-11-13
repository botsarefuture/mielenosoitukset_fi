"""Signed, short-lived token that a sign-out form must carry.

Signing out used to be a plain GET link, so a browser prefetch, a crawler or a
stray hover could end a session. The sign-out route now needs a POST that
carries this token. It is stateless (nothing is stored in the session cookie),
bound to the signed-in account, and expires after the session lifetime, so
server-rendered pages and the React host can both mint it from the session.
"""

from __future__ import annotations

from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer

LOGOUT_TOKEN_SALT = "logout-form-v1"
MAX_TOKEN_AGE_SECONDS = 12 * 60 * 60


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=LOGOUT_TOKEN_SALT)


def make_logout_token(user_id) -> str:
    return _serializer().dumps(str(user_id))


def valid_logout_token(token, user_id) -> bool:
    if not isinstance(token, str) or not token or len(token) > 512:
        return False
    try:
        owner = _serializer().loads(token, max_age=MAX_TOKEN_AGE_SECONDS)
    except BadSignature:
        return False
    return owner == str(user_id)


def is_prefetch_request(headers) -> bool:
    """True for browser prefetch/prerender and any non-navigation fetch of a page."""
    purpose = (headers.get("Sec-Purpose", "") + " " + headers.get("Purpose", "")).lower()
    if "prefetch" in purpose or "prerender" in purpose:
        return True
    mode = headers.get("Sec-Fetch-Mode")
    return bool(mode) and mode.lower() != "navigate"
