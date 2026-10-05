from datetime import date, timedelta

from bson import ObjectId
from flask import url_for

from mielenosoitukset_fi.utils.classes import Demonstration, RecurringDemonstration
from mielenosoitukset_fi.utils.classes.RepeatSchedule import RepeatSchedule
from mielenosoitukset_fi.utils.recurrence import calculate_recurrence_dates


def _make_recurring_series(client, *, days=2000, weekday="saturday"):
    """Create a parent recurring demo and generate thousands of child demos."""
    parent_id = ObjectId()
    today = date.today()

    parent = {
        "_id": parent_id,
        "title": "Pitkä sarja – hyökkääjä",
        "date": today.isoformat(),
        "start_time": "08:30",
        "end_time": "09:00",
        "city": "Helsinki",
        "address": "Testikatu 1, Helsingin kaupunki",
        "slug": "pitka-sarja-hyokkaaja",
        "recurs": True,
        "parent": None,
        "approved": True,
        "hide": False,
        "rejected": False,
        "repeat_schedule": RepeatSchedule(
            frequency="weekly", interval=1, weekday=weekday
        ).to_dict(),
        "created_until": today + timedelta(days=days),
        "freezed_children": [],
        "break_dates": [],
        "organizers": [],
        "tags": ["mielenosoitus"],
        "default_language": "fi",
        "translations": {},
        "description": "Regresiotesti: pitkä toistuva sarja.",
        "event_type": "marssi",
    }

    parent_demo = RecurringDemonstration.from_dict(parent.copy())
    parent_demo.save()

    scheduled = calculate_recurrence_dates(
        today,
        parent_demo.repeat_schedule or RepeatSchedule(),
        created_until=parent_demo.created_until,
        max_occurrences=days,
    )

    created = 0
    for occurrence_date in scheduled:
        child_slug_bits = (parent.get("slug") or "").strip()
        candidate_slug = (
            f"{child_slug_bits}-{occurrence_date.isoformat()}" if child_slug_bits else None
        )

        demo_data = {
            "_id": ObjectId(),
            "parent": parent_id,
            "title": parent["title"],
            "date": occurrence_date.isoformat(),
            "start_time": parent["start_time"],
            "end_time": parent["end_time"],
            "city": parent["city"],
            "address": parent["address"],
            "slug": candidate_slug,
            "approved": True,
            "hide": False,
            "cancelled": False,
            "recurs": False,
            "recurring": True,
            "organizers": [],
            "tags": ["mielenosoitus"],
            "default_language": "fi",
            "translations": {},
            "description": "Regresiotesti lapsidemo.",
            "event_type": "marssi",
        }

        demo = Demonstration.from_dict(demo_data)
        demo.save()
        created += 1

    return str(parent_id), created


def test_recurring_siblings_does_not_dump_pathological_series(client):
    """Public recurring siblings page must stay small even for huge series."""
    parent_id, created_count = _make_recurring_series(
        client, days=2000, weekday="saturday"
    )

    response = client.get(url_for("siblings_meeting", parent=parent_id))
    assert response.status_code == 200, "Siblings page should render for huge series"

    body = response.get_data(as_text=True)

    future_link_count = body.count(
        f'class="occurrence-link" href="{url_for("demonstration_detail", demo_id="IDPLACEHOLDER")}"'
    )

    assert created_count > 500, "Seed must produce a pathological series"
    assert future_link_count <= 16, (
        f"Expected a small capped future window, got {future_link_count} future links "
        f"for a series with {created_count} children"
    )

    assert "Pitkä sarja – hyökkääjä" in body
    assert "selaa kaikkia mielenosoituksia" in body
