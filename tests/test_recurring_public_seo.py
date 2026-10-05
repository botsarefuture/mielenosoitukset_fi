import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from bson import ObjectId
import html5lib
import pytest

from mielenosoitukset_fi.utils.demo_seo import select_relevant_occurrence


def _insert_occurrences(db, seeded_data, dates):
    """Publish a seeded series and insert distinct occurrences for the supplied dates."""
    parent_id = seeded_data["recu_demo_id"]
    db.recu_demos.update_one(
        {"_id": parent_id},
        {"$set": {"approved": True, "hide": False, "rejected": False}},
    )
    source = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
    inserted = []
    for index, occurrence_date in enumerate(dates, start=1):
        document = dict(source)
        document.update(
            {
                "_id": ObjectId(),
                "parent": parent_id,
                "date": occurrence_date,
                "start_time": "12:00",
                "end_time": "14:00",
                "slug": f"recurring-seo-{index}",
                "running_number": 98000 + index,
                "recurs": True,
                "cancelled": False,
            }
        )
        db.demonstrations.insert_one(document)
        inserted.append(document)
    return parent_id, inserted


def _sitemap_locs(response):
    """Extract location URLs from a sitemap response using its XML namespace."""
    root = ET.fromstring(response.data)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [loc.text for loc in root.findall(".//sm:loc", ns)]


def test_recurring_series_has_one_sitemap_url_and_no_child_urls(app, db, seeded_data):
    """A series contributes one canonical sitemap URL regardless of its occurrence dates."""
    today = date.today()
    parent_id, children = _insert_occurrences(
        db,
        seeded_data,
        [
            (today - timedelta(days=5)).isoformat(),
            (today + timedelta(days=3)).isoformat(),
            (today + timedelta(days=30)).isoformat(),
        ],
    )

    response = app.test_client().get("/sitemap.xml", base_url="https://example.test")
    locs = _sitemap_locs(response)
    series_url = f"https://example.test/demonstration/{parent_id}/children"

    assert response.status_code == 200
    assert locs.count(series_url) == 1
    for child in children:
        assert not any(child["slug"] in loc for loc in locs)


def test_series_page_selects_next_occurrence_and_aligns_seo_metadata(app, db, seeded_data):
    """The default occurrence supplies event metadata while canonical URLs identify the series."""
    today = date.today()
    parent_id, children = _insert_occurrences(
        db,
        seeded_data,
        [
            (today - timedelta(days=5)).isoformat(),
            (today + timedelta(days=3)).isoformat(),
            (today + timedelta(days=30)).isoformat(),
        ],
    )
    response = app.test_client().get(
        f"/demonstration/{parent_id}/children",
        base_url="https://example.test",
    )
    page = response.get_data(as_text=True)
    canonical_url = f"https://example.test/demonstration/{parent_id}/children"

    assert response.status_code == 200
    assert page.count('rel="canonical"') == 1
    assert f'rel="canonical" href="{canonical_url}"' in page
    assert f'property="og:url" content="{canonical_url}"' in page
    assert page.count('aria-current="date"') == 1
    assert datetime.fromisoformat(children[1]["date"]).strftime("%d.%m.%Y") in page
    assert datetime.fromisoformat(children[0]["date"]).strftime("%d.%m.%Y") in page

    structured_match = re.search(
        r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
        page,
        re.DOTALL,
    )
    assert structured_match
    structured = json.loads(structured_match.group(1))
    assert structured["url"] == canonical_url
    assert structured["startDate"].startswith(children[1]["date"])


def test_old_child_url_redirects_to_current_series_page(app, db, seeded_data):
    """Legacy occurrence URLs permanently redirect visitors to the series page."""
    today = date.today()
    parent_id, children = _insert_occurrences(
        db,
        seeded_data,
        [
            (today - timedelta(days=5)).isoformat(),
            (today + timedelta(days=3)).isoformat(),
        ],
    )

    response = app.test_client().get(f"/demonstration/{children[0]['slug']}")

    assert response.status_code == 301
    redirect = urlsplit(response.headers["Location"])
    assert redirect.path == f"/demonstration/{parent_id}/children"
    assert parse_qs(redirect.query)["occurrence"] == [children[0]["slug"]]


