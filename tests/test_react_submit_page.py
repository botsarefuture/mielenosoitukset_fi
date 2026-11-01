"""The React submission page is opt-in and keeps the legacy server contract."""
import json
import re

import pytest


def _props(page: str) -> dict:
    match = re.search(r'<script type="application/json" id="submit-page-props">(.*?)</script>', page, re.S)
    assert match, "props JSON block is missing"
    return json.loads(match.group(1))


def test_legacy_template_stays_default(client):
    page = client.get("/submit").get_data(as_text=True)

    assert 'data-react-island="submit-progress"' in page
    assert 'data-react-island="submit-page"' not in page


def test_react_template_renders_when_enabled(app, client):
    app.config["PUBLIC_SUBMIT_REACT_ENABLED"] = True
    response = client.get("/submit")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'data-react-island="submit-page"' in page
    assert 'data-props-id="submit-page-props"' in page
    assert "<noscript>" in page
    # The built entry is resolved through the committed manifest.
    assert re.search(r"/frontend/assets/submitReact-[A-Za-z0-9_-]+\.js", page)


def test_react_props_match_the_server_contract(app, client):
    app.config["PUBLIC_SUBMIT_REACT_ENABLED"] = True
    props = _props(client.get("/submit").get_data(as_text=True))

    for key in ("action", "importUrl", "orgSearchUrl", "termsUrl", "privacyUrl", "homeUrl", "guidesUrl",
                "contactUrl", "infoUrl", "token", "cities", "locales", "localeNames",
                "defaultLanguage", "canEditDemo", "messages"):
        assert key in props, key

    assert props["action"].endswith("/submit")
    assert props["importUrl"].endswith("/submit/facebook_import")
    assert props["orgSearchUrl"].endswith("/api/v1/search_organizations")
    assert re.fullmatch(r"[0-9a-f]{32}", props["token"])
    assert props["cities"], "the city list must not be empty"
    assert props["defaultLanguage"] in props["locales"]
    assert len(props["messages"]["steps"]) == 6
    # Behaviour messages the component renders are all translated strings.
    for key in ("errorGeneric", "errorTerms", "conflictConfirm", "submit", "next", "previous"):
        assert isinstance(props["messages"][key], str) and props["messages"][key]


def test_react_props_are_escaped_json_not_template_source(app, client):
    app.config["PUBLIC_SUBMIT_REACT_ENABLED"] = True
    page = client.get("/submit").get_data(as_text=True)
    block = re.search(
        r'<script type="application/json" id="submit-page-props">(.*?)</script>', page, re.S
    ).group(1)

    # tojson() escapes angle brackets so data cannot open markup.
    assert "<" not in block
    assert "</script" not in block


def test_noscript_fallback_posts_the_required_server_fields(app, client):
    app.config["PUBLIC_SUBMIT_REACT_ENABLED"] = True
    page = client.get("/submit").get_data(as_text=True)
    # base.html has its own noscript block; ours is the last one.
    fallback = page.split("<noscript>")[-1].split("</noscript>")[0]

    for field in ("title", "tags", "date", "start_time", "type", "city", "address",
                  "submitter_role", "submitter_name", "submitter_email", "accept_terms",
                  "submission_token"):
        assert f'name="{field}"' in fallback, field
    assert 'method="POST"' in fallback
    assert 'action="/submit"' in fallback


@pytest.mark.parametrize("enabled", [True, False])
def test_submit_route_still_keeps_both_error_contracts(app, client, enabled):
    """Turning the flag on must not change the POST contract."""
    app.config["PUBLIC_SUBMIT_REACT_ENABLED"] = enabled

    # Native posts flash and redirect back, as before.
    native = client.post("/submit", data={})
    assert native.status_code == 302
    assert native.headers["Location"].endswith("/submit")

    # AJAX posts get the JSON error contract the React page depends on.
    ajax = client.post("/submit", data={}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert ajax.status_code == 400
    payload = ajax.get_json()
    assert payload["success"] is False
    assert payload["error_code"]
