from bson import ObjectId
import pytest


def _queued_email(subject, recipients, _id=None):
    return {
        "_id": _id if _id is not None else ObjectId(),
        "subject": subject,
        "recipients": recipients,
        "body": f"Body for {subject}",
        "html": f"<p>Body for {subject}</p>",
        "sender": None,
        "attachments": [],
        "extra_headers": {},
        "instance_id": "00000000-0000-0000-0000-000000000000",
    }


def _patch_sender(monkeypatch, fail_first=0):
    from mielenosoitukset_fi.scripts import process_email_queue as script

    sent = []
    state = {"calls": 0}

    def fake_send_email(email_job, raise_on_error=False):
        if not raise_on_error:
            raise AssertionError(
                "Drainer must send with raise_on_error=True to surface delivery errors"
            )
        state["calls"] += 1
        if state["calls"] <= fail_first:
            raise RuntimeError("smtp down")
        sent.append({"subject": email_job.subject, "recipients": email_job.recipients})

    monkeypatch.setattr(script._sender, "send_email", fake_send_email)
    return sent


@pytest.mark.integration
@pytest.mark.jobs
def test_process_email_queue_drains_orphaned_jobs_regardless_of_instance(db, monkeypatch):
    from mielenosoitukset_fi.scripts.process_email_queue import run

    db.email_queue.delete_many({})
    db.email_queue.insert_many(
        [
            _queued_email("Admin reply A", ["a@example.test"]),
            _queued_email("Auto reply B", ["b@example.test"]),
            _queued_email("Confirmation C", ["c@example.test"]),
        ]
    )

    sent = _patch_sender(monkeypatch)

    processed = run(max_jobs=10)

    assert processed == 3
    assert sorted(job["subject"] for job in sent) == [
        "Admin reply A",
        "Auto reply B",
        "Confirmation C",
    ]
    assert db.email_queue.count_documents({}) == 0


@pytest.mark.integration
@pytest.mark.jobs
def test_process_email_queue_keeps_failed_job_for_retry(db, monkeypatch):
    from mielenosoitukset_fi.scripts.process_email_queue import run

    db.email_queue.delete_many({})
    broken_id = ObjectId("5c0000000000000000000001")
    db.email_queue.insert_many(
        [
            _queued_email("Broken first", ["broken@example.test"], _id=broken_id),
            _queued_email(
                "Healthy second", ["ok@example.test"], _id=ObjectId("5c0000000000000000000002")
            ),
        ]
    )

    sent = _patch_sender(monkeypatch, fail_first=1)

    processed = run(max_jobs=10)

    # The healthy job is sent and deleted; the broken one must be kept for
    # a later retry (no delete-before-send data loss).
    assert processed == 1
    assert [job["subject"] for job in sent] == ["Healthy second"]
    remaining = list(db.email_queue.find({}))
    assert len(remaining) == 1
    assert remaining[0]["_id"] == broken_id
    assert remaining[0]["status"] == "failed"
    assert remaining[0]["attempts"] == 1
    assert remaining[0]["last_error"]
    error_log = db.admin_logs.find_one(
        {
            "event": "email_delivery_failed",
            "details.job_id": str(broken_id),
        }
    )
    assert error_log["level"] == "error"
    assert error_log["details"]["error"] == "smtp down"
    assert error_log["details"]["recipient_count"] == 1
    assert "broken@example.test" not in str(error_log)
    assert "Broken" not in str(error_log)


@pytest.mark.integration
@pytest.mark.jobs
def test_process_email_queue_retries_failed_job_on_later_run(db, monkeypatch):
    from datetime import datetime, timezone, timedelta

    from mielenosoitukset_fi.scripts.process_email_queue import run

    db.email_queue.delete_many({})
    db.email_queue.insert_one(
        _queued_email("Flaky reply", ["flaky@example.test"], _id=ObjectId("5c0000000000000000000001"))
    )

    sent = _patch_sender(monkeypatch, fail_first=1)

    # First run: SMTP down, job marked failed and kept.
    processed = run(max_jobs=10)
    assert processed == 0
    assert sent == []
    remaining = db.email_queue.find_one({})
    assert remaining["status"] == "failed"
    assert remaining["attempts"] == 1

    # Simulate the retry cooldown elapsing.
    db.email_queue.update_one(
        {},
        {"$set": {"last_attempt_at": datetime.now(timezone.utc) - timedelta(hours=1)}},
    )

    # Second run: SMTP is back. The failed job must be picked up and delivered.
    processed = run(max_jobs=10)
    assert processed == 1
    assert [job["subject"] for job in sent] == ["Flaky reply"]
    assert db.email_queue.count_documents({}) == 0


@pytest.mark.integration
@pytest.mark.jobs
def test_process_email_queue_is_idempotent_on_empty_queue(db, monkeypatch):
    from mielenosoitukset_fi.scripts.process_email_queue import run

    db.email_queue.delete_many({})

    sent = _patch_sender(monkeypatch)

    assert run(max_jobs=10) == 0
    assert sent == []


def _case_with_outbound(mid):
    return {
        "_id": ObjectId("5c000000000000000000000a"),
        "type": "support_ticket",
        "running_num": 1,
        "submitter": {"submitter_email": "x@example.test"},
        "suggestion": {
            "messages": [
                {"message_id": mid, "direction": "out", "message": "Hi", "status": "queued"}
            ]
        },
        "meta": {"ticket": {"reply_message_ids": [mid]}},
    }


