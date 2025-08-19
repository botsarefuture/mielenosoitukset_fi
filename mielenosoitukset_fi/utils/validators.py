"""
Module for validating various types of data.

This module provides functions to validate email addresses, event types, and to return existing values among provided variables.

Functions
---------
valid_email(email)
    Check if the given email address is valid.
valid_event_type(event_type)
    Check if the given event type is valid.
return_exists(var1, var2, default=None)
    Return the existing values among the provided variables.

Changelog
---------
v2.4.0:
    - Added `valid_email` function.
v2.6.0:
    - Added `valid_event_type` function.
    - Added `return_exists` function.
"""

import re
from typing import Union
from mielenosoitukset_fi.utils.variables import EVENT_TYPES


def valid_email(email):
    """
    Check if the given email address is valid.

    Parameters
    ----------
    email : str
        The email address to validate.

    Returns
    -------
    bool
        True if the email is valid, False otherwise.

    Changelog
    ---------
    v2.4.0:
        - Added this function.
    """
    # Regular expression for validating an email
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None


def valid_event_type(event_type: Union[str, "EventType"]):
    """
    Check if the given event type is valid.

    Parameters
    ----------
    event_type : str
        The event type to validate.

    Returns
    -------
    bool
        True if the event type is valid, False otherwise.

    Changelog
    ---------
    v2.6.0:
        - Added this function.
    """
    return event_type in EVENT_TYPES


def return_exists(var1, var2, default=None):
    """
    Return the existing values among the provided variables.

    This function checks the provided variables `var1` and `var2` and returns the existing values.
    If both variables are provided, it returns both. If only one is provided, it returns that value twice.
    If neither is provided, it returns the default value twice.

    Parameters
    ----------
    var1 : any
        The first variable to check.
    var2 : any
        The second variable to check.
    default : any, optional
        The default value to return if both `var1` and `var2` are not provided. Defaults to None.

    Returns
    -------
    tuple
        A tuple containing the existing values or the default value.

    Examples
    --------
    >>> return_exists(1, 2)
    (1, 2)
    >>> return_exists(1, None)
    (1, 1)
    >>> return_exists(None, 2)
    (2, 2)
    >>> return_exists(None, None, default=0)
    (0, 0)
    """
    if var1 and var2:
        return var1, var2

    elif var1 and not var2:
        return var1, var1

    elif var2 and not var1:
        return var2, var2

    else:
        return default, default


def event_type_convertor(event_type: str) -> str:
    """
    Parameters
    ----------
    event_type : str
        The event type to be converted. Expected values are "marssi", "paikallaan", "muut",
        or any valid event type.

    Returns
    -------
    standardized_event_type : str
        The standardized event type. Returns "MARCH" for "marssi", "STAY_STILL" for "paikallaan",
        "OTHER" for "muut", or the original event type if it is already valid.

    Raises
    ------
    ValueError
        If the event type is not already standardized and not one of the expected values ("marssi", "paikallaan", "muut").
    """

    event_type_mapping = {
        "marssi": "MARCH",
        "paikallaan": "STAY_STILL",
        "muut": "OTHER",
    }

    if not valid_event_type(event_type):
        if event_type in event_type_mapping.keys():
            return event_type_mapping[event_type]

        else:
            # raise ValueError(f"Invalid event type: {event_type}") # fIXED A SILI BUG
            return "STAY_STILL"

    else:
        return event_type
