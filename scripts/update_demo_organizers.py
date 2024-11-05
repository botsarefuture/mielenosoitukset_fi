import logging
from bson.objectid import ObjectId

# from database_manager import DatabaseManager
# from classes import Demonstration

import importlib
import sys
import os

# Get the parent directory
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

database_manager = importlib.import_module("database_manager")
DatabaseManager = database_manager.DatabaseManager

classes = importlib.import_module("classes")
Demonstration = classes.Demonstration

# Configure logger
logger = logging.getLogger("GayKip")
logger.setLevel(logging.INFO)

# Initialize database instance
instance = DatabaseManager().get_instance()
db = instance.get_db()

# Collection references
DEMOCOL = db.demonstrations
ORGCOL = db.organizations


def find_organization(org_id):
    """
    Find an organization by its ID.

    Args:
        org_id (str or dict): The organization ID or a dictionary containing the ObjectId.

    Returns:
        tuple: The organization document (if found) and the ObjectId.
    """
    try:
        if isinstance(org_id, dict) and "$oid" in org_id:
            org_id = ObjectId(org_id["$oid"])

        elif isinstance(org_id, str):
            org_id = ObjectId(org_id)

    except Exception as e:
        logger.error(f"Invalid organization ID format: {org_id}, Error: {e}")
        return None, None

    return ORGCOL.find_one({"_id": org_id}), org_id


def find_organization_by_name(org_name):
    """
    Find an organization by its name.

    Args:
        org_name (str): The name of the organization.

    Returns:
        dict: The organization document (if found).
    """
    return ORGCOL.find_one({"name": org_name})


def update_demo_organizers(demo):
    """
    Update the organizers of a demonstration with their organization IDs.

    Args:
        demo (dict): The demonstration document.
    """
    _demo = Demonstration.from_dict(demo)
    organizers = _demo.organizers

    for organizer in organizers:
        if organizer.organization_id is not None:
            organization, org_id = find_organization(organizer.organization_id)
            organizer.organization_id = org_id

            if organization is None:
                logger.error(
                    f"Organization with ID {organizer.organization_id} not found, skipping..."
                )
                continue

        else:
            # Try to match organizer's name with organization name
            organization = find_organization_by_name(organizer.name)

            if organization:
                logger.info(f"Matched organization by name: {organization['name']}")
                organizer.organization_id = ObjectId(
                    organization["_id"]
                )  # Ensure it is an ObjectId
            else:
                logger.warning(
                    f"Could not match organizer {organizer.name} with any organization."
                )
                continue

    # After processing, update the demonstration with the correct organization id
    DEMOCOL.update_one(
        {"_id": demo["_id"]},
        {"$set": {"organizers": [o.to_dict() for o in _demo.organizers]}},
    )


def main():
    """
    Main function to update organizers' organization IDs in all demonstrations.
    """
    demonstrations = list(DEMOCOL.find())

    for demo in demonstrations:
        update_demo_organizers(demo)


if __name__ == "__main__":
    main()