@pytest.mark.integration
@pytest.mark.jobs
def test_process_email_queue_records_delivery_status_on_case(db, monkeypatch):
    from mielenosoitukset_fi.scripts.process_email_queue import run

    db.email_queue.delete_many({})
    db.cases.delete_many({})

    mid = "<abc123@mielenosoitukset.fi>"
    db.cases.insert_one(_case_with_outbound(mid))

    job = _queued_email("Admin reply", ["x@example.test"])
    job["extra_headers"] = {"Message-ID": mid}
    db.email_queue.insert_one(job)

    _patch_sender(monkeypatch)
    processed = run(max_jobs=10)

    assert processed == 1
    reopened = db.cases.find_one({"_id": ObjectId("5c000000000000000000000a")})
    message = reopened["suggestion"]["messages"][0]
    assert message["status"] == "sent"
    assert "sent_at" in message
    # The queued job itself is deleted only after successful delivery.
    assert db.email_queue.count_documents({}) == 0


@pytest.mark.integration
@pytest.mark.jobs
def test_process_email_queue_records_failure_status_on_case(db, monkeypatch):
    from mielenosoitukset_fi.scripts.process_email_queue import run

    db.email_queue.delete_many({})
    db.cases.delete_many({})

    mid = "<abc123@mielenosoitukset.fi>"
    db.cases.insert_one(_case_with_outbound(mid))

    job = _queued_email("Admin reply", ["x@example.test"])
    job["extra_headers"] = {"Message-ID": mid}
    db.email_queue.insert_one(job)

    _patch_sender(monkeypatch, fail_first=99)
    processed = run(max_jobs=10)

    assert processed == 0
    reopened = db.cases.find_one({"_id": ObjectId("5c000000000000000000000a")})
    message = reopened["suggestion"]["messages"][0]
    assert message["status"] == "failed"
    assert message["error"]
    # The job is retained (not deleted) so it can be retried later.
    assert db.email_queue.count_documents({}) == 1


@pytest.mark.integration
@pytest.mark.jobs
def test_process_email_queue_reopens_exhausted_legacy_ticket_job(db, monkeypatch):
    from datetime import datetime, timezone, timedelta

    from mielenosoitukset_fi.scripts.process_email_queue import run

    db.email_queue.delete_many({})
    db.email_queue.insert_one(
        {
            "_id": ObjectId("5c0000000000000000000001"),
            "subject": "Legacy ticket reply",
            "recipients": ["ticket@example.test"],
            "body": "Body for legacy ticket reply",
            "html": "<p>Body for legacy ticket reply</p>",
            "sender": {
                "email_server": "",
                "email_port": 587,
                "username": "",
                "password": "",
                "use_tls": True,
                "email_address": "",
            },
            "attachments": [],
            "extra_headers": {},
            "instance_id": "00000000-0000-0000-0000-000000000000",
            "status": "failed",
            "attempts": 30,
            "last_attempt_at": datetime.now(timezone.utc) - timedelta(hours=1),
        }
    )

    sent = _patch_sender(monkeypatch)

    processed = run(max_jobs=10)

    assert processed == 1
    assert [job["subject"] for job in sent] == ["Legacy ticket reply"]
    assert db.email_queue.count_documents({}) == 0


@pytest.mark.integration
@pytest.mark.jobs
def test_process_email_queue_does_not_reopen_real_sender_exhausted_jobs(db, monkeypatch):
    from datetime import datetime, timezone, timedelta

    from mielenosoitukset_fi.scripts.process_email_queue import run

    db.email_queue.delete_many({})
    db.email_queue.insert_one(
        {
            "_id": ObjectId("5c0000000000000000000001"),
            "subject": "Real sender job",
            "recipients": ["user@example.test"],
            "body": "Body for real sender job",
            "html": "<p>Body for real sender job</p>",
            "sender": {
                "email_server": "smtp.example.test",
                "email_port": 587,
                "username": "user",
                "password": "secret",
                "use_tls": True,
                "email_address": "no-reply@example.test",
            },
            "attachments": [],
            "extra_headers": {},
            "instance_id": "00000000-0000-0000-0000-000000000000",
            "status": "failed",
            "attempts": 30,
            "last_attempt_at": datetime.now(timezone.utc) - timedelta(hours=1),
        }
    )

    sent = _patch_sender(monkeypatch)

    processed = run(max_jobs=10)

    assert processed == 0
    assert sent == []
    remaining = db.email_queue.find_one({})
    assert remaining["attempts"] == 30


@pytest.mark.integration
@pytest.mark.jobs
def test_process_email_queue_redacts_recipients_in_delivery_errors(db, monkeypatch):
    import smtplib

    from mielenosoitukset_fi.scripts import process_email_queue as script
    from mielenosoitukset_fi.scripts.process_email_queue import run

    db.email_queue.delete_many({})
    broken_id = ObjectId("5c0000000000000000000001")
    db.email_queue.insert_one(
        _queued_email("Admin reply", ["refused@example.test"], _id=broken_id)
    )

    def refused_send(email_job, raise_on_error=False):
        if not raise_on_error:
            raise AssertionError(
                "Drainer must send with raise_on_error=True to surface delivery errors"
            )
        raise smtplib.SMTPRecipientsRefused(
            {"refused@example.test": (550, b"No such user here")}
        )

    monkeypatch.setattr(script._sender, "send_email", refused_send)

    processed = run(max_jobs=10)

    assert processed == 0
    job = db.email_queue.find_one({"_id": broken_id})
    assert "refused@example.test" not in job["last_error"]
    assert "[redacted]" in job["last_error"]
    error_log = db.admin_logs.find_one(
        {
            "event": "email_delivery_failed",
            "details.job_id": str(broken_id),
        }
    )
    assert error_log["details"]["error"] == job["last_error"]
    assert "refused@example.test" not in str(error_log)
