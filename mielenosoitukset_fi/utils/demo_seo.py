"""Shared date rules for public demonstration search discovery."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any


SITEMAP_PAST_DAYS = 365
SITEMAP_FUTURE_DAYS = 365 * 2


def parse_demo_date(value: Any) -> date | None:
    """Return a date for the storage formats used by demonstrations."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except (TypeError, ValueError):
            return None
    return None


def sitemap_date_window(reference_date: date | None = None) -> tuple[date, date]:
    """Return the inclusive date window used for public demo discovery."""
    today = reference_date or date.today()
    return (
        today - timedelta(days=SITEMAP_PAST_DAYS),
        today + timedelta(days=SITEMAP_FUTURE_DAYS),
    )


def demo_date_is_in_sitemap_window(
    value: Any,
    reference_date: date | None = None,
) -> bool:
    """Whether a demonstration date belongs to the sitemap's date window."""
    demo_date = parse_demo_date(value)
    if demo_date is None:
        return False
    start_date, end_date = sitemap_date_window(reference_date)
    return start_date <= demo_date <= end_date


def demo_is_beyond_future_horizon(
    value: Any,
    reference_date: date | None = None,
) -> bool:
    """Whether a demo must be noindexed because it is beyond discovery horizon.

    Invalid dates fail closed. Historical pages remain indexable even after they
    leave the sitemap's deliberately shorter one-year history window.
    """
    demo_date = parse_demo_date(value)
    if demo_date is None:
        return True
    _, end_date = sitemap_date_window(reference_date)
    return demo_date > end_date


def demo_sitemap_priority(value: Any, reference_date: date | None = None) -> str:
    """Return a monotonic sitemap hint: dates closest to today score highest.

    Search engines may ignore this optional sitemap field. The value remains useful
    to consumers that honor the protocol hint and never replaces canonical/noindex
    controls. Sitemap dates have day precision, so events on the same date tie.
    """
    today = reference_date or date.today()
    demo_date = parse_demo_date(value)
    if demo_date is None:
        return "0.5"

    distance_days = min(abs((demo_date - today).days), SITEMAP_FUTURE_DAYS)
    priority = 1.0 - (0.5 * distance_days / SITEMAP_FUTURE_DAYS)
    return f"{priority:.3f}".rstrip("0").rstrip(".")


def occurrence_end_at(document: dict[str, Any], timezone) -> datetime | None:
    """Return the local end instant used to decide whether an occurrence is over."""
    occurrence_date = parse_demo_date(document.get("date"))
    if occurrence_date is None:
        return None

    raw_end = document.get("end_time") or document.get("start_time")
    end_time = time(23, 59, 59)
    if raw_end:
        for pattern in ("%H:%M:%S", "%H:%M"):
            try:
                end_time = datetime.strptime(str(raw_end), pattern).time()
                break
            except ValueError:
                continue
    return datetime.combine(occurrence_date, end_time, tzinfo=timezone)


def select_relevant_occurrence(
    documents: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any] | None:
    """Select the next active occurrence, or the latest past one as fallback."""
    valid_documents = [
        document for document in documents if occurrence_end_at(document, now.tzinfo)
    ]
    if not valid_documents:
        return None

    ordered = sorted(
        valid_documents,
        key=lambda document: (
            str(document.get("date") or ""),
            str(document.get("start_time") or ""),
            str(document.get("_id") or ""),
        ),
    )
    for document in ordered:
        if document.get("cancelled"):
            continue
        if occurrence_end_at(document, now.tzinfo) >= now:
            return document

    non_cancelled = [document for document in ordered if not document.get("cancelled")]
    return (non_cancelled or ordered)[-1]
