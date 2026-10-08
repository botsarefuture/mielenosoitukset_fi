"""Privacy, aggregation, and delivery contracts for first-party Web Vitals."""

from importlib import import_module
from inspect import unwrap
from pathlib import Path
from unittest.mock import Mock

import pytest

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
    assert 'window.addEventListener("pagehide", flushVitals)' in script
    assert "metric.id" not in script
    assert "metric.attribution" not in script


@pytest.mark.e2e
@pytest.mark.parametrize("persisted", [False, True])
def test_pagehide_flushes_vitals_once_and_restoration_starts_a_new_visit(
    browser_page, persisted
):
    browser_page.evaluate(
        """() => {
            window.vitalCallbacks = {};
            window.vitalBeacons = [];
            window.webVitals = {};
            for (const name of ["CLS", "INP", "LCP", "TTFB"]) {
                window.webVitals[`on${name}`] = callback => {
                    window.vitalCallbacks[name] = callback;
                };
            }
            navigator.sendBeacon = (url, body) => {
                window.vitalBeacons.push({ url, body });
                return true;
            };
        }"""
    )
    browser_page.add_script_tag(
        path=str(ROOT / "mielenosoitukset_fi/static/js/site_analytics.js")
    )

    def beacons():
        return browser_page.evaluate(
            """() => Promise.all(window.vitalBeacons.map(async ({ url, body }) => ({
                url, payload: JSON.parse(await body.text())
            })))"""
        )

    # Exercise pagehide without visibilitychange, as a fallback for cache entry.
    browser_page.evaluate(
        """persisted => {
            window.vitalCallbacks.LCP({ name: "LCP", value: 1200 });
            window.vitalCallbacks.LCP({ name: "LCP", value: 1600 });
            window.dispatchEvent(new PageTransitionEvent("pagehide", { persisted }));
        }""",
        persisted,
    )
    first_visit = [
        {"url": "/api/analytics/vitals", "payload": {"metric": "LCP", "value": 1600}}
    ]
    assert beacons() == first_visit

    browser_page.evaluate(
        """() => {
            Object.defineProperty(document, "visibilityState", { value: "hidden" });
            document.dispatchEvent(new Event("visibilitychange"));
            window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: false }));
            window.vitalCallbacks.LCP({ name: "LCP", value: 1800 });
            window.dispatchEvent(new PageTransitionEvent("pagehide"));
        }"""
    )
    assert beacons() == first_visit

    browser_page.evaluate(
        """() => {
            window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true }));
            window.dispatchEvent(new PageTransitionEvent("pagehide"));
        }"""
    )
    assert beacons() == first_visit

    browser_page.evaluate(
        """() => {
            window.vitalCallbacks.LCP({ name: "LCP", value: 900 });
            window.dispatchEvent(new PageTransitionEvent("pagehide", { persisted: true }));
        }"""
    )
    assert beacons() == first_visit + [
        {"url": "/api/analytics/vitals", "payload": {"metric": "LCP", "value": 900}}
    ]


@pytest.mark.parametrize("summary_fails", [False, True])
def test_admin_overview_reads_vitals_once_and_preserves_devices(
    app, monkeypatch, summary_fails
):
    analytics = import_module("mielenosoitukset_fi.admin.admin_site_analytics_bp")

    for name in (
        "get_overview", "get_traffic_series", "get_visitor_overview",
        "get_visitor_series", "get_top_pages", "get_event_totals",
        "get_top_event_resources",
    ):
        monkeypatch.setattr(analytics, name, Mock(return_value=[]))
    devices = [{"value": "mobile", "count": 12}]
    breakdown = Mock(
        side_effect=lambda dimension, **kwargs: devices if dimension == "device" else []
    )
    monkeypatch.setattr(analytics, "get_breakdown", breakdown)
    summary = [{"metric": "LCP", "count": 12}]
    read_vitals = Mock(
        return_value=summary,
        side_effect=RuntimeError("optional storage unavailable") if summary_fails else None,
    )
    monkeypatch.setattr(analytics, "get_web_vitals_summary", read_vitals)
    monkeypatch.setattr(analytics, "log_admin_action_V2", Mock())
    render = Mock(return_value="dashboard rendered")
    monkeypatch.setattr(analytics, "render_template", render)

    with app.test_request_context("/admin/analytics/?range=7"):
        assert unwrap(analytics.site_overview)() == "dashboard rendered"

    read_vitals.assert_called_once_with(days=7)
    assert render.call_args.kwargs["devices"] == devices
    assert render.call_args.kwargs["web_vitals"] == ([] if summary_fails else summary)
    assert render.call_args.kwargs["range_days"] == 7
    assert breakdown.call_args_list[1].args == ("device",)