def test_authenticated_old_child_url_also_redirects_to_series(
    user_client, db, seeded_data
):
    """Signed-in visitors receive the same permanent series redirect as anonymous visitors."""
    today = date.today()
    parent_id, children = _insert_occurrences(
        db,
        seeded_data,
        [
            (today - timedelta(days=2)).isoformat(),
            (today + timedelta(days=2)).isoformat(),
        ],
    )

    response = user_client.get(f"/demonstration/{children[0]['slug']}")

    assert response.status_code == 301
    redirect = urlsplit(response.headers["Location"])
    assert redirect.path == f"/demonstration/{parent_id}/children"
    assert parse_qs(redirect.query)["occurrence"] == [children[0]["slug"]]


def test_explicit_occurrence_keeps_clean_series_canonical(app, db, seeded_data):
    """Choosing a historical occurrence preserves the clean canonical and Open Graph URLs."""
    today = date.today()
    parent_id, children = _insert_occurrences(
        db,
        seeded_data,
        [
            (today - timedelta(days=5)).isoformat(),
            (today + timedelta(days=3)).isoformat(),
        ],
    )
    response = app.test_client().get(
        f"/demonstration/{parent_id}/children?occurrence={children[0]['slug']}",
        base_url="https://example.test",
    )
    page = response.get_data(as_text=True)
    canonical_url = f"https://example.test/demonstration/{parent_id}/children"

    assert response.status_code == 200
    assert datetime.fromisoformat(children[0]["date"]).strftime("%d.%m.%Y") in page
    assert f'rel="canonical" href="{canonical_url}"' in page
    assert f'property="og:url" content="{canonical_url}"' in page


def test_all_past_series_selects_latest_and_explains_state(app, db, seeded_data):
    """An ended series displays its latest occurrence and explains the lack of future dates."""
    today = date.today()
    parent_id, children = _insert_occurrences(
        db,
        seeded_data,
        [
            (today - timedelta(days=30)).isoformat(),
            (today - timedelta(days=2)).isoformat(),
        ],
    )

    response = app.test_client().get(f"/demonstration/{parent_id}/children")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Ei tulevia ajankohtia" in page
    assert datetime.fromisoformat(children[1]["date"]).strftime("%d.%m.%Y") in page
    assert page.count('aria-current="date"') == 1


def test_selection_skips_cancelled_future_occurrence():
    """A cancelled occurrence cannot displace the next active occurrence as the default."""
    now = datetime.fromisoformat("2026-10-05T12:00:00+03:00")
    cancelled = {
        "_id": ObjectId(),
        "date": "2026-10-06",
        "start_time": "12:00",
        "end_time": "14:00",
        "cancelled": True,
    }
    active = {
        "_id": ObjectId(),
        "date": "2026-10-07",
        "start_time": "12:00",
        "end_time": "14:00",
        "cancelled": False,
    }

    assert select_relevant_occurrence([cancelled, active], now) is active


def test_selection_returns_none_when_every_occurrence_is_cancelled():
    now = datetime.fromisoformat("2026-10-05T12:00:00+03:00")
    cancelled_occurrences = [
        {
            "_id": ObjectId(),
            "date": "2026-10-04",
            "start_time": "12:00",
            "end_time": "14:00",
            "cancelled": True,
        },
        {
            "_id": ObjectId(),
            "date": "2026-10-06",
            "start_time": "12:00",
            "end_time": "14:00",
            "cancelled": True,
        },
    ]

    assert select_relevant_occurrence(cancelled_occurrences, now) is None


def test_all_cancelled_series_is_noindex_and_omitted_from_sitemap(
    app, db, seeded_data
):
    today = date.today()
    parent_id, children = _insert_occurrences(
        db,
        seeded_data,
        [
            (today - timedelta(days=2)).isoformat(),
            (today + timedelta(days=2)).isoformat(),
        ],
    )
    db.demonstrations.update_many(
        {"_id": {"$in": [child["_id"] for child in children]}},
        {"$set": {"cancelled": True}},
    )

    client = app.test_client()
    page_response = client.get(f"/demonstration/{parent_id}/children")
    sitemap_response = client.get("/sitemap.xml", base_url="https://example.test")

    assert page_response.status_code == 200
    assert page_response.headers["X-Robots-Tag"] == "noindex, follow"
    assert f"https://example.test/demonstration/{parent_id}/children" not in _sitemap_locs(
        sitemap_response
    )


