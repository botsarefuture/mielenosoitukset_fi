from datetime import date, timedelta
from urllib.parse import parse_qs, urlsplit

from bson import ObjectId
import html5lib

from mielenosoitukset_fi.utils.classes import Demonstration, RecurringDemonstration
from mielenosoitukset_fi.utils.classes.RepeatSchedule import RepeatSchedule


def _make_recurring_series(db, *, count=600):
    """Seed a large series independently of the worker generation horizon."""
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
        "repeat_schedule": RepeatSchedule(
            frequency="weekly", interval=1
        ).to_dict(),
        "created_until": (today + timedelta(weeks=count)).isoformat(),
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
    db.recu_demos.insert_one(parent_demo.to_dict())
    scheduled = [today + timedelta(weeks=index) for index in range(count)]

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


def test_recurring_siblings_does_not_dump_pathological_series(client, db):
    """Public recurring siblings page must stay small even for huge series."""
    parent_id, created_count = _make_recurring_series(db)
    series_path = f"/demonstration/{parent_id}/children"
    response = client.get(series_path)
    assert response.status_code == 200, "Siblings page should render for huge series"

    body = response.get_data(as_text=True)

    page = html5lib.parse(body, namespaceHTMLElements=False)
    chooser = page.find(".//section[@class='recurring-occurrence-switcher animate-fade-in-up']")
    assert chooser is not None
    occurrence_links = [
        link
        for link in chooser.findall(".//a[@href]")
        if urlsplit(link.get("href")).path == series_path
        and "occurrence" in parse_qs(urlsplit(link.get("href")).query)
    ]
    future_link_count = len(occurrence_links)
    assert future_link_count > 0, "The page must actually render child links"
    child_slugs = {
        child["slug"] for child in db.demonstrations.find({"parent": ObjectId(parent_id)})
    }
    for link in occurrence_links:
        assert parse_qs(urlsplit(link.get("href")).query)["occurrence"][0] in child_slugs

    assert created_count > 500, "Seed must produce a pathological series"
    assert future_link_count <= 16, (
        f"Expected a small capped future window, got {future_link_count} future links "
        f"for a series with {created_count} children"
    )

    assert "Pitkä sarja – hyökkääjä" in body
    assert chooser.find('.//a[@href="/demonstrations"]') is not None
