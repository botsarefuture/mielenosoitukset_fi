"""
This module contains helper functions that can be used across the application.

Functions
---------
OIDifySOID(soid):
    Convert a string representation of an ObjectId to an ObjectId.

.. deprecated:: 2.8.0
    This module will be removed in v2.9.0, it is replaced by
    `utils.database.revert_stringified_object_ids` and `utils.database.stringify_object_ids`.
"""

from bson.objectid import ObjectId


def OIDifySOID(soid):
    """
    Convert a string representation of an ObjectId to an ObjectId.

    Parameters
    ----------
    soid : str
        The string representation of the ObjectId.

    Returns
    -------
    bson.objectid.ObjectId
        The ObjectId corresponding to the given string.

    .. deprecated:: 2.8.0
        `OIDifySOID` will be removed in v2.9.0, it is replaced by
        `utils.database.revert_stringified_object_ids` and `utils.database.stringify_object_ids`.

    See Also
    --------
    utils.database.revert_stringified_object_ids: A function that converts all string representations of ObjectId back to ObjectId instances.
    utils.database.stringify_object_ids: A function that converts all instances of ObjectId to their string representation
    """
    return ObjectId(soid)
