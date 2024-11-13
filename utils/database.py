from bson.objectid import ObjectId
from datetime import datetime

DEMO_FILTER = {"approved": True, "$or": [{"hide": {"$exists": False}}, {"hide": False}]}


def stringify_object_ids(data):
    """
    This function traverses through the provided data structure, which can be a dictionary or a list,
    and converts all instances of ObjectId to their string representation. Additionally, it converts
    datetime instances to a string formatted as "dd.mm.yyyy".

    :param data: The data structure (dict or list) containing ObjectId and datetime instances.
    :return: A new data structure with ObjectId instances converted to strings and datetime instances
             formatted as "dd.mm.yyyy".            
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
