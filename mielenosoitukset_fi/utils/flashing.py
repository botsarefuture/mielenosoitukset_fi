from flask import flash, g, has_request_context
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

    # Mark the current request as having flash messages so caches can opt-out
    if has_request_context():
        g._has_flash_messages = True

    # Flash the translated message
    flash(_(message), mapped_category)
