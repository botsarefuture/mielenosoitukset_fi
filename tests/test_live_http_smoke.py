import json
from urllib.request import urlopen

import pytest
from playwright.sync_api import expect

from tests.conftest import _seed_database


@pytest.mark.integration
def test_public_pages_render_over_real_http(app, db, live_server, browser_page):
    seeded_data = _seed_database(app, db)

    # Since #1007 the home page ships a server-rendered React shell whose
    # events grid is built in the browser from the public /api/home contract;
    # `demos-grid` no longer exists in the server HTML.
    with urlopen(f"{live_server}/", timeout=10) as index_response:
        index_body = index_response.read().decode("utf-8")
        assert index_response.status == 200
    assert 'data-react-island="home"' in index_body
    assert 'home-events' in index_body
    assert "Ilmoita mielenosoituksesta" in index_body
    assert 'id="home-props"' in index_body

    with urlopen(
        f"{live_server}/demonstration/{seeded_data['demo_id']}",
        timeout=10,
    ) as detail_response:
        detail_body = detail_response.read().decode("utf-8")
        assert detail_response.status == 200
    assert "Climate March Helsinki" in detail_body

    with urlopen(
        f"{live_server}/organization/{seeded_data['org_id']}",
        timeout=10,
    ) as organization_response:
        organization_body = organization_response.read().decode("utf-8")
        assert organization_response.status == 200
    assert "Test Organization" in organization_body

    # The home island must still deliver real content over the live HTTP server.
    # The public /api/home endpoint is a Go service that does not run in tests, so
    # the fetch is fulfilled with the same contract; the rendered empty state
    # proves the island fetched, validated and rendered the response end to end.
    page = browser_page
    page.route("**/api/home**", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"events": [], "recommended": False})))
    page.goto(f"{live_server}/", wait_until="networkidle")
    expect(page.locator('[data-react-island="home"][data-react-mounted="true"]')).to_be_visible()
    expect(page.locator(".home-intro h1")).to_contain_text("Tulevat mielenosoitukset")
    expect(page.locator(".home-empty")).to_contain_text("Uusia mielenosoituksia")
