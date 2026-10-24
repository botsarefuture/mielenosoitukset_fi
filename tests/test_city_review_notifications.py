"""Real inbox/queue persistence; SMTP is deliberately replaced, not delivered."""

import smtplib
from datetime import timedelta

import pytest

from tests.conftest import _client_for_user
from tests.test_city_scoped_admin import _create_scoped_admin
from mielenosoitukset_fi.utils import notifications
from mielenosoitukset_fi.utils.time_utils import utcnow


@pytest.fixture
def assignment(app, db, seeded_data):
    user_id = _create_scoped_admin(db, ["helsinki"], ["ACCEPT_DEMO"])
    demo_id = seeded_data["pending_demo_id"]
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {
        "title": "Private city review", "city": "Helsinki", "city_key": "helsinki",
        "city_assignment": {"city_key": "helsinki", "city_admin_ids": [user_id],
                            "assigned_at": utcnow(), "escalated": False},
    }})
    return user_id, demo_id


def test_delivery_deduplicates_and_preserves_read_notice(app, db, assignment):
    user_id, demo_id = assignment
    other = _create_scoped_admin(db, ["helsinki"], ["ACCEPT_DEMO"])
    notifications.notify_city_reviewers(db, str(demo_id))
    notice = db.notifications.find_one({"user_id": user_id})
    assert notice["payload"] == {"demo_id": demo_id, "demo_title": "Private city review"}
    assert notice["link"] == f"/admin/demo/review/{demo_id}"
    assert db.notifications.count_documents({"user_id": other}) == 0
    db.notifications.update_one({"_id": notice["_id"]}, {"$set": {"read": True}})
    notifications.notify_city_reviewers(db, demo_id)
    assert db.notifications.count_documents({"type": "city_review"}) == 1
    assert db.notifications.find_one({"_id": notice["_id"]}) == {**notice, "read": True}
    client = _client_for_user(app, user_id)
    response = client.get("/api/notifications/")
    assert response.status_code == 200
    assert response.json[0]["message"] == "Odottaa hyväksyntää: Private city review"
    assert response.json[0]["read"] is True
    assert client.get(notice["link"]).status_code == 200


@pytest.mark.parametrize("change", [
    "revoked", "disabled", "banned", "missing_user", "wrong_permission",
    "wrong_city", "removed_assignee", "approved", "rejected", "cancelled", "escalated",
    "deleted_demo", "cleared_assignment", "in_past", "missing_email", "conflicting_city_key",
])
def test_inbox_rechecks_scope_and_resolution(app, db, assignment, change):
    user_id, demo_id = assignment
    notifications.notify_city_reviewers(db, demo_id)
    assert len(notifications.fetch_notifications(user_id)) == 1
    if change == "revoked":
        db.admin_scope_grants.update_many({"user_id": user_id}, {"$set": {"revoked_at": utcnow()}})
    elif change in {"disabled", "banned"}:
        db.users.update_one({"_id": user_id}, {"$set": {"active" if change == "disabled" else "banned": change == "banned"}})
    elif change == "missing_user":
        db.users.delete_one({"_id": user_id})
    elif change == "missing_email":
        db.users.update_one({"_id": user_id}, {"$set": {"email": ""}})
    elif change == "deleted_demo":
        db.demonstrations.delete_one({"_id": demo_id})
    elif change == "cleared_assignment":
        db.demonstrations.update_one({"_id": demo_id}, {"$unset": {"city_assignment": ""}})
    elif change == "wrong_permission":
        db.admin_scope_grants.update_many({"user_id": user_id}, {"$set": {"permissions": ["LIST_DEMOS"]}})
    else:
        changes = {
            "wrong_city": {"city": "Turku", "city_key": "turku"},
            "conflicting_city_key": {"city_key": "turku"},
            "removed_assignee": {"city_assignment.city_admin_ids": []},
            "escalated": {"city_assignment.escalated": True},
        }.get(change, {change: True})
        db.demonstrations.update_one({"_id": demo_id}, {"$set": changes})
    assert notifications.fetch_notifications(user_id) == []
    if change == "revoked":
        response = _client_for_user(app, user_id).get("/api/notifications/")
        assert response.status_code == 200 and response.json == []
    db.notifications.delete_many({"type": "city_review"})
    notifications.notify_city_reviewers(db, demo_id)
    assert db.notifications.count_documents({"type": "city_review"}) == 0


def test_notice_does_not_change_other_notification_types(app, db, assignment):
    user_id, _ = assignment
    notifications.create_notification(user_id, "friend_request", {"sender_name": "Friend"}, "/friends")
    doc = notifications.fetch_notifications(user_id)[0]
    with app.test_request_context():
        serialized = notifications.serialize_notification(doc)
    assert serialized["type"] == "friend_request"
    assert serialized["message"].endswith("Friend")
    assert serialized["link"] == "/friends"


