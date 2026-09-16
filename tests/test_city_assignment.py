"""Tests for the city-admin demo-assignment feature."""

from datetime import timedelta

import pytest
from bson import ObjectId

from mielenosoitukset_fi.utils.city_assignment import (
    CITY_ASSIGNMENT_FIELD,
    DEFAULT_ESCALATION_HOURS,
    NOT_ESCALATED_ASSIGNMENT_CLAUSE,
    active_city_admins_for_city,
    assign_demo_to_city,
    clear_city_assignment,
    escalate_overdue,
    has_live_assignment,
    mark_escalated,
    touch_city_assignment,
)
from mielenosoitukset_fi.utils.cities import normalize_city_key
from mielenosoitukset_fi.utils.time_utils import utcnow
from tests.conftest import _user_doc


@pytest.fixture(autouse=True)
def _clean_assignment_data(db):
    """Ensure each test starts with clean relevant collections."""
    db.users.delete_many({"role": "city_admin"})
    db.admin_scope_grants.delete_many({"scope_type": "city"})
    db.demo_notifications_queue.delete_many({})
    yield


@pytest.mark.integration
class TestActiveCityAdmins:
    def test_returns_active_city_admins_with_accept_demo_permission(self, db):
        user_id = _create_city_admin(
            db, ["helsinki"], ["LIST_DEMOS", "VIEW_DEMO", "ACCEPT_DEMO"]
        )
        admins = active_city_admins_for_city(db, "helsinki")
        emails = [a["email"] for a in admins]
        user = db.users.find_one({"_id": user_id})
        assert user["email"] in emails

    def test_returns_empty_when_no_admins_for_city(self, db):
        assert active_city_admins_for_city(db, "tampere") == []

    def test_ignores_revoked_grants(self, db):
        user_id = _create_city_admin(
            db, ["helsinki"], ["ACCEPT_DEMO"], revoked=True
        )
        admins = active_city_admins_for_city(db, "helsinki")
        assert all(a["user_id"] != user_id for a in admins)

    def test_ignores_inactive_users(self, db):
        user_id = _create_city_admin(
            db, ["helsinki"], ["ACCEPT_DEMO"], active=False
        )
        admins = active_city_admins_for_city(db, "helsinki")
        assert all(a["user_id"] != user_id for a in admins)

    def test_ignores_banned_users(self, db):
        user_id = _create_city_admin(
            db, ["helsinki"], ["ACCEPT_DEMO"], banned=True
        )
        admins = active_city_admins_for_city(db, "helsinki")
        assert all(a["user_id"] != user_id for a in admins)

    def test_normalises_city_key(self, db):
        _create_city_admin(db, ["helsinki"], ["ACCEPT_DEMO"])
        assert active_city_admins_for_city(db, "Helsinki") != []

    def test_ignores_wrong_permission(self, db):
        _create_city_admin(db, ["helsinki"], ["LIST_DEMOS"])
        assert active_city_admins_for_city(db, "helsinki") == []


