from flask import flash
from flask_babel import _


def flash_message(message, category="message"):
    """
    Flash a message with a specific category.

    Parameters
    ----------
    message : str
        The message to be flashed.
    category : str, optional
        The category of the message (default is "message").

    Notes
    -----
    By default, the message is translated.

    Changelog
    ---------
    v2.5.0:
        - By default translate the message

    """
    categories = {
        "info": "info",
        "approved": "success",
        "success": "success",
        "warning": "warning",
        "error": "danger",
    }
    flash(_(message), categories.get(category, "info"))
