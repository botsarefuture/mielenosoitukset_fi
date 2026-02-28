from __future__ import annotations

from functools import wraps
from typing import Any, Dict, Optional

import requests
from flask import current_app, g, request

from mielenosoitukset_fi.api.exceptions import ApiException, Message
from mielenosoitukset_fi.utils.logger import logger


MOLTBOOK_VERIFY_URL = "https://moltbook.com/api/v1/agents/verify-identity"
MOLTBOOK_IDENTITY_HEADER = "X-Moltbook-Identity"

_ERROR_STATUS_MAP = {
    "identity_token_expired": 401,
    "invalid_token": 401,
    "missing_app_key": 401,
    "invalid_app_key": 401,
    "audience_required": 401,
    "audience_mismatch": 401,
    "agent_deactivated": 403,
    "agent_not_found": 404,
    "rate_limit_exceeded": 429,
}

_ERROR_MESSAGE_MAP = {
    "identity_token_expired": "Moltbook identity token expired.",
    "invalid_token": "Moltbook identity token is invalid.",
    "missing_app_key": "Moltbook app key is missing.",
    "invalid_app_key": "Moltbook app key is invalid.",
    "audience_required": "Moltbook identity token requires an audience.",
    "audience_mismatch": "Moltbook identity token audience mismatch.",
    "agent_deactivated": "Moltbook agent has been deactivated.",
    "agent_not_found": "Moltbook agent not found.",
    "rate_limit_exceeded": "Moltbook verification rate limit exceeded.",
}


def _raise_moltbook_error(error_code: str) -> None:
    status = _ERROR_STATUS_MAP.get(error_code, 401)
    message = _ERROR_MESSAGE_MAP.get(
        error_code, "Moltbook identity verification failed."
    )
    raise ApiException(Message(message, error_code), status)


def verify_moltbook_identity(token: str) -> Dict[str, Any]:
    app_key = current_app.config.get("MOLTBOOK_APP_KEY")
    if not app_key:
        logger.error("Moltbook app key missing; set MOLTBOOK_APP_KEY.")
        raise ApiException(
            Message("Moltbook app key is not configured.", "missing_app_key"), 500
        )

    try:
        response = requests.post(
            MOLTBOOK_VERIFY_URL,
            headers={"X-Moltbook-App-Key": app_key},
            json={"token": token},
            timeout=8,
        )
    except requests.RequestException:
        logger.exception("Failed to reach Moltbook verification endpoint.")
        raise ApiException(
            Message("Failed to verify Moltbook identity.", "moltbook_unreachable"), 502
        )

    try:
        payload = response.json()
    except ValueError:
        logger.error("Invalid Moltbook response: non-JSON body.")
        raise ApiException(
            Message("Invalid Moltbook verification response.", "moltbook_bad_response"),
            502,
        )

    if payload.get("valid") is True and payload.get("agent"):
        return payload["agent"]

    error_code = payload.get("error") or "invalid_token"
    _raise_moltbook_error(error_code)


def attach_moltbook_agent(require_token: bool = False) -> Optional[Dict[str, Any]]:
    if hasattr(g, "moltbook_agent"):
        if g.moltbook_agent is not None:
            request.moltbook_agent = g.moltbook_agent
            return g.moltbook_agent
        request.moltbook_agent = None
        if require_token:
            raise ApiException(
                Message("Missing Moltbook identity token.", "missing_identity_token"),
                401,
            )
        return None

    identity_token = request.headers.get(MOLTBOOK_IDENTITY_HEADER)
    if not identity_token:
        g.moltbook_agent = None
        request.moltbook_agent = None
        if require_token:
            raise ApiException(
                Message("Missing Moltbook identity token.", "missing_identity_token"),
                401,
            )
        return None

    agent = verify_moltbook_identity(identity_token)
    g.moltbook_agent = agent
    request.moltbook_agent = agent
    return agent


def require_moltbook_agent(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        attach_moltbook_agent(require_token=True)
        return fn(*args, **kwargs)

    return wrapper
