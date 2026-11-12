"""
auth.py

This module provides functions for generating and verifying JWT tokens for various purposes such as password reset and account confirmation.

Functions
---------
_generate_token(data: dict, expiration: int) -> str
    Generate a JWT token using the provided data and expiration time.

_verify_token(token: str) -> Tuple[Optional[dict], int]
    Verify the provided token and return the associated data and status code.

generate_reset_token(email: str) -> str
    Generate a password reset token for the given email address.

verify_reset_token(token: str) -> Optional[str]
    Verify a password reset token and return the associated email address if valid.

generate_confirmation_token(email: str) -> str
    Generate an account confirmation token for the given email address.

verify_confirmation_token(token: str) -> Optional[str]
    Verify the confirmation token and return the associated email address if valid.
"""

from typing import Tuple, Optional

from mielenosoitukset_fi.utils.time_utils import utcnow
import datetime
import jwt
from flask import current_app


def _generate_token(data, expiration):
    """
    Generate a token using the provided data and expiration time.

    This function generates a JWT token using the provided data and expiration time.

    Parameters
    ----------
    data : dict
        The data to be included in the token.
    expiration : int
        The expiration time in seconds.

    Returns
    -------
    str
        The generated JWT token.
    """
    return jwt.encode(
        {
            **data,
            "iat": utcnow(),
            "exp": utcnow() + datetime.timedelta(seconds=expiration),
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )


def _verify_token(token: str) -> Tuple[Optional[dict], int]:
    """
    Verify the provided token.

    This function decodes the provided token using the application's secret key and the HS256 algorithm.
    If the token is valid, it returns the data associated with the token and a status code of 1.
    If the token has expired, it returns None and a status code of -1.
    If the token is invalid, it returns None and a status code of 0.

    Parameters
    ----------
    token : str
        The token to be verified.

    Returns
    -------
    Tuple[Optional[dict], int]
        A tuple containing the data associated with the token if the token is valid, otherwise None,
        and an integer status code indicating the result:
        -1 if the token has expired,
        0 if the token is invalid,
        1 if the token is valid.

    Raises
    ------
    jwt.ExpiredSignatureError
        If the token has expired.

    jwt.InvalidTokenError
        If the token is invalid.
    """
    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return data, 1

    except jwt.ExpiredSignatureError:
        current_app.logger.warning("Token has expired.")
        return None, -1

    except jwt.InvalidTokenError:
        current_app.logger.warning("Invalid token.")
        return None, 0


def _purpose_allows(data, purpose: str) -> bool:
    """Reject a token minted for another purpose.

    Links issued before the ``purpose`` claim existed carry none and stay valid
    until they expire (one hour), so deploying this breaks no pending email.
    """
    claimed = (data or {}).get("purpose")
    return claimed is None or claimed == purpose


def generate_reset_token(email: str) -> str:
    """
    Generate a password reset token for the given email address.

    Parameters
    ----------
    email : str
        The email address for which to generate the reset token.

    Returns
    -------
    str
        The generated JWT token.
    """
    return _generate_token({"email": email, "purpose": "password_reset"}, 3600)


def verify_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token.

    Parameters
    ----------
    token : str
        The JWT token to verify.

    Returns
    -------
    Optional[str]
        The email address if the token is valid, None otherwise.
    """
    data, status = _verify_token(token)
    if status == 1 and _purpose_allows(data, "password_reset"):
        return data.get("email")
    return None


def generate_confirmation_token(email: str) -> str:
    """
    Generate an account confirmation token for the given email address.

    Parameters
    ----------
    email : str
        The email address for which to generate the confirmation token.

    Returns
    -------
    str
        The generated JWT token.
    """
    # Use 3600 seconds (1 hour) for expiration, as _generate_token expects seconds (int)
    return _generate_token({"email": email, "purpose": "email_confirmation"}, 3600)


def verify_confirmation_token(token: str) -> Optional[str]:
    """
    Verify the confirmation token.

    Parameters
    ----------
    token : str
        The confirmation token to be verified.

    Returns
    -------
    Optional[str]
        The email address associated with the token if the token is valid, otherwise None.
    """
    data, status = _verify_token(token)
    if status == 1 and data and isinstance(data, dict) and _purpose_allows(data, "email_confirmation"):
        return data.get("email")
    return None


def reset_invalidation_enabled() -> bool:
    """Whether a password reset also ends sessions and older reset links.

    Off unless ``INVALIDATE_ON_PASSWORD_RESET`` is set in the app config or the
    environment. Turning it off again (unset, restart) is the whole revert.
    """
    import os

    value = current_app.config.get("INVALIDATE_ON_PASSWORD_RESET")
    if value is None:
        value = os.environ.get("INVALIDATE_ON_PASSWORD_RESET", "")
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def token_issued_before(token: str, moment) -> bool:
    """True if a signed token was issued before ``moment``.

    Tokens minted before the ``iat`` claim existed are dated one hour before
    their expiry, which is the lifetime they were given.
    """
    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return False
    issued = data.get("iat")
    if issued is None and data.get("exp") is not None:
        issued = data["exp"] - 3600
    if issued is None or moment is None:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    return datetime.datetime.fromtimestamp(issued, datetime.timezone.utc) < moment
