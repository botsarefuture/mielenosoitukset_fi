"""
This module provides utility functions for handling database operations, specifically for converting
ObjectId and datetime instances within data structures to their string representations.

Functions
---------
stringify_object_ids(data):
    Traverses through a dictionary or list and converts all instances of ObjectId to their string 
    representation and datetime instances to a string formatted as "dd.mm.yyyy".

revert_stringified_object_ids(data):
    Traverses through a dictionary or list and converts all string representations of ObjectId back to 
    ObjectId instances and strings formatted as "dd.mm.yyyy" back to datetime instances.

Constants
---------
DEMO_FILTER : dict
    A filter used to query approved demonstrations that are not hidden.
"""

from bson.objectid import ObjectId
from datetime import datetime
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.users.models import User

DEMO_FILTER = {"approved": True, "$or": [{"hide": {"$exists": False}}, {"hide": False}]}


def stringify_object_ids(data):
    """This function traverses through the provided data structure, which can be a dictionary or a list,
    and converts all instances of ObjectId to their string representation. Additionally, it converts
    datetime instances to a string formatted as "dd.mm.yyyy".

    Parameters
    ----------
    data : dict or list of str, ObjectId, or datetime instances
        The data structure to be traversed and modified.

    Returns
    -------
    dict or list of str
        The modified data structure with all ObjectId instances converted to strings and datetime instances to "dd.mm.yyyy" strings.

    Examples
    --------
    >>> from bson.objectid import ObjectId
    >>> from datetime import datetime
    >>> data = {
    ...     "id": ObjectId("60f8e1e7a1b9c9b8f6b3f3b2"),
    ...     "date": datetime(2022, 1, 1),
    ...     "nested": {
    ...         "id": ObjectId("60f8e1e7a1b9c9b8f6b3f3b3"),
    ...         "date": datetime(2022, 1, 2)
    ...     }
    ... }
    >>> stringify_object_ids(data)
    {'id': '60f8e1e7a1b9c9b8f6b3f3b2',
     'date': '01.01.2022',
     'nested': {'id': '60f8e1e7a1b9c9b8f6b3f3b3', 'date': '02.01.2022'}}

    See Also
    --------
    utils.database.revert_stringified_object_ids: A function that converts string representations of ObjectId back to ObjectId instances.
    """

    if isinstance(data, dict):
        return {k: stringify_object_ids(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [stringify_object_ids(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, datetime):
        return data.strftime("%d.%m.%Y")  # Convert datetime to Finnish date format
    elif isinstance(data, User):
        return data.to_dict(True)
    else:
        return data


def revert_stringified_object_ids(data):
    """
    This function traverses through the provided data structure, which can be a dictionary or a list,
    and converts all string representations of ObjectId back to ObjectId instances. Additionally, it converts
    strings formatted as "dd.mm.yyyy" back to datetime instances.

    Parameters
    ----------
    data : dict or list of str, ObjectId, or datetime instances
        The data structure to be traversed and modified.

    Returns
    -------
    dict or list of str, ObjectId, or datetime instances
        The modified data structure with all string representations of ObjectId converted back to ObjectId instances
        and "dd.mm.yyyy" strings converted back to datetime instances.

    Examples
    --------
    >>> data = {
    ...     "id": "60f8e1e7a1b9c9b8f6b3f3b2",
    ...     "date": "01.01.2022",
    ...     "nested": {
    ...         "id": "60f8e1e7a1b9c9b8f6b3f3b3",
    ...         "date": "02.01.2022"
    ...     }
    ... }
    >>> revert_stringified_object_ids(data)
    {'id': ObjectId('60f8e1e7a1b9c9b8f6b3f3b2'),
     'date': datetime.datetime(2022, 1, 1, 0, 0),
     'nested': {'id': ObjectId('60f8e1e7a1b9c9b8f6b3f3b3'), 'date': datetime.datetime(2022, 1, 2, 0, 0)}}

    See Also
    --------
    utils.database.stringify_object_ids: A function that converts ObjectId and datetime instances to their string representations.

    """

    if isinstance(data, dict):
        return {k: revert_stringified_object_ids(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [revert_stringified_object_ids(item) for item in data]
    elif isinstance(data, str):
        try:
            return ObjectId(data)
        except:
            try:
                return datetime.strptime(data, "%d.%m.%Y")
            except:
                return data
    else:
        return data


def get_database_manager():
    """
    Get the database manager instance.

    Returns
    -------
    :class:'Database'
        The database instance.
    """
    db_manager = DatabaseManager()
    return db_manager.get_instance().get_db()
