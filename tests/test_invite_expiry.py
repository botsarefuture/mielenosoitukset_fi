"""SEC-04: organization invitations expire after 30 days when dated."""

from datetime import datetime, timedelta, timezone

from mielenosoitukset_fi.users.BPs.orgs import _get_invited_emails
from mielenosoitukset_fi.utils.invitations import invitation_expired

NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


def test_dated_invitation_expires_after_thirty_days():
    fresh = {"email": "a@x.test", "invited_at": NOW - timedelta(days=29)}
    stale = {"email": "a@x.test", "invited_at": NOW - timedelta(days=31)}
    assert not invitation_expired(fresh, NOW)
    assert invitation_expired(stale, NOW)


def test_naive_stored_datetime_is_read_as_utc():
    stale = {"email": "a@x.test", "invited_at": datetime(2026, 1, 1)}
    assert invitation_expired(stale, NOW)


def test_legacy_invitations_never_expire():
    assert not invitation_expired("old@x.test", NOW)
    assert not invitation_expired({"email": "old@x.test", "role": "member"}, NOW)
    assert not invitation_expired({"email": "a@x.test", "invited_at": None}, NOW)


def test_expired_invitation_is_not_acceptable():
    old = datetime.now(timezone.utc) - timedelta(days=40)
    invitations = [
        "legacy@x.test",
        {"email": "undated@x.test"},
        {"email": "fresh@x.test", "invited_at": datetime.now(timezone.utc)},
        {"email": "stale@x.test", "invited_at": old},
    ]
    assert _get_invited_emails(invitations) == [
        "legacy@x.test",
        "undated@x.test",
        "fresh@x.test",
    ]


def test_has_invite_ignores_expired_invitation(app, db, seeded_data):
    from mielenosoitukset_fi.users.models import User

    org = db.organizations.find_one({"invitations": {"$exists": True, "$ne": []}})
    old = datetime.now(timezone.utc) - timedelta(days=40)
    db.organizations.update_one(
        {"_id": org["_id"]},
        {"$set": {"invitations": [{"email": "bob@example.test", "invited_at": old}]}},
    )
    user = User.from_db(db.users.find_one({"email": "bob@example.test"}))
    with app.app_context():
        assert user.has_invite(org["_id"]) is False
        db.organizations.update_one(
            {"_id": org["_id"]},
            {"$set": {"invitations": [{"email": "bob@example.test"}]}},
        )
        assert user.has_invite(org["_id"]) is True
