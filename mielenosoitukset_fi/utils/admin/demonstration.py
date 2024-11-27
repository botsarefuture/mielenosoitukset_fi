"""
demonstration.py

This module provides utility functions for handling request data and fixing organizer information.

Functions
---------
collect_tags(request: Request) -> List[str]
    Collect and return a list of tags from the request form data.

fix_organizers(data: dict) -> dict
    Fix the 'organization_id' field for each organizer in the provided data.
"""

from flask import Request
from typing import List
from bson.objectid import ObjectId

def rlace(item: object, old: str, new: str = ''):
    item = item.replace(old, new)

def collect_tags(request: Request) -> List[str]:
    """
    Collect and return a list of tags from the request form data.

    This function extracts all form fields that start with 'tag_' (regardless of index),
    ensuring that gaps in numbering don't prevent tag collection.

    Parameters
    ----------
    request : Request
        The incoming Flask request object containing form data.

    Returns
    -------
    List[str]
        A list of non-empty, trimmed tags from the form.

    Examples
    --------
    >>> from flask import Request
    >>> request = Request.from_values(form={'tag_1': 'python', 'tag_2': 'flask', 'tag_3': '  '})
    >>> collect_tags(request)
    ['python', 'flask']

    Changelog
    ---------
    v2.4.0:
        - Added dynamic collection of all `tag_` prefixed fields.
        - Introduced sorting of `tag_` keys by numerical index to handle gaps in numbering.
        - Enhanced handling of empty or whitespace-only tags by skipping them.
    """
    # Extract all keys starting with 'tag_' and sort them
    tag_keys = sorted(
        (key for key in request.form if key.startswith("tag_")),
        key=lambda k: int(k.split("_")[1]),
    )

    tags = []
    for key in tag_keys:
        tag_name = request.form.get(key, "").strip()
        if tag_name:  # Only add non-empty, trimmed tags
            # Tags should have '#' in front of them 
            rlace(tag_name, "#", "")
            tags.append(tag_name)

    return tags


def fix_organizers(data: dict) -> dict:
    """
    Fix the 'organization_id' field for each organizer in the provided data.

    Parameters
    ----------
    data : dict
        A dictionary containing a list of organizers under the key 'organizers'.

    Returns
    -------
    dict
        The modified data dictionary with 'organization_id' fields converted to ObjectId.

    Examples
    --------
    >>> data = {
    ...     "organizers": [
    ...         {"organization_id": {"$oid": "507f1f77bcf86cd799439011"}},
    ...         {"organization_id": "507f1f77bcf86cd799439012"}
    ...     ]
    ... }
    >>> fix_organizers(data)
    {
        "organizers": [
            {"organization_id": ObjectId("507f1f77bcf86cd799439011")},
            {"organization_id": ObjectId("507f1f77bcf86cd799439012")}
        ]
    }
    """
    for organizer in data["organizers"]:
        if organizer["organization_id"] == None or organizer["organization_id"].lower() == "none":
            continue
        
        if (
            isinstance(organizer["organization_id"], dict)
            and "$oid" in organizer["organization_id"]
        ):
            organizer["organization_id"] = ObjectId(
                organizer["organization_id"]["$oid"]
            )
            
        elif isinstance(organizer["organization_id"], str):
            organizer["organization_id"] = ObjectId(organizer["organization_id"])

    return data
