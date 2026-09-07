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
    seeded_data = _seed_database(app, db)
    browser_page.set_viewport_size({"width": viewport_width, "height": 1000})

    paths = (
        "/",
        "/demonstrations",
        "/cities",
        "/mielenosoitukset-tanaan",
        "/info",
        "/contact",
        "/privacy",
        "/submit",
        "/upcoming/translations/",
        f"/demonstration/{seeded_data['demo_id']}",
        f"/organization/{seeded_data['org_id']}",
    )
    theme_backgrounds = {}
    for theme in ("light", "dark"):
        rendered_styles = []
        for path in paths:
            browser_page.goto(f"{live_server}{path}", wait_until="domcontentloaded")
            browser_page.evaluate(
                """theme => {
                    document.documentElement.classList.toggle('dark', theme === 'dark');
                    document.documentElement.classList.toggle('light', theme === 'light');
                }""",
                theme,
            )
            hero = browser_page.locator(".site-hero").first
            hero.wait_for(state="visible")
            styles = hero.evaluate(
                """element => {
                    const computed = getComputedStyle(element);
                    const heading = element.querySelector('h1, h2, .demo-title');
                    const headingStyle = heading ? getComputedStyle(heading) : null;
                    const rect = element.getBoundingClientRect();
                    return {
                        backgroundImage: computed.backgroundImage,
                        borderRadius: parseFloat(computed.borderRadius),
                        headingSize: headingStyle ? parseFloat(headingStyle.fontSize) : 0,
                        headingTextAlign: headingStyle ? headingStyle.textAlign : '',
                        left: rect.left,
                        right: rect.right,
                        textAlign: computed.textAlign,
                        viewport: document.documentElement.clientWidth,
                        width: rect.width,
                    };
                }"""
            )
            assert "gradient" in styles["backgroundImage"]
            assert styles["borderRadius"] >= 16
            assert styles["textAlign"] == "center"
            assert styles["headingTextAlign"] == "center", path
            assert styles["headingSize"] > 0
            assert styles["headingSize"] <= (40 if viewport_width == 390 else 52), path
            assert styles["left"] >= 0, path
            assert styles["right"] <= styles["viewport"] + 1, path
            rendered_styles.append(styles)

        assert max(style["width"] for style in rendered_styles) - min(
            style["width"] for style in rendered_styles
        ) <= 2
        assert len({style["backgroundImage"] for style in rendered_styles}) == 1
        theme_backgrounds[theme] = rendered_styles[0]["backgroundImage"]

    assert theme_backgrounds["light"] != theme_backgrounds["dark"]


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


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [390, 1440])
def test_admin_pages_share_responsive_theme_aware_heroes(
    app,
    db,
    live_server,
    browser_page,
    viewport_width,
):
    _seed_database(app, db)
    browser_page.set_viewport_size({"width": viewport_width, "height": 1000})
    browser_page.goto(f"{live_server}/admin/dashboard", wait_until="domcontentloaded")
    _submit_login_form(browser_page, "admin", "AdminPass1!")
    _wait_for_url(browser_page, re.compile(r".*/admin/dashboard$"))

    paths = (
        "/admin/dashboard",
        "/admin/demo/",
        "/admin/user/",
        "/admin/organization/",
        "/admin/stats",
        "/admin/demo_analytics",
        "/admin/cities/",
        "/admin/governance/",
        "/admin/background-jobs",
        "/admin/logs",
        "/admin/case/",
        "/admin/demo/translations",
        "/admin/demo/suggestions",
        "/admin/recu_demo/",
        "/admin/ui-translations",
    )
    theme_backgrounds = {}
    for theme in ("light", "dark"):
        rendered_styles = []
        for path in paths:
            browser_page.goto(f"{live_server}{path}", wait_until="domcontentloaded")
            browser_page.evaluate(
                """theme => {
                    document.documentElement.classList.toggle('dark', theme === 'dark');
                    document.documentElement.classList.toggle('light', theme === 'light');
                    document.documentElement.setAttribute('data-bs-theme', theme);
                }""",
                theme,
            )
            hero = browser_page.locator(".admin-page-hero").first
            hero.wait_for(state="visible")
            styles = hero.evaluate(
                """element => {
                    const computed = getComputedStyle(element);
                    const heading = element.querySelector('h1, h2');
                    const headingStyle = heading ? getComputedStyle(heading) : null;
                    const rect = element.getBoundingClientRect();
                    return {
                        backgroundImage: computed.backgroundImage,
                        borderRadius: parseFloat(computed.borderRadius),
                        headingColor: headingStyle ? headingStyle.color : '',
                        headingSize: headingStyle ? parseFloat(headingStyle.fontSize) : 0,
                        left: rect.left,
                        right: rect.right,
                        viewport: document.documentElement.clientWidth,
                    };
                }"""
            )
            assert "gradient" in styles["backgroundImage"]
            assert styles["borderRadius"] >= 20
            assert styles["headingColor"] == "rgb(255, 255, 255)"
            assert styles["headingSize"] >= 30
            assert styles["left"] >= 0, path
            assert styles["right"] <= styles["viewport"] + 1, path
            rendered_styles.append(styles)

        assert len({style["backgroundImage"] for style in rendered_styles}) == 1
        theme_backgrounds[theme] = rendered_styles[0]["backgroundImage"]

    assert theme_backgrounds["light"] != theme_backgrounds["dark"]


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [390, 1440])
def test_admin_summary_cards_keep_icons_labels_and_values_separate(
    app,
    db,
    live_server,
    browser_page,
    viewport_width,
):
    seeded_data = _seed_database(app, db)
    browser_page.set_viewport_size({"width": viewport_width, "height": 1000})
    browser_page.goto(f"{live_server}/admin/dashboard", wait_until="domcontentloaded")
    _submit_login_form(browser_page, "admin", "AdminPass1!")
    _wait_for_url(browser_page, re.compile(r".*/admin/dashboard$"))

    pages = (
        ("/admin/demo/", ".admin-workspace-summary-card", ".admin-workspace-summary-icon", "div > span", "div > strong"),
        ("/admin/cities/", ".admin-workspace-summary-card", ".admin-workspace-summary-icon", "div > span", "div > strong"),
        ("/admin/user/", ".users-summary-card", ".users-summary-icon", "div > span", "div > strong"),
        ("/admin/organization/", ".orgs-summary-card", ".orgs-summary-icon", "div > span", "div > strong"),
        (f"/admin/organization/view/{seeded_data['org_id']}", ".org-detail-summary-card", ".org-detail-summary-icon", "div > span", "div > strong"),
        ("/admin/stats", ".stats-shell > .stat-grid .stat-card", ".stat-icon", ".stat-label", ".stat-value"),
    )

    for path, card_selector, icon_selector, label_selector, value_selector in pages:
        browser_page.goto(f"{live_server}{path}", wait_until="domcontentloaded")
        cards = browser_page.locator(card_selector)
        assert cards.count() >= 3, path
        geometry = cards.evaluate_all(
            """(elements, selectors) => elements.map(element => {
                const icon = element.querySelector(selectors.icon);
                const label = element.querySelector(selectors.label);
                const value = element.querySelector(selectors.value);
                const content = label ? label.parentElement : null;
                const cardRect = element.getBoundingClientRect();
                return {
                    card: cardRect.toJSON(),
                    content: content ? content.getBoundingClientRect().toJSON() : null,
                    icon: icon ? icon.getBoundingClientRect().toJSON() : null,
                    label: label ? label.getBoundingClientRect().toJSON() : null,
                    value: value ? value.getBoundingClientRect().toJSON() : null,
                    viewport: document.documentElement.clientWidth,
                };
            })""",
            {"icon": icon_selector, "label": label_selector, "value": value_selector},
        )

        for item in geometry:
            assert item["icon"] and item["content"] and item["label"] and item["value"], path
            assert item["card"]["height"] >= 90, path
            assert item["icon"]["right"] < item["content"]["left"], path
            assert item["label"]["bottom"] <= item["value"]["top"] + 1, path
            assert item["card"]["left"] >= 0, path
            assert item["card"]["right"] <= item["viewport"] + 1, path

        widths = [item["card"]["width"] for item in geometry]
        assert max(widths) - min(widths) <= 2, path
