from flask import Request
from typing import List


def collect_tags(request: Request) -> List[str]:
    """
    Collect and return a list of tags from the request form data.

    This function extracts all form fields that start with 'tag_' (regardless of index),
    ensuring that gaps in numbering don't prevent tag collection.

    Args:
        request (Request): The incoming Flask request object containing form data.

    Returns:
        List[str]: A list of non-empty, trimmed tags from the form.

    Changelog:
    ----------
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
            tags.append(tag_name)

    return tags