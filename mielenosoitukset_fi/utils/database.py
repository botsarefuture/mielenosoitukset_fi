"""
This module provides utility functions for handling database operations, specifically for converting
ObjectId and datetime instances within data structures to their string representations.

Functions
---------
stringify_object_ids(data):
    Traverses through a dictionary or list and converts all instances of ObjectId to their string 
    representation and datetime instances to a string formatted as "YYYY-MM-DD".

revert_stringified_object_ids(data):
    Traverses through a dictionary or list and converts all string representations of ObjectId back to 
    ObjectId instances and strings formatted as "YYYY-MM-DD" back to datetime instances.

Constants
---------
DEMO_FILTER : dict
    A filter used to query approved demonstrations that are not hidden.
"""

from bson.objectid import ObjectId
from datetime import datetime
from mielenosoitukset_fi.database_manager import DatabaseManager

DEMO_FILTER = {
    "approved": True,
    "cancelled": {"$ne": True},
    "$and": [
        {
            "$or": [
                {"hide": {"$exists": False}},
                {"hide": False},
            ]
        },
        {
            "$or": [
                {"rejected": {"$exists": False}},
                {"rejected": False},
            ]
        },
    ],
}



def stringify_object_ids(data):
    """This function traverses through the provided data structure, which can be a dictionary or a list,
    and converts all instances of ObjectId to their string representation. Additionally, it converts
    datetime instances to a string formatted as "YYYY-MM-DD".

    Parameters
    ----------
    data : dict or list of str, ObjectId, or datetime instances
        The data structure to be traversed and modified.

    Returns
    -------
    dict or list of str
        The modified data structure with all ObjectId instances converted to strings and datetime instances to "YYYY-MM-DD" strings.

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
     'date': '2022-01-01',
     'nested': {'id': '60f8e1e7a1b9c9b8f6b3f3b3', 'date': '2022-01-02'}}

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
        return data.strftime("%Y-%m-%d")  # Convert datetime to ISO 8601 date format
    elif isinstance(data, object) and data.__class__.__name__ == "User":
       # from mielenosoitukset_fi.users.models import User
        return data.to_dict(True)
    else:
        return data


def revert_stringified_object_ids(data):
    """
    This function traverses through the provided data structure, which can be a dictionary or a list,
    and converts all string representations of ObjectId back to ObjectId instances. Additionally, it converts
    strings formatted as "YYYY-MM-DD" back to datetime instances.

    Parameters
    ----------
    data : dict or list of str, ObjectId, or datetime instances
        The data structure to be traversed and modified.

    Returns
    -------
    dict or list of str, ObjectId, or datetime instances
        The modified data structure with all string representations of ObjectId converted back to ObjectId instances
        and "YYYY-MM-DD" strings converted back to datetime instances.

    Examples
    --------
    >>> data = {
    ...     "id": "60f8e1e7a1b9c9b8f6b3f3b2",
    ...     "date": "2022-01-01",
    ...     "nested": {
    ...         "id": "60f8e1e7a1b9c9b8f6b3f3b3",
    ...         "date": "2022-01-02"
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
                return datetime.strptime(data, "%Y-%m-%d")
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


def finnish_to_iso(finnish_date: str) -> str:
    """
    Convert Finnish date format (dd.mm.yyyy) to ISO 8601 format (yyyy-mm-dd).

    Parameters
    ----------
    finnish_date : str
        Date string in Finnish format.

    Returns
    -------
    str
        Date string in ISO 8601 format.
    """
    from datetime import datetime
    return datetime.strptime(finnish_date, "%d.%m.%Y").strftime("%Y-%m-%d")


def iso_to_finnish(iso_date: str) -> str:
    """
    Convert ISO 8601 date format (yyyy-mm-dd) to Finnish format (dd.mm.yyyy).

    Parameters
    ----------
    iso_date : str
        Date string in ISO 8601 format.

    Returns
    -------
    str
        Date string in Finnish format.
    """
    from datetime import datetime
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")

