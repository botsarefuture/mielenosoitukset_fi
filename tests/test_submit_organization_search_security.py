import json
import re
from pathlib import Path

import pytest


TEMPLATE = Path("mielenosoitukset_fi/templates/submit.html")
WORKSPACE_CSS = Path("mielenosoitukset_fi/static/css/user-workspace.css")
BASE_TEMPLATE = Path("mielenosoitukset_fi/templates/base.html")


@pytest.mark.parametrize("query,expected_names", [
    (None, set()),
    ("   ", set()),
    ("L", set()),
    ("zz", {"zz minimum"}),
    ("  literal [DEMO]  ", {"Literal [demo] organization"}),
    ("x" * 100, {"x" * 100}),
    ("x" * 101, None),
    ("Limit match", {f"Limit match {index}" for index in range(11)}),
])
def test_organization_search_treats_query_as_bounded_literal_text(client, db, query, expected_names):
    names = [
        "Literal [demo] organization", "Literal d organization", "zz minimum", "x" * 100,
        *[f"Limit match {index}" for index in range(11)],
    ]
    db.organizations.insert_many([{"name": name} for name in names])

    response = client.get(
        "/api/v1/search_organizations",
        query_string={} if query is None else {"q": query},
    )
    if expected_names is None:
        assert response.status_code == 400
        error = response.get_json()
        assert set(error) == {"error"}
        assert isinstance(error["error"], str) and error["error"]
        return

    assert response.status_code == 200
    results = response.get_json()
    assert len(results) == min(len(expected_names), 10)
    actual_names = {result["name"] for result in results}
    assert len(actual_names) == len(results)
    assert actual_names <= expected_names


@pytest.mark.parametrize("variant", ["malformed", "missing", "boundary", "overlong"])
def test_organization_search_normalizes_public_result_fields(client, db, variant):
    record = {"name": "Normalization target", "internal_note": "not a public field"}
    expected = {"name": record["name"], "email": "", "website": "", "description": ""}
    if variant == "malformed":
        record.update(email={"unexpected": "mapping"}, website=["https://example.test"],
            description={"unexpected": "mapping"})
    elif variant in {"boundary", "overlong"}:
        excess = int(variant == "overlong")
        record.update(
            name=record["name"].ljust(200 + excess, "n"),
            email="e" * (254 + excess),
            website="w" * (2048 + excess),
            description="d" * (100 + excess),
        )
        expected.update(name=record["name"][:200], email="e" * 254, website="w" * 2048,
            description="d" * 100 + ("..." if excess else ""))
    inserted = db.organizations.insert_one(record)

    response = client.get(
        "/api/v1/search_organizations",
        query_string={"q": "Normalization target"},
    )
    assert response.status_code == 200
    assert response.get_json() == [{"id": str(inserted.inserted_id), **expected}]


def test_submit_autocomplete_uses_shared_safe_native_controls():
    template = TEMPLATE.read_text(encoding="utf-8")
    css = WORKSPACE_CSS.read_text(encoding="utf-8")
    base = BASE_TEMPLATE.read_text(encoding="utf-8")

    autocomplete_source = template.split(
        "const ORGANIZATION_SEARCH_EMPTY", 1
    )[1].split("window.removeOrganizer", 1)[0]

    assert "document.createElement('button')" in autocomplete_source
    assert "name.textContent = organization.name" in autocomplete_source
    assert "detail.textContent = value" in autocomplete_source
    assert "button.addEventListener('click'" in autocomplete_source
    assert "resultsContainer.replaceChildren" in autocomplete_source
    assert "const organizationSearchRequests = new Map()" in template
    assert "controller: new AbortController()" in autocomplete_source
    assert (
        "organizationSearchRequests.get(organizerNum) !== requestState"
        in autocomplete_source
    )
    assert "innerHTML" not in autocomplete_source
    assert "onclick=" not in autocomplete_source
    assert 'class="user-autocomplete__results"' in template
    assert "maxlength=\"100\"" in template
    assert ".user-autocomplete__option:focus-visible" in css
    assert "min-height: 2.75rem" in css
    assert re.search(r"css/user-workspace\.css.*v='\d{8}-user-workspace-\d+'", base)


