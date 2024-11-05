from bson.objectid import ObjectId
from database_manager import DatabaseManager
from datetime import datetime
from classes import Organization
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
import logging

# Initialize logging
logger = logging.getLogger(__name__)

# Initialize the database manager and get the MongoDB instance
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()


def get_org_name(org_id: str) -> str:
    """
    Retrieve the name of the organization based on its ID.

    Parameters:
        org_id (str): The ID of the organization to retrieve.

    Returns:
        str: The name of the organization or 'Unknown Organization' if not found.
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
    Retrieve detailed information about an organization based on its ID.

    Parameters:
        org_id (str): The ID of the organization to retrieve.

    Returns:
        Organization: An instance of the Organization class with the organization's details.

    Raises:
        ValueError: If the organization is not found.
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

    Parameters:
        user: The user object performing the action.
        action (str): A description of the action performed.
        details (str): Additional details about the action.
    """
    try:
        mongo.admin_logs.insert_one(
            {
                "user_id": user.get_id(),
                "email": user.email,
                "action": action,
                "details": details,
                "timestamp": datetime.utcnow(),
            }
        )
        logger.info(f"Admin action logged: {action} by user {user.email}")
    except PyMongoError as e:
        logger.error(f"Error logging admin action: {e}")
