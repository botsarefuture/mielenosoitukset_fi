import logging
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def permission_needed(permission, organization_id=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Sinun tulee kirjautua sisään käyttääksesi sivua.")
                logger.warning("User not authenticated, redirecting to login.")
                return redirect(url_for("auth.login"))

            # Check for global admin
            if current_user.global_admin:
                logger.info("Global admin access granted.")
                return f(*args, **kwargs)

            elif not current_user.global_admin and organization_id is None:
                return current_user.can_use(permission)

            # Determine organization ID
            org_id = (
                organization_id if organization_id else kwargs.get("organization_id")
            )

            # Check membership
            if not org_id or not current_user.is_member_of_organization(org_id):
                flash("Sinä et ole tämän organisaation jäsen.")
                logger.warning(
                    f"User {current_user.username} is not a member of organization {org_id}."
                )
                return redirect(url_for("index"))

            # Check organization-specific permissions
            if not current_user.has_permission(
                org_id, permission
            ) and not current_user.can_use(permission):
                flash("Sinun käyttöoikeutesi eivät riitä tämän sivun käyttämiseen.")
                logger.warning(
                    f"User {current_user.username} does not have permission '{permission}' in organization {org_id}."
                )
                return redirect(url_for("index"))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def admin_required(f):
    """
    Decorator that checks if the current user is a global admin.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Ensure the user is authenticated
        if not current_user.is_authenticated:
            flash("Sinun täytyy kirjautua sisään käyttääksesi tätä sivua.")
            logger.warning("User not authenticated, redirecting to login.")
            return redirect(url_for("auth.login"))

        if not current_user.global_admin and current_user.role in ["user", "member"]:
            flash("Sinun käyttöoikeutesi eivät riitä sivun tarkasteluun.")
            logger.warning(f"User {current_user.username} is not a global admin.")
            return redirect(url_for("index"))

        logger.info(f"User {current_user.username} is a admin.")
        return f(*args, **kwargs)

    return decorated_function


def permission_required(permission_name):
    """
    Decorator to check if a user has a specific permission.

    Args:
        permission_name (str): The name of the permission to check.

    Returns:
        function: The wrapped function.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if the user is authenticated
            if not current_user.is_authenticated:
                flash("Sinun tulee kirjautua sisään käyttääksesi sivua.")
                logger.warning("User not authenticated, redirecting to login.")
                return redirect(url_for("auth.login"))

            # If the user is a global admin, grant access
            if current_user.global_admin:
                logger.info("Global admin access granted.")
                return f(*args, **kwargs)

            if current_user.can_use(permission_name):
                return f(*args, **kwargs)

            # Check if the user has the specified permission
            if permission_name in current_user.global_permissions:
                logger.info(
                    f"User {current_user.username} has permission '{permission_name}'."
                )
                return f(*args, **kwargs)

            # If permission is not granted, handle it appropriately
            flash("Sinun käyttöoikeutesi eivät riitä tämän toiminnon suorittamiseen.")
            logger.warning(
                f"User {current_user.username} does not have permission '{permission_name}'."
            )
            return redirect(url_for("index"))

        return decorated_function

    return decorator
