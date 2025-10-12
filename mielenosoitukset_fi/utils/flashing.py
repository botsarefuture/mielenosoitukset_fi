from flask import flash
from flask_babel import _

def flash_message(message, category="message"):
    """
    Flash a message with a specific category, compatible with the new flash styles.

    Parameters
    ----------
    message : str
        The message to be flashed.
    category : str, optional
        The category of the message. Defaults to "message".

    Notes
    -----
    The message is translated by default.

    Supported categories:
        - success
        - error / danger
        - warning
        - info
        - message (default / neutral)
    """
    # Map incoming category to the template categories
    categories_map = {
        "info": "info",
        "approved": "success",
        "success": "success",
        "warning": "warning",
        "error": "error",   # or "danger", either works
        "danger": "danger",
        "message": "default"  # neutral / fallback
    }

    # Get the mapped category or fallback to "default"
    mapped_category = categories_map.get(category.lower(), "default")

    # Flash the translated message
    flash(_(message), mapped_category)