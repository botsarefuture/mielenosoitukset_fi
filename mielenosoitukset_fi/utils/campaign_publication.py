"""One explicit publication gate for campaign pages; missing state is private."""

from functools import wraps

from flask import current_app, g, jsonify, make_response
from flask_babel import _
from flask_login import current_user
from pymongo.errors import PyMongoError

from mielenosoitukset_fi.database_manager import DatabaseManager

PUBLICATION_ID = "public_pages"


def campaign_pages_public():
    if not hasattr(g, "campaign_pages_public"):
        try:
            db = DatabaseManager.get_instance().get_db()
            state = db.campaign_settings.find_one({"_id": PUBLICATION_ID}) or {}
            g.campaign_pages_public = state.get("published") is True
        except PyMongoError:
            current_app.logger.exception("Could not read campaign publication state")
            g.campaign_pages_public = False
    return g.campaign_pages_public


def campaign_preview_required(view=None, *, api=False):
    """Allow logged-in preview until publication; never cache these responses."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            published = campaign_pages_public()
            if not published and not current_user.is_authenticated:
                if api:
                    response = make_response(jsonify(
                        success=False,
                        error=_("Kirjaudu sisään nähdäksesi valmisteilla olevan kampanjan."),
                    ), 401)
                else:
                    response = make_response(current_app.login_manager.unauthorized())
            else:
                response = make_response(function(*args, **kwargs))
            # A later return to private must not expose a cached public response.
            response.headers["Cache-Control"] = "private, no-store"
            response.vary.add("Cookie")
            if not published:
                response.headers["X-Robots-Tag"] = "noindex, nofollow"
            return response
        return wrapped
    return decorate(view) if view is not None else decorate
