from functools import wraps
from bson import ObjectId
from flask import redirect, url_for, abort
from flask_babel import _
from flask_login import current_user
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.logger import logger


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

def _get_mongo():
    """Safely obtain a MongoDB handle."""
    try:
        return DatabaseManager.get_instance().get_db()
    except Exception as exc:  # pragma: no cover - defensive logging path
        logger.error("Failed to obtain database connection: %s", exc)
        return None


def _normalize_object_id(value):
    """Convert various ID formats to ObjectId or return None."""
    if isinstance(value, dict) and "$oid" in value:
        value = value.get("$oid")

    if isinstance(value, ObjectId):
        return value

    if isinstance(value, str):
        try:
            return ObjectId(value)
        except Exception:
            return None

    return None


def has_demo_permission(user, _id, permission_name):
    """
    Determine whether a user has permission for a specific demonstration.

    The check is intentionally defensive:
    - Validates authentication and admin status early.
    - Resolves the demonstration by `_id` (returns False if missing/invalid).
    - Grants permission when the user is listed as an explicit editor.
    - Grants permission when the user has the required permission in any
      organization that appears in the demonstration's organizers.

    Parameters
    ----------
    user :
        The current user object (expected to behave like flask-login's
        `current_user`).
    _id : str | ObjectId
        Demonstration identifier.
    permission_name : str
        Name of the permission being requested (e.g., "EDIT_DEMO").

    Returns
    -------
    bool
        True if permission is granted, otherwise False.
    """
    if user is None:
        logger.warning("Demo permission denied: no user provided.")
        return False

    if getattr(user, "global_admin", False):
        logger.info("Demo permission granted: user is global admin.")
        return True

    if not getattr(user, "is_authenticated", False):
        logger.info("Demo permission denied: user not authenticated.")
        return False

    if not _id:
        logger.warning(
            "Demo permission denied: missing demonstration id for '%s'.",
            permission_name,
        )
        return False

    demo_id = _normalize_object_id(_id)
    if not demo_id:
        logger.warning(
            "Demo permission denied: invalid demonstration id '%s' for '%s'.",
            _id,
            permission_name,
        )
        return False

    mongo = _get_mongo()
    if not mongo:
        logger.error(
            "Demo permission denied: database unavailable for '%s'.", permission_name
        )
        return False

    demo_doc = mongo.demonstrations.find_one({"_id": demo_id})
    if not demo_doc:
        logger.warning(
            "Demo permission denied: demonstration %s not found for '%s'.",
            demo_id,
            permission_name,
        )
        return False

    # Explicit editors on the document
    user_identifiers = {
        str(getattr(user, "id", "")),
        str(getattr(user, "_id", "")),
    }
    editors = {
        str(e.get("$oid")) if isinstance(e, dict) and "$oid" in e else str(e)
        for e in demo_doc.get("editors", [])
    }
    if user_identifiers & editors:
        logger.info(
            "Demo permission granted: user %s listed as editor for %s.",
            getattr(user, "id", None),
            demo_id,
        )
        return True

    # Organization-based permissions via organizers
    organizer_orgs = []
    for organizer in demo_doc.get("organizers", []):
        org_id = None
        if isinstance(organizer, dict):
            org_id = organizer.get("organization_id")
        else:
            org_id = getattr(organizer, "organization_id", None)

        org_oid = _normalize_object_id(org_id)
        if org_oid:
            organizer_orgs.append(org_oid)

    for org_oid in organizer_orgs:
        if user.has_permission(permission_name, org_oid):
            logger.info(
                "Demo permission granted: user %s has '%s' for organization %s.",
                getattr(user, "id", None),
                permission_name,
                org_oid,
            )
            return True

    logger.info(
        "Demo permission denied: user %s lacks '%s' for demonstration %s.",
        getattr(user, "id", None),
        permission_name,
        demo_id,
    )
    return False

def permission_required(permission_name: str, _id: str | None = None, _type: str | None = None):
    """
    Decorator to enforce specific permission requirements for route access.

    This decorator checks multiple layers of permissions for the `current_user`:
    1. Authentication status: user must be logged in.
    2. Global admin: automatically bypasses permission checks.
    3. Role-based permissions: user must have the specified permission in their role.
    4. Global permissions: user must have the specified permission in global_permissions.
    5. Demonstration-specific permissions (if `_type="DEMONSTRATION"`).

    If the user does not meet the required permissions, access is denied with a 403
    Forbidden error, and a flash message is displayed.

    Changelog
    ---------
    v2.6.0:
        - Enhanced logging at each step to improve debugging capabilities.
        - Added logic for global admin bypass of specific permissions.
        - Integrated flash messaging to notify user of access restrictions.
        - Consolidated and clarified permission handling logic.
        - Replaced redirect with abort(403) for unauthorized access.

    Parameters
    ----------
    permission_name : str
        The name of the permission required to access the decorated route.
    _id : str, optional
        Optional resource-specific ID used in permission checks.
    _type : str, optional
        Optional type of permission check, e.g., "DEMONSTRATION".

    Returns
    -------
    decorator : function
        The decorator function that wraps the route handler.

    Notes
    -----
    - Intended to be used with Flask route handlers.
    - Uses `flash_message` to notify users of denied access.
    - Uses `logger` to log permission checks and access denials.
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

            if _type == "DEMONSTRATION":
                has = has_demo_permission(current_user, _id, permission_name)
                if has:
                    return f(*args, **kwargs)
                logger.warning(
                    "Demonstration permission '%s' denied for user %s and demo %s.",
                    permission_name,
                    getattr(current_user, "id", None),
                    _id,
                )
                                
            # Check if the user has the specified permission via user role permissions
            if current_user.has_permission(
                permission_name,
                _id
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
