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
            "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=expiration),
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
    return _generate_token({"email": email}, 3600)


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
    if status == 1:
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
    return _generate_token({"email": email}, 3600)


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
    if status == 1 and data and isinstance(data, dict):
        return data.get("email")
    return None
