"""Tests for distinct-visitor analytics.

The pageview path is covered by ``tests/test_site_analytics.py``; these tests
cover the separate visitor collection, its privacy properties and the way
unavailable history is reported.
"""

import datetime
from datetime import timezone

import pytest

from mielenosoitukset_fi.app import create_app
from mielenosoitukset_fi.utils import site_analytics
from mielenosoitukset_fi.utils.time_utils import utcnow


def _helsinki_today():
    """Interpret the project's naive ``utcnow`` value explicitly as UTC."""
    return utcnow().replace(tzinfo=timezone.utc).astimezone(
        site_analytics.HELSINKI_TZ
    ).date()


@pytest.fixture(autouse=True)
def _clear_visitor_collections(db):
    db[site_analytics.SITE_ANALYTICS_COLLECTION].delete_many({})
    db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].delete_many({})
    yield
    db[site_analytics.SITE_ANALYTICS_COLLECTION].delete_many({})
    db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].delete_many({})


# ---------------------------------------------------------------------------
# Helper: build a fake Flask request-like object for record_visitor_for_request
# ---------------------------------------------------------------------------

class _FakeRequest:
    """Minimal request object that satisfies record_visitor_for_request."""
    def __init__(self, remote_addr):
        self.environ = {"REMOTE_ADDR": remote_addr}
        self.headers = {}


# ---------------------------------------------------------------------------
# Deduplication semantics (test visitor_hash directly)
# ---------------------------------------------------------------------------


def test_hash_same_ip_device_same_week_is_stable():
    # Pick a moment safely inside a 7-day bucket (not near boundaries)
    moment = datetime.datetime(2024, 1, 3, 12, 0, tzinfo=timezone.utc)
    later_same_week = moment + datetime.timedelta(days=3)

    first = site_analytics.visitor_hash("192.0.2.1", device="desktop", when=moment, secret=b"k")
    same = site_analytics.visitor_hash("192.0.2.1", device="desktop", when=later_same_week, secret=b"k")
    assert first == same
    assert first is not None


def test_hash_rotates_after_one_week():
    # Pick a moment and exactly 7 days later (crosses bucket)
    moment = datetime.datetime(2024, 1, 3, 12, 0, tzinfo=timezone.utc)
    next_week = moment + datetime.timedelta(days=7)

    first = site_analytics.visitor_hash("192.0.2.1", device="desktop", when=moment, secret=b"k")
    rotated = site_analytics.visitor_hash("192.0.2.1", device="desktop", when=next_week, secret=b"k")
    assert first != rotated


def test_hash_depends_on_device():
    moment = datetime.datetime(2024, 1, 1, tzinfo=timezone.utc)
    base = site_analytics.visitor_hash("192.0.2.1", device="desktop", when=moment, secret=b"k")
    assert base != site_analytics.visitor_hash("192.0.2.1", device="mobile", when=moment, secret=b"k")


def test_hash_depends_on_address():
    moment = datetime.datetime(2024, 1, 1, tzinfo=timezone.utc)
    base = site_analytics.visitor_hash("192.0.2.1", device="desktop", when=moment, secret=b"k")
    assert base != site_analytics.visitor_hash("192.0.2.2", device="desktop", when=moment, secret=b"k")


def test_hash_depends_on_secret():
    moment = datetime.datetime(2024, 1, 1, tzinfo=timezone.utc)
    base = site_analytics.visitor_hash("192.0.2.1", device="desktop", when=moment, secret=b"k")
    assert base != site_analytics.visitor_hash("192.0.2.1", device="desktop", when=moment, secret=b"other")


def test_invalid_or_unparsable_address_yields_no_hash():
    assert site_analytics.visitor_hash("not-an-ip", secret=b"k") is None
    assert site_analytics.visitor_hash("0.0.0.0", secret=b"k") is None
    assert site_analytics.visitor_hash("", secret=b"k") is None


def test_hash_length_is_configured():
    h = site_analytics.visitor_hash("192.0.2.1", secret=b"k")
    assert len(h) == site_analytics.VISITOR_HASH_LENGTH


def test_hash_ignores_ipv4_mapped_ipv6_form():
    moment = datetime.datetime(2024, 1, 1, tzinfo=timezone.utc)
    v4 = site_analytics.visitor_hash("192.0.2.10", secret=b"k", when=moment)
    mapped = site_analytics.visitor_hash("::ffff:192.0.2.10", secret=b"k", when=moment)
    assert v4 == mapped


# ---------------------------------------------------------------------------
# Visitor recording with DB
# ---------------------------------------------------------------------------


def test_record_visitor_creates_document(db, app):
    """record_visitor_for_request inserts/upserts one visitor doc."""
    with app.app_context():
        site_analytics.record_visitor_for_request(
            _FakeRequest("192.0.2.10"), device="desktop"
        )

    today = _helsinki_today().strftime("%Y-%m-%d")
    doc = db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].find_one({"date": today})
    assert doc is not None
    assert doc["pageviews"] == 1
    assert doc["visitor_hash"] == site_analytics.visitor_hash("192.0.2.10", device="desktop", secret=app.config["SECRET_KEY"].encode())
    assert len(doc["visitor_hash"]) == site_analytics.VISITOR_HASH_LENGTH


def test_record_visitor_same_ip_same_day_increments_pageviews(db, app):
    with app.app_context():
        site_analytics.record_visitor_for_request(_FakeRequest("192.0.2.11"), device="desktop")
        site_analytics.record_visitor_for_request(_FakeRequest("192.0.2.11"), device="desktop")

    today = _helsinki_today().strftime("%Y-%m-%d")
    doc = db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].find_one({"date": today})
    assert doc["pageviews"] == 2


def test_record_visitor_different_ips_are_distinct(db, app):
    with app.app_context():
        site_analytics.record_visitor_for_request(_FakeRequest("192.0.2.20"), device="desktop")
        site_analytics.record_visitor_for_request(_FakeRequest("192.0.2.21"), device="desktop")

    today = _helsinki_today().strftime("%Y-%m-%d")
    count = db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].count_documents({"date": today})
    assert count == 2


def test_record_visitor_different_device_buckets_are_distinct(db, app):
    with app.app_context():
        site_analytics.record_visitor_for_request(_FakeRequest("192.0.2.30"), device="desktop")
        site_analytics.record_visitor_for_request(_FakeRequest("192.0.2.30"), device="mobile")

    today = _helsinki_today().strftime("%Y-%m-%d")
    count = db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].count_documents({"date": today})
    assert count == 2


def test_record_visitor_unknown_addresses_ignored(db, app):
    with app.app_context():
        site_analytics.record_visitor_for_request(_FakeRequest("0.0.0.0"), device="desktop")
        site_analytics.record_visitor_for_request(_FakeRequest("::"), device="desktop")

    today = _helsinki_today().strftime("%Y-%m-%d")
    count = db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].count_documents({"date": today})
    assert count == 0


def test_record_visitor_disabled_flag(db, app):
    with app.app_context():
        site_analytics.record_visitor_for_request(_FakeRequest("192.0.2.40"), device="desktop")
    today = _helsinki_today().strftime("%Y-%m-%d")
    count = db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].count_documents({"date": today})
    assert count == 1

    app.config["SITE_ANALYTICS_VISITORS_ENABLED"] = False
    with app.app_context():
        site_analytics.record_visitor_for_request(_FakeRequest("192.0.2.41"), device="desktop")
    # Should not have created a new visitor document for the second IP
    count2 = db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].count_documents({"date": today})
    assert count2 == 1


# ---------------------------------------------------------------------------
# Read path: visitor_total and overview
# ---------------------------------------------------------------------------


def test_visitor_total_counts_distinct_hashes(db):
    today = _helsinki_today()
    db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].insert_many([
        {"date": today.strftime("%Y-%m-%d"), "visitor_hash": "aaa", "bucket": 1, "pageviews": 2, "expires_at": utcnow()},
        {"date": today.strftime("%Y-%m-%d"), "visitor_hash": "bbb", "bucket": 1, "pageviews": 1, "expires_at": utcnow()},
        {"date": today.strftime("%Y-%m-%d"), "visitor_hash": "ccc", "bucket": 1, "pageviews": 5, "expires_at": utcnow()},
    ])
    assert site_analytics._visitor_total(today, today) == 3


def test_visitor_total_zero_when_no_docs(db):
    today = _helsinki_today()
    assert site_analytics._visitor_total(today, today) == 0


def test_get_visitor_overview_structure(db):
    today = _helsinki_today()
    db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].insert_one({
        "date": today.strftime("%Y-%m-%d"), "visitor_hash": "h1", "bucket": 1, "pageviews": 1, "expires_at": utcnow()
    })
    overview = site_analytics.get_visitor_overview(days=7)
    for key in ("today", "week", "month", "window", "window_days", "tracked_from", "available"):
        assert key in overview
    assert overview["available"] is True
    assert overview["tracked_from"] == today.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Read path: visitor series and availability of history
# ---------------------------------------------------------------------------


def test_no_data_reports_unavailable_not_zero(db):
    overview = site_analytics.get_visitor_overview(days=7)
    assert overview["available"] is False
    for period in ("today", "week", "month", "window"):
        assert overview[period]["current"] is None
        assert overview[period]["previous"] is None
        assert overview[period]["available"] is False


def test_period_fully_before_tracking_is_unavailable(db):
    old_date = datetime.date(2024, 5, 1)
    db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].insert_one({
        "date": "2024-06-01",
        "visitor_hash": "abc123abc123abc1",
        "bucket": 0,
        "pageviews": 1,
        "expires_at": datetime.datetime(2024, 6, 1, tzinfo=timezone.utc),
    })
    assert site_analytics.visitor_data_start() == "2024-06-01"

    overview = site_analytics.get_visitor_overview(
        start=datetime.date(2024, 5, 1), end=datetime.date(2024, 5, 31)
    )
    assert overview["window"]["current"] is None
    assert overview["window"]["available"] is False


def test_visitor_series_marks_pre_tracking_days_as_none(db):
    db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].insert_one({
        "date": "2024-06-05",
        "visitor_hash": "abc123abc123abc1",
        "bucket": 0,
        "pageviews": 2,
        "expires_at": datetime.datetime(2024, 6, 5, tzinfo=timezone.utc),
    })
    series = site_analytics.get_visitor_series(
        start=datetime.date(2024, 6, 1), end=datetime.date(2024, 6, 7)
    )
    assert series["tracked_from"] == "2024-06-05"
    assert series["values"][:4] == [None, None, None, None]
    assert series["values"][4] == 1
    assert series["values"][5:] == [0, 0]


def test_tracking_start_note_present_in_overview(db):
    db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].insert_one({
        "date": "2024-06-05",
        "visitor_hash": "abc123abc123abc1",
        "bucket": 0,
        "pageviews": 1,
        "expires_at": datetime.datetime(2024, 6, 5, tzinfo=timezone.utc),
    })
    overview = site_analytics.get_visitor_overview(
        start=datetime.date(2024, 6, 1), end=datetime.date(2024, 6, 30)
    )
    assert overview["tracked_from"] == "2024-06-05"
    assert overview["window"]["current"] == 1


def test_visitor_series_shape_matches_traffic_series(db):
    start = datetime.date(2024, 6, 1)
    end = datetime.date(2024, 6, 3)
    visitors = site_analytics.get_visitor_series(start=start, end=end)
    traffic = site_analytics.get_traffic_series(start=start, end=end)
    assert visitors["labels"] == traffic["labels"]
    assert len(visitors["values"]) == len(traffic["values"]) == 3


# ---------------------------------------------------------------------------
# Salt rotation limitation (documented behaviour)
# ---------------------------------------------------------------------------


def test_salt_rotation_dedupes_only_within_a_week(db, app):
    monday = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    next_monday = monday + datetime.timedelta(days=7)

    with app.app_context():
        site_analytics.record_visitor_for_request(
            _FakeRequest("192.0.2.55"), device="desktop", when=monday
        )
        site_analytics.record_visitor_for_request(
            _FakeRequest("192.0.2.55"), device="desktop", when=next_monday
        )

    week1 = monday.astimezone(site_analytics.HELSINKI_TZ).date()
    week2 = next_monday.astimezone(site_analytics.HELSINKI_TZ).date()
    assert site_analytics._visitor_total(week1, week1) == 1
    assert site_analytics._visitor_total(week2, week2) == 1
    # Documented limitation: the same person is counted once per salt week.
    assert site_analytics._visitor_total(week1, week2) == 2


# ---------------------------------------------------------------------------
# Migration registration
# ---------------------------------------------------------------------------


def test_visitor_migration_is_registered():
    from mielenosoitukset_fi.utils import migration_runner

    ids = [m["id"] for m in migration_runner.MIGRATIONS]
    assert "008_visitor_analytics" in ids


def test_visitor_migration_creates_indexes(db):
    from mielenosoitukset_fi.utils.migrations import migration_008_visitor_analytics as migration

    migration.migrate_visitor_analytics(db)

    indexes = {
        index["name"]: index
        for index in db[site_analytics.SITE_ANALYTICS_VISITORS_COLLECTION].list_indexes()
    }
    # unique compound index on date + visitor_hash
    has_unique = any(i.get("unique") for i in indexes.values())
    assert has_unique, "expected unique compound index on (date, visitor_hash)"
    # TTL index on expires_at
    ttl = [i for i in indexes.values() if i.get("expireAfterSeconds") is not None]
    assert ttl, "expected a TTL index for retention"
    assert ttl[0]["expireAfterSeconds"] == 0
    # key is a SON object, convert to list for comparison
    assert list(ttl[0]["key"].items()) == [("expires_at", 1)]
