from flask import flash, g, has_request_context
from flask_babel import _

def flash_message(message, category="message", **variables):
    """
    Flash a message with a specific category, compatible with the new flash styles.

    Parameters
    ----------
    message : str
        The message to be flashed.
    category : str, optional
        The category of the message. Defaults to "message".
    **variables
        Named interpolation values for ``%(name)s`` placeholders. Keeping the
        untranslated message as the first literal argument lets Babel extract
        it from ``flash_message(...)`` calls.

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

    # Translate the literal message id first, then interpolate user/runtime
    # values. This preserves extraction and lets translations reorder values.
    translated_message = _(message)
    if variables:
        translated_message %= variables
    flash(translated_message, mapped_category)
