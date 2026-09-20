"""
WebAuthn (passkeys) helpers.

This module owns the ``user_passkeys`` and ``passkey_challenges`` collections
and wraps ``py-webauthn`` so blueprints only deal with JSON in/out.

Design rules (mirroring the requirements behind passkey support):

* Credentials are stored per-user with a globally unique ``credential_id``.
* Challenges are stored server-side, bound to the requesting browser session
  (and to a user when the flow is authenticated), are single-use and expire
  after a short window.
* Login: a passkey that belongs to *any* user can be used; the credential is
  resolved back to its owner server-side.
* Registration and step-up always bind the challenge to the logged-in user.
"""

import datetime
import logging
import secrets
from typing import Optional

from bson import ObjectId
from flask import current_app, session

_logger = logging.getLogger(__name__)
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.options_to_json_dict import options_to_json_dict
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.time_utils import utcnow

PASSKEY_COLLECTION = "user_passkeys"
CHALLENGE_COLLECTION = "passkey_challenges"

# Challenges must be consumed within a short window; unused ones expire.
CHALLENGE_TTL_SECONDS = 300
# The pubic-key credential request should stay valid as long as the challenge.
AUTHENTICATOR_TIMEOUT_MS = 300000

# Purpose values stored with challenges.
PURPOSE_REGISTER = "register"
PURPOSE_LOGIN = "login"
PURPOSE_STEP_UP = "step_up"

# Attribute used on the session to bind challenges to the browser session.
SESSION_CHALLENGE_TOKEN = "passkey_challenge_session"


def _get_mongo():
    """Return the active database handle."""
    return DatabaseManager().get_instance().get_db()


def _rp_id() -> str:
    return current_app.config["WEBAUTHN_RP_ID"]


def _rp_name() -> str:
    return current_app.config.get("WEBAUTHN_RP_NAME", "Mielenosoitukset.fi")


def _allowed_origins():
    return current_app.config["WEBAUTHN_ALLOWED_ORIGINS"]


def _session_token() -> str:
    """Return a stable per-browser token used to bind challenges to sessions."""
    token = session.get(SESSION_CHALLENGE_TOKEN)
    if not token:
        token = secrets.token_urlsafe(24)
        session[SESSION_CHALLENGE_TOKEN] = token
        session.modified = True
    return token


def _create_challenge(
    user_id: Optional[ObjectId] = None,
    purpose: str = PURPOSE_REGISTER,
) -> bytes:
    """Create + store a single-use challenge, returning raw bytes for signing."""
    challenge = secrets.token_bytes(32)
    _get_mongo()[CHALLENGE_COLLECTION].insert_one(
        {
            "challenge": bytes_to_base64url(challenge),
            "user_id": ObjectId(user_id) if user_id else None,
            "purpose": purpose,
            "session_token": _session_token(),
            "created_at": utcnow(),
            "expires_at": utcnow() + datetime.timedelta(seconds=CHALLENGE_TTL_SECONDS),
            "used": False,
        }
    )
    return challenge


def pending_challenge_b64(
    purpose: str,
    user_id: Optional[ObjectId] = None,
) -> Optional[str]:
    """
    Return the most recent unused, unexpired challenge for this user + session.

    The challenge is never trusted from the client: it is looked up server-side
    so the expected value always matches what the RP actually issued.
    """
    query = {
        "purpose": purpose,
        "used": False,
        "expires_at": {"$gt": utcnow()},
        "session_token": _session_token(),
    }
    if user_id is not None:
        query["user_id"] = ObjectId(user_id)
    else:
        query["user_id"] = None

    doc = _get_mongo()[CHALLENGE_COLLECTION].find_one(
        query, sort=[("created_at", -1)]
    )
    return doc["challenge"] if doc else None


def consume_challenge(
    challenge_b64: str,
    purpose: str,
    user_id: Optional[ObjectId] = None,
) -> bool:
    """
    Atomically mark a challenge as used.

    Returns False if the challenge is missing, belongs to another user/session,
    was already consumed, or has expired.
    """
    query = {
        "challenge": challenge_b64,
        "purpose": purpose,
        "used": False,
        "expires_at": {"$gt": utcnow()},
        "session_token": _session_token(),
    }
    if user_id is not None:
        query["user_id"] = ObjectId(user_id)
    else:
        query["user_id"] = None

    result = _get_mongo()[CHALLENGE_COLLECTION].find_one_and_update(
        query,
        {"$set": {"used": True, "used_at": utcnow()}},
    )
    return result is not None


def _user_handle(user_id) -> bytes:
    """Stable byte identifier for a user (used as the WebAuthn user handle)."""
    return ObjectId(user_id).binary


def _descriptors_for(user_id) -> list:
    """PublicKeyCredentialDescriptors for every passkey a user owns."""
    docs = _get_mongo()[PASSKEY_COLLECTION].find(
        {"user_id": ObjectId(user_id)}
    )
    return [
        PublicKeyCredentialDescriptor(
            id=base64url_to_bytes(doc["credential_id"]),
            type=PublicKeyCredentialType.PUBLIC_KEY,
        )
        for doc in docs
    ]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def registration_options(user, exclude_credentials: bool = True) -> dict:
    """Build WebAuthn registration options for a logged-in user."""
    opts = generate_registration_options(
        rp_id=_rp_id(),
        rp_name=_rp_name(),
        user_id=_user_handle(user._id),
        user_name=user.username,
        user_display_name=user.displayname or user.username,
        challenge=_create_challenge(user_id=user._id, purpose=PURPOSE_REGISTER),
        timeout=AUTHENTICATOR_TIMEOUT_MS,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=_descriptors_for(user._id) if exclude_credentials else [],
    )
    return options_to_json_dict(opts)


