import re


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
