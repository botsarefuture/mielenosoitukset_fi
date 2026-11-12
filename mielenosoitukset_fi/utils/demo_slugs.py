"""Canonical helpers for administrator-managed demonstration slugs."""

import re
import unicodedata


_NON_SLUG_CHARACTERS = re.compile(r"[^a-z0-9]+")


def normalize_demo_slug(value):
    """Return a lowercase, URL-safe slug or ``None`` for an empty value."""
    raw_value = (value or "").strip()
    if not raw_value:
        return None

    ascii_value = (
        unicodedata.normalize("NFKD", raw_value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    normalized = _NON_SLUG_CHARACTERS.sub("-", ascii_value).strip("-")
    normalized = normalized[:160].rstrip("-")
    return normalized or None


def demo_slug_is_available(collection, slug, *, exclude_id=None):
    """Check whether ``slug`` is unused in a MongoDB collection."""
    if not slug:
        return True

    query = {"slug": slug}
    if exclude_id is not None:
        query["_id"] = {"$ne": exclude_id}
    return collection.find_one(query, {"_id": 1}) is None


def recurring_child_slug(parent_slug, occurrence_date):
    """Build the stable public slug for one occurrence of a recurring series."""
    normalized_parent = normalize_demo_slug(parent_slug)
    normalized_date = str(occurrence_date or "").strip()
    if not normalized_parent or not normalized_date:
        return None
    return f"{normalized_parent}-{normalized_date}"
