"""Shared server-rendered pagination state for admin collection views."""

from flask import url_for


ADMIN_PAGE_SIZES = (20, 50, 100)


def parse_admin_pagination(args, *, default_per_page=20):
    """Normalize page and page-size query values against the shared allowlist."""
    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        requested_per_page = int(args.get("per_page", default_per_page))
    except (TypeError, ValueError):
        requested_per_page = default_per_page
    per_page = (
        requested_per_page
        if requested_per_page in ADMIN_PAGE_SIZES
        else default_per_page
    )
    return page, per_page


def build_admin_pagination(endpoint, *, total_count, page, per_page, query_args=None):
    """Build the canonical template context and stable slice for a collection."""
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    current_page = min(max(page, 1), total_pages)
    range_start = (current_page - 1) * per_page + 1 if total_count else 0
    range_end = min(current_page * per_page, total_count)
    preserved = {
        key: value
        for key, value in (query_args or {}).items()
        if value not in (None, "")
    }
    preserved["per_page"] = per_page

    def page_url(target_page):
        return url_for(endpoint, **preserved, page=target_page)

    window_start = max(1, current_page - 2)
    window_end = min(total_pages, current_page + 2)
    visible_pages = [
        {"number": number, "url": page_url(number)}
        for number in range(window_start, window_end + 1)
    ]
    previous_page = current_page - 1 if current_page > 1 else None
    next_page = current_page + 1 if current_page < total_pages else None

    return {
        "current_page": current_page,
        "per_page": per_page,
        "total_pages": total_pages,
        "range_start": range_start,
        "range_end": range_end,
        "slice_start": (current_page - 1) * per_page,
        "slice_end": current_page * per_page,
        "prev_page": previous_page,
        "next_page": next_page,
        "prev_page_url": page_url(previous_page) if previous_page else None,
        "next_page_url": page_url(next_page) if next_page else None,
        "visible_pages": visible_pages,
        "first_page_url": page_url(1),
        "last_page_url": page_url(total_pages),
    }
