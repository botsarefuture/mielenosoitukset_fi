from datetime import datetime, timedelta, timezone
import secrets
import hashlib
from bson.objectid import ObjectId

from mielenosoitukset_fi.utils.database import get_database_manager

mongo = get_database_manager()

TOKENS_COLLECTION = mongo["api_tokens"]
TOKEN_USAGE_LOGS = mongo["api_usage"]

def _hash_token(token: str) -> str:
    """Deterministic hash for token storage and verification."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_token(user_id=None, token_type="short", scopes=None, system=False):
    token = secrets.token_urlsafe(32)
    
    if token_type == "short":
        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    elif token_type == "long":
        expires_at = datetime.now(timezone.utc) + timedelta(days=90)
    else:
        raise ValueError("Invalid token_type")
    
    TOKENS_COLLECTION.insert_one({
        "user_id": ObjectId(user_id) if user_id else None,
        "token": _hash_token(token),
        "type": token_type,
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
    
    if not token:
        raise ApiException(Message("Missing token", "token_missing"), 401)
    
    hashed = _hash_token(token)
    record = TOKENS_COLLECTION.find_one({"token": hashed})
    
    if not record:
        raise ApiException(Message("Invalid token", "token_invalid"), 401)
    
    if token_expired(record):
        raise ApiException(Message("Token has expired", "token_expired"), 401)
    
    return record


from datetime import datetime, timezone

def token_renewal_needed(token_record):
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

from datetime import datetime, timezone

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