@pytest.mark.parametrize(
    "start_fields",
    [
        {"start_time": "09:00"},
        {"start_time": "09:00:30"},
        {},
        {"start_time": None},
        {"start_time": ""},
        {"start_time": "invalid"},
        {"start_time": "25:00"},
    ],
)
def test_selection_orders_start_times_with_midnight_fallback(start_fields):
    """Selection orders parsed start times and treats absent or invalid times as midnight."""
    early = {
        "_id": "z",
        "date": "2026-10-06",
        "end_time": "14:00",
        **start_fields,
    }
    late = {
        "_id": "a",
        "date": "2026-10-06",
        "start_time": "12:00",
        "end_time": "14:00",
    }
    before = datetime.fromisoformat("2026-10-05T12:00:00+03:00")
    after = datetime.fromisoformat("2026-10-07T12:00:00+03:00")

    assert select_relevant_occurrence([late, early], before) is early
    assert select_relevant_occurrence([early, late], after) is late


def test_same_day_occurrence_remains_current_until_its_end_time():
    """The default advances to the next occurrence only after the current one ends."""
    occurrence = {
        "_id": ObjectId(),
        "date": "2026-10-05",
        "start_time": "12:00",
        "end_time": "14:00",
        "cancelled": False,
    }
    next_occurrence = {
        "_id": ObjectId(),
        "date": "2026-10-06",
        "start_time": "12:00",
        "end_time": "14:00",
        "cancelled": False,
    }

    before_end = datetime.fromisoformat("2026-10-05T13:59:00+03:00")
    after_end = datetime.fromisoformat("2026-10-05T14:01:00+03:00")

    assert select_relevant_occurrence([occurrence, next_occurrence], before_end) is occurrence
    assert select_relevant_occurrence([occurrence, next_occurrence], after_end) is next_occurrence


def test_invalid_recurring_parent_is_404(app):
    """Malformed and nonexistent series identifiers both return a not-found response."""
    client = app.test_client()

    assert client.get("/demonstration/not-an-object-id/children").status_code == 404
    assert client.get(f"/demonstration/{ObjectId()}/children").status_code == 404


def test_empty_recurring_series_is_noindex_in_html_and_response_header(
    app, db, seeded_data
):
    """An empty series suppresses indexing through both HTML metadata and HTTP headers."""
    parent_id = seeded_data["recu_demo_id"]
    db.recu_demos.update_one(
        {"_id": parent_id},
        {"$set": {"approved": True, "hide": False, "rejected": False}},
    )
    db.demonstrations.delete_many(
        {"parent": {"$in": [parent_id, str(parent_id)]}}
    )

    response = app.test_client().get(f"/demonstration/{parent_id}/children")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.headers["X-Robots-Tag"] == "noindex, follow"
    assert '<meta name="robots" content="noindex, follow"' in page


def test_public_api_and_today_page_link_recurring_occurrences_to_series(
    app, db, seeded_data
):
    """API results and today listings link recurring occurrences to the canonical series."""
    today = date.today()
    parent_id, children = _insert_occurrences(
        db,
        seeded_data,
        [today.isoformat()],
    )
    series_path = f"/demonstration/{parent_id}/children"
    child_id = str(children[0]["_id"])

    client = app.test_client()
    api_response = client.get("/api/v1/demonstrations")
    today_response = client.get("/mielenosoitukset-tanaan")

    assert api_response.status_code == 200
    api_child = next(
        item
        for item in api_response.get_json()["demonstrations"]
        if item["_id"] == child_id
    )
    assert api_child["parent"] == str(parent_id)
    assert api_child["detail_url"] == series_path
    assert f'href="{series_path}"' in today_response.get_data(as_text=True)


def test_api_cards_use_standalone_url_when_parent_series_is_invisible(
    app, db, seeded_data
):
    today = date.today()
    parent_id, children = _insert_occurrences(db, seeded_data, [today.isoformat()])
    db.recu_demos.update_one({"_id": parent_id}, {"$set": {"hide": True}})
    child_id = str(children[0]["_id"])
    standalone_path = f"/demonstration/{children[0]['slug']}"

    client = app.test_client()
    api_response = client.get("/api/v1/demonstrations")
    today_response = client.get("/mielenosoitukset-tanaan")

    assert api_response.status_code == 200
    api_child = next(
        item
        for item in api_response.get_json()["demonstrations"]
        if item["_id"] == child_id
    )
    assert api_child["detail_url"] == standalone_path
    assert f'href="{standalone_path}"' in today_response.get_data(as_text=True)
    assert f"/demonstration/{parent_id}/children" not in today_response.get_data(
        as_text=True
    )


