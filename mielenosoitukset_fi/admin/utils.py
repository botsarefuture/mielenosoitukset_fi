from datetime import datetime
from typing import Any

from bson.objectid import ObjectId
from pymongo.errors import PyMongoError

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.classes import Organization
from mielenosoitukset_fi.utils.logger import logger

db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()


def get_org_name(org_id: str) -> str:
    """
    Retrieve the name of the organization.

    Parameters
    ----------
    org_id : str
        The organization ID.

    Returns
    -------
    str
        The organization name if found; otherwise "Unknown Organization".
    """
    try:
        result = mongo.organizations.find_one({"_id": ObjectId(org_id)})
        if not result:
            logger.warning(f"Organization with ID {org_id} not found.")
            return "Unknown Organization"
        org = Organization.from_dict(result)
        return org.name
    except PyMongoError as e:
        logger.error(f"Error retrieving organization name: {e}")
        return "Unknown Organization"


def get_org_details(org_id: str) -> Organization:
    """
    Retrieve detailed information about an organization.

    Parameters
    ----------
    org_id : str
        The organization ID.

    Returns
    -------
    Organization
        An Organization object containing detailed information.

    Raises
    ------
    ValueError
        If the organization is not found or retrieval fails.
    """
    try:
        result = mongo.organizations.find_one({"_id": ObjectId(org_id)})
        if not result:
            logger.warning(f"Organization with ID {org_id} not found.")
            raise ValueError("Organization not found")
        return Organization.from_dict(result)
    except PyMongoError as e:
        logger.error(f"Error retrieving organization details: {e}")
        raise ValueError("Failed to retrieve organization details")


def log_admin_action(user, action: str, details: str):
    """
    Log an admin action to MongoDB.

    Parameters
    ----------
    user : User
        The user performing the action.
    action : str
        The action performed.
    details : str
        Additional details about the action.

    Returns
    -------
    None
    """
    try:
        mongo.admin_logs.insert_one(
            {
                "user_id": user.get_id(),
                "email": user.email,
                "action": action,
                "details": details,
                "timestamp": datetime.utcnow(),  # using UTC time
            }
        )
        logger.info(f"Admin action logged: {action} by user {user.email}")
    except PyMongoError as e:
        logger.error(f"Error logging admin action: {e}")


# TODO: Transfer organization-related functions to utils.organizations


def dictify_object(obj):
    """
    Convert an object to a dictionary.

    Parameters
    ----------
    obj : any
        The object to be converted.

    Returns
    -------
    dict or equivalent
        The dictionary representation of the object.
    """
    if isinstance(obj, dict):
        return {k: dictify_object(v) for k, v in obj.items()}
    elif hasattr(obj, "__dict__"):
        return {k: dictify_object(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, (list, tuple, set)):
        return type(obj)(dictify_object(v) for v in obj)
    return obj


def log_admin_action_V2(aact: dict):
    """
    Log an admin action (version 2) to MongoDB.

    Parameters
    ----------
    aact : dict
        A dictionary containing the admin action details.

    Returns
    -------
    None
    """
    try:
        to_insert = {
            "timestamp": datetime.utcnow(),
        }
        to_insert.update(aact)

        mongo.admin_logs.insert_one(to_insert)
    except PyMongoError as e:
        logger.error(f"Error logging admin action: {e}")


class AdminActParser:
    """
    Parse admin activity logs and handle request data.
    """

    def __init__(self):
        pass

    def log_request_info(self, request, user):
        """
        Log request and user information.

        Parameters
        ----------
        request : dict
            The HTTP request data.
        user : User
            The user object.

        Returns
        -------
        dict
            A dictionary with parsed request and user data.
        """
        try:
            import json

            request_data = json.loads(json.dumps({**request}, skipkeys=True, default=str))
            user_data = user.to_dict() if hasattr(user, "to_dict") else dictify_object(user)
            return {"request": request_data, "user": user_data}
        except Exception as e:
            logger.exception(f"Error parsing request info: {e}")
            return {}