@pytest.mark.parametrize("failure", ["smtp", "inbox", "changed_email"])
def test_submission_worker_retries_without_duplicate_inbox_delivery(app, db, assignment, monkeypatch, failure):
    from mielenosoitukset_fi.scripts import process_submission_notifications as worker

    user_id, demo_id = assignment
    monkeypatch.setattr(worker, "merge_duplicate_submissions", lambda **kwargs: None)
    monkeypatch.setattr(worker, "_enqueue_admin_reminders", lambda db: None)
    attempts = []
    original_notify = worker.notify_city_reviewers
    inbox_attempts = []

    def notify(db, demo_id):
        inbox_attempts.append(demo_id)
        if failure == "inbox" and len(inbox_attempts) == 1:
            raise RuntimeError("Test inbox failure")
        original_notify(db, demo_id)

    monkeypatch.setattr(worker, "notify_city_reviewers", notify)

    def send(job, **kwargs):
        attempts.append(job.subject)
        if failure == "smtp" and len(attempts) == 1:
            raise smtplib.SMTPConnectError(421, "Test failure")
        return True

    monkeypatch.setattr(worker.email_sender, "send_email", send)
    job_id = db.demo_notifications_queue.insert_one({
        "demo_id": demo_id, "status": "pending", "created_at": utcnow(),
        "notification_type": "city_assignment", "messages": [{
            "template_name": "admin_demo_city_assignment.html", "subject": "Assigned",
            "recipients": [db.users.find_one({"_id": user_id})["email"]], "context": {},
        }],
    }).inserted_id
    if failure == "changed_email":
        db.users.update_one({"_id": user_id}, {"$set": {"email": "changed@example.test"}})
    worker.run(max_jobs=1)
    if failure == "changed_email":
        assert db.demo_notifications_queue.find_one({"_id": job_id})["status"] == "cancelled"
        assert len(notifications.fetch_notifications(user_id)) == 1
        assert attempts == []  # never send to the stale address
        return
    assert db.demo_notifications_queue.find_one({"_id": job_id})["status"] == "error"
    assert db.notifications.count_documents({"user_id": user_id}) == (1 if failure == "smtp" else 0)
    if failure == "inbox":
        assert attempts == []  # no email acknowledged while inbox persistence failed
    notifications.mark_all_read(user_id)
    db.demo_notifications_queue.update_one({"_id": job_id}, {"$set": {"next_attempt_at": utcnow() - timedelta(seconds=1)}})
    worker.run(max_jobs=1)
    assert db.demo_notifications_queue.find_one({"_id": job_id})["status"] == "completed"
    assert attempts == (["Assigned", "Assigned"] if failure == "smtp" else ["Assigned"])
    assert db.notifications.count_documents({"user_id": user_id}) == 1
    assert notifications.fetch_notifications(user_id)[0]["read"] is (failure == "smtp")


def test_multiple_assigned_reviewers_and_duplicate_legacy_grants(app, db, assignment):
    first, demo_id = assignment
    second = _create_scoped_admin(db, ["helsinki"], ["ACCEPT_DEMO"])
    foreign = _create_scoped_admin(db, ["turku"], ["ACCEPT_DEMO"])
    db.admin_scope_grants.insert_one({
        "user_id": first, "scope_type": "city", "scope_key": "helsinki",
        "permissions": ["ACCEPT_DEMO"],
    })
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {
        "city_assignment.city_admin_ids": [first, first, second, foreign],
    }})
    notifications.notify_city_reviewers(db, demo_id)
    assert {doc["user_id"] for doc in db.notifications.find({"type": "city_review"})} == {first, second}
    assert db.notifications.count_documents({"type": "city_review"}) == 2
    db.admin_scope_grants.delete_many({"user_id": first, "scope_keys": {"$exists": True}})
    assert len(notifications.fetch_notifications(first)) == 1  # singular legacy grant still valid


def test_hidden_newer_notices_do_not_consume_visible_limit(app, db, assignment):
    user_id, demo_id = assignment
    notifications.create_notification(user_id, "friend_request", {"sender_name": "Older"}, "/friends")
    notifications.notify_city_reviewers(db, demo_id)
    assert notifications.fetch_notifications(user_id, limit=1)[0]["type"] == "city_review"
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"approved": True}})
    visible = notifications.fetch_notifications(user_id, limit=1)
    assert len(visible) == 1 and visible[0]["type"] == "friend_request"
