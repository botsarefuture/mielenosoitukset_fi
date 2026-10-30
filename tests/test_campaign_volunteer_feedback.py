import json

import pytest


@pytest.fixture(autouse=True)
def published_campaign(db, seeded_data):
    """Existing public-content checks exercise the explicitly published state."""
    db.campaign_settings.update_one(
        {"_id": "public_pages"}, {"$set": {"published": True}}, upsert=True
    )
    yield
    db.campaign_settings.delete_one({"_id": "public_pages"})




def _set_locale(client, locale):
    with client.session_transaction() as session:
        session["locale"] = locale


def test_campaign_loads_its_page_and_shared_header_entries_with_translated_json_props(client):
    import re

    page = client.get("/kampanja/").get_data(as_text=True)
    props = json.loads(re.search(r'<script id="campaign-page-props" type="application/json">(.*?)</script>', page, re.S).group(1))
    assert props["volunteer"]["endpoint"] == "/kampanja/api/volunteers"
    assert "Nimi ja sähköpostiosoite" in props["volunteer"]["messages"]["required"]
    assert 'data-react-island="campaign-page"' in page
    assert '<fieldset class="campaign-fallback" disabled="">' in page
    scripts = re.findall(r'<script type="module" src="([^"]+)"', page)
    assert len(scripts) == 2
    assert scripts[0].startswith("/static/frontend/assets/header-")
    assert scripts[1].startswith("/static/frontend/assets/campaign-")
    for script in scripts:
        assert client.get(script).status_code == 200


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
        (401, '{"success": false, "error": "Kirjaudu sisään."}', "application/json", False, "Kirjaudu sisään."),
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
    assert "Uutiskirjeen tilaus onnistui." in browser_page.locator("#newsletter-msg").inner_text()


@pytest.mark.e2e
@pytest.mark.integration
def test_react_volunteer_signup_preserves_payload_and_confirmation_flow(
    live_server, browser_page, db, monkeypatch
):
    from mielenosoitukset_fi.kampanja.routes import email_sender

    queued = []
    monkeypatch.setattr(email_sender, "queue_email", lambda **kwargs: queued.append(kwargs))
    browser_page.goto(f"{live_server}/kampanja/", wait_until="domcontentloaded")
    values = {
        "name": "  Test Volunteer  ", "email": "react-volunteer@example.test",
        "phone": " 040 123 4567 ", "city": " Turku ", "notes": " Tarrojen jakaminen ",
    }
    for name, value in values.items():
        browser_page.locator(f"#vol-{name}").fill(value)
    browser_page.locator("#vol-submit").click()
    browser_page.wait_for_function("document.querySelector('#vol-msg').textContent.includes('Kiitos')")

    volunteer = db.volunteers.find_one({"email": values["email"]})
    assert volunteer is not None
    for name, value in values.items():
        assert volunteer[name] == value.strip()
    assert volunteer["confirmed"] is False
    assert len(queued) == 1
    assert queued[0]["recipients"] == [values["email"]]
    token = volunteer["confirmation_token"]
    assert queued[0]["context"]["confirm_link"].endswith(f"/kampanja/confirm/{token}")
    assert browser_page.locator("#vol-name").input_value() == ""
    browser_page.goto(f"{live_server}/kampanja/confirm/{token}")
    confirmed = db.volunteers.find_one({"_id": volunteer["_id"]})
    assert confirmed["confirmed"] is True
    assert "confirmation_token" not in confirmed


@pytest.mark.e2e
@pytest.mark.integration
def test_react_volunteer_pending_error_and_retry_keep_user_values(live_server, browser_page):
    requests = []
    browser_page.route("**/kampanja/api/volunteers", lambda route: requests.append(route))
    browser_page.goto(f"{live_server}/kampanja/", wait_until="domcontentloaded")
    browser_page.locator("#vol-name").fill("Test Volunteer")
    browser_page.locator("#vol-email").fill("volunteer@example.test")
    browser_page.locator("#vol-submit").click()
    browser_page.wait_for_function("document.querySelector('#vol-submit').getAttribute('aria-busy') === 'true'")
    assert browser_page.locator("#vol-name").is_disabled()
    assert "Lähetetään" in browser_page.locator("#vol-submit").inner_text()
    assert len(requests) == 1
    requests.pop().fulfill(status=429, content_type="application/json", body=json.dumps({
        "success": False, "error": '<img src=x onerror="alert(1)"> Odota hetki.',
    }))
    browser_page.locator("#vol-msg").wait_for(state="visible")
    assert browser_page.locator("#vol-msg").get_attribute("role") == "alert"
    assert "<img" in browser_page.locator("#vol-msg").inner_text()
    assert browser_page.locator("#vol-msg img").count() == 0
    assert browser_page.locator("#vol-name").input_value() == "Test Volunteer"
    assert browser_page.locator("#vol-email").input_value() == "volunteer@example.test"
    browser_page.locator("#vol-submit").click()
    browser_page.wait_for_function("document.querySelector('#vol-submit').disabled")
    assert len(requests) == 1
    requests.pop().fulfill(status=201, content_type="application/json", body='{"success":true}')
    browser_page.wait_for_function("document.querySelector('#vol-msg').textContent.includes('Kiitos')")
    assert browser_page.locator("#vol-msg").get_attribute("role") == "status"


@pytest.mark.e2e
@pytest.mark.integration
def test_missing_react_bundle_keeps_fallback_disabled_and_newsletter_working(live_server, browser_page):
    browser_page.route("**/static/frontend/**", lambda route: route.abort())
    browser_page.goto(f"{live_server}/kampanja/", wait_until="networkidle")
    assert browser_page.locator("#vol-name").is_disabled()
    assert browser_page.locator("#vol-submit").is_disabled()
    assert "Lomaketta ladataan" in browser_page.locator('[data-react-island="campaign-page"]').inner_text()
    assert browser_page.locator('#vapaaehtoiseksi a[href^="mailto:"]').first.is_visible()
    assert browser_page.locator("#newsletter-form button").is_disabled()


def test_other_public_pages_load_only_shared_header_and_admin_stays_separate(client, admin_client):
    import re

    for url in ("/info", "/keräys", "/users/auth/login"):
        response = client.get(url)
        assert response.status_code == 200
        page = response.get_data(as_text=True)
        scripts = re.findall(r'<script type="module" src="([^"]+)"', page)
        assert len(scripts) == 1
        assert scripts[0].startswith("/static/frontend/assets/header-")
        assert 'data-react-island="site-header"' in page
        assert 'data-react-island="campaign-page"' not in page
    # Since #1007 the home page is a React shell: the shared header entry is
    # paired with exactly one home entry, and nothing else.
    response = client.get("/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    scripts = re.findall(r'<script type="module" src="([^"]+)"', page)
    assert len(scripts) == 2
    assert scripts[0].startswith("/static/frontend/assets/header-")
    assert scripts[1].startswith("/static/frontend/assets/home-")
    assert 'data-react-island="site-header"' in page
    assert 'data-react-island="home"' in page
    assert 'data-react-island="campaign-page"' not in page
    response = admin_client.get("/admin/dashboard")
    assert response.status_code == 200
    assert "/static/frontend/" not in response.get_data(as_text=True)
