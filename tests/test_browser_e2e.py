import re

import pytest

from tests.conftest import _seed_database


def _wait_for_body_text(page, text):
    page.wait_for_function(
        "expected => document.body && document.body.innerText.includes(expected)",
        arg=text,
    )


def _submit_login_form(page, username, password):
    _wait_for_body_text(page, "Kirjaudu sisään")
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.locator("#login-btn").click()


def _wait_for_url(page, pattern):
    page.wait_for_url(pattern, wait_until="domcontentloaded")


@pytest.mark.e2e
@pytest.mark.integration
def test_public_pages_render_in_real_browser(app, db, live_server, browser_page):
    seeded_data = _seed_database(app, db)

    browser_page.goto(f"{live_server}/", wait_until="domcontentloaded")
    _wait_for_body_text(browser_page, "Climate March Helsinki")

    browser_page.goto(
        f"{live_server}/demonstration/{seeded_data['demo_id']}",
        wait_until="domcontentloaded",
    )
    _wait_for_body_text(browser_page, "Climate March Helsinki")
    _wait_for_body_text(browser_page, "Mannerheimintie 1, Helsinki")

    browser_page.goto(
        f"{live_server}/organization/{seeded_data['org_id']}",
        wait_until="domcontentloaded",
    )
    _wait_for_body_text(browser_page, "Test Organization")


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [390, 1440])
def test_standard_public_heroes_share_visual_foundation(
    app,
    db,
    live_server,
    browser_page,
    viewport_width,
):
    _seed_database(app, db)
    browser_page.set_viewport_size({"width": viewport_width, "height": 1000})

    for path in ("/", "/cities", "/mielenosoitukset-tanaan", "/info", "/privacy"):
        browser_page.goto(f"{live_server}{path}", wait_until="domcontentloaded")
        hero = browser_page.locator(".site-hero").first
        hero.wait_for(state="visible")
        styles = hero.evaluate(
            """element => {
                const computed = getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return {
                    backgroundImage: computed.backgroundImage,
                    borderRadius: parseFloat(computed.borderRadius),
                    left: rect.left,
                    right: rect.right,
                    viewport: document.documentElement.clientWidth,
                };
            }"""
        )
        assert "gradient" in styles["backgroundImage"]
        assert styles["borderRadius"] >= 16
        assert styles["left"] >= 0
        assert styles["right"] <= styles["viewport"] + 1


@pytest.mark.e2e
@pytest.mark.integration
def test_user_login_and_notifications_flow_in_real_browser(
    app,
    db,
    live_server,
    browser_page,
):
    _seed_database(app, db)

    browser_page.goto(
        f"{live_server}/users/auth/login?next=/users/profile/",
        wait_until="domcontentloaded",
    )
    _submit_login_form(browser_page, "alice", "UserPass1!")
    _wait_for_url(browser_page, re.compile(r".*/users/profile/?$"))
    _wait_for_body_text(browser_page, "Alice Tester")

    browser_page.goto(f"{live_server}/api/notifications/all", wait_until="domcontentloaded")
    _wait_for_body_text(browser_page, "Kaikki ilmoitukset")
    _wait_for_body_text(browser_page, "Kutsu mielenosoitukseen: Climate March Helsinki")


@pytest.mark.e2e
@pytest.mark.integration
def test_developer_dashboard_redirects_through_login_in_real_browser(
    app,
    db,
    live_server,
    browser_page,
):
    _seed_database(app, db)

    browser_page.goto(f"{live_server}/developer/", wait_until="domcontentloaded")
    _wait_for_url(browser_page, re.compile(r".*/users/auth/login.*"))
    _submit_login_form(browser_page, "dev", "DevPass1!")
    _wait_for_url(browser_page, re.compile(r".*/developer/?$"))
    _wait_for_body_text(browser_page, "Luo uusi token")
    _wait_for_body_text(browser_page, "Seeded Developer App")


@pytest.mark.e2e
@pytest.mark.integration
def test_admin_dashboard_redirects_through_login_in_real_browser(
    app,
    db,
    live_server,
    browser_page,
):
    _seed_database(app, db)

    browser_page.goto(f"{live_server}/admin/dashboard", wait_until="domcontentloaded")
    _wait_for_url(browser_page, re.compile(r".*/users/auth/login.*"))
    _submit_login_form(browser_page, "admin", "AdminPass1!")
    _wait_for_url(browser_page, re.compile(r".*/admin/dashboard$"))
    _wait_for_body_text(browser_page, "Reaaliaikainen tilannekuva")
    _wait_for_body_text(browser_page, "Panic Mode")
