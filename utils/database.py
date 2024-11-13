from bson.objectid import ObjectId
from datetime import datetime

DEMO_FILTER = {"approved": True, "$or": [{"hide": {"$exists": False}}, {"hide": False}]}


def stringify_object_ids(data):
    """
    Recursively converts all ObjectId instances in the given data structure to strings.

    :param data: The data structure (dict or list) containing ObjectId instances.
    :return: A new data structure with ObjectId instances converted to strings.
    """
    if isinstance(data, dict):
        return {k: stringify_object_ids(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [stringify_object_ids(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, datetime):
        return data.strftime("%d.%m.%Y")  # Convert datetime to Finnish date format
    else:
        return data
