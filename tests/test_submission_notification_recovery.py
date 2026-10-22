"""Real Mongo queue transitions; SMTP is a double and never sends real mail."""

from datetime import datetime, timedelta
import smtplib

from bson import ObjectId
import pytest


@pytest.fixture
def worker(db, monkeypatch):
    from mielenosoitukset_fi.scripts import process_submission_notifications as script

    db.demo_notifications_queue.delete_many({})
    clock = [datetime(2026, 10, 22, 12)]
    monkeypatch.setattr(script, "utcnow", lambda: clock[0])
    monkeypatch.setattr(script, "merge_duplicate_submissions", lambda **kwargs: 0)
    monkeypatch.setattr(script, "_enqueue_admin_reminders", lambda db: None)
    sent = []
    monkeypatch.setattr(script.email_sender, "send_email", lambda job, **kwargs: sent.append(job.subject) or True)
    demo_id = db.demonstrations.insert_one({"approved": False, "city": "Helsinki"}).inserted_id
    job_id = db.demo_notifications_queue.insert_one({
        "demo_id": demo_id, "status": "pending", "created_at": clock[0],
        "notification_type": "initial_submission", "marks_admin_contact": True,
        "messages": [{"template_name": "admin_demo_approve_notification.html",
                      "subject": subject, "recipients": ["admin@example.test"], "context": {}}
                     for subject in ("first", "second")],
    }).inserted_id
    return script, clock, sent, job_id, demo_id


def test_retry_resumes_after_recorded_delivery_and_observes_cooldown(db, monkeypatch, worker):
    script, clock, sent, job_id, demo_id = worker

    def deliver(job, **kwargs):
        sent.append(job.subject)
        if len(sent) == 2:
            raise smtplib.SMTPDataError(451, b"temporary rejection")
        return True

    monkeypatch.setattr(script.email_sender, "send_email", deliver)
    script.run(max_jobs=25)
    job = db.demo_notifications_queue.find_one({"_id": job_id})
    assert job["status"] == "error"
    assert job["attempts"] == 1
    assert job["delivered_indices"] == [0]
    assert db.demonstrations.find_one({"_id": demo_id}).get("admin_notification_last_sent_at") is None
    clock[0] += timedelta(seconds=59)
    script.run()
    assert sent == ["first", "second"]
    clock[0] += timedelta(seconds=1)
    script.run()
    job = db.demo_notifications_queue.find_one({"_id": job_id})
    assert sent == ["first", "second", "second"]
    assert job["status"] == "completed"
    assert job["messages_sent"] == 2
    assert job["attempts"] == 2
    assert "error" not in job and "claim_token" not in job
    assert db.demonstrations.find_one({"_id": demo_id})["admin_notification_last_sent_at"] == clock[0]


def test_retries_are_bounded_and_reminders_do_not_bypass_cooldown(db, monkeypatch, worker):
    script, clock, sent, job_id, demo_id = worker

    def reject(*args, **kwargs):
        raise smtplib.SMTPConnectError(421, "private@example.test /token/secret")

    monkeypatch.setattr(script.email_sender, "send_email", reject)
    for attempt in range(1, script.MAX_ATTEMPTS + 1):
        script.run()
        job = db.demo_notifications_queue.find_one({"_id": job_id})
        assert job["attempts"] == attempt
        assert job["error"] == "SMTPConnectError"
        assert script._pending_admin_job_exists(db.demo_notifications_queue, demo_id, clock[0] - timedelta(hours=24))
        clock[0] = job["next_attempt_at"]
    script.run()
    assert db.demo_notifications_queue.find_one({"_id": job_id})["attempts"] == script.MAX_ATTEMPTS
    clock[0] += timedelta(hours=25)
    assert not script._pending_admin_job_exists(db.demo_notifications_queue, demo_id, clock[0] - timedelta(hours=24))


@pytest.mark.parametrize("age,sending,expected", [
    (599, False, "processing"), (600, False, "completed"),
    (600, True, "delivery_unknown"),
])
def test_stale_claim_recovery_distinguishes_smtp_ambiguity(db, worker, age, sending, expected):
    script, clock, sent, job_id, demo_id = worker
    fields = {"status": "processing", "claim_token": "old-worker", "attempts": 1,
              "delivery_tracking_version": 1,
              "processing_started_at": clock[0] - timedelta(seconds=age)}
    if sending:
        fields["sending_index"] = 0
    db.demo_notifications_queue.update_one({"_id": job_id}, {"$set": fields})
    script.run()
    job = db.demo_notifications_queue.find_one({"_id": job_id})
    assert job["status"] == expected
    assert sent == (["first", "second"] if expected == "completed" else [])
    if expected == "delivery_unknown":
        assert "claim_token" not in job
        assert script._pending_admin_job_exists(db.demo_notifications_queue, demo_id, clock[0])


