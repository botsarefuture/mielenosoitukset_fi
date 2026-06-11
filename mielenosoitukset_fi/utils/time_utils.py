"""Datetime helpers for the application's legacy naive-UTC storage contract."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """
    Return the current UTC time without timezone information.

    Existing MongoDB records use naive UTC datetimes. This keeps that contract
    while using Python's modern timezone-aware UTC clock internally.
    """
    return datetime.now(UTC).replace(tzinfo=None)
