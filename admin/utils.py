from bson.objectid import ObjectId
from database_manager import DatabaseManager

# Initialize the database manager and get the MongoDB instance
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

def get_org_name(org_id):
    """
    Retrieve the name of the organization based on its ID.

    Parameters:
        org_id (str): The ID of the organization to retrieve.

    Returns:
        str: The name of the organization or 'Unknown Organization' if not found.
    """
    result = mongo.organizations.find_one({"_id": ObjectId(org_id)})
    return result.get("name") if result else "Unknown Organization"
