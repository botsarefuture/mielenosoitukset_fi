import json
from pathlib import Path

import pytest


TEMPLATE_PATH = Path("mielenosoitukset_fi/templates/kampanja/index.html")


def _set_locale(client, locale):
    with client.session_transaction() as session:
        session["locale"] = locale


def test_campaign_volunteer_feedback_contract_uses_accessible_in_page_status():
    source = TEMPLATE_PATH.read_text(encoding="utf-8")
    volunteer_script = source.split("// Volunteer form (async POST)", 1)[1].split(
        "// Newsletter subscribe function", 1
    )[0]

    assert 'id="vol-msg" class="flash-message flash-message--inline" role="status"' in source
    assert 'aria-live="polite"' in source
    assert 'aria-atomic="true"' in source
    assert 'id="vol-submit"' in source
    assert "alert(" not in volunteer_script
    assert "volunteerMsgText.textContent = message" in volunteer_script
    assert "volunteerForm.querySelectorAll(':invalid')" in volunteer_script
    assert ").filter((field) => !field.value.trim())" in volunteer_script
    assert "...missingRequiredFields" in volunteer_script
    assert "field.setAttribute('aria-invalid', 'true')" in volunteer_script
    assert "firstInvalidField.focus()" in volunteer_script
    assert "if (volunteerForm.dataset.requestPending === 'true') return" in volunteer_script
    assert "volunteerForm.dataset.requestPending = 'true'" in volunteer_script
    assert "volunteerSubmit.disabled = true" in volunteer_script
    assert "volunteerSubmit.setAttribute('aria-busy', 'true')" in volunteer_script
    assert "} finally {" in volunteer_script
    assert "delete volunteerForm.dataset.requestPending" in volunteer_script
    assert "volunteerSubmit.disabled = false" in volunteer_script
    assert "volunteerSubmit.removeAttribute('aria-busy')" in volunteer_script


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("fi", "Nimi ja sähköpostiosoite ovat pakollisia."),
        ("en", "Name and email address are required."),
        ("sv", "Namn och e-postadress krävs."),
    ],
)
def test_campaign_volunteer_api_localizes_required_fields_error(
    app, client, locale, expected
):
    app.config["BABEL_PUBLIC_LOCALES"] = ["fi", "en", "sv"]
    _set_locale(client, locale)

    response = client.post("/kampanja/api/volunteers", json={"name": "Example"})

    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": expected}


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   ", "email": "volunteer@example.test"},
        {"name": "Volunteer", "email": "  \t"},
        {"name": None, "email": "volunteer@example.test"},
    ],
)
def test_campaign_volunteer_api_rejects_blank_normalized_required_values(
    client, db, payload
):
    before = db.volunteers.count_documents({})

    response = client.post("/kampanja/api/volunteers", json=payload)

    assert response.status_code == 400
    assert db.volunteers.count_documents({}) == before


