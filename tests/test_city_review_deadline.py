from datetime import datetime, timedelta

import pytest

from mielenosoitukset_fi.utils import city_assignment as assignment


def _assign(db, demo_id, hours):
    return assignment.assign_demo_to_city(
        db, demo_id, "helsinki", [{"user_id": demo_id, "email": "admin@example.test"}],
        template_name="admin_demo_city_assignment.html", subject="Review",
        context={}, escalate_after_hours=hours,
    )


@pytest.mark.parametrize("hours", [24, 48])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_stored_deadline_matches_email_and_escalation_despite_config_change(
    app, db, seeded_data, monkeypatch, hours, offset
):
    clock = [datetime(2026, 10, 22, 12)]
    monkeypatch.setattr(assignment, "utcnow", lambda: clock[0])
    demo_id = seeded_data["pending_demo_id"]
    message = _assign(db, demo_id, hours)
    deadline = clock[0] + timedelta(hours=hours)
    monkeypatch.setitem(app.config, "CITY_ASSIGNMENT_ESCALATION_HOURS", 72)
    demo = db.demonstrations.find_one({"_id": demo_id})
    assert assignment.city_review_deadline(demo) == deadline
    assert message["context"]["review_deadline_at"] == deadline
    assert message["context"]["escalate_after_hours"] == hours
    # Exercise the same actual email environment used by the queue, without SMTP.
    from mielenosoitukset_fi.scripts.process_submission_notifications import email_sender

    rendered = email_sender._env.get_template(message["template_name"]).render(message["context"])
    assert deadline.strftime("%Y-%m-%d %H:%M UTC") in rendered
    clock[0] = deadline + timedelta(seconds=offset)
    overdue = assignment.escalate_overdue(db, escalate_after_hours=72)
    assert any(demo["_id"] == demo_id for demo in overdue) is (offset >= 0)


@pytest.mark.parametrize("hours", [24, 48])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_legacy_deadline_uses_explicit_configured_window(db, seeded_data, monkeypatch, hours, offset):
    started = datetime(2026, 10, 22, 12)
    deadline = started + timedelta(hours=hours)
    monkeypatch.setattr(assignment, "utcnow", lambda: deadline + timedelta(seconds=offset))
    demo_id = seeded_data["pending_demo_id"]
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"city_assignment": {
        "assigned_at": started, "city_key": "helsinki", "escalated": False,
    }}})
    demo = db.demonstrations.find_one({"_id": demo_id})
    assert assignment.city_review_deadline(demo, escalate_after_hours=hours) == deadline
    overdue = assignment.escalate_overdue(db, escalate_after_hours=hours)
    assert any(demo["_id"] == demo_id for demo in overdue) is (offset >= 0)
    assert "review_deadline_at" not in db.demonstrations.find_one({"_id": demo_id})["city_assignment"]


@pytest.mark.parametrize("legacy", [False, True])
def test_explicit_reset_keeps_stored_duration_and_snapshots_legacy_config(app, db, seeded_data, monkeypatch, legacy):
    clock = [datetime(2026, 10, 22, 12)]
    monkeypatch.setattr(assignment, "utcnow", lambda: clock[0])
    demo_id = seeded_data["pending_demo_id"]
    _assign(db, demo_id, 24)
    if legacy:
        db.demonstrations.update_one({"_id": demo_id}, {"$unset": {
            "city_assignment.review_hours": "", "city_assignment.review_deadline_at": "",
        }})
    monkeypatch.setitem(app.config, "CITY_ASSIGNMENT_ESCALATION_HOURS", 48)
    clock[0] += timedelta(hours=2)
    with app.app_context():
        assert assignment.touch_city_assignment(db, demo_id)
    stored = db.demonstrations.find_one({"_id": demo_id})["city_assignment"]
    assert stored["assigned_at"] == clock[0]
    assert stored["review_hours"] == (48 if legacy else 24)
    assert stored["review_deadline_at"] == clock[0] + timedelta(hours=48 if legacy else 24)


def test_ordinary_edit_does_not_extend_city_review_deadline(admin_client, db, seeded_data):
    demo_id = seeded_data["pending_demo_id"]
    _assign(db, demo_id, 24)
    before = db.demonstrations.find_one({"_id": demo_id})["city_assignment"]
    response = admin_client.post(f"/admin/demo/edit_demo/{demo_id}", data={
        "title": "Updated pending event", "date": "2026-12-01",
        "start_time": "12:00", "end_time": "14:00", "city": "Helsinki",
        "address": "Kansalaistori", "description": "Updated description", "type": "STAY_STILL",
    })
    assert response.status_code == 302
    after = db.demonstrations.find_one({"_id": demo_id})
    assert after["title"] == "Updated pending event"
    assert after["city_assignment"] == before


@pytest.mark.parametrize("value", [0, -1, True, 24.5, "wrong", "0"])
def test_invalid_review_duration_fails_before_assignment(db, seeded_data, value):
    demo_id = seeded_data["pending_demo_id"]
    with pytest.raises(ValueError):
        _assign(db, demo_id, value)
    assert "city_assignment" not in db.demonstrations.find_one({"_id": demo_id})


@pytest.mark.parametrize("stored", ["missing_assigned", "null_deadline", "invalid_deadline"])
def test_missing_legacy_timestamp_does_not_invent_a_deadline(db, seeded_data, stored):
    demo_id = seeded_data["pending_demo_id"]
    fields = {"city_key": "helsinki"}
    if stored != "missing_assigned":
        fields["assigned_at"] = datetime(2020, 1, 1)
        fields["review_deadline_at"] = None if stored == "null_deadline" else "invalid"
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"city_assignment": fields}})
    demo = db.demonstrations.find_one({"_id": demo_id})
    assert assignment.city_review_deadline(demo) is None
    assert not any(demo["_id"] == demo_id for demo in assignment.escalate_overdue(db))


def test_escalation_email_uses_stored_window_and_deadline(app, db, seeded_data, monkeypatch):
    from mielenosoitukset_fi.scripts import escalate_city_assignments as script
    from mielenosoitukset_fi.scripts.process_submission_notifications import email_sender

    clock = [datetime(2026, 10, 22, 12)]
    monkeypatch.setattr(assignment, "utcnow", lambda: clock[0])
    demo_id = seeded_data["pending_demo_id"]
    _assign(db, demo_id, 48)
    deadline = clock[0] + timedelta(hours=48)
    clock[0] = deadline
    # Do not create real bearer tokens or send any real message.
    for name in ("generate_demo_approve_link", "generate_demo_reject_link", "generate_demo_preview_link"):
        monkeypatch.setattr(script, name, lambda demo_id: "https://example.test/review")
    sent = []
    monkeypatch.setattr(email_sender, "send_email", lambda job, **kwargs: sent.append(job) or True)
    assert script.escalate_once(db, email_sender=email_sender, escalate_after_hours=24) == 1
    assert len(sent) == 1
    assert "48 tunnin" in sent[0].html
    assert "24 tunnin" not in sent[0].html
    assert deadline.strftime("%Y-%m-%d %H:%M UTC") in sent[0].html
    assert db.demonstrations.find_one({"_id": demo_id})["city_assignment"]["escalated"] is True
