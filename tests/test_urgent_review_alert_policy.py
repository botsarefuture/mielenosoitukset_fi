from datetime import UTC, datetime, timedelta, timezone

from bson import ObjectId
import pytest

from mielenosoitukset_fi.utils.urgent_review_alerts import (
    build_urgent_review_alert, review_event_start,
)

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
DEMO_ID = ObjectId("507f1f77bcf86cd799439011")


def _demo(**changes):
    return {
        "_id": DEMO_ID, "title": "Review this event", "city": "Helsinki",
        "date": "2026-10-24", "start_time": "15:00",
        "approved": False, "rejected": False, "cancelled": False,
        **changes,
    }


@pytest.mark.parametrize("remaining,expected", [
    (172801, None), (172800, None), (172799, "urgent"),
    (86401, "urgent"), (86400, "urgent"), (86399, "critical"),
    (1, "critical"), (0, None), (-1, None),
])
def test_urgency_thresholds_are_strict_and_use_the_start_instant(remaining, expected):
    demo = _demo()
    start = review_event_start(demo)
    snapshot = build_urgent_review_alert(demo, start - timedelta(seconds=remaining))
    if expected is None:
        assert snapshot is None
    else:
        assert snapshot["state"] == "pending"
        assert snapshot["urgency"] == expected
        assert snapshot["threshold_hours"] == (24 if expected == "critical" else 48)


@pytest.mark.parametrize("changes,state", [
    ({"approved": True}, "approved"), ({"rejected": True}, "rejected"),
    ({"cancelled": True, "approved": True}, "cancelled"),
    ({"start_time": "invalid"}, "invalid_time"),
    ({"in_past": True, "date": "2026-10-20"}, "archived"),
    ({"date": "2026-10-20"}, "started"), ({"date": "2026-11-01"}, "rescheduled"),
])
def test_existing_messages_get_explicit_state_updates_without_new_announcements(changes, state):
    demo = _demo(**changes)
    assert build_urgent_review_alert(demo, NOW) is None
    snapshot = build_urgent_review_alert(demo, NOW, has_message=True)
    assert snapshot["state"] == state
    assert snapshot["urgency"] is None
    assert snapshot["threshold_hours"] is None
    assert snapshot["demo_id"] == str(DEMO_ID)


@pytest.mark.parametrize("changes,expected", [
    ({"approved": True, "moderation_decision": {"status": "approved", "at": NOW}}, NOW),
    ({"rejected": True, "moderation_decision": {"status": "rejected", "at": NOW}}, NOW),
    ({"cancelled": True, "cancelled_at": NOW}, NOW),
    ({"approved": True, "moderation_decision": {"status": "rejected", "at": NOW}}, None),
    ({"approved": True}, None),
    ({"moderation_decision": {"status": "approved", "at": NOW}}, None),
])
def test_handled_time_comes_only_from_matching_persisted_state(changes, expected):
    snapshot = build_urgent_review_alert(_demo(**changes), NOW, has_message=True)
    assert snapshot["handled_at"] == expected
    assert ("Käsitelty:" in snapshot["text"]) is (expected is not None)
    if not changes.get("approved") and not changes.get("rejected") and not changes.get("cancelled"):
        assert snapshot["state"] == "pending"  # stale decision metadata is not a new decision


@pytest.mark.parametrize("day,clock,expected", [
    ("2026-10-23", "15:00", datetime(2026, 10, 23, 12, tzinfo=UTC)),
    ("2026-12-01", "15:00:30", datetime(2026, 12, 1, 13, 0, 30, tzinfo=UTC)),
    ("2026-03-29", "03:30", None), ("2026-10-25", "03:30", None),
    ("2026-10-25", "04:30", datetime(2026, 10, 25, 2, 30, tzinfo=UTC)),
    ("wrong", "15:00", None), ("2026-10-23", "25:00", None),
    ("2026-10-23", None, None), (None, "12:00", None),
])
def test_helsinki_start_parsing_never_guesses_missing_or_dst_instants(day, clock, expected):
    assert review_event_start(_demo(date=day, start_time=clock)) == expected


def test_reference_clock_accepts_storage_utc_and_aware_instants_consistently():
    demo = _demo()
    aware = build_urgent_review_alert(demo, NOW)
    assert build_urgent_review_alert(demo, NOW.replace(tzinfo=None)) == aware
    assert build_urgent_review_alert(demo, NOW.astimezone(timezone(timedelta(hours=-5)))) == aware
    with pytest.raises(ValueError):
        build_urgent_review_alert(demo, None)