@pytest.mark.parametrize(
    ("locale", "expected_messages"),
    [
        (
            "fi",
            (
                "Tarkista korostetut tiedot ja yritä uudelleen.",
                "Kiitos ilmoittautumisestasi! Tarkista sähköpostisi vahvistaaksesi ilmoittautumisen.",
                "Ilmoittautuminen epäonnistui. Yritä uudelleen.",
                "Yhteys palveluun epäonnistui. Yritä myöhemmin uudelleen.",
            ),
        ),
        (
            "en",
            (
                "Check the highlighted information and try again.",
                "Thank you for signing up! Check your email to confirm your registration.",
                "Registration failed. Please try again.",
                "Could not connect to the service. Please try again later.",
            ),
        ),
        (
            "sv",
            (
                "Kontrollera de markerade uppgifterna och försök igen.",
                "Tack för din anmälan! Kontrollera din e-post för att bekräfta anmälan.",
                "Anmälan misslyckades. Försök igen.",
                "Det gick inte att ansluta till tjänsten. Försök igen senare.",
            ),
        ),
    ],
)
def test_campaign_page_embeds_localized_volunteer_feedback(
    app, client, locale, expected_messages
):
    app.config["BABEL_PUBLIC_LOCALES"] = ["fi", "en", "sv"]
    _set_locale(client, locale)

    response = client.get("/kampanja/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for message in expected_messages:
        assert json.dumps(message, ensure_ascii=True) in body


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize(
    ("status", "body", "content_type", "abort", "expected"),
    [
        (201, '{"success": true}', "application/json", False, "Kiitos ilmoittautumisestasi!"),
        (400, '{"success": false, "error": "Tarkista tiedot."}', "application/json", False, "Tarkista tiedot."),
        (429, '{"success": false, "error": "Yritä hetken kuluttua."}', "application/json", False, "Yritä hetken kuluttua."),
        (500, '{"success": false}', "application/json", False, "Ilmoittautuminen epäonnistui."),
        (200, "not-json", "text/plain", False, "Ilmoittautuminen epäonnistui."),
        (0, "", "text/plain", True, "Yhteys palveluun epäonnistui."),
    ],
)
def test_campaign_volunteer_feedback_handles_request_outcomes(
    live_server,
    browser_page,
    status,
    body,
    content_type,
    abort,
    expected,
):
    def handle_volunteer(route):
        if abort:
            route.abort("failed")
            return
        route.fulfill(status=status, body=body, content_type=content_type)

    browser_page.route("**/kampanja/api/volunteers", handle_volunteer)
    browser_page.goto(f"{live_server}/kampanja/", wait_until="domcontentloaded")
    browser_page.locator("#vol-name").fill("Test User")
    browser_page.locator("#vol-email").fill("test@example.test")
    browser_page.locator("#vol-submit").click()

    feedback = browser_page.locator("#vol-msg")
    feedback.wait_for(state="visible")
    assert expected in feedback.inner_text()
    assert not browser_page.locator("#vol-submit").is_disabled()
    assert browser_page.locator("#vol-submit").get_attribute("aria-busy") is None


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize(
    "name,email,expected_field,expected_message",
    [
        ("", "", "vol-name", "Nimi ja sähköpostiosoite ovat pakollisia."),
        ("Test User", "not-an-email", "vol-email", "Tarkista korostetut tiedot"),
    ],
)
def test_campaign_volunteer_validation_focuses_first_invalid_field(
    live_server, browser_page, name, email, expected_field, expected_message
):
    browser_page.goto(f"{live_server}/kampanja/", wait_until="domcontentloaded")
    browser_page.locator("#vol-name").fill(name)
    browser_page.locator("#vol-email").fill(email)
    browser_page.locator("#vol-submit").click()

    assert browser_page.evaluate("document.activeElement.id") == expected_field
    assert browser_page.locator(f"#{expected_field}").get_attribute("aria-invalid") == "true"
    assert browser_page.locator("#vol-fields").get_attribute("aria-invalid") is None
    assert expected_message in browser_page.locator("#vol-msg").inner_text()


@pytest.mark.e2e
@pytest.mark.integration
def test_campaign_volunteer_validation_rejects_whitespace_only_name(
    live_server, browser_page
):
    request_count = 0

    def handle_volunteer(route):
        nonlocal request_count
        request_count += 1
        route.fulfill(status=201, body='{"success": true}', content_type="application/json")

    browser_page.route("**/kampanja/api/volunteers", handle_volunteer)
    browser_page.goto(f"{live_server}/kampanja/", wait_until="domcontentloaded")
    browser_page.locator("#vol-name").fill("   ")
    browser_page.locator("#vol-email").fill("volunteer@example.test")
    browser_page.locator("#vol-submit").click()

    assert browser_page.evaluate("document.activeElement.id") == "vol-name"
    assert "Nimi ja sähköpostiosoite ovat pakollisia." in browser_page.locator(
        "#vol-msg"
    ).inner_text()
    assert request_count == 0


@pytest.mark.e2e
@pytest.mark.integration
def test_campaign_volunteer_double_submit_starts_one_request(live_server, browser_page):
    request_count = 0

    def handle_volunteer(route):
        nonlocal request_count
        request_count += 1
        route.fulfill(
            status=201,
            body='{"success": true}',
            content_type="application/json",
        )

    browser_page.route("**/kampanja/api/volunteers", handle_volunteer)
    browser_page.goto(f"{live_server}/kampanja/", wait_until="domcontentloaded")
    browser_page.locator("#vol-name").fill("Test User")
    browser_page.locator("#vol-email").fill("test@example.test")

    browser_page.evaluate(
        """() => {
            const form = document.querySelector('#volunteer-form');
            form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        }"""
    )

    browser_page.locator("#vol-msg").wait_for(state="visible")
    assert request_count == 1


@pytest.mark.e2e
@pytest.mark.integration
def test_campaign_without_javascript_disables_both_signups(live_server, playwright_browser):
    context = playwright_browser.new_context(java_script_enabled=False)
    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(live_server) else route.abort())
    try:
        page = context.new_page()
        page.goto(f"{live_server}/kampanja/", wait_until="domcontentloaded")
        assert page.locator("#vol-submit").is_disabled()
        assert page.locator('#newsletter-form button').is_disabled()
        assert page.locator("#vol-name").is_disabled()
        assert not page.locator("#vol-msg").is_visible()
        assert not page.locator("#newsletter-msg").is_visible()
        assert "Tietojasi ei ole lähetetty" in page.locator("#vapaaehtoiseksi").inner_text()
        assert page.locator('#vapaaehtoiseksi a[href="mailto:tuki@mielenosoitukset.fi"]').count() >= 1
        assert not page.url.split("/kampanja/", 1)[1]
    finally:
        context.close()


@pytest.mark.e2e
@pytest.mark.integration
def test_campaign_newsletter_preserves_signup_integration(live_server, browser_page):
    import json
    requests = []

    def signup(route):
        requests.append(route.request.post_data_json)
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"message": "ok"}))

    browser_page.route("https://mailist.luova.club/signup", signup)
    browser_page.goto(f"{live_server}/kampanja/", wait_until="domcontentloaded")
    browser_page.locator("#email").fill("newsletter@example.test")
    browser_page.locator('#newsletter-form button').click()
    browser_page.locator("#newsletter-msg.show").wait_for()
    assert requests == [{"email": "newsletter@example.test", "list_id": "68d26ca27f8e9dee7c846a22"}]
    assert "Tilauksesi onnistui" in browser_page.locator("#newsletter-msg").inner_text()