def test_ambiguous_smtp_failure_is_not_automatically_replayed(db, monkeypatch, worker):
    script, clock, sent, job_id, demo_id = worker

    def uncertain(job, **kwargs):
        sent.append(job.subject)
        raise smtplib.SMTPServerDisconnected("private@example.test /token/secret")

    monkeypatch.setattr(script.email_sender, "send_email", uncertain)
    script.run()
    clock[0] += timedelta(days=2)
    script.run()
    job = db.demo_notifications_queue.find_one({"_id": job_id})
    assert job["status"] == "delivery_unknown"
    assert job["error"] == "SMTPServerDisconnected"
    assert sent == ["first"]
    assert job.get("delivered_indices", []) == []


def test_lost_owner_cannot_acknowledge_or_send_the_next_message(db, monkeypatch, worker):
    script, clock, sent, job_id, demo_id = worker

    def replace_owner(job, **kwargs):
        sent.append(job.subject)
        db.demo_notifications_queue.update_one({"_id": job_id}, {"$set": {"claim_token": "replacement"}})
        return True

    monkeypatch.setattr(script.email_sender, "send_email", replace_owner)
    script.run()
    job = db.demo_notifications_queue.find_one({"_id": job_id})
    assert sent == ["first"]
    assert job["claim_token"] == "replacement"
    assert job["status"] == "processing"
    assert job.get("delivered_indices", []) == []
    assert db.demonstrations.find_one({"_id": demo_id}).get("admin_notification_last_sent_at") is None


@pytest.mark.parametrize("state", ["approved", "rejected", "cancelled", "in_past", "deleted"])
def test_resolved_moderation_is_not_replayed(db, worker, state):
    script, clock, sent, job_id, demo_id = worker
    if state == "deleted":
        db.demonstrations.delete_one({"_id": demo_id})
    else:
        db.demonstrations.update_one({"_id": demo_id}, {"$set": {state: True}})
    script.run()
    assert sent == []
    assert db.demo_notifications_queue.find_one({"_id": job_id})["status"] == "cancelled"


@pytest.mark.parametrize("state", ["active", "revoked", "escalated", "cleared"])
def test_city_retry_intersects_current_grants_and_original_recipients(db, monkeypatch, worker, state):
    script, clock, sent, job_id, demo_id = worker
    assigned_id, new_id = ObjectId(), ObjectId()
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"city_assignment": {
        "city_key": "helsinki", "city_admin_ids": [assigned_id], "escalated": state == "escalated",
    }}})
    if state == "cleared":
        db.demonstrations.update_one({"_id": demo_id}, {"$unset": {"city_assignment": ""}})
    job = db.demo_notifications_queue.find_one({"_id": job_id})
    messages = job["messages"]
    for message in messages:
        message["recipients"] = ["revoked@example.test", "kept@example.test"]
    db.demo_notifications_queue.update_one({"_id": job_id}, {"$set": {
        "notification_type": "city_assignment", "marks_admin_contact": False, "messages": messages,
    }})
    admins = [
        {"user_id": assigned_id, "email": "kept@example.test"},
        {"user_id": new_id, "email": "new@example.test"},
    ] if state != "revoked" else []
    monkeypatch.setattr(script, "active_city_admins_for_city", lambda db, city: admins)
    recipients = []
    monkeypatch.setattr(script.email_sender, "send_email", lambda job, **kwargs: recipients.append(job.recipients) or True)
    script.run()
    assert recipients == ([["kept@example.test"], ["kept@example.test"]] if state == "active" else [])
    expected = "completed" if state == "active" else "cancelled"
    assert db.demo_notifications_queue.find_one({"_id": job_id})["status"] == expected


def test_failed_database_acknowledgement_quarantines_possible_delivery(db, monkeypatch, worker):
    script, clock, sent, job_id, demo_id = worker
    real_update = script._owned_update

    def fail_receipt(queue, owner, update):
        if "$addToSet" in update:
            raise RuntimeError("database write unavailable")
        return real_update(queue, owner, update)

    monkeypatch.setattr(script, "_owned_update", fail_receipt)
    script.run()
    script.run()
    job = db.demo_notifications_queue.find_one({"_id": job_id})
    assert sent == ["first"]
    assert job["status"] == "delivery_unknown"
    assert job["sending_index"] == 0


@pytest.mark.parametrize("status", ["error", "processing"])
def test_legacy_unreceipted_failures_need_reconciliation(db, worker, status):
    script, clock, sent, job_id, demo_id = worker
    db.demo_notifications_queue.update_one({"_id": job_id}, {"$set": {
        "status": status, "processing_started_at": clock[0] - timedelta(hours=1),
    }})
    script.run()
    assert sent == []
    assert db.demo_notifications_queue.find_one({"_id": job_id})["status"] == "delivery_unknown"