@pytest.mark.parametrize("escalated,responsibility", [(False, "city"), (True, "national")])
def test_city_responsibility_and_review_deadline_do_not_control_event_urgency(escalated, responsibility):
    deadline = NOW - timedelta(days=5)
    demo = _demo(city_assignment={
        "escalated": escalated, "review_hours": 72,
        "review_deadline_at": deadline.replace(tzinfo=None),
    })
    snapshot = build_urgent_review_alert(demo, NOW)
    assert snapshot["state"] == "pending"
    assert snapshot["urgency"] == "urgent"
    assert snapshot["review_deadline_at"] == deadline
    assert snapshot["responsibility"] == responsibility
    assert "Käsittelyn määräaika:" in snapshot["text"]


def test_message_is_bounded_escaped_and_has_only_an_authenticated_canonical_link():
    private = "private-contact-and-bearer-sentinel"
    demo = _demo(
        title='<script>"&' + "x" * 10000, city="<b>Helsinki</b>",
        submitter_email=private, approve_link=f"https://evil.test/{private}",
        description=private, token=private,
        moderation_decision={"actor": {"email": private}, "status": "approved", "at": NOW},
    )
    snapshot = build_urgent_review_alert(demo, NOW)
    assert private not in str(snapshot)
    assert "<script>" not in snapshot["text"]
    assert "&lt;script&gt;" in snapshot["text"]
    assert "&lt;b&gt;Helsinki&lt;/b&gt;" in snapshot["text"]
    assert len(snapshot["text"]) < 2000
    assert snapshot["text"].count('<a href="') == 1
    assert f'https://mielenosoitukset.fi/admin/demo/review/{DEMO_ID}' in snapshot["text"]
    assert "evil.test" not in snapshot["text"]
    assert set(snapshot) == {
        "demo_id", "state", "urgency", "threshold_hours", "responsibility",
        "starts_at", "review_deadline_at", "handled_at", "text", "text_sha256",
    }
    nested = build_urgent_review_alert(_demo(title={"email": private}), NOW)
    assert private not in str(nested)


def test_same_state_has_stable_content_hash_until_an_actual_change():
    demo = _demo()
    first = build_urgent_review_alert(demo, NOW - timedelta(minutes=2))
    same = build_urgent_review_alert(demo, NOW - timedelta(minutes=1))
    assert first["text_sha256"] == same["text_sha256"]
    critical = build_urgent_review_alert(demo, NOW + timedelta(seconds=1))
    assert critical["urgency"] == "critical"
    assert critical["text_sha256"] != first["text_sha256"]
    assert build_urgent_review_alert(_demo(title="Changed title"), NOW)["text_sha256"] != first["text_sha256"]


@pytest.mark.parametrize("demo_id", [None, "invalid", 123, "https://evil.test/?token=secret"])
def test_invalid_identity_never_builds_a_link_or_alert(demo_id):
    assert build_urgent_review_alert(_demo(_id=demo_id), NOW) is None


@pytest.mark.parametrize("urgent,critical", [(24, 24), (24, 48), (0, 0), (48, -1), (True, 1), (48, 24.5)])
def test_invalid_threshold_configuration_is_rejected(urgent, critical):
    with pytest.raises(ValueError):
        build_urgent_review_alert(_demo(), NOW, urgent_hours=urgent, critical_hours=critical)


def test_configured_thresholds_change_the_displayed_limit_and_severity_together():
    demo = _demo()
    now = review_event_start(demo) - timedelta(hours=9)
    snapshot = build_urgent_review_alert(demo, now, urgent_hours=20, critical_hours=10)
    assert snapshot["urgency"] == "critical"
    assert snapshot["threshold_hours"] == 10
    assert "alle 10 h" in snapshot["text"]


@pytest.mark.parametrize("has_message", [False, True])
def test_rescheduling_overrides_stale_archive_flag(has_message):
    snapshot = build_urgent_review_alert(_demo(in_past=True), NOW, has_message=has_message)
    assert snapshot["state"] == "pending"
    assert snapshot["urgency"] == "urgent"


@pytest.mark.parametrize("state", ["approved", "rejected", "cancelled"])
def test_terminal_snapshot_does_not_invent_national_responsibility(state):
    snapshot = build_urgent_review_alert(_demo(**{state: True}), NOW, has_message=True)
    assert snapshot["responsibility"] is None
    assert "Vastuu:" not in snapshot["text"]
    pending = build_urgent_review_alert(_demo(), NOW)
    assert pending["responsibility"] == "national"
    assert "Vastuu: kansallinen tiimi" in pending["text"]
