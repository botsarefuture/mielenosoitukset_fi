from database_manager import DatabaseManager
from datetime import datetime

from bson.objectid import ObjectId

db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

def log_demo_view(demo_id, user_id=None, session_id=None):
    """
    This function logs a demonstration view by inserting a new document into the "views" collection in the database.

    :param demo_id: The ObjectId of the demonstration that was viewed.
    :param user_id: The ObjectId of the user who viewed the demonstration.
    :param session_id: The session ID of the user who viewed the demonstration.
    """
    view_data = {
        "demo_id": ObjectId(demo_id),
        "timestamp": datetime.now()
    }
    
    if user_id:
        view_data["user_id"] = user_id
    else:
        view_data["session_id"] = session_id

    mongo.analytics.insert_one(view_data)
    
def get_demo_views(demo_id=None):
    """
    This function retrieves all views of a demonstration from the "views" collection in the database.

    :param demo_id: The ObjectId of the demonstration for which views are to be retrieved.
    :return: A list of dictionaries containing the view data for each view of the demonstration.
    """
    if not demo_id:
        return mongo.analytics.find()
    else:
        mongo.analytics.find({"demo_id": ObjectId(demo_id)})