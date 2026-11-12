"""Expiry rules for organization invitations."""

from datetime import datetime, timedelta, timezone

INVITE_LIFETIME = timedelta(days=30)


def invitation_expired(invitation, now=None) -> bool:
    """True when an invitation carries ``invited_at`` older than 30 days.

    Legacy invitations (plain e-mail strings, or dicts without ``invited_at``)
    never expire, so nothing sent before this field existed stops working.
    """
    if not isinstance(invitation, dict):
        return False
    invited_at = invitation.get("invited_at")
    if not isinstance(invited_at, datetime):
        return False
    if invited_at.tzinfo is None:
        invited_at = invited_at.replace(tzinfo=timezone.utc)
    return (now or datetime.now(timezone.utc)) - invited_at > INVITE_LIFETIME
