"""The React host retains anonymous page/campaign/visitor aggregates."""

import pytest


def _headers(**extra):
    return {
        "Referer": "http://localhost/",
        "Origin": "http://localhost",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124",
        **extra,
    }


def _clear(db):
    db.site_analytics.delete_many({})
    db.site_analytics_visitors.delete_many({})


def test_public_app_beacon_records_one_page_without_counting_the_api(client, app, db):
    app.config.update(SITE_ANALYTICS_ENABLED=True, SITE_ANALYTICS_VISITORS_ENABLED=True)
    _clear(db)
    response = client.post(
        "/api/analytics/pageview", json={"referrer": "https://www.google.com/?q=private"},
        headers=_headers(),
    )

    assert response.status_code == 200
    rows = list(db.site_analytics.find())
    assert len(rows) == 1
    assert rows[0]["page_type"] == "index"
    assert rows[0]["count"] == 1
    assert rows[0]["referrer"] == "google"
    assert db.site_analytics_visitors.count_documents({}) == 1
    visitor = db.site_analytics_visitors.find_one()
    assert visitor["pageviews"] == 1
    for row in [*rows, visitor]:
        assert not {"url", "path", "ip", "user_agent", "cookie", "session"}.intersection(row)
        assert "private" not in str(row)


@pytest.mark.parametrize("headers,payload", [
    ({"Referer": "https://external.test/"}, {}),
    ({"Referer": "http://localhost:9999/"}, {}),
    ({"Referer": "https://localhost/"}, {}),
    ({"Referer": "http://localhost/city/helsinki/tanaan"}, {}),
    ({"Referer": ""}, {}),
    ({"Origin": "https://external.test"}, {}),
    ({"Sec-Fetch-Site": "cross-site"}, {}),
    ({"DNT": "1"}, {}),
    ({"User-Agent": "Googlebot"}, {}),
    ({"Purpose": "prefetch"}, {}),
    ({}, {"path": "/admin", "referrer": ""}),
    ({}, {"referrer": 42}),
])
def test_public_app_beacon_rejects_ineligible_signals(client, app, db, headers, payload):
    app.config.update(SITE_ANALYTICS_ENABLED=True, SITE_ANALYTICS_VISITORS_ENABLED=True)
    _clear(db)
    assert client.post("/api/analytics/pageview", json=payload, headers=_headers(**headers)).status_code == 200
    assert db.site_analytics.count_documents({}) == 0
    assert db.site_analytics_visitors.count_documents({}) == 0


def test_public_app_beacon_respects_config_and_body_limit(client, app, db):
    _clear(db)
    app.config["SITE_ANALYTICS_ENABLED"] = False
    assert client.post("/api/analytics/pageview", json={}, headers=_headers()).status_code == 200
    app.config["SITE_ANALYTICS_ENABLED"] = True
    assert client.post(
        "/api/analytics/pageview", json={"referrer": "x" * 2048}, headers=_headers(),
    ).status_code == 200
    assert db.site_analytics.count_documents({}) == 0


def test_public_app_beacon_preserves_campaign_counts_separately(client, app, db):
    app.config["SITE_ANALYTICS_ENABLED"] = True
    _clear(db)
    headers = _headers(Referer="http://localhost/?mtm_campaign=Spring&mtm_source=newsletter&private=discard")
    assert client.post("/api/analytics/pageview", json={}, headers=headers).status_code == 200
    page = db.site_analytics.find_one({"page_type": "index"})
    campaign = db.site_analytics.find_one({"event": "campaign_view"})
    assert page["count"] == campaign["count"] == 1
    assert campaign["campaign"]["name"] == "Spring"
    assert "private" not in str(campaign)


def test_public_session_summary_exposes_public_telemetry_flags(client, app):
    app.config.update(SITE_ANALYTICS_ENABLED=False, MATOMO_ENABLED=True)
    payload = client.get("/api/session").get_json()
    assert payload["site_analytics_enabled"] is False
    assert payload["matomo_enabled"] is True


@pytest.mark.parametrize("path,page_type", [
    ("/demonstrations", "demonstrations"),
    ("/city/Helsinki", "city"),
    ("/tag/rauha", "tag"),
    ("/organization/66fa58601102367d5d52887f", "organization"),
])
def test_migrated_listing_display_and_search_signals(client, app, db, path, page_type):
    app.config.update(SITE_ANALYTICS_ENABLED=True, SITE_ANALYTICS_VISITORS_ENABLED=True)
    _clear(db)
    headers = _headers(Referer="http://localhost" + path)
    client.post("/api/analytics/pageview", json={}, headers=headers)
    page = db.site_analytics.find_one({"page_type": page_type})
    assert page and page["count"] == 1
    client.post("/api/analytics/event", json={"event": "demo_search", "resource_id": "rauha"}, headers=headers)
    search = db.site_analytics.find_one({"event": "demo_search"})
    assert search and search["count"] == 1


@pytest.mark.parametrize("path", ["/", "/admin", "/city/Helsinki/tanaan"])
def test_search_beacon_is_restricted_to_migrated_listings(client, app, db, path):
    app.config["SITE_ANALYTICS_ENABLED"] = True
    _clear(db)
    client.post("/api/analytics/event", json={"event": "demo_search", "resource_id": "rauha"},
                headers=_headers(Referer="http://localhost" + path))
    assert db.site_analytics.count_documents({"event": "demo_search"}) == 0
