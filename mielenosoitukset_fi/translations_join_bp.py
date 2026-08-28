# translations_join_bp.py
"""Self-service joining for the translation project.

Logged-in users can grant themselves the translation capabilities
(TRANSLATE_DEMO and TRANSLATE_UI) that the catalog checks require, without
needing to email the project team. Review and admin rights are intentionally
NOT granted here.
"""
from flask import Blueprint, redirect, url_for
from flask_login import current_user, login_required

from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.database_manager import DatabaseManager
from flask_babel import _


translations_join_bp = Blueprint(
    "translations_join", __name__, url_prefix="/upcoming/translations"
)


def _get_mongo():
    """Return the active database handle (fresh per request in tests)."""
    return DatabaseManager().get_instance().get_db()


TRANSLATE_DEMO_PERMS = ("TRANSLATE_DEMO", "TRANSLATE_UI")


@translations_join_bp.route("/join", methods=["POST"])
@login_required
def join():
    """Grant the current user translation capabilities (idempotent)."""
    user_id = current_user._id

    for perm in TRANSLATE_DEMO_PERMS:
        _get_mongo().users.update_one(
            {"_id": user_id}, {"$addToSet": {"global_permissions": perm}}
        )

    flash_message(
        _("Olet nyt mukana käännöstyössä. Kiitos avustasi!"),
        "success",
    )
    return redirect(url_for("upcoming_translations"))