@pytest.fixture
def vital_browser(browser_page):
    """Capture the real script's callbacks and beacons without external traffic."""
    browser_page.evaluate(
        """() => {
            window.vitalCallbacks = {};
            window.vitalBeacons = [];
            window.webVitals = {};
            for (const name of ["CLS", "INP", "LCP", "TTFB"]) {
                window.webVitals[`on${name}`] = callback => {
                    window.vitalCallbacks[name] = callback;
                };
            }
            navigator.sendBeacon = (url, body) => {
                window.vitalBeacons.push({url, body});
                return true;
            };
        }"""
    )
    browser_page.add_script_tag(
        path=str(ROOT / "mielenosoitukset_fi/static/js/site_analytics.js")
    )
    return browser_page


def _vital_beacons(page):
    return page.evaluate(
        """() => Promise.all(window.vitalBeacons.map(async ({url, body}) => ({
            url, type: body.type, payload: JSON.parse(await body.text())
        })))"""
    )


@pytest.mark.e2e
@pytest.mark.parametrize("failure", ["rejected", "exception"])
def test_failed_beacon_retries_latest_value_without_resending_successes(vital_browser, failure):
    vital_browser.evaluate(
        """failure => {
            const send = navigator.sendBeacon;
            let first = true;
            navigator.sendBeacon = (url, body) => {
                if (first) {
                    first = false;
                    if (failure === "exception") throw new Error("beacon failed");
                    return false;
                }
                return send(url, body);
            };
            window.vitalCallbacks.CLS({name: "CLS", value: 0.02});
            window.vitalCallbacks.LCP({name: "LCP", value: 1200});
            window.dispatchEvent(new PageTransitionEvent("pagehide"));
        }""",
        failure,
    )
    lcp = {"url": "/api/analytics/vitals", "type": "application/json",
           "payload": {"metric": "LCP", "value": 1200}}
    assert _vital_beacons(vital_browser) == [lcp]
    vital_browser.evaluate(
        """() => {
            window.vitalCallbacks.CLS({name: "CLS", value: 0.03});
            window.vitalCallbacks.LCP({name: "LCP", value: 1800});
            Object.defineProperty(document, "visibilityState", {value: "hidden"});
            document.dispatchEvent(new Event("visibilitychange"));
            window.dispatchEvent(new PageTransitionEvent("pagehide"));
        }"""
    )
    assert _vital_beacons(vital_browser) == [lcp, {
        "url": "/api/analytics/vitals", "type": "application/json",
        "payload": {"metric": "CLS", "value": 0.03},
    }]


