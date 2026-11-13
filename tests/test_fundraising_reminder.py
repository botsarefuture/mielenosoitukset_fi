"""Fundraising reminder: confirmation mails, the one opening reminder, purge."""
import hashlib
import re
from datetime import datetime, timedelta, timezone

import pytest

from mielenosoitukset_fi.utils import fundraising_reminder as fr

ON = {fr.ENABLED_FLAG: "true"}
APPROVED = {fr.ENABLED_FLAG: "true", fr.APPROVED_FLAG: "true"}
DAY = fr.SEND_AT + timedelta(hours=1)
NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clean(db):
    for name in (fr.COLLECTION, fr.SENT_COLLECTION, "email_queue"):
        db[name].delete_many({})
    yield
    for name in (fr.COLLECTION, fr.SENT_COLLECTION, "email_queue"):
        db[name].delete_many({})


def signup(db, email, status="pending", **extra):
    row = {"email": email, "status": status, "locale": "fi", "results_consent": False,
           "consent_at": NOW, "consent_version": "2026-11-13", "created_at": NOW,
           "confirmation_requested_at": NOW, "confirmation_sent_at": None, "confirmation_count": 0}
    row.update(extra)
    return db[fr.COLLECTION].insert_one(row).inserted_id


def token_in(body, marker):
    return re.search(marker + r"#t=([A-Za-z0-9_-]+)", body).group(1)


def test_confirmation_is_off_by_default(db):
    signup(db, "a@example.test")
    assert fr.send_confirmations(db, environ={}) == {"enabled": False, "queued": 0}
    assert db.email_queue.count_documents({}) == 0


