# mielenosoitukset_fi/campaign/__init__.py
from flask import Blueprint

campaign_bp = Blueprint(
    "campaign",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/kampanja/"
)

from . import routes