def test_submit_autocomplete_feedback_is_localized_in_english_and_swedish(
    app, client
):
    app.config.update(
        BABEL_SUPPORTED_LOCALES=["fi", "en", "sv"],
        BABEL_PUBLIC_LOCALES=["fi", "en", "sv"],
    )
    for locale, results_label, error_message in (
        ("en", "Organization search results", "Organization search failed. Try again."),
        (
            "sv",
            "Resultat för organisationssökning",
            "Organisationssökningen misslyckades. Försök igen.",
        ),
    ):
        with client.session_transaction() as session:
            session["locale"] = locale

        page = client.get("/submit").get_data(as_text=True)

        assert results_label in page
        assert json.dumps(error_message, ensure_ascii=True)[1:-1] in page


@pytest.mark.e2e
@pytest.mark.integration
def test_submit_autocomplete_renders_and_selects_untrusted_values_safely(
    live_server, browser_page
):
    payload = '<img src=x onerror="window.organizationSearchExecuted=true">'
    email = "org'quote@example.test"
    website = 'https://example.test/path?quote="yes"'
    description = '<script>window.organizationSearchExecuted=true</script>'

    def fulfill_search(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                [
                    {
                        "id": "safe-id",
                        "name": payload,
                        "email": email,
                        "website": website,
                        "description": description,
                    }
                ]
            ),
        )

    browser_page.add_init_script("window.organizationSearchExecuted = false;")
    browser_page.route("**/api/v1/search_organizations?**", fulfill_search)
    browser_page.goto(f"{live_server}/submit", wait_until="domcontentloaded")
    browser_page.evaluate("showPage(4)")

    search_input = browser_page.locator("#org_search_1")
    search_input.fill("safe organization")
    option = browser_page.locator(
        "#org_search_results_1 .user-autocomplete__option"
    )
    option.wait_for(state="visible")

    results = browser_page.locator("#org_search_results_1")
    assert payload in results.text_content()
    assert description in results.text_content()
    assert results.locator("img, script").count() == 0
    assert results.locator("[onclick], [onerror], [onmouseover]").count() == 0
    assert browser_page.evaluate("window.organizationSearchExecuted") is False

    assert search_input.get_attribute("aria-expanded") == "true"
    search_input.press("Tab")
    assert option.evaluate("element => element === document.activeElement")
    option.press("Enter")

    assert browser_page.locator("#organizer_name_1").input_value() == payload
    assert browser_page.locator("#organizer_email_1").input_value() == email
    assert browser_page.locator("#organizer_website_1").input_value() == website
    assert search_input.input_value() == ""
    assert search_input.get_attribute("aria-expanded") == "false"
    assert results.is_hidden()
    assert browser_page.evaluate("window.organizationSearchExecuted") is False


@pytest.mark.e2e
@pytest.mark.integration
def test_submit_autocomplete_ignores_an_older_delayed_failure(
    live_server, browser_page
):
    browser_page.goto(f"{live_server}/submit", wait_until="domcontentloaded")
    browser_page.evaluate("showPage(4)")
    browser_page.evaluate(
        """
        () => {
          window.organizationSearchPending = new Map();
          window.fetch = (url) => new Promise((resolve, reject) => {
            const query = new URL(url, window.location.href).searchParams.get("q");
            window.organizationSearchPending.set(query, { resolve, reject });
          });
        }
        """
    )

    search_input = browser_page.locator("#org_search_1")
    search_input.fill("older query")
    browser_page.wait_for_function(
        "window.organizationSearchPending.has('older query')"
    )
    search_input.fill("newer query")
    browser_page.wait_for_function(
        "window.organizationSearchPending.has('newer query')"
    )

    browser_page.evaluate(
        """
        () => window.organizationSearchPending.get("newer query").resolve({
          ok: true,
          status: 200,
          json: async () => [{
            id: "newer",
            name: "Newer result",
            email: "newer@example.test",
            website: "",
            description: "Latest response",
          }],
        })
        """
    )
    option = browser_page.locator(
        "#org_search_results_1 .user-autocomplete__option"
    )
    option.wait_for(state="visible")
    assert "Newer result" in option.text_content()

    browser_page.evaluate(
        """
        () => window.organizationSearchPending
          .get("older query")
          .reject(new Error("delayed older failure"))
        """
    )
    browser_page.wait_for_timeout(50)

    results = browser_page.locator("#org_search_results_1")
    assert "Newer result" in results.text_content()
    assert "Organisaatiohaku ei onnistunut" not in results.text_content()
    assert results.get_attribute("aria-busy") is None
    assert search_input.get_attribute("aria-expanded") == "true"
