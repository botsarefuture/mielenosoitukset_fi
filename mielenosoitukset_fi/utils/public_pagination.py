"""Shared ordering and page metadata for public demonstration APIs."""

# ISO dates and normalized HH:MM start times sort chronologically. _id owns
# ties, including legacy documents without a start time, before skip/limit.
PUBLIC_DEMONSTRATION_ORDER = [("date", 1), ("start_time", 1), ("_id", 1)]
PUBLIC_DEMONSTRATION_INDEX = "public_demo_chronological"


def ensure_public_demo_pagination_index(database):
    """Support approved public date ranges without a blocking in-memory sort.

    approved is an equality predicate; the remaining keys match the complete
    order before skip/limit. Visibility exclusions stay in the query because
    missing/legacy hide and rejected flags are intentionally supported.
    """
    database.demonstrations.create_index(
        [("approved", 1), *PUBLIC_DEMONSTRATION_ORDER],
        name=PUBLIC_DEMONSTRATION_INDEX,
        background=True,
    )


def public_page_args(args, default_per_page=20):
    """Normalize each numeric argument independently without changing filters."""
    def positive_int(name, default):
        try:
            return max(int(args.get(name) or default), 1)
        except (TypeError, ValueError):
            return default

    return positive_int("page", 1), positive_int("per_page", default_per_page)


def public_page_metadata(page, per_page, total, result_count):
    """Describe the same filtered query used to retrieve the current page."""
    start = (page - 1) * per_page + 1 if result_count else 0
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max((total + per_page - 1) // per_page, 1),
        "result_start": start,
        "result_end": start + result_count - 1 if result_count else 0,
    }
