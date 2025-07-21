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


def rlace(item: object, old: str, new: str = ""):
    item = item.replace(old, new)


def collect_tags(request: Request) -> List[str]:
    """
    Collect and return a list of tags from the request form data.

    This function supports both:
    - Old style: form fields named like 'tag_1', 'tag_2', etc.
    - New style: multiple tags sent as 'tags[]' array.

    It extracts all tags, trims whitespace, removes '#' characters,
    and skips empty or whitespace-only tags.

    Parameters
    ----------
    request : Request
        The incoming Flask request object containing form data.

    Returns
    -------
    List[str]
        A list of non-empty, cleaned tags from the form.

    Examples
    --------
    >>> from flask import Request
    >>> # Old style
    >>> request = Request.from_values(form={'tag_1': 'python', 'tag_2': 'flask', 'tag_3': '  '})
    >>> collect_tags(request)
    ['python', 'flask']
    >>> # New style
    >>> request = Request.from_values(form={'tags[]': ['palestiina', '#climate']})
    >>> collect_tags(request)
    ['palestiina', 'climate']

    Changelog
    ---------
    v2.4.0:
        - Added dynamic collection of all `tag_` prefixed fields.
        - Introduced sorting of `tag_` keys by numerical index to handle gaps in numbering.
        - Enhanced handling of empty or whitespace-only tags by skipping them.
    v4.0.0:
        - Added support for new tag array input format using 'tags[]'.
        - Maintained backward compatibility with old 'tag_N' style inputs.
    """
    tags = []

    # New style: collect tags from tags[] array
    raw_tags = request.form.getlist("tags[]")
    for tag in raw_tags:
        cleaned_tag = tag.strip().replace("#", "")
        if cleaned_tag:
            tags.append(cleaned_tag)

    # Old style: collect tags from keys like tag_1, tag_2...
    tag_keys = sorted(
        (key for key in request.form if key.startswith("tag_")),
        key=lambda k: int(k.split("_")[1]) if k.split("_")[1].isdigit() else 0,
    )
    for key in tag_keys:
        tag_name = request.form.get(key, "").strip().replace("#", "")
        if tag_name:
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
        org_id = organizer["organization_id"]
        if org_id is None or (isinstance(org_id, str) and org_id.lower() == "none"):
            organizer["organization_id"] = None
            continue
        if isinstance(org_id, dict) and "$oid" in org_id:
            organizer["organization_id"] = ObjectId(org_id["$oid"])
        elif isinstance(org_id, str):
            organizer["organization_id"] = ObjectId(org_id)
    return data