@pytest.mark.e2e
def test_browser_rejects_invalid_metrics_and_only_sends_latest_numeric_values(vital_browser):
    vital_browser.evaluate(
        """() => {
            const callback = window.vitalCallbacks.LCP;
            for (const metric of [null, {}, {name: "FID", value: 1},
                    ...[NaN, Infinity, -Infinity, -1, "42", null, true].map(
                        value => ({name: "LCP", value}))]) {
                callback(metric);
            }
            window.dispatchEvent(new PageTransitionEvent("pagehide"));
        }"""
    )
    assert _vital_beacons(vital_browser) == []
    vital_browser.evaluate(
        """() => {
            for (const name of ["CLS", "INP", "LCP", "TTFB"]) {
                window.vitalCallbacks[name]({name, value: 42});
                window.vitalCallbacks[name]({name, value: 0, id: "private",
                    attribution: {url: "https://secret.example", target: "#secret"}});
            }
            Object.defineProperty(document, "visibilityState", {
                value: "visible", configurable: true
            });
            document.dispatchEvent(new Event("visibilitychange"));
        }"""
    )
    assert _vital_beacons(vital_browser) == []
    vital_browser.evaluate(
        """() => {
            Object.defineProperty(document, "visibilityState", {value: "hidden"});
            document.dispatchEvent(new Event("visibilitychange"));
            window.dispatchEvent(new PageTransitionEvent("pagehide"));
        }"""
    )
    assert _vital_beacons(vital_browser) == [
        {"url": "/api/analytics/vitals", "type": "application/json",
         "payload": {"metric": name, "value": 0}}
        for name in ("CLS", "INP", "LCP", "TTFB")
    ]


@pytest.mark.e2e
def test_missing_vitals_library_preserves_other_analytics(browser_page):
    browser_page.set_content('<div class="leaflet-container"></div>')
    browser_page.evaluate(
        """() => {
            delete window.webVitals;
            window.vitalBeacons = [];
            navigator.sendBeacon = (url, body) => {
                window.vitalBeacons.push({url, body});
                return true;
            };
        }"""
    )
    browser_page.add_script_tag(path=str(ROOT / "mielenosoitukset_fi/static/js/site_analytics.js"))
    browser_page.evaluate(
        """() => {
            const map = document.querySelector(".leaflet-container");
            map.dispatchEvent(new Event("pointerdown"));
            map.dispatchEvent(new Event("pointerdown"));
            window.dispatchEvent(new PageTransitionEvent("pagehide"));
        }"""
    )
    beacons = _vital_beacons(browser_page)
    assert len(beacons) == 1
    assert beacons[0]["url"] == "/api/analytics/event"
    assert beacons[0]["payload"]["event"] == "map_interaction"


@pytest.mark.parametrize("body,content_type", [
    (b'{"metric":"CLS",', "application/json"),
    (b'{"metric":"CLS","value":"\xff"}', "application/json"),
    (b"metric=CLS&value=\xff", "application/x-www-form-urlencoded"),
    (b"[]", "application/json"),
    (b"null", "application/json"),
    (b'{"metric":"CLS","value":0.1}', "text/plain"),
])
def test_vitals_endpoint_malformed_body_is_successful_without_storage(client, db, body, content_type):
    response = client.post("/api/analytics/vitals", data=body, content_type=content_type, headers=_headers())
    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert _collection(db).count_documents({}) == 0


@pytest.mark.parametrize("chunked", [False, True])
def test_vitals_endpoint_accepts_exactly_512_bytes(client, db, chunked):
    body = b'{"metric":"TTFB","value":321}'.ljust(512, b" ")
    overrides = {"CONTENT_LENGTH": "", "wsgi.input_terminated": True} if chunked else {}
    response = client.open(
        "/api/analytics/vitals", method="POST", data=body, content_type="application/json",
        headers=_headers(), environ_overrides=overrides,
    )
    assert response.status_code == 200
    assert _collection(db).find_one({"metric": "TTFB"})["sum"] == 321


def test_vitals_endpoint_accepts_urlencoded_beacons(client, db):
    response = client.post(
        "/api/analytics/vitals", data="metric=+cls+&value=0.125",
        content_type="application/x-www-form-urlencoded", headers=_headers(),
    )
    assert response.status_code == 200
    document = _collection(db).find_one({"metric": "CLS"})
    assert document["sum"] == 0.125
    assert document["histogram"] == {"b012": 1}
