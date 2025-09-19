"""
This module initializes the main user Blueprint and registers sub-Blueprints for authentication, user organizations, and user profiles.

Blueprints:
    auth_bp: Handles authentication-related routes.
    user_orgs_bp: Manages routes related to user organizations.
    profile_bp: Manages user profile-related routes.

The combined Blueprint `user_bp` is created and the sub-Blueprints are registered to it.

Attributes:
    user_bp (Blueprint): The main Blueprint for user-related routes, with sub-Blueprints registered to it.
"""

from flask import Blueprint
from .auth import auth_bp
from .orgs import user_orgs_bp
from .profile import profile_bp


def create_user_blueprint():
    """Create and configure the main user Blueprint, registering sub-Blueprints."""
    user_bp = Blueprint("users", __name__, template_folder="templates")
    user_bp.register_blueprint(auth_bp)
    user_bp.register_blueprint(user_orgs_bp)
    user_bp.register_blueprint(profile_bp)

    return user_bp


# Create the user blueprint
user_bp = create_user_blueprint()
