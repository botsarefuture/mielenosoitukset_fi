import re
import warnings
import json
import os


def load_from_file(_filename):
    """
    Load and parse JSON data from a specified file located in the ".utils" directory.

    This function reads the content of a JSON file and returns it as a Python dictionary.
    The file is expected to be located in the `.utils` folder relative to the current working directory.

    Args:
        _filename (str): The name of the JSON file to load (e.g., 'city_list.json').

    Returns:
        dict: A dictionary containing the parsed JSON data.

    Raises:
        FileNotFoundError: If the specified file does not exist in the ".utils" directory.
        json.JSONDecodeError: If the file is not a valid JSON file.

    Changelog:
    ----------
    v2.4.0:
        - Added this function to load JSON data from the ".utils" directory.
    """
    file_path = os.path.join(".utils", _filename)

    # Attempt to open and load the file
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


CITY_LIST = load_from_file("city_list.json")
PERMISSIONS_GROUPS = load_from_file("permission_groups.json")


def is_valid_email(email):
    """
    Deprecated: This function is deprecated and will be removed in future versions.
    Please use `valid_email` from this module instead.

    Args:
        email (str): The email address to validate.

    Returns:
        bool: True if the email is valid, False otherwise.

    Changelog:
    ----------
    v2.4.0:
        - Deprecated this function. Use `valid_email` instead.
    """
    warnings.warn(
        "The 'is_valid_email' function is deprecated; use 'valid_email' from this module instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Regular expression for validating an email
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None


def valid_email(email):
    """
    Check if the given email address is valid.

    Args:
        email (str): The email address to validate.

    Returns:
        bool: True if the email is valid, False otherwise.

    Changelog:
    ----------
    v2.4.0:
        - Added this function.
    """
    # Regular expression for validating an email
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None


def load_version() -> str:
    """
    Load the current version of the application from the VERSION file.

    Returns:
        str: The version string currently running.

    Changelog:
    ----------
    v2.4.0:
        - Added this function to load the version.

    v2.5.0:
        - Moved this function to utils lib, but keeping this here as an alias.
    """

    from utils import VERSION

    return VERSION
