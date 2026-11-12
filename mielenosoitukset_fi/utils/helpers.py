"""
This module contains helper functions that can be used across the application.

Functions
---------
OIDifySOID(soid):
    Convert a string representation of an ObjectId to an ObjectId.

.. deprecated:: 2.8.0
    This module will be removed in v2.9.0, it is replaced by
    `utils.database.revert_stringified_object_ids` and `utils.database.stringify_object_ids`.
"""

from bson.objectid import ObjectId


def OIDifySOID(soid):
    """
    Convert a string representation of an ObjectId to an ObjectId.

    Parameters
    ----------
    soid : str
        The string representation of the ObjectId.

    Returns
    -------
    bson.objectid.ObjectId
        The ObjectId corresponding to the given string.

    .. deprecated:: 2.8.0
        `OIDifySOID` will be removed in v2.9.0, it is replaced by
        `utils.database.revert_stringified_object_ids` and `utils.database.stringify_object_ids`.

    See Also
    --------
    utils.database.revert_stringified_object_ids: A function that converts all string representations of ObjectId back to ObjectId instances.
    utils.database.stringify_object_ids: A function that converts all instances of ObjectId to their string representation
    """
    return ObjectId(soid)

import re

def is_strong_password(password: str, username: str = "", email: str = "") -> (bool, str):
    if len(password) < 12:
        return False, "Password must be at least 12 characters long."

    # Require 3 of 4 categories
    categories = 0
    if re.search(r"[a-z]", password): categories += 1
    if re.search(r"[A-Z]", password): categories += 1
    if re.search(r"\d", password): categories += 1
    if re.search(r"[!@#$%^&*()\-_+=\[\]{};:,.<>?]", password): categories += 1
    if categories < 3:
        return False, "Password must include at least 3 of the 4 categories: uppercase, lowercase, digit, special character."

    # Prevent personal info
    normalized_password = password.lower()
    normalized_username = (username or "").strip().lower()
    email_identity = (email or "").strip().lower().split("@", 1)[0]
    if (
        normalized_username and normalized_username in normalized_password
    ) or (
        email_identity and email_identity in normalized_password
    ):
        return False, "Password cannot contain your username or email."

    return True, "Password is strong."