def verify_registration(
    credential,
    user_id: ObjectId,
):
    """
    Verify a registration response against the stored server-side challenge.

    Returns ``(verified_or_None, error_message)``.
    """
    challenge_b64 = pending_challenge_b64(PURPOSE_REGISTER, user_id)
    if not challenge_b64 or not consume_challenge(challenge_b64, PURPOSE_REGISTER, user_id):
        return None, "Challenge puuttuu, on jo käytetty tai se on vanhentunut."

    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_rp_id=_rp_id(),
            expected_origin=_allowed_origins(),
        )
    except Exception as exc:
        _logger.debug("Registration verification failed: %s", exc)
        return None, "Virheellinen rekisteröintivastaus."

    credential_id = bytes_to_base64url(verified.credential_id)
    existing = _get_mongo()[PASSKEY_COLLECTION].find_one({"credential_id": credential_id})
    if existing:
        return None, "Tämä passkey on jo rekisteröity."

    return verified, None


def store_credential(
    user_id,
    verified,
    name: str = "Authenticator",
    transports: Optional[list] = None,
):
    """Persist a verified public key credential for the user."""
    _get_mongo()[PASSKEY_COLLECTION].insert_one(
        {
            "user_id": ObjectId(user_id),
            "credential_id": bytes_to_base64url(verified.credential_id),
            "public_key": bytes_to_base64url(verified.credential_public_key),
            "sign_count": verified.sign_count,
            "name": (name or "Authenticator")[:60],
            "transports": [t for t in (transports or []) if isinstance(t, str)],
            "created_at": utcnow(),
            "last_used_at": None,
        }
    )


# ---------------------------------------------------------------------------
# Authentication (login / step-up)
# ---------------------------------------------------------------------------


def authentication_options(
    user_id: Optional[ObjectId] = None,
    purpose: str = PURPOSE_LOGIN,
) -> dict:
    """Build WebAuthn request options.

    ``allowCredentials`` is only restricted when ``user_id`` is given (login
    with a typed username, step-up). Login challenges stay unbound to a user so
    the verify step can resolve the owner from the credential itself.
    """
    if purpose == PURPOSE_LOGIN:
        challenge = _create_challenge(user_id=None, purpose=purpose)
    else:
        challenge = _create_challenge(user_id=user_id, purpose=purpose)

    opts = generate_authentication_options(
        rp_id=_rp_id(),
        challenge=challenge,
        timeout=AUTHENTICATOR_TIMEOUT_MS,
        allow_credentials=_descriptors_for(user_id) if user_id else None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    return options_to_json_dict(opts)


def credential_owner(credential_id_b64: str) -> Optional[dict]:
    """Return the stored passkey record for a given credential id."""
    return _get_mongo()[PASSKEY_COLLECTION].find_one(
        {"credential_id": credential_id_b64}
    )


def verify_authentication(
    credential,
    user_id: Optional[ObjectId] = None,
    purpose: str = PURPOSE_LOGIN,
):
    """
    Verify an assertion and update the roaming sign counter.

    Returns ``(record_or_None, error_message)`` where ``record`` includes the
    embedded ``user_id`` so callers can resolve the authenticated user.
    """
    challenge_b64 = pending_challenge_b64(purpose, user_id)
    if not challenge_b64 or not consume_challenge(challenge_b64, purpose, user_id):
        return None, "Challenge puuttuu, on jo käytetty tai se on vanhentunut."

    credential_id = credential.get("id") if isinstance(credential, dict) else credential.id
    record = _get_mongo()[PASSKEY_COLLECTION].find_one({"credential_id": credential_id})
    if not record:
        return None, "Tuntematon passkey."

    if user_id is not None and record.get("user_id") != ObjectId(user_id):
        return None, "Tämä passkey ei kuulu tilillesi."

    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_rp_id=_rp_id(),
            expected_origin=_allowed_origins(),
            credential_public_key=base64url_to_bytes(record["public_key"]),
            credential_current_sign_count=record.get("sign_count", 0),
        )
    except Exception:
        return None, "Virheellinen vahvistusvastaus."

    _get_mongo()[PASSKEY_COLLECTION].update_one(
        {"_id": record["_id"]},
        {"$set": {"sign_count": verified.new_sign_count, "last_used_at": utcnow()}},
    )
    return record, None


# ---------------------------------------------------------------------------
# Passkey management
# ---------------------------------------------------------------------------


def list_passkeys(user_id) -> list:
    """Return serialisable passkey metadata for the user."""
    docs = _get_mongo()[PASSKEY_COLLECTION].find(
        {"user_id": ObjectId(user_id)}
    ).sort("created_at", 1)
    return [serialize_passkey(doc) for doc in docs]


def serialize_passkey(doc) -> dict:
    def _iso(value):
        return value.isoformat() if value else None

    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", "Authenticator"),
        "created_at": _iso(doc.get("created_at")),
        "last_used_at": _iso(doc.get("last_used_at")),
        "transports": doc.get("transports", []),
    }


def rename_passkey(passkey_id: str, user_id, name: str) -> bool:
    result = _get_mongo()[PASSKEY_COLLECTION].update_one(
        {"_id": ObjectId(passkey_id), "user_id": ObjectId(user_id)},
        {"$set": {"name": (name or "Authenticator")[:60]}},
    )
    return result.matched_count == 1


def delete_passkey(passkey_id: str, user_id) -> bool:
    result = _get_mongo()[PASSKEY_COLLECTION].delete_one(
        {"_id": ObjectId(passkey_id), "user_id": ObjectId(user_id)}
    )
    return result.deleted_count == 1


def passkey_count(user_id) -> int:
    """Number of passkeys registered for the user."""
    return _get_mongo()[PASSKEY_COLLECTION].count_documents(
        {"user_id": ObjectId(user_id)}
    )