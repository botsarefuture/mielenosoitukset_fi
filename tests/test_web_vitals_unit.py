"""Isolated validation and reporting tests for anonymous Web Vitals."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from flask import Flask, request

from mielenosoitukset_fi.utils import site_analytics
from mielenosoitukset_fi.utils.migrations import migration_010_web_vitals


@pytest.fixture
def vital_store(monkeypatch):
    collection = Mock()
    monkeypatch.setattr(site_analytics, "_web_vitals_collection", lambda: collection)
    return collection


@pytest.fixture
def vital_request():
    return SimpleNamespace(
        host="example.test",
        headers={
            "Referer": "https://example.test/demonstration/private-id?token=secret",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Mobile) Chrome/124",
        },
    )


@pytest.mark.parametrize("metric", ["CLS", "INP", "LCP", "TTFB"])
@pytest.mark.parametrize("value", [None, "", "invalid", [], {}, -0.001, float("nan"), float("inf"), float("-inf")])
def test_invalid_values_never_write(vital_store, vital_request, metric, value):
    assert site_analytics.record_web_vital(
        {"metric": metric, "value": value}, request=vital_request
    ) is False
    vital_store.update_one.assert_not_called()


@pytest.mark.parametrize("payload", [None, [], "LCP", 42, {}, {"value": 10}, {"metric": "FID", "value": 10}])
def test_invalid_payloads_never_write(vital_store, vital_request, payload):
    assert site_analytics.record_web_vital(payload, request=vital_request) is False
    vital_store.update_one.assert_not_called()


@pytest.mark.parametrize("metric,value", [("CLS", 5.001), ("INP", 60000.001), ("LCP", 60000.001), ("TTFB", 60000.001)])
def test_values_above_validation_ceiling_never_write(vital_store, vital_request, metric, value):
    assert site_analytics.record_web_vital(
        {"metric": metric, "value": value}, request=vital_request
    ) is False
    vital_store.update_one.assert_not_called()


@pytest.mark.parametrize("metric", ["INP", "LCP", "TTFB"])
@pytest.mark.parametrize("value,bucket", [
    (0, "b000"), (50, "b000"), (50.001, "b001"),
    (5000, "b099"), (5000.001, "b100"), (5250, "b100"),
    (10000, "b119"), (10000.001, "b120"), (15000, "b120"),
    (15000.001, "b121"), (30000, "b121"), (30000.001, "b122"),
    (60000, "b122"),
])
def test_millisecond_bucket_boundaries(vital_store, vital_request, metric, value, bucket):
    assert site_analytics.record_web_vital(
        {"metric": metric, "value": value}, request=vital_request
    ) is True
    assert vital_store.update_one.call_args.args[1]["$inc"] == {
        "count": 1, "sum": value, f"histogram.{bucket}": 1,
    }


@pytest.mark.parametrize("value,bucket", [
    (0, "b000"), (0.01, "b000"), (0.01001, "b001"),
    (1, "b099"), (1.00001, "b100"), (1.1, "b100"),
    (4.9, "b138"), (4.90001, "b139"), (5, "b139"),
])
def test_cls_bucket_boundaries(vital_store, vital_request, value, bucket):
    assert site_analytics.record_web_vital(
        {"metric": "CLS", "value": value}, request=vital_request
    ) is True
    assert vital_store.update_one.call_args.args[1]["$inc"] == {
        "count": 1, "sum": value, f"histogram.{bucket}": 1,
    }


@pytest.mark.parametrize("referrer", [
    "", "/demonstrations", "https://[", "https://evil.example/",
    "https://example.test.evil.example/", "https://example.test@evil.example/",
    "https://example.test/admin/analytics/", "https://example.test/users/settings",
    "https://example.test/board/", "https://example.test/developer/",
    "https://example.test/api/analytics/vitals", "https://example.test/static/app.js",
])
def test_missing_untrusted_and_private_referrers_never_write(vital_store, vital_request, referrer):
    vital_request.headers["Referer"] = referrer
    assert site_analytics.record_web_vital(
        {"metric": "LCP", "value": 100}, request=vital_request
    ) is False
    vital_store.update_one.assert_not_called()


def test_bot_samples_never_write(vital_store, vital_request):
    vital_request.headers["User-Agent"] = "Googlebot/2.1"
    assert site_analytics.record_web_vital(
        {"metric": "LCP", "value": 100}, request=vital_request
    ) is False
    vital_store.update_one.assert_not_called()


@pytest.mark.parametrize("month,utc_hour,local_date,midnight_hour", [
    (1, 21, "2026-01-15", 22), (1, 22, "2026-01-16", 22),
    (7, 20, "2026-07-15", 21), (7, 21, "2026-07-16", 21),
])
@pytest.mark.parametrize("aware", [False, True])
def test_recording_uses_local_day_and_discards_client_dimensions(
    vital_store, vital_request, month, utc_hour, local_date, midnight_hour, aware
):
    moment = datetime(2026, month, 15, utc_hour, 30)
    if aware:
        moment = moment.replace(tzinfo=timezone.utc)
    payload = {
        "metric": " lcp ", "value": "1632.4", "page_type": "admin",
        "device": "bot", "date": "1900-01-01", "histogram": {"unbounded": 1},
        "id": "private", "url": "https://secret.example", "visitor": "secret",
    }
    assert site_analytics.record_web_vital(payload, request=vital_request, when=moment) is True
    dimensions = {"date": local_date, "page_type": "demonstration", "device": "mobile", "metric": "LCP"}
    # Midnight in Helsinki falls on the preceding UTC date in both seasons.
    midnight = datetime.fromisoformat(local_date).replace(tzinfo=timezone.utc) - timedelta(days=1)
    expires = midnight.replace(hour=midnight_hour) + timedelta(days=400)
    vital_store.update_one.assert_called_once_with(
        dimensions,
        {
            "$inc": {"count": 1, "sum": 1632.4, "histogram.b032": 1},
            "$min": {"min": 1632.4}, "$max": {"max": 1632.4},
            "$set": {"last_seen_at": moment.replace(tzinfo=timezone.utc)},
            "$setOnInsert": {**dimensions, "expires_at": expires},
        },
        upsert=True,
    )


def test_request_context_is_used_when_request_is_omitted(vital_store):
    app = Flask(__name__)
    with app.test_request_context(
        "/api/analytics/vitals", base_url="https://EXAMPLE.test:8443",
        headers={"Referer": "https://example.test:8443/", "User-Agent": "Mozilla/5.0"},
    ):
        assert request.host.lower() == "example.test:8443"
        assert site_analytics.record_web_vital({"metric": "TTFB", "value": 0}) is True
    dimensions = vital_store.update_one.call_args.args[0]
    assert dimensions["page_type"] == "index"
    assert dimensions["metric"] == "TTFB"


def test_storage_failure_is_invisible_to_the_caller(vital_store, vital_request):
    vital_store.update_one.side_effect = RuntimeError("database unavailable")
    assert site_analytics.record_web_vital(
        {"metric": "INP", "value": 250}, request=vital_request
    ) is False
    vital_store.update_one.assert_called_once()


@pytest.mark.parametrize("count", [0, 9, 10])
def test_summary_suppresses_percentiles_until_ten_samples(vital_store, count):
    vital_store.find.return_value = [
        {"metric": "CLS", "count": count, "sum": count * 0.02, "histogram": {"b001": count}}
    ]
    rows = site_analytics.get_web_vitals_summary()
    assert [row["metric"] for row in rows] == ["LCP", "INP", "CLS", "TTFB"]
    row = rows[2]
    assert row["count"] == count
    assert row["sufficient"] is (count >= 10)
    assert row["average"] == (0.02 if count else None)
    for key in ("p50", "p75", "p95", "p99"):
        assert row[key] == (0.02 if count >= 10 else None)
    for row in (rows[0], rows[1], rows[3]):
        assert row == {"metric": row["metric"], "count": 0, "sufficient": False,
                       "average": None, "p50": None, "p75": None, "p95": None, "p99": None}


def test_summary_merges_histograms_across_days_routes_and_devices(vital_store, monkeypatch):
    monkeypatch.setattr(site_analytics, "utcnow", lambda: datetime(2026, 7, 15, 22))
    vital_store.find.return_value = [
        {"date": "2026-07-15", "page_type": "index", "device": "desktop",
         "metric": "LCP", "count": 6, "sum": 300, "histogram": {"b000": 6}},
        {"date": "2026-07-16", "page_type": "demonstration", "device": "mobile",
         "metric": "LCP", "count": 4, "sum": 1500, "histogram": {"b000": 1, "b009": 3}},
        {"metric": "INP", "count": 10, "sum": 1000, "histogram": {"b001": 10}},
        {"metric": "unknown", "count": 1000, "sum": 1, "histogram": {"b000": 1000}},
    ]
    rows = site_analytics.get_web_vitals_summary(days=7)
    vital_store.find.assert_called_once_with({"date": {"$gte": "2026-07-10", "$lte": "2026-07-16"}})
    assert rows[0] == {"metric": "LCP", "count": 10, "sufficient": True,
                       "average": 180, "p50": 50, "p75": 500, "p95": 500, "p99": 500}
    assert rows[1] == {"metric": "INP", "count": 10, "sufficient": True,
                       "average": 100, "p50": 100, "p75": 100, "p95": 100, "p99": 100}


def test_summary_honors_custom_minimum_samples(vital_store):
    vital_store.find.return_value = [{"metric": "TTFB", "count": 2, "sum": 175, "histogram": {"b001": 2}}]
    row = site_analytics.get_web_vitals_summary(minimum_samples=2)[3]
    assert row["sufficient"] is True
    assert row["average"] == 87.5
    assert [row[key] for key in ("p50", "p75", "p95", "p99")] == [100] * 4


@pytest.mark.parametrize("percentile,expected", [(0.5, 100), (0.75, 200), (0.95, 300), (0.99, 300)])
def test_percentiles_use_nearest_rank_in_numeric_bucket_order(percentile, expected):
    # Insertion order differs from bucket order; ranks must round up.
    histogram = {"b002": 1, "b000": 2, "b001": 1}
    assert site_analytics._histogram_percentile(histogram, 4, (100, 200, 300), percentile) == expected


def test_migration_defines_exact_unique_reporting_and_expiry_indexes():
    collection = Mock()
    collection.index_information.return_value = {"web_vitals_daily_expiry": {}, "_id_": {}}
    result = migration_010_web_vitals.migrate_web_vitals({"web_vitals_daily": collection})
    assert collection.create_index.call_args_list == [
        call([("date", 1), ("page_type", 1), ("device", 1), ("metric", 1)],
             unique=True, name="web_vitals_daily_dimensions"),
        call([("date", 1), ("metric", 1)], name="web_vitals_daily_reporting"),
        call("expires_at", expireAfterSeconds=0, name="web_vitals_daily_expiry"),
    ]
    assert result == {"web_vitals_indexes": ["_id_", "web_vitals_daily_expiry"]}
