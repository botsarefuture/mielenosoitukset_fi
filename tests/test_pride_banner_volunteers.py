"""Pride banner carrier signup: confirmation mails, retention, export."""
import csv
import hashlib
import io
import re
from datetime import datetime, timedelta, timezone

import pytest

from mielenosoitukset_fi.utils import pride_banner_volunteers as pb

ON = {pb.ENABLED_FLAG: "true"}
NOW = datetime(2027, 3, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clean(db):
    for name in (pb.COLLECTION, "email_queue"):
        db[name].delete_many({})
    yield
    for name in (pb.COLLECTION, "email_queue"):
        db[name].delete_many({})


def signup(db, email, status="pending", **extra):
    row = {"email": email, "name": "Aino", "city": "Oulu", "pride": "Oulun Pride", "unsure": False, "note": "",
           "status": status, "locale": "fi", "consent_at": NOW, "consent_version": "2026-11-13", "created_at": NOW,
           "confirmation_requested_at": NOW, "confirmation_sent_at": None, "confirmation_count": 0}
    row.update(extra)
    return db[pb.COLLECTION].insert_one(row).inserted_id


def token_in(body, marker):
    return re.search(marker + r"#t=([A-Za-z0-9_-]+)", body).group(1)


def test_mails_are_off_by_default(db):
    signup(db, "a@example.test")
    assert pb.send_confirmations(db, environ={}) == {"enabled": False, "queued": 0}
    assert db.email_queue.count_documents({}) == 0


def test_confirmation_is_plain_text_hashed_token_and_leaks_no_form_text(db):
    row_id = signup(db, "a@example.test", name="Klikkaa http://evil.example", note="salasana on 1234")
    assert pb.send_confirmations(db, now=NOW, environ=ON)["queued"] == 1
    assert pb.send_confirmations(db, now=NOW, environ=ON)["queued"] == 0  # claimed once

    mail = db.email_queue.find_one({})
    assert mail["kind"] == "pride_banner_volunteer" and mail["recipients"] == ["a@example.test"] and mail["html"] is None
    assert "evil.example" not in mail["body"] and "1234" not in mail["body"] and "Klikkaa" not in mail["body"]
    assert "!" not in mail["body"]
    token = token_in(mail["body"], "kantaja=vahvista")
    unsubscribe = token_in(mail["body"], "kantaja=peru")
    row = db[pb.COLLECTION].find_one({"_id": row_id})
    assert row["confirm_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert hashlib.sha256(unsubscribe.encode()).hexdigest() in row["unsubscribe_hashes"]
    assert token not in repr(row) and unsubscribe not in repr(row)
    assert mail["extra_headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert f"/api/pride-banner/volunteer/unsubscribe?t={unsubscribe}" in mail["extra_headers"]["List-Unsubscribe"]
    # The promise and the retention are in the mail, and nothing about limits.
    assert "ei sido sinua mihinkään" in mail["body"] and "Pride-kauden jälkeen" in mail["body"]
    assert "rajalli" not in mail["body"].lower()


def test_resend_request_queues_a_new_mail_and_keeps_the_old_removal_link(db):
    row_id = signup(db, "a@example.test")
    pb.send_confirmations(db, now=NOW, environ=ON)
    db[pb.COLLECTION].update_one({"_id": row_id}, {"$set": {"confirmation_sent_at": None}})
    pb.send_confirmations(db, now=NOW + timedelta(hours=1), environ=ON)
    assert db.email_queue.count_documents({}) == 2
    assert len(db[pb.COLLECTION].find_one({"_id": row_id})["unsubscribe_hashes"]) == 2


def test_confirmed_and_unrequested_rows_get_no_mail(db):
    signup(db, "c@example.test", "confirmed")
    signup(db, "n@example.test", confirmation_requested_at=None)
    assert pb.send_confirmations(db, now=NOW, environ=ON)["queued"] == 0


def test_purge_removes_stale_pending_then_everything_after_the_season(db):
    signup(db, "old@example.test", created_at=NOW - pb.PENDING_MAX_AGE - timedelta(days=1))
    signup(db, "new@example.test")
    signup(db, "ok@example.test", "confirmed")
    assert pb.purge(db, now=NOW, dry_run=True)["pending_expired"] == 1
    assert db[pb.COLLECTION].count_documents({}) == 3
    assert pb.purge(db, now=NOW)["pending_expired"] == 1
    assert pb.purge(db, now=pb.PURGE_AFTER - timedelta(minutes=1))["retention_ended"] == 0
    # The previous run already removed the stale pending signup; the confirmed one goes with the season.
    assert db[pb.COLLECTION].distinct("email") == ["ok@example.test"]
    assert pb.purge(db, now=pb.PURGE_AFTER) == {"dry_run": False, "pending_expired": 0, "retention_ended": 1}
    assert db[pb.COLLECTION].count_documents({}) == 0


def test_purge_honours_a_later_retain_until(db):
    signup(db, "keep@example.test", "confirmed", retain_until=pb.PURGE_AFTER + timedelta(days=30))
    signup(db, "go@example.test", "confirmed")
    assert pb.purge(db, now=pb.PURGE_AFTER)["retention_ended"] == 1
    assert db[pb.COLLECTION].distinct("email") == ["keep@example.test"]


def test_export_lists_confirmed_only_and_neutralises_formulas(db):
    signup(db, "c@example.test", "confirmed", name="=HYPERLINK(1)", confirmed_at=NOW)
    signup(db, "p@example.test")
    rows = list(csv.reader(io.StringIO(pb.export_confirmed(db))))
    assert rows[0][:2] == ["name", "email"] and len(rows) == 2
    assert rows[1][0] == "'=HYPERLINK(1)" and rows[1][1] == "c@example.test"


def test_jobs_are_registered_and_the_retention_date_is_after_the_season():
    from mielenosoitukset_fi.background_jobs.definitions import JOB_DEFINITION_MAP
    for key in ("deliver_pride_banner_confirmations", "purge_pride_banner_volunteers"):
        assert key in JOB_DEFINITION_MAP
    assert pb.PURGE_AFTER.date().isoformat() == "2027-10-31"
