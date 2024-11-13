from flask import flash
from flask_babel import _


def flash_message(message, category="message"):
    """flash_message a message with a specific category.

    Changelog:
    ----------
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
