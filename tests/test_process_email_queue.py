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
def test_process_email_queue_continues_after_send_failure(db, monkeypatch):
    from mielenosoitukset_fi.scripts.process_email_queue import run

    db.email_queue.delete_many({})
    db.email_queue.insert_many(
        [
            _queued_email(
                "Broken first", ["broken@example.test"], _id=ObjectId("5c0000000000000000000001")
            ),
            _queued_email(
                "Healthy second", ["ok@example.test"], _id=ObjectId("5c0000000000000000000002")
            ),
        ]
    )

    sent = _patch_sender(monkeypatch, fail_first=1)

    processed = run(max_jobs=10)

    assert processed == 1
    assert [job["subject"] for job in sent] == ["Healthy second"]
    assert db.email_queue.count_documents({}) == 0


@pytest.mark.integration
@pytest.mark.jobs
def test_process_email_queue_is_idempotent_on_empty_queue(db, monkeypatch):
    from mielenosoitukset_fi.scripts.process_email_queue import run

    db.email_queue.delete_many({})

    sent = _patch_sender(monkeypatch)

    assert run(max_jobs=10) == 0
    assert sent == []