from bson.objectid import ObjectId

from database_manager import DatabaseManager
db_manager = DatabaseManager().get_instance()

mongo = db_manager.get_db()

def get_org_name(org_id):
    result = mongo.organizations.find_one({"_id": ObjectId(org_id)})
    return result.get("name") if result else "Unknown Organization"