def test_series_page_stays_indexable_when_selected_occurrence_is_beyond_horizon(
    app, db, seeded_data
):
    today = date.today()
    parent_id, _children = _insert_occurrences(
        db,
        seeded_data,
        [
            (today - timedelta(days=5)).isoformat(),
            (today + timedelta(days=800)).isoformat(),
        ],
    )
    series_url = f"https://example.test/demonstration/{parent_id}/children"

    client = app.test_client()
    sitemap_response = client.get("/sitemap.xml", base_url="https://example.test")
    page_response = client.get(
        f"/demonstration/{parent_id}/children",
        base_url="https://example.test",
    )

    assert page_response.status_code == 200
    assert page_response.headers.get("X-Robots-Tag") != "noindex, follow"
    assert (
        '<meta name="robots" content="index, follow"'
        in page_response.get_data(as_text=True)
    )
    assert _sitemap_locs(sitemap_response).count(series_url) == 1


def test_series_page_is_noindex_when_no_occurrence_is_in_discovery_window(
    app, db, seeded_data
):
    today = date.today()
    parent_id, _children = _insert_occurrences(
        db,
        seeded_data,
        [(today + timedelta(days=800)).isoformat()],
    )
    series_url = f"https://example.test/demonstration/{parent_id}/children"

    client = app.test_client()
    sitemap_response = client.get("/sitemap.xml", base_url="https://example.test")
    page_response = client.get(
        f"/demonstration/{parent_id}/children",
        base_url="https://example.test",
    )

    assert _sitemap_locs(sitemap_response).count(series_url) == 0
    assert page_response.headers.get("X-Robots-Tag") == "noindex, follow"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize(
    ("theme", "viewport"),
    [
        ("light", {"width": 1440, "height": 900}),
        ("dark", {"width": 360, "height": 800}),
    ],
)
def test_recurring_series_chooser_is_theme_aware_and_portrait_safe(
    app,
    db,
    seeded_data,
    live_server,
    browser_page,
    theme,
    viewport,
):
    """The chooser keeps one selected date and fits desktop and portrait layouts in both themes."""
    today = date.today()
    parent_id, _ = _insert_occurrences(
        db,
        seeded_data,
        [
            (today - timedelta(days=2)).isoformat(),
            (today + timedelta(days=2)).isoformat(),
            (today + timedelta(days=30)).isoformat(),
        ],
    )
    browser_page.set_viewport_size(viewport)
    browser_page.add_init_script(
        f"localStorage.setItem('theme', {json.dumps(theme)})"
    )

    browser_page.goto(
        f"{live_server}/demonstration/{parent_id}/children",
        wait_until="domcontentloaded",
    )

    chooser = browser_page.locator(".recurring-occurrence-switcher")
    assert chooser.is_visible()
    assert chooser.locator('[aria-current="date"]').count() == 1
    assert theme in (browser_page.locator("html").get_attribute("class") or "")
    assert browser_page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth + 1"
    )


@pytest.mark.parametrize("offset", [-5, 30, 120])
@pytest.mark.parametrize("identifier", ["_id", "slug", "running_number"])
def test_requested_occurrence_is_independent_of_chooser_limits(
    app, db, seeded_data, offset, identifier
):
    today = date.today()
    parent_id, children = _insert_occurrences(
        db, seeded_data,
        [(today + timedelta(days=day)).isoformat() for day in range(1, 18)]
        + [(today + timedelta(days=offset)).isoformat()],
    )
    requested = children[-1]
    db.demonstrations.update_one(
        {"_id": requested["_id"]}, {"$set": {"title": "Requested occurrence"}}
    )
    response = app.test_client().get(
        f"/demonstration/{parent_id}/children",
        query_string={"occurrence": str(requested[identifier])},
    )
    page = html5lib.parse(response.data, namespaceHTMLElements=False)

    assert response.status_code == 200
    assert "Requested occurrence" in page.find(".//title").text
    upcoming = page.find(".//ol[@class='recurring-occurrence-list']")
    assert len(upcoming.findall(".//a")) == 16
    assert all(str(requested[identifier]) not in a.get("href") for a in upcoming.findall(".//a"))


@pytest.mark.parametrize("offset,cancelled", [(-2, False), (2, False), (2, True)])
def test_occurrence_without_hide_field_remains_visible(
    app, db, seeded_data, offset, cancelled
):
    today = date.today()
    parent_id, children = _insert_occurrences(
        db, seeded_data,
        [(today + timedelta(days=2)).isoformat(),
         (today + timedelta(days=offset)).isoformat()],
    )
    requested = children[1]
    db.demonstrations.update_one(
        {"_id": requested["_id"]},
        {"$unset": {"hide": ""},
         "$set": {"title": "Occurrence without hide", "cancelled": cancelled}},
    )
    client = app.test_client()
    series_path = f"/demonstration/{parent_id}/children"
    response = client.get(series_path)
    assert response.status_code == 200
    page = html5lib.parse(response.data, namespaceHTMLElements=False)
    chooser = page.find(".//section[@class='recurring-occurrence-switcher animate-fade-in-up']")
    assert any(requested["slug"] in a.get("href") for a in chooser.findall(".//a"))

    response = client.get(series_path, query_string={"occurrence": requested["slug"]})
    assert response.status_code == 200
    page = html5lib.parse(response.data, namespaceHTMLElements=False)
    assert "Occurrence without hide" in page.find(".//title").text


@pytest.mark.parametrize("changes", [
    {"approved": False}, {"hide": True}, {"rejected": True}, {"parent": ObjectId()},
])
def test_requested_occurrence_obeys_series_visibility(app, db, seeded_data, changes):
    today = date.today()
    parent_id, children = _insert_occurrences(
        db, seeded_data,
        [(today + timedelta(days=2)).isoformat(), (today + timedelta(days=120)).isoformat()],
    )
    db.demonstrations.update_one(
        {"_id": children[1]["_id"]}, {"$set": {"title": "Invisible occurrence", **changes}}
    )
    response = app.test_client().get(
        f"/demonstration/{parent_id}/children?occurrence={children[1]['slug']}"
    )
    assert response.status_code == 200
    page = html5lib.parse(response.data, namespaceHTMLElements=False)
    assert "Invisible occurrence" not in page.find(".//title").text
    chooser = page.find(".//section[@class='recurring-occurrence-switcher animate-fade-in-up']")
    assert all(children[1]["slug"] not in a.get("href") for a in chooser.findall(".//a"))


def test_cancelled_rows_do_not_consume_active_limit_and_remain_linked(app, db, seeded_data):
    today = date.today()
    parent_id, children = _insert_occurrences(
        db, seeded_data,
        [(today + timedelta(days=day)).isoformat() for day in range(1, 18)]
        + [(today - timedelta(days=day)).isoformat() for day in range(1, 21)],
    )
    db.demonstrations.update_many(
        {"_id": {"$in": [child["_id"] for child in children[:16]]}},
        {"$set": {"cancelled": True}},
    )
    db.demonstrations.update_one(
        {"_id": children[16]["_id"]}, {"$set": {"title": "Active occurrence"}}
    )
    client = app.test_client()
    response = client.get(f"/demonstration/{parent_id}/children")
    page = html5lib.parse(response.data, namespaceHTMLElements=False)

    assert response.status_code == 200
    assert "Active occurrence" in page.find(".//title").text
    upcoming = page.find(".//ol[@class='recurring-occurrence-list']")
    assert len(upcoming.findall(".//a")) == 1
    history = page.find(".//details[@class='recurring-occurrence-history']")
    assert "open" not in history.attrib
    assert len(history.findall(".//a")) == 32  # 16 past + 16 cancelled
    cancelled = history.find(".//a[@class='recurring-occurrence-link is-cancelled']")
    assert cancelled is not None
    assert "aria-disabled" not in cancelled.attrib
    requested = client.get(cancelled.get("href"))
    assert requested.status_code == 200
    assert "Peruttu" in requested.get_data(as_text=True)


def test_all_cancelled_series_exposes_working_occurrence_links(app, db, seeded_data):
    parent_id, children = _insert_occurrences(
        db, seeded_data, [(date.today() + timedelta(days=2)).isoformat()],
    )
    db.demonstrations.update_one(
        {"_id": children[0]["_id"]},
        {"$set": {"cancelled": True, "title": "Cancelled occurrence"}},
    )
    client = app.test_client()
    response = client.get(f"/demonstration/{parent_id}/children")
    page = html5lib.parse(response.data, namespaceHTMLElements=False)
    link = page.find(".//details//a[@class='occurrence-link']")
    assert link is not None
    assert "aria-disabled" not in link.attrib
    requested = client.get(link.get("href"), follow_redirects=True)
    assert requested.status_code == 200
    assert "Cancelled occurrence" in html5lib.parse(
        requested.data, namespaceHTMLElements=False
    ).find(".//title").text