def test_confirmation_queues_plain_text_with_hashed_token(db):
    row_id = signup(db, "a@example.test")
    assert fr.send_confirmations(db, now=NOW, environ=ON)["queued"] == 1
    assert fr.send_confirmations(db, now=NOW, environ=ON)["queued"] == 0  # claimed once

    mail = db.email_queue.find_one({})
    assert mail["recipients"] == ["a@example.test"] and mail["html"] is None
    token = token_in(mail["body"], "muistutus=vahvista")
    unsubscribe = token_in(mail["body"], "muistutus=peru")
    row = db[fr.COLLECTION].find_one({"_id": row_id})
    # Only hashes are stored, never the raw tokens.
    assert row["confirm_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert hashlib.sha256(unsubscribe.encode()).hexdigest() in row["unsubscribe_hashes"]
    assert token not in repr(row) and unsubscribe not in repr(row)
    assert row["confirm_expires_at"].replace(tzinfo=timezone.utc) == NOW + fr.CONFIRM_TTL
    assert mail["extra_headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert f"unsubscribe?t={unsubscribe}" in mail["extra_headers"]["List-Unsubscribe"]


def test_resend_request_queues_a_new_mail_with_a_new_token(db):
    row_id = signup(db, "a@example.test")
    fr.send_confirmations(db, now=NOW, environ=ON)
    first = token_in(db.email_queue.find_one({})["body"], "muistutus=vahvista")
    # What Go does on a second signup 15+ minutes later.
    db[fr.COLLECTION].update_one({"_id": row_id}, {"$set": {"confirmation_sent_at": None}})
    fr.send_confirmations(db, now=NOW + timedelta(hours=1), environ=ON)
    assert db.email_queue.count_documents({}) == 2
    row = db[fr.COLLECTION].find_one({"_id": row_id})
    assert row["confirm_hash"] != hashlib.sha256(first.encode()).hexdigest()
    assert len(row["unsubscribe_hashes"]) == 2  # the first mail's unsubscribe link still works


def test_reminder_dry_run_counts_and_writes_nothing(db):
    signup(db, "a@example.test", "confirmed")
    signup(db, "b@example.test", "confirmed")
    signup(db, "c@example.test", "pending")
    result = fr.send_reminders(db, now=DAY, dry_run=True, environ={})
    assert result["dry_run"] and result["would_send"] == 2 and result["pending"] == 1
    assert db.email_queue.count_documents({}) == 0
    assert db[fr.COLLECTION].count_documents({"reminder_claimed_at": None}) == 3


def test_reminder_needs_flags_approval_and_the_window(db):
    signup(db, "a@example.test", "confirmed")
    assert fr.send_reminders(db, now=DAY, environ={})["sent"] == 0
    assert fr.send_reminders(db, now=DAY, environ=ON)["sent"] == 0  # no approval flag
    assert fr.send_reminders(db, now=fr.SEND_AT - timedelta(minutes=1), environ=APPROVED)["sent"] == 0
    assert fr.send_reminders(db, now=fr.SEND_UNTIL + timedelta(minutes=1), environ=APPROVED)["sent"] == 0
    assert db.email_queue.count_documents({}) == 0


def test_reminder_goes_to_confirmed_only_and_exactly_once(db):
    signup(db, "a@example.test", "confirmed")
    signup(db, "p@example.test", "pending")
    assert fr.send_reminders(db, now=DAY, environ=APPROVED)["sent"] == 1
    assert fr.send_reminders(db, now=DAY, environ=APPROVED)["sent"] == 0
    assert fr.send_reminders(db, now=DAY + timedelta(hours=3), environ=APPROVED)["sent"] == 0
    mails = list(db.email_queue.find({}))
    assert [m["recipients"] for m in mails] == [["a@example.test"]]
    assert "tämä on ainoa viesti" in mails[0]["body"].lower()
    assert token_in(mails[0]["body"], "muistutus=peru")


def test_reminder_survives_a_deleted_queue_row_and_duplicate_rows(db):
    """The marker keeps an address from getting a second mail after the queue drained."""
    signup(db, "a@example.test", "confirmed")
    fr.send_reminders(db, now=DAY, environ=APPROVED)
    db.email_queue.delete_many({})  # drained after sending
    db[fr.COLLECTION].update_one({}, {"$set": {"reminder_claimed_at": None}})  # worst case: claim lost
    assert fr.send_reminders(db, now=DAY, environ=APPROVED) == {"sent": 0, "skipped": 1}
    assert db.email_queue.count_documents({}) == 0


def test_purge_removes_stale_pending_then_everything_after_retention(db):
    signup(db, "old@example.test", created_at=NOW - fr.PENDING_MAX_AGE - timedelta(days=1))
    signup(db, "new@example.test")
    signup(db, "ok@example.test", "confirmed")
    db[fr.SENT_COLLECTION].insert_one({"_id": "x", "created_at": NOW})

    assert fr.purge(db, now=NOW, dry_run=True)["pending_expired"] == 1
    assert db[fr.COLLECTION].count_documents({}) == 3
    assert fr.purge(db, now=NOW)["pending_expired"] == 1
    assert db[fr.COLLECTION].count_documents({}) == 2
    assert db[fr.SENT_COLLECTION].count_documents({}) == 1  # markers stay until retention ends

    just_before = fr.PURGE_AFTER - timedelta(minutes=1)
    assert fr.purge(db, now=just_before)["retention_ended"] == 0
    result = fr.purge(db, now=fr.PURGE_AFTER)
    assert result["retention_ended"] == 1 and result["markers"] == 1
    assert db[fr.COLLECTION].count_documents({}) == 0 and db[fr.SENT_COLLECTION].count_documents({}) == 0


def test_purge_honours_a_later_retain_until(db):
    signup(db, "keep@example.test", "confirmed", retain_until=fr.PURGE_AFTER + timedelta(days=30))
    signup(db, "go@example.test", "confirmed")
    assert fr.purge(db, now=fr.PURGE_AFTER)["retention_ended"] == 1
    assert db[fr.COLLECTION].distinct("email") == ["keep@example.test"]


def test_jobs_are_registered_and_dates_match_the_permit():
    from mielenosoitukset_fi.background_jobs.definitions import JOB_DEFINITION_MAP
    for key in ("deliver_fundraising_reminder_confirmations", "send_fundraising_reminders", "purge_fundraising_reminders"):
        assert key in JOB_DEFINITION_MAP
    helsinki = pytest.importorskip("zoneinfo").ZoneInfo("Europe/Helsinki")
    assert fr.SEND_AT.astimezone(helsinki) == datetime(2026, 11, 16, 0, 0, tzinfo=helsinki)
    assert fr.PURGE_AFTER.date().isoformat() == "2027-03-17"