@pytest.mark.integration
class TestAssignDemoToCity:
    def test_writes_assignment_and_returns_message(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        city_key = normalize_city_key("Helsinki")
        admins = [{"user_id": ObjectId(), "email": "admin@example.test", "displayname": "A"}]
        msg = assign_demo_to_city(
            db, demo_id, city_key, admins,
            template_name="admin_demo_city_assignment.html",
            subject="Test subject",
            context={"foo": "bar"},
        )
        assert msg is not None
        assert msg["template_name"] == "admin_demo_city_assignment.html"
        assert msg["recipients"] == ["admin@example.test"]

        doc = db.demonstrations.find_one({"_id": demo_id})
        assignment = doc[CITY_ASSIGNMENT_FIELD]
        assert assignment["city_key"] == city_key
        assert assignment["escalated"] is False
        assert assignment["assigned_at"] is not None

    def test_returns_none_for_empty_admins(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        msg = assign_demo_to_city(
            db, demo_id, "helsinki", [],
            template_name="x.html", subject="x", context={},
        )
        assert msg is None
        doc = db.demonstrations.find_one({"_id": demo_id})
        assert doc.get(CITY_ASSIGNMENT_FIELD) is None


@pytest.mark.integration
class TestTouchCityAssignment:
    def test_resets_assigned_at_when_not_escalated(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, escalated=False)
        before = db.demonstrations.find_one({"_id": demo_id})[CITY_ASSIGNMENT_FIELD]["assigned_at"]
        touch_city_assignment(db, demo_id)
        after = db.demonstrations.find_one({"_id": demo_id})[CITY_ASSIGNMENT_FIELD]["assigned_at"]
        assert after > before

    def test_does_not_reset_when_escalated(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, escalated=True)
        before = db.demonstrations.find_one({"_id": demo_id})[CITY_ASSIGNMENT_FIELD]["assigned_at"]
        touch_city_assignment(db, demo_id)
        after = db.demonstrations.find_one({"_id": demo_id})[CITY_ASSIGNMENT_FIELD]["assigned_at"]
        assert after == before

    def test_returns_false_when_no_assignment(self, db, seeded_data):
        assert touch_city_assignment(db, seeded_data["pending_demo_id"]) is False


@pytest.mark.integration
class TestClearCityAssignment:
    def test_removes_assignment(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id)
        assert clear_city_assignment(db, demo_id) is True
        doc = db.demonstrations.find_one({"_id": demo_id})
        assert doc.get(CITY_ASSIGNMENT_FIELD) is None

    def test_returns_false_when_no_assignment(self, db, seeded_data):
        assert clear_city_assignment(db, seeded_data["pending_demo_id"]) is False


@pytest.mark.integration
class TestEscalateOverdue:
    def test_finds_overdue_demo(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, assigned_hours_ago=DEFAULT_ESCALATION_HOURS + 1)
        overdue = escalate_overdue(db)
        assert any(d["_id"] == demo_id for d in overdue)

    def test_skips_recently_assigned(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, assigned_hours_ago=1)
        assert not any(d["_id"] == demo_id for d in escalate_overdue(db))

    def test_skips_already_escalated(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, assigned_hours_ago=DEFAULT_ESCALATION_HOURS + 1, escalated=True)
        assert not any(d["_id"] == demo_id for d in escalate_overdue(db))


@pytest.mark.integration
class TestMarkEscalated:
    def test_flips_escalated(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, escalated=False)
        assert mark_escalated(db, demo_id) is True
        doc = db.demonstrations.find_one({"_id": demo_id})
        assert doc[CITY_ASSIGNMENT_FIELD]["escalated"] is True
        assert doc[CITY_ASSIGNMENT_FIELD]["escalated_at"] is not None

    def test_double_escalation_returns_false(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, escalated=True)
        assert mark_escalated(db, demo_id) is False


@pytest.mark.integration
class TestHasLiveAssignment:
    def test_returns_true_for_non_escalated_assignment(self):
        assert has_live_assignment({CITY_ASSIGNMENT_FIELD: {"escalated": False}}) is True

    def test_returns_false_for_escalated(self):
        assert has_live_assignment({CITY_ASSIGNMENT_FIELD: {"escalated": True}}) is False

    def test_returns_false_for_no_assignment(self):
        assert has_live_assignment({}) is False


@pytest.mark.integration
class TestNotEscalatedAssignmentClause:
    def test_matches_demos_without_assignment(self, db, seeded_data):
        clause = NOT_ESCALATED_ASSIGNMENT_CLAUSE
        demo = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
        assert demo.get(CITY_ASSIGNMENT_FIELD) is None
        assert db.demonstrations.find_one({"_id": seeded_data["demo_id"], **clause}) is not None

    def test_matches_escalated_assignments(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, escalated=True)
        assert db.demonstrations.find_one({"_id": demo_id, **NOT_ESCALATED_ASSIGNMENT_CLAUSE}) is not None

    def test_excludes_non_escalated_assignments(self, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, escalated=False)
        assert db.demonstrations.find_one({"_id": demo_id, **NOT_ESCALATED_ASSIGNMENT_CLAUSE}) is None


@pytest.mark.integration
class TestSubmitIntegration:
    def test_city_with_admins_gets_assignment_and_skips_national_queue(
        self, app, db, seeded_data, external_side_effects, monkeypatch
    ):
        helsinki_key = normalize_city_key("Helsinki")
        _create_city_admin(db, [helsinki_key], ["ACCEPT_DEMO"])
        demo_id = seeded_data["pending_demo_id"]

        with app.test_client() as c:
            resp = c.post(
                "/submit",
                data={
                    "title": "Assignment Test",
                    "date": (utcnow().date() + timedelta(days=40)).isoformat(),
                    "start_time": "12:00",
                    "end_time": "14:00",
                    "city": "Helsinki",
                    "address": "Assignmentmäki 7",
                    "description": "Testidemo",
                    "submitter_role": "organizer",
                    "submitter_email": "test@example.test",
                    "submitter_name": "Test Ilmoittaja",
                    "accept_terms": "on",
                },
            )
            assert resp.status_code in (200, 302)

        submitted = list(db.demo_notifications_queue.find({}))
        assignment_msgs = [j for j in submitted if j.get("notification_type") == "city_assignment"]
        national_msgs = [j for j in submitted if j.get("notification_type") == "initial_submission"]
        assert len(assignment_msgs) == 1
        assert len(national_msgs) == 0

    def test_city_without_admins_falls_back_to_national_queue(
        self, app, db, seeded_data, external_side_effects, monkeypatch
    ):
        assert active_city_admins_for_city(db, normalize_city_key("Tampere")) == []

        with app.test_client() as c:
            resp = c.post(
                "/submit",
                data={
                    "title": "National Fallback",
                    "date": (utcnow().date() + timedelta(days=41)).isoformat(),
                    "start_time": "12:00",
                    "end_time": "14:00",
                    "city": "Tampere",
                    "address": "Fallbackkatu 3",
                    "description": "Testidemo",
                    "submitter_role": "organizer",
                    "submitter_email": "test@example.test",
                    "submitter_name": "Test Ilmoittaja",
                    "accept_terms": "on",
                },
            )
            assert resp.status_code in (200, 302)

        submitted = list(db.demo_notifications_queue.find({}))
        national_msgs = [j for j in submitted if j.get("notification_type") == "initial_submission"]
        assert len(national_msgs) == 1


@pytest.mark.integration
class TestDecisionClearsAssignment:
    def test_approve_clears_assignment(self, app, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, escalated=False)
        with app.app_context():
            from mielenosoitukset_fi.demonstrations.decisions import apply_demo_decision

            email_sender = type("ES", (), {"queue_email": lambda self, **kw: None})()
            apply_demo_decision(
                db,
                demo_id,
                "approved",
                actor={"id": "test", "name": "test"},
                source="test",
                email_sender=email_sender,
            )
        doc = db.demonstrations.find_one({"_id": demo_id})
        assert doc.get(CITY_ASSIGNMENT_FIELD) is None

    def test_reject_clears_assignment(self, app, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, escalated=False)
        with app.app_context():
            from mielenosoitukset_fi.demonstrations.decisions import apply_demo_decision

            email_sender = type("ES", (), {"queue_email": lambda self, **kw: None})()
            apply_demo_decision(
                db,
                demo_id,
                "rejected",
                actor={"id": "test", "name": "test"},
                source="test",
                email_sender=email_sender,
            )
        doc = db.demonstrations.find_one({"_id": demo_id})
        assert doc.get(CITY_ASSIGNMENT_FIELD) is None


@pytest.mark.integration
class TestEscalationScript:
    def test_escalate_once_succeeds_with_no_overdue(self, app, db, seeded_data):
        from mielenosoitukset_fi.scripts.escalate_city_assignments import escalate_once

        with app.app_context():
            email_sender = type("ES", (), {"queue_email": lambda self, **kw: None, "send_email": lambda self, **kw: None})()
            emails_sent = escalate_once(db, email_sender=email_sender)
        assert emails_sent == 0


@pytest.mark.integration
class TestNationalReminderSkipsAssignments:
    def test_enqueues_no_reminders_for_active_assignments(self, app, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, escalated=False)
        from mielenosoitukset_fi.scripts.process_submission_notifications import _enqueue_admin_reminders

        with app.app_context():
            _enqueue_admin_reminders(db)
        query = {"notification_type": "admin_pending_reminder"}
        assert db.demo_notifications_queue.count_documents(query) == 0

    def test_enqueues_reminders_for_escalated_assignments(self, app, db, seeded_data):
        demo_id = seeded_data["pending_demo_id"]
        _seed_assignment(db, demo_id, escalated=True)
        from mielenosoitukset_fi.scripts.process_submission_notifications import _enqueue_admin_reminders

        with app.test_request_context():
            _enqueue_admin_reminders(db)
        query = {"notification_type": "admin_pending_reminder"}
        assert db.demo_notifications_queue.count_documents(query) >= 1


# ---- helpers ----


def _create_city_admin(db, city_keys, permissions, *, revoked=False, active=True, banned=False):
    user_id = ObjectId()
    suffix = str(user_id)[-8:]
    doc = _user_doc(
        f"city-admin-{suffix}",
        f"ca-{suffix}@example.test",
        "CityPass1!",
        _id=user_id,
        displayname="City Admin",
        role="city_admin",
        global_admin=False,
        global_permissions=[],
    )
    doc["active"] = active
    doc["banned"] = banned
    db.users.insert_one(doc)
    grant = {
        "user_id": user_id,
        "scope_type": "city",
        "scope_keys": city_keys,
        "role": "city_admin",
        "permissions": permissions,
    }
    if revoked:
        grant["revoked_at"] = utcnow()
    db.admin_scope_grants.insert_one(grant)
    return user_id


def _seed_assignment(
    db,
    demo_id,
    *,
    escalated=False,
    assigned_hours_ago=1,
):
    now = utcnow()
    db.demonstrations.update_one(
        {"_id": demo_id},
        {
            "$set": {
                CITY_ASSIGNMENT_FIELD: {
                    "assigned_at": now - timedelta(hours=assigned_hours_ago),
                    "city_key": normalize_city_key("Helsinki"),
                    "city_admin_ids": [ObjectId()],
                    "escalated": escalated,
                    "escalated_at": now if escalated else None,
                    "escalation_notified_at": now if escalated else None,
                }
            }
        },
    )
