from mielenosoitukset_fi.utils.logger import logger
from functools import wraps
from flask import redirect, url_for, abort
from flask_babel import _
from flask_login import current_user
from mielenosoitukset_fi.utils.flashing import flash_message


def admin_required(f):
    """Decorator to enforce that a user has global admin privileges to access a specific route.

    The decorator performs two checks:
    1. Ensures the user is authenticated.
    2. Verifies that the user has a global admin role.

    If either check fails, a 403 Forbidden response is returned, and an appropriate log message is created.

    Changelog:
    ----------
    v2.6.0:
        - Replaced flash message and redirect with abort(403) for unauthorized access.
        - Enhanced logging for each access control check.
        - Improved log messages for better debugging capabilities.
        - Simplified access control logic for better readability.
        - Replaced multiple return statements with a single return statement.
        - Added function documentation for clarity.
        - Removed unnecessary try-except block.


    Args:
        f (function): The route function requiring admin access.

    Returns:
        function: The wrapped function with access control enforced.

    Parameters
    ----------
    f :


    Returns
    -------


    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        """

        Parameters
        ----------
        *args :

        **kwargs :


        Returns
        -------


        """
        # Check if the user is authenticated
        if not current_user.is_authenticated:
            logger.warning("User not authenticated, Unauthorized (401).")
            abort(401)

        # Check if the user has global admin privileges
        if not current_user.role in ["global_admin", "admin"]:
            logger.warning(
                f"User {current_user.username} is not a global admin, access forbidden (403)."
            )
            abort(403)

        # User is a global admin, access granted
        logger.info(f"User {current_user.username} is an admin, access granted.")
        return f(*args, **kwargs)

    return decorated_function


def permission_required(permission_name):
    """Decorator to enforce specific permission requirements for route access.

    This decorator checks:
    1. If the user is authenticated.
    2. If the user has global admin privileges (bypasses specific permission check).
    3. If the user has the specified permission.

    If access is denied, the user is redirected and a flash message is displayed.

    Changelog:
    ----------
    v2.6.0:
        - Enhanced logging at each step to improve debugging capabilities.
        - Added logic for global admin bypass of specific permissions.
        - Integrated flash messaging to notify user of access restrictions.
        - Consolidated and clarified permission handling logic.
        - Replaced redirect with abort(403) for unauthorized access.

    Parameters
    ----------
    permission_name : str
        The specific permission name required to access the route.

    Returns
    -------


    """

    def decorator(f):
        """

        Parameters
        ----------
        f :


        Returns
        -------


        """

        @wraps(f)
        def decorated_function(*args, **kwargs):
            """

            Parameters
            ----------
            *args :

            **kwargs :


            Returns
            -------


            """
            # Ensure the user is authenticated
            if not current_user.is_authenticated:
                flash_message("Sinun tulee kirjautua sisään käyttääksesi sivua.")
                logger.warning("User not authenticated, redirecting to login.")
                return redirect(url_for("users.auth.login"))

            # Allow access if the user is a global admin
            if current_user.global_admin:
                logger.info("Global admin access granted.")
                return f(*args, **kwargs)

            # Check if the user has the specified permission via user role permissions
            if current_user.has_permission(
                permission_name
            ):  # DEPRACED: Use has_permission instead
                logger.info(
                    f"User {current_user.username} has permission '{permission_name}' via role."
                )
                return f(*args, **kwargs)

            # Check if user has the specified permission directly in global permissions
            if permission_name in current_user.global_permissions:
                logger.info(
                    f"User {current_user.username} has global permission '{permission_name}'."
                )
                return f(*args, **kwargs)

            # Access denied if no permissions are met
            flash_message(
                "Sinun käyttöoikeutesi eivät riitä tämän toiminnon suorittamiseen."
            )
            logger.warning(
                f"User {current_user.username} does not have permission '{permission_name}'."
            )
            return abort(403)  # Forbidden

        return decorated_function

    return decorator

def depracated_endpoint(f):
    """Decorator to mark a route as deprecated.

    This decorator adds a warning message to the route's docstring to inform users that the route is deprecated.

    Changelog:
    ----------
    v2.6.0:
        - Added deprecated warning message to the route's docstring.
        - Enhanced logging for deprecated routes.
        - Improved function documentation for clarity.

    Parameters
    ----------
    f : function
        The route function to be marked as deprecated.

    Returns
    -------
    function
        The wrapped function with the deprecated warning added to the docstring.

    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        """

        Parameters
        ----------
        *args :

        **kwargs :


        Returns
        -------


        """
        logger.warning(f"Deprecated route accessed: {f.__name__}")
        flash_message("This endpoint is deprecated and no longer available.")
        return abort(410)  # 410 Gone

    return decorated_function