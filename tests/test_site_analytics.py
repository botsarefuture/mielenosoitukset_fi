"""Tests for the built-in first-party, server-side analytics system."""

from datetime import timedelta

import pytest
from bson import ObjectId

from mielenosoitukset_fi.utils.site_analytics import (
    SITE_ANALYTICS_COLLECTION,
    classify_device,
    classify_path,
    classify_referrer,
    increment_counter,
)
from mielenosoitukset_fi.utils.time_utils import utcnow
from tests.conftest import _client_for_user


def _counts(db):
    return list(db[SITE_ANALYTICS_COLLECTION].find())


def _total(db, **match):
    query = dict(match)
    rows = list(db[SITE_ANALYTICS_COLLECTION].aggregate(
        [{"$match": query}, {"$group": {"_id": None, "count": {"$sum": "$count"}}}]
    ))
    return rows[0]["count"] if rows else 0


def _clear(db):
    db[SITE_ANALYTICS_COLLECTION].delete_many({})


# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------


def test_static_assets_are_not_counted():
    assert classify_path("/static/css/admin/workspace.css") is None
    assert classify_path("/favicon.ico") is None
    assert classify_path("/manifest.json") is None
    assert classify_path("/robots.txt") is None
    assert classify_path("/sitemap.xml") is None


def test_admin_and_account_pages_are_not_counted():
    assert classify_path("/admin/dashboard") is None
    assert classify_path("/admin/analytics/") is None
    assert classify_path("/users/auth/login") is None
    assert classify_path("/users/settings") is None


def test_health_checks_and_status_are_not_counted():
    assert classify_path("/health") is None
    assert classify_path("/status") is None


def test_api_and_analytics_endpoints_are_not_counted():
    assert classify_path("/api/v1/demonstrations") is None
    assert classify_path("/api/analytics/track_view") is None
    assert classify_path("/mcp/status") is None


def test_demonstration_page_is_classified():
    assert classify_path("/demonstration/abc123") == {
        "page_type": "demonstration",
        "resource_id": "abc123",
    }


def test_demonstration_subresources_are_not_pageviews():
    # Calendar file, share page, child listing: utilities, not pageviews.
    assert classify_path("/demonstration/abc/ics") is None
    assert classify_path("/demonstration/abc/some") is None
    assert classify_path("/demonstration/abc/children") is None


def test_organization_page_is_classified():
    assert classify_path("/organization/org123") == {
        "page_type": "organization",
        "resource_id": "org123",
    }


def test_index_and_generic_pages_are_classified():
    assert classify_path("/")["page_type"] == "index"
    assert classify_path("/terms")["page_type"] == "page"
    assert classify_path("/privacy")["page_type"] == "page"


def test_devices_are_bucketed_coarsely():
    assert classify_device("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)...") == "mobile"
    assert classify_device("Mozilla/5.0 (Android 14; Mobile)") == "mobile"
    assert classify_device("Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X)") == "tablet"
    assert classify_device("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome") == "desktop"
    assert classify_device("Mozilla/5.0 (Macintosh; Intel Mac OS X 14) Safari") == "desktop"
    assert classify_device("Googlebot/2.1 (+http://www.google.com/bot.html)") == "bot"
    assert classify_device("python-requests/2.31") == "bot"
    assert classify_device("curl/8.4.0") == "bot"
    assert classify_device("UptimeRobot/2.0") == "bot"
    assert classify_device("") == "other"


def test_referrers_are_categorized_not_stored_raw():
    assert classify_referrer("", "mielenosoitukset.fi") == "direct"
    assert classify_referrer("https://mielenosoitukset.fi/x", "mielenosoitukset.fi") == "internal"
    assert classify_referrer("https://www.google.com/", "mielenosoitukset.fi") == "google"
    assert classify_referrer("https://www.facebook.com/", "mielenosoitukset.fi") == "facebook"
    assert classify_referrer("https://l.facebook.com/l.php?u=x", "mielenosoitukset.fi") == "facebook"
    assert classify_referrer("https://www.instagram.com/", "mielenosoitukset.fi") == "instagram"
    assert classify_referrer("https://t.co/abc", "mielenosoitukset.fi") == "x-twitter"
    assert classify_referrer("https://www.example.org/page", "mielenosoitukset.fi") == "other"


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


def _create_public_demo(db):
    """Insert an approved public demonstration and return its id string."""
    demo_id = ObjectId()
    db.demonstrations.insert_one(
        {
            "_id": demo_id,
            "title": "Analytics pageview demo",
            "date": (utcnow().date() + timedelta(days=30)).isoformat(),
            "start_time": "12:00",
            "end_time": "14:00",
            "city": "Helsinki",
            "address": "Mannerheimintie 1, Helsinki",
            "description": "Demo used by analytics tests.",
            "approved": True,
            "hide": False,
            "rejected": False,
            "organizers": [],
        }
    )
    return str(demo_id)


def test_multiple_requests_aggregate_into_single_counters(app, db):
    _clear(db)
    demo_id = _create_public_demo(db)
    client = app.test_client()

    with patch_classification(client):
        for _ in range(3):
            assert client.get(f"/demonstration/{demo_id}").status_code == 200

    docs = _counts(db)
    assert len(docs) == 1
    assert docs[0]["page_type"] == "demonstration"
    assert docs[0]["resource_id"] == demo_id
    assert docs[0]["count"] == 3


def test_language_is_recorded(app, db):
    _clear(db)
    demo_id = _create_public_demo(db)
    client = app.test_client()

    with patch_classification(client, language="en"):
        client.get(f"/demonstration/{demo_id}")

    assert _total(db, language="en") == 1
    assert _total(db, language="fi") == 0


def test_device_and_referrer_are_recorded(app, db):
    _clear(db)
    demo_id = _create_public_demo(db)
    client = app.test_client()

    with patch_classification(client, device="mobile", referrer="facebook"):
        client.get(f"/demonstration/{demo_id}")

    assert _total(db, device="mobile", referrer="facebook") == 1


def test_increment_counter_buckets_by_helsinki_local_hour(db):
    from datetime import timezone

    from mielenosoitukset_fi.utils.site_analytics import HELSINKI_TZ

    _clear(db)
    now_helsinki = utcnow().replace(tzinfo=timezone.utc).astimezone(HELSINKI_TZ)
    when_utc = utcnow().replace(tzinfo=None)  # naive-UTC app contract
    increment_counter(page_type="page", when=when_utc)
    increment_counter(page_type="page", when=when_utc)

    docs = _counts(db)
    assert len(docs) == 1
    assert docs[0]["count"] == 2
    assert docs[0]["hour"] == now_helsinki.hour
    assert docs[0]["date"] == now_helsinki.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Request filtering through the actual app
# ---------------------------------------------------------------------------


def test_health_endpoint_does_not_record(app, db):
    _clear(db)
    client = app.test_client()
    client.get("/health")
    assert _counts(db) == []


def test_admin_pages_do_not_record(admin_client, db):
    _clear(db)
    assert admin_client.get("/admin/stats").status_code == 200
    assert _counts(db) == []


def test_static_assets_do_not_record(app, db):
    _clear(db)
    client = app.test_client()
    client.get("/static/css/admin/analytics.css")
    assert _counts(db) == []


def test_api_requests_do_not_record(app, db):
    _clear(db)
    client = app.test_client()
    client.get("/api/v1/demonstrations")
    assert _counts(db) == []


def test_bot_user_agents_do_not_record(app, db, monkeypatch):
    _clear(db)
    monkeypatch.setattr(
        "mielenosoitukset_fi.utils.site_analytics.classify_device",
        lambda ua: "bot",
    )
    demo_id = _create_public_demo(db)
    client = app.test_client()
    client.get(f"/demonstration/{demo_id}")
    assert _counts(db) == []


def test_404_and_errors_are_not_recorded(app, db):
    _clear(db)
    client = app.test_client()
    client.get("/demonstration/nonexistent-object-id")
    assert _counts(db) == []

    # A pending (unapproved) demo returns 401 — not a tracked pageview.
    pending_id = ObjectId()
    db.demonstrations.insert_one(
        {
            "_id": pending_id,
            "title": "Pending demo",
            "date": (utcnow().date() + timedelta(days=30)).isoformat(),
            "approved": False,
            "hide": False,
            "organizers": [],
        }
    )
    client.get(f"/demonstration/{pending_id}")
    assert _counts(db) == []


def test_non_html_responses_are_not_recorded(app, db, monkeypatch):
    _clear(db)
    from mielenosoitukset_fi.utils import site_analytics as sa

    client = app.test_client()
    client.get("/terms")  # HTML page
    html_total = _total(db)
    assert html_total >= 1

    _clear(db)
    client.get("/demonstrations.rss")
    assert _counts(db) == []


def test_analytics_failure_does_not_break_page(app, db, monkeypatch):
    _clear(db)
    demo_id = _create_public_demo(db)

    def boom(*args, **kwargs):
        raise RuntimeError("analytics down")

    monkeypatch.setattr(
        "mielenosoitukset_fi.utils.site_analytics.increment_counter", boom
    )
    client = app.test_client()
    response = client.get(f"/demonstration/{demo_id}")
    assert response.status_code == 200


def test_analytics_can_be_disabled(app, db, app_factory):
    _clear(db)
    demo_id = _create_public_demo(db)

    from tests.conftest import _cleanup_app_resources

    disabled_app = app_factory(SITE_ANALYTICS_ENABLED=False)
    try:
        client = disabled_app.test_client()
        client.get(f"/demonstration/{demo_id}")
        assert _counts(db) == []
    finally:
        _cleanup_app_resources(disabled_app)


# ---------------------------------------------------------------------------
# Admin dashboards
# ---------------------------------------------------------------------------


def _seed_counters(db, demo_id, days=5):
    from datetime import timezone
    from mielenosoitukset_fi.utils.site_analytics import HELSINKI_TZ

    base = utcnow().replace(tzinfo=timezone.utc).astimezone(HELSINKI_TZ)
    for offset in range(days):
        day = (base - timedelta(days=offset)).replace(hour=12, minute=0)
        increment_counter(
            page_type="demonstration",
            resource_id=str(demo_id),
            language="fi" if offset % 2 else "en",
            device="mobile" if offset % 2 else "desktop",
            referrer="google" if offset % 3 else "direct",
            when=day.replace(tzinfo=timezone.utc),
        )


def test_admin_overview_returns_200_and_numbers(admin_client, db):
    _clear(db)
    _seed_counters(db, str(ObjectId()))

    response = admin_client.get("/admin/analytics/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Palvelun analytiikka" in page or "analytiikka" in page.lower()


def test_admin_overview_labels_resourceless_page_types(admin_client, db):
    """Submit/calendar/index views show Finnish labels, not raw type keys."""
    from datetime import timezone as _tz

    from mielenosoitukset_fi.utils.site_analytics import HELSINKI_TZ

    _clear(db)
    base = utcnow().replace(tzinfo=_tz.utc).astimezone(HELSINKI_TZ)
    for page_type in ("submit", "calendar", "index"):
        increment_counter(page_type=page_type, when=base.replace(tzinfo=_tz.utc))

    response = admin_client.get("/admin/analytics/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Ilmoita mielenosoitus" in page
    assert "Kalenteri" in page
    assert "Etusivu" in page


def test_admin_overview_documents_limits(admin_client, db):
    """The dashboard states what is excluded and that no one is identified."""
    _clear(db)
    _seed_counters(db, str(ObjectId()))

    response = admin_client.get("/admin/analytics/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Laskuriin kirjataan vain julkiset" in page


def test_overview_period_math(admin_client, db, app):
    _clear(db)
    demo_id = str(ObjectId())
    _seed_counters(db, demo_id, days=7)

    from mielenosoitukset_fi.utils import site_analytics as sa

    overview = sa.get_overview(days=7)
    assert overview["window"]["current"] == 7
    assert overview["today"]["current"] == 1

    series = sa.get_traffic_series(days=7)
    assert len(series["labels"]) == 7
    assert sum(series["values"]) == 7


def test_demo_analytics_numbers(admin_client, db):
    _clear(db)
    demo_id = str(ObjectId())
    _seed_counters(db, demo_id, days=7)

    from mielenosoitukset_fi.utils import site_analytics as sa

    data = sa.get_demonstration_analytics(demo_id, days=7)
    assert data["total"] == 7
    assert data["today"] == 1
    assert sum(data["daily_values"]) == 7
    assert {row["value"] for row in data["languages"]} == {"fi", "en"}
    assert {row["value"] for row in data["devices"]} == {"mobile", "desktop"}
    assert sum(row["count"] for row in data["languages"]) == 7


def test_demo_analytics_resolves_slug_and_id(db):
    _clear(db)
    demo_id = ObjectId()
    slug = "climate-march-helsinki"
    db.demonstrations.insert_one({"_id": demo_id, "title": "Climate March", "slug": slug})

    from mielenosoitukset_fi.utils import site_analytics as sa

    identifiers = sa.get_demonstration_identifiers(str(demo_id))
    assert str(demo_id) in identifiers
    assert slug in identifiers

    increment_counter(page_type="demonstration", resource_id=slug)
    data = sa.get_demonstration_analytics(str(demo_id), days=7)
    assert data["total"] == 1


def test_admin_demo_analytics_page(admin_client, db):
    _clear(db)
    demo_id = ObjectId()
    db.demonstrations.insert_one(
        {
            "_id": demo_id,
            "title": "Analytics demo",
            "approved": True,
            "date": (utcnow().date() + timedelta(days=30)).isoformat(),
            "start_time": "12:00",
            "end_time": "14:00",
            "city": "Helsinki",
            "address": "Mannerheimintie 1, Helsinki",
            "organizers": [],
        }
    )
    _seed_counters(db, str(demo_id), days=3)

    response = admin_client.get(f"/admin/analytics/demonstration/{demo_id}")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Analytics demo" in page


def test_admin_demo_analytics_unknown_demo_404(admin_client, db):
    response = admin_client.get(f"/admin/analytics/demonstration/{ObjectId()}")
    assert response.status_code == 404


def test_analytics_requires_login(app, db):
    client = app.test_client()
    assert client.get("/admin/analytics/").status_code in {301, 302}


def test_analytics_requires_permission(app, db, seeded_data):
    client = _client_for_user(app, seeded_data["user_id"])
    assert client.get("/admin/analytics/").status_code == 403


def test_top_pages_ranks_demos_and_titles(admin_client, db):
    _clear(db)
    first = ObjectId()
    second = ObjectId()
    for title, oid in (("First demo", first), ("Second demo", second)):
        db.demonstrations.insert_one({"_id": oid, "title": title})

    for _ in range(5):
        increment_counter(page_type="demonstration", resource_id=str(first))
    for _ in range(2):
        increment_counter(page_type="demonstration", resource_id=str(second))
    increment_counter(page_type="index")

    from mielenosoitukset_fi.utils import site_analytics as sa

    rows = sa.get_top_pages(days=30, limit=10)
    assert rows[0]["count"] == 5
    demo_rows = sa.get_top_pages(page_type="demonstration", days=30, limit=10)
    assert demo_rows[0]["resource_id"] == str(first)
    assert demo_rows[0]["count"] == 5


# ---------------------------------------------------------------------------
# Events (searches, language changes, beacon interactions)
# ---------------------------------------------------------------------------


def test_demo_search_event_recorded_once_per_search(app, db):
    _clear(db)
    client = app.test_client()

    assert client.get("/api/v1/demonstrations?search=climate&page=1").status_code == 200
    assert client.get("/api/v1/demonstrations?search=climate&page=1").status_code == 200

    docs = [doc for doc in _counts(db) if doc.get("event") == "demo_search"]
    assert len(docs) == 1
    assert docs[0]["count"] == 2
    assert "climate" in docs[0]["resource_id"]


def test_demo_search_pagination_does_not_record(app, db):
    _clear(db)
    client = app.test_client()

    client.get("/api/v1/demonstrations?search=climate&page=1")
    client.get("/api/v1/demonstrations?search=climate&page=2")

    docs = [doc for doc in _counts(db) if doc.get("event") == "demo_search"]
    assert len(docs) == 1
    assert docs[0]["count"] == 1


def test_plain_list_loads_do_not_record_search(app, db):
    _clear(db)
    client = app.test_client()

    client.get("/api/v1/demonstrations?page=1")
    client.get("/api/v1/demonstrations?city=Helsinki&page=1")

    assert [doc for doc in _counts(db) if doc.get("event")] == []


def test_language_change_event(app_factory, db):
    from tests.conftest import _cleanup_app_resources

    _clear(db)
    app = app_factory(
        BABEL_SUPPORTED_LOCALES=["fi", "en"],
        BABEL_PUBLIC_LOCALES=["fi", "en"],
    )
    try:
        client = app.test_client()
        response = client.get("/set_language/en")
        assert response.status_code in {301, 302}
        events = [doc for doc in _counts(db) if doc.get("event") == "language_change"]
        assert len(events) == 1
        assert events[0]["resource_id"] == "en"
    finally:
        _cleanup_app_resources(app)


def test_beacon_records_allowlisted_events(app, db):
    _clear(db)
    client = app.test_client()

    response = client.post(
        "/api/analytics/event",
        json={"event": "map_interaction", "resource_id": "/demonstration/abc"},
    )
    assert response.status_code == 200

    docs = [doc for doc in _counts(db) if doc.get("event") == "map_interaction"]
    assert len(docs) == 1
    assert docs[0]["resource_id"] == "/demonstration/abc"


def test_beacon_rejects_unknown_events(app, db):
    _clear(db)
    client = app.test_client()

    client.post("/api/analytics/event", json={"event": "keystroke", "resource_id": "a"})
    client.post("/api/analytics/event", json={})
    client.post("/api/analytics/event", data="not json", content_type="text/plain")

    assert [doc for doc in _counts(db) if doc.get("event")] == []


def test_beacon_rejects_cross_origin_referrer(app, db):
    _clear(db)
    client = app.test_client()

    client.post(
        "/api/analytics/event",
        json={"event": "map_interaction"},
        headers={"Referer": "https://evil.example/spam"},
    )

    assert _counts(db) == []


def test_beacon_external_link_uses_hostname_only(app, db):
    _clear(db)
    client = app.test_client()

    client.post(
        "/api/analytics/event",
        json={"event": "external_link", "resource_id": "facebook.com"},
    )

    docs = [doc for doc in _counts(db) if doc.get("event") == "external_link"]
    assert len(docs) == 1
    assert docs[0]["resource_id"] == "facebook.com"


def test_event_totals_and_top_search_terms(db):
    _clear(db)

    increment_counter(event="demo_search", resource_id="climate")
    increment_counter(event="demo_search", resource_id="climate")
    increment_counter(event="demo_search", resource_id="helsinki")
    increment_counter(event="language_change", resource_id="en")
    increment_counter(page_type="index")

    from mielenosoitukset_fi.utils import site_analytics as sa

    totals = {row["event"]: row["count"] for row in sa.get_event_totals(days=30)}
    assert totals == {"demo_search": 3, "language_change": 1}

    top_terms = sa.get_top_event_resources("demo_search", days=30)
    assert top_terms[0]["resource_id"] == "climate"
    assert top_terms[0]["count"] == 2


def test_resource_id_is_length_capped(db):
    _clear(db)
    long_value = "x" * 500

    increment_counter(event="demo_search", resource_id=long_value)

    docs = _counts(db)
    assert len(docs) == 1
    assert len(docs[0]["resource_id"]) == 200


def test_dashboard_shows_events(admin_client, db):
    _clear(db)
    increment_counter(event="demo_submitted", resource_id=str(ObjectId()))
    increment_counter(event="demo_search", resource_id="ilmastomarssi")

    response = admin_client.get("/admin/analytics/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Ilmoitetut mielenosoitukset" in page
    assert "ilmastomarssi" in page


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class patch_classification:
    """Force a deterministic classification for requests made by a client.

    The demo detail route caches rendered pages; requests during tests may
    bypass after_request when caches interfere, so these tests patch the
    classifier used by the middleware via monkeypatching the module
    attribute. That keeps the tests honest: the real middleware code runs.
    """

    def __init__(self, client, language="fi", device="desktop", referrer="direct"):
        self.client = client
        self.language = language
        self.device = device
        self.referrer = referrer
        self._originals = {}

    def __enter__(self):
        from mielenosoitukset_fi.utils import site_analytics as sa

        self._originals["classify"] = sa.classify_request

        def fake_classify(request):
            path_class = sa.classify_path(request.path)
            if path_class is None:
                return None
            path_class = dict(path_class)
            path_class["language"] = self.language
            path_class["device"] = self.device
            path_class["referrer"] = self.referrer
            return path_class

        sa.classify_request = fake_classify
        return self.client

    def __exit__(self, *exc):
        from mielenosoitukset_fi.utils import site_analytics as sa

        sa.classify_request = self._originals["classify"]
        return False
