from gettext import gettext as _
from flask import flash

def flash_message(message, category):
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
