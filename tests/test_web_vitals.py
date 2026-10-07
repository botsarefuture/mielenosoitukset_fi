"""Privacy, aggregation, and delivery contracts for first-party Web Vitals."""

from pathlib import Path

from mielenosoitukset_fi.utils import site_analytics


ROOT = Path(__file__).parents[1]


def _collection(db):
    return db[site_analytics.WEB_VITALS_COLLECTION]


def _headers(path="/demonstration/example"):
    return {
        "Referer": f"http://localhost{path}",
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; Mobile) Chrome/124",
    }


def test_vitals_endpoint_stores_only_coarse_aggregate_dimensions(
    client, db, seeded_data
):
    response = client.post(
        "/api/analytics/vitals",
        json={"metric": "LCP", "value": 1632.4, "id": "must-not-be-stored"},
        headers=_headers("/demonstration/secret-resource-id"),
    )

    assert response.status_code == 200
    document = _collection(db).find_one()
    assert document["metric"] == "LCP"
    assert document["page_type"] == "demonstration"
    assert document["device"] == "mobile"
    assert document["count"] == 1
    assert document["sum"] == 1632.4
    assert sum(document["histogram"].values()) == 1
    for forbidden in ("id", "resource_id", "url", "path", "visitor", "session"):
        assert forbidden not in document


def test_vitals_endpoint_rejects_cross_origin_invalid_and_bot_input(
    client, db, seeded_data
):
    collection = _collection(db)

    client.post(
        "/api/analytics/vitals",
        json={"metric": "LCP", "value": 1200},
        headers={**_headers(), "Referer": "https://evil.example/demo"},
    )
    client.post(
        "/api/analytics/vitals",
        json={"metric": "LCP", "value": 1200},
        headers={**_headers(), "User-Agent": "Googlebot/2.1"},
    )
    for payload in (
        {"metric": "unknown", "value": 1},
        {"metric": "CLS", "value": -1},
        {"metric": "CLS", "value": 6},
        {"metric": "TTFB", "value": 60001},
        {"metric": "INP", "value": "not-a-number"},
    ):
        client.post("/api/analytics/vitals", json=payload, headers=_headers())

    assert collection.count_documents({}) == 0


def test_vitals_endpoint_rejects_oversized_bodies_before_parsing(
    client, db, seeded_data
):
    collection = _collection(db)

    response = client.post(
        "/api/analytics/vitals",
        data=b"x" * 513,
        content_type="application/octet-stream",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert collection.count_documents({}) == 0


def test_vitals_endpoint_accepts_bounded_chunked_body_without_content_length(
    client, db, seeded_data
):
    response = client.open(
        "/api/analytics/vitals",
        method="POST",
        data=b'{"metric":"TTFB","value":321}',
        content_type="application/json",
        headers=_headers(),
        environ_overrides={"CONTENT_LENGTH": "", "wsgi.input_terminated": True},
    )

    assert response.status_code == 200
    assert _collection(db).count_documents({"metric": "TTFB"}) == 1


def test_vitals_endpoint_bounds_chunked_body_without_content_length(
    client, db, seeded_data
):
    response = client.open(
        "/api/analytics/vitals",
        method="POST",
        data=b"x" * 513,
        content_type="application/octet-stream",
        headers=_headers(),
        environ_overrides={"CONTENT_LENGTH": "", "wsgi.input_terminated": True},
    )

    assert response.status_code == 200
    assert _collection(db).count_documents({}) == 0


def test_vitals_summary_reports_bounded_histogram_percentiles(
    client, db, seeded_data
):
    for value in range(1000, 2000, 100):
        client.post(
            "/api/analytics/vitals",
            json={"metric": "LCP", "value": value},
            headers=_headers("/demonstrations"),
        )

    summary = {
        row["metric"]: row
        for row in site_analytics.get_web_vitals_summary(days=7)
    }
    assert summary["LCP"] == {
        "metric": "LCP",
        "count": 10,
        "sufficient": True,
        "average": 1450.0,
        "p50": 1400,
        "p75": 1700,
        "p95": 1900,
        "p99": 1900,
    }
    assert summary["INP"]["count"] == 0
    assert summary["INP"]["p50"] is None


def test_web_vitals_migration_is_registered_and_bounded(db, seeded_data):
    from mielenosoitukset_fi.utils import migration_runner
    from mielenosoitukset_fi.utils.migrations import migration_010_web_vitals

    assert "010_web_vitals" in [item["id"] for item in migration_runner.MIGRATIONS]
    migration_010_web_vitals.migrate_web_vitals(db)
    indexes = list(_collection(db).list_indexes())
    assert any(index.get("unique") for index in indexes)
    assert any(index.get("expireAfterSeconds") == 0 for index in indexes)


def test_public_pages_load_pinned_first_party_vitals_without_identifiers():
    base = (ROOT / "mielenosoitukset_fi/templates/base.html").read_text()
    script = (ROOT / "mielenosoitukset_fi/static/js/site_analytics.js").read_text()

    assert (
        "https://cdn2.mielenosoitukset.fi/vendor/web-vitals/6.2.2/"
        "web-vitals.iife.js"
    ) in base
    assert (
        'integrity="sha256-Hl6bmva41xz+9QjlqGnFO0zyu8ytjJtaxmTDTpP2FRo="'
        in base
    )
    for private_prefix in ("/admin", "/users", "/board", "/developer"):
        assert f"not request.path.startswith('{private_prefix}')" in base
        assert f'path.indexOf("{private_prefix}") === 0' in script
    assert 'window.webVitals.onLCP(sendVital, { reportAllChanges: true })' in script
    assert 'window.webVitals.onINP(sendVital, { reportAllChanges: true })' in script
    assert 'window.webVitals.onCLS(sendVital, { reportAllChanges: true })' in script
    assert "window.webVitals.onTTFB(sendVital)" in script
    assert 'JSON.stringify({ metric: name, value: pendingVitals[name] })' in script
    assert "var queued = navigator.sendBeacon(" in script
    assert "if (queued) sentVitals[name] = true;" in script
    assert 'window.addEventListener("pagehide"' in script
    assert 'document.addEventListener("visibilitychange"' in script
    assert 'document.visibilityState === "hidden"' in script
    assert 'window.addEventListener("pageshow"' in script
    assert "if (!event.persisted) return;" in script
    assert script.count("pendingVitals = Object.create(null)") == 2
    assert script.count("sentVitals = Object.create(null)") == 2
    assert "if (event.persisted) return" in script
    assert "metric.id" not in script
    assert "metric.attribution" not in script


def test_web_vitals_summary_failure_is_optional_for_admin_overview():
    source = (
        ROOT / "mielenosoitukset_fi/admin/admin_site_analytics_bp.py"
    ).read_text()

    assert 'logger.exception("Failed to read Web Vitals summary")' in source
    assert "web_vitals = []" in source
