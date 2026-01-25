from datetime import datetime, timedelta, timezone
import secrets
import hashlib
from bson.objectid import ObjectId

from mielenosoitukset_fi.utils.database import get_database_manager

mongo = get_database_manager()

TOKENS_COLLECTION = mongo["api_tokens"]
TOKEN_USAGE_LOGS = mongo["api_usage"]

# Durations
SHORT_HOURS = 48  # short-lived user/app tokens
LONG_DAYS = 90    # long-lived tokens
SESSION_HOURS = 168  # session tokens (7 days)

# Supported scopes (reference)
SUPPORTED_SCOPES = {"read", "write", "admin", "submit_demonstrations"}


def _hash_token(token: str) -> str:
    """Deterministic hash for token storage and verification."""
    return hashlib.sha256(token.encode()).hexdigest()


def _expiry_for_type(token_type: str) -> datetime:
    now = datetime.now(timezone.utc)
    if token_type == "short":
        return now + timedelta(hours=SHORT_HOURS)
    if token_type == "long":
        return now + timedelta(days=LONG_DAYS)
    if token_type == "session":
        return now + timedelta(hours=SESSION_HOURS)
    raise ValueError("Invalid token_type")


def create_token(
    user_id=None,
    token_type="short",
    scopes=None,
    system=False,
    *,
    category="user",
    app_id=None,
    session_id=None,
):
    """
    Create a token with category support.

    Categories: user, app, system, session.
    token_type: short (48h), long (90d), session (7d). Long is typically created via exchange.
    """
    token = secrets.token_urlsafe(32)
    expires_at = _expiry_for_type(token_type)

    TOKENS_COLLECTION.insert_one({
        "user_id": ObjectId(user_id) if user_id else None,
        "app_id": ObjectId(app_id) if app_id else None,
        "session_id": session_id,
        "token": _hash_token(token),
        "type": token_type,
        "category": category,
        "scopes": scopes or ["read"],
        "rate_limit": None if system else "100/minute",
        "system": system,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc)
    })
    
    return token, expires_at


def check_token(token: str):
    """
    Verifies a token and returns its DB record if valid.
    Raises ApiException if token is missing, invalid, or expired.
    """
    from mielenosoitukset_fi.api.exceptions import ApiException, Message
    from flask import request

    if not token:
        raise ApiException(Message("Missing token", "token_missing"), 401)

    hashed = _hash_token(token)
    record = TOKENS_COLLECTION.find_one({"token": hashed})
    
    if not record:
        raise ApiException(Message("Invalid token", "token_invalid"), 401)

    if token_expired(record):
        raise ApiException(Message("Token has expired", "token_expired"), 401)

    return record


def token_renewal_needed(token_record):
    # Only long and session tokens can be renewed
    if token_record.get("type") not in {"long", "session"}:
        return False

    created_at = token_record['created_at']
    expires_at = token_record['expires_at']

    # Make datetimes timezone-aware if naive
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    lifetime = expires_at - created_at
    remaining = expires_at - datetime.now(timezone.utc)

    return remaining.total_seconds() < lifetime.total_seconds() / 3


def token_expired(token_record):
    expires_at = token_record.get("expires_at")
    if not expires_at:
        return False  # non-expiring token

    if isinstance(expires_at, str):
        # parse ISO string
        expires_at = datetime.fromisoformat(expires_at)
    
    # Make naive datetime UTC-aware
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    return now > expires_at
