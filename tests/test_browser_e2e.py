from datetime import datetime
import re

import pytest
from bson import ObjectId

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


def _install_bootstrap_modal_test_double(page):
    """Keep modal flows testable while browser fixtures block remote CDNs."""
    page.add_init_script(
        """
        (() => {
          const instances = new WeakMap();
          class Modal {
            constructor(element) {
              this.element = element;
              instances.set(element, this);
            }
            show() {
              this.element.style.display = 'block';
              this.element.classList.add('show');
              this.element.removeAttribute('aria-hidden');
              this.element.dispatchEvent(new Event('shown.bs.modal'));
            }
            hide() {
              this.element.style.display = 'none';
              this.element.classList.remove('show');
              this.element.setAttribute('aria-hidden', 'true');
              this.element.dispatchEvent(new Event('hidden.bs.modal'));
            }
            static getOrCreateInstance(element) {
              return instances.get(element) || new Modal(element);
            }
          }
          window.bootstrap = { Modal };
          document.addEventListener('click', event => {
            const dismiss = event.target.closest('[data-bs-dismiss="modal"]');
            const modal = dismiss?.closest('.modal');
            if (modal) Modal.getOrCreateInstance(modal).hide();
          });
        })();
        """
    )


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
            if path == "/submit":
                assert abs((styles["left"] + styles["right"]) / 2 - styles["viewport"] / 2) <= 1
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
    seeded_data = _seed_database(app, db)

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
def test_submitter_modal_can_be_closed_and_reopened(
    app,
    db,
    live_server,
    browser_page,
):
    _install_bootstrap_modal_test_double(browser_page)
    seeded_data = _seed_database(app, db)
    browser_page.goto(f"{live_server}/admin/demo/", wait_until="domcontentloaded")
    _submit_login_form(browser_page, "admin", "AdminPass1!")
    _wait_for_url(browser_page, re.compile(r".*/admin/demo/?$"))

    row = browser_page.locator(f"#demo-{seeded_data['pending_demo_id']}")
    actions_toggle = row.locator(".dropdown-toggle")
    submitter_action = row.locator("button[onclick*='showSubmitterInfoModal']")
    modal = browser_page.locator("#submitterInfoModal")

    for _ in range(2):
        actions_toggle.click()
        with browser_page.expect_response(
            re.compile(r".*/admin/demo/get_submitter_info/.*")
        ) as response_info:
            submitter_action.click()
        assert response_info.value.ok
        modal.locator("#submitterInfoResult").wait_for(state="visible")
        browser_page.wait_for_function(
            "() => document.querySelector('#submitterName')?.textContent === 'Alice Tester'"
        )
        assert modal.locator("#submitterName").text_content() == "Alice Tester"
        modal.locator("#closeSubmitterInfo").click()
        modal.wait_for(state="hidden")
        assert actions_toggle.evaluate("element => element === document.activeElement")


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
    seeded_data = _seed_database(app, db)
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
        f"/admin/demo/suggestions/{seeded_data['suggestion_id']}",
        f"/admin/demo/edit_history/{seeded_data['demo_id']}",
        f"/admin/demo/view_demo_diff/{seeded_data['history_id']}",
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
def test_admin_summary_cards_center_icons_and_keep_copy_separate(
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
        ("/admin/organization/", ".admin-workspace-summary-card", ".admin-workspace-summary-icon", "div > span", "div > strong"),
        (f"/admin/organization/view/{seeded_data['org_id']}", ".admin-workspace-summary-card", ".admin-workspace-summary-icon", "div > span", "div > strong"),
        ("/admin/stats", ".admin-workspace-summary .admin-workspace-summary-card", ".admin-workspace-summary-icon", "div > span", "div > strong"),
        (f"/admin/demo/suggestions/{seeded_data['suggestion_id']}", ".admin-workspace-summary-card", ".admin-workspace-summary-icon", "div > span", "div > strong"),
    )

    for path, card_selector, icon_selector, label_selector, value_selector in pages:
        browser_page.goto(f"{live_server}{path}", wait_until="domcontentloaded")
        cards = browser_page.locator(card_selector)
        assert cards.count() >= 3, path
        geometry = cards.evaluate_all(
            """(elements, selectors) => elements.map(element => {
                const icon = element.querySelector(selectors.icon);
                const iconGlyph = icon ? icon.querySelector('i') : null;
                const label = element.querySelector(selectors.label);
                const value = element.querySelector(selectors.value);
                const content = label ? label.parentElement : null;
                const cardRect = element.getBoundingClientRect();
                return {
                    card: cardRect.toJSON(),
                    content: content ? content.getBoundingClientRect().toJSON() : null,
                    icon: icon ? icon.getBoundingClientRect().toJSON() : null,
                    iconGlyph: iconGlyph ? iconGlyph.getBoundingClientRect().toJSON() : null,
                    label: label ? label.getBoundingClientRect().toJSON() : null,
                    value: value ? value.getBoundingClientRect().toJSON() : null,
                    viewport: document.documentElement.clientWidth,
                };
            })""",
            {"icon": icon_selector, "label": label_selector, "value": value_selector},
        )

        for item in geometry:
            assert item["icon"] and item["iconGlyph"] and item["content"] and item["label"] and item["value"], path
            assert item["card"]["height"] >= 90, path
            assert item["icon"]["right"] < item["content"]["left"], path
            icon_center_x = item["icon"]["left"] + item["icon"]["width"] / 2
            glyph_center_x = item["iconGlyph"]["left"] + item["iconGlyph"]["width"] / 2
            icon_center_y = item["icon"]["top"] + item["icon"]["height"] / 2
            glyph_center_y = item["iconGlyph"]["top"] + item["iconGlyph"]["height"] / 2
            assert abs(icon_center_x - glyph_center_x) <= 1, path
            assert abs(icon_center_y - glyph_center_y) <= 1, path
            assert item["label"]["bottom"] <= item["value"]["top"] + 1, path
            assert item["card"]["left"] >= 0, path
            assert item["card"]["right"] <= item["viewport"] + 1, path

        widths = [item["card"]["width"] for item in geometry]
        assert max(widths) - min(widths) <= 2, path


@pytest.mark.e2e
@pytest.mark.integration
def test_admin_demo_suggestion_selection_and_reject_modal_are_accessible(
    app,
    db,
    live_server,
    browser_page,
):
    seeded_data = _seed_database(app, db)
    browser_page.goto(f"{live_server}/admin/dashboard", wait_until="domcontentloaded")
    _submit_login_form(browser_page, "admin", "AdminPass1!")
    _wait_for_url(browser_page, re.compile(r".*/admin/dashboard$"))
    browser_page.goto(
        f"{live_server}/admin/demo/suggestions/{seeded_data['suggestion_id']}",
        wait_until="domcontentloaded",
    )

    checkbox = browser_page.locator(".field-checkbox").first
    row = checkbox.locator("xpath=ancestor::tr")
    assert checkbox.is_checked()
    assert row.get_attribute("aria-selected") == "true"
    checkbox.uncheck()
    assert row.get_attribute("aria-selected") == "false"
    assert browser_page.locator("#apply-btn").is_disabled()

    trigger = browser_page.locator('[data-bs-target="#rejectSuggestionModal"]')
    trigger.focus()
    trigger.click()
    modal = browser_page.locator("#rejectSuggestionModal")
    modal.wait_for(state="visible")
    modal.locator(".btn-close").click()
    browser_page.wait_for_function(
        "document.querySelector('#rejectSuggestionModal')?.getAttribute('aria-hidden') === 'true'"
    )
    browser_page.wait_for_function(
        "document.querySelector('[data-bs-target=\"#rejectSuggestionModal\"]') === document.activeElement"
    )


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [390, 1440])
def test_admin_demo_diff_toggle_and_rollback_modal_are_accessible(
    app,
    db,
    live_server,
    browser_page,
    viewport_width,
):
    seeded_data = _seed_database(app, db)
    db.demo_edit_history.update_one(
        {"_id": seeded_data["history_id"]},
        {
            "$set": {
                "old_demo": {"title": "Old title", "city": "Helsinki"},
                "new_demo": {"title": "New title", "city": "Helsinki"},
            }
        },
    )
    browser_page.set_viewport_size({"width": viewport_width, "height": 1000})
    browser_page.goto(f"{live_server}/admin/dashboard", wait_until="domcontentloaded")
    _submit_login_form(browser_page, "admin", "AdminPass1!")
    _wait_for_url(browser_page, re.compile(r".*/admin/dashboard$"))
    browser_page.goto(
        f"{live_server}/admin/demo/view_demo_diff/{seeded_data['history_id']}",
        wait_until="domcontentloaded",
    )

    unchanged_row = browser_page.locator(".admin-diff-row--unchanged")
    toggle = browser_page.locator("#toggleUnchanged")
    assert unchanged_row.is_hidden()
    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    assert unchanged_row.is_visible()
    assert browser_page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"
    )

    trigger = browser_page.locator('[data-bs-target="#rollbackModal"]')
    trigger.focus()
    trigger.click()
    modal = browser_page.locator("#rollbackModal")
    modal.wait_for(state="visible")
    modal.locator(".btn-close").click()
    browser_page.wait_for_function(
        "document.querySelector('#rollbackModal')?.getAttribute('aria-hidden') === 'true'"
    )
    browser_page.wait_for_function(
        "document.querySelector('[data-bs-target=\"#rollbackModal\"]') === document.activeElement"
    )


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [390, 1440])
def test_admin_filter_toolbars_use_shared_theme_and_fit_viewport(
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
        "/admin/demo/",
        "/admin/recu_demo/",
        "/admin/stats",
        "/admin/logs",
        "/admin/demo/translations",
        "/admin/ui-translations",
        "/admin/demo/suggestions",
    )
    theme_backgrounds = {}
    for theme in ("light", "dark"):
        theme_backgrounds[theme] = []
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
            toolbar = browser_page.locator(".admin-workspace-toolbar").first
            toolbar.wait_for(state="visible")
            styles = toolbar.evaluate(
                """element => {
                    const computed = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return {
                        background: computed.backgroundColor,
                        border: computed.borderColor,
                        radius: parseFloat(computed.borderRadius),
                        left: rect.left,
                        right: rect.right,
                        viewport: document.documentElement.clientWidth,
                        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                    };
                }"""
            )
            assert styles["background"] != "rgba(0, 0, 0, 0)", path
            assert styles["border"] != "rgba(0, 0, 0, 0)", path
            assert styles["radius"] >= 12, path
            assert styles["left"] >= 0, path
            assert styles["right"] <= styles["viewport"] + 1, path
            assert styles["overflow"] <= 1, path
            theme_backgrounds[theme].append(styles["background"])

    assert theme_backgrounds["light"] != theme_backgrounds["dark"]


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [390, 1440])
def test_admin_demo_forms_use_shared_theme_and_control_contract(
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

    theme_surfaces = {}
    for theme in ("light", "dark"):
        theme_surfaces[theme] = []
        for path in ("/admin/demo/create_demo", "/admin/recu_demo/create_recu_demo"):
            browser_page.goto(f"{live_server}{path}", wait_until="domcontentloaded")
            browser_page.evaluate(
                """theme => {
                    document.documentElement.classList.toggle('dark', theme === 'dark');
                    document.documentElement.classList.toggle('light', theme === 'light');
                    document.documentElement.setAttribute('data-bs-theme', theme);
                }""",
                theme,
            )
            control = browser_page.locator(".admin-editor-form .form-control").first
            control.focus()
            # Bootstrap transitions form focus styles; sample the settled state.
            browser_page.wait_for_timeout(200)
            styles = browser_page.locator(".admin-editor-form").evaluate(
                """form => {
                    const section = form.querySelector('.form-section');
                    const control = form.querySelector('.form-control');
                    const required = form.querySelector('.admin-required');
                    const save = form.querySelector('.editor-save-bar .btn-primary');
                    const sectionStyle = getComputedStyle(section);
                    const controlStyle = getComputedStyle(control);
                    const requiredStyle = getComputedStyle(required);
                    const saveStyle = getComputedStyle(save);
                    return {
                        sectionBackground: sectionStyle.backgroundColor,
                        sectionBorder: sectionStyle.borderColor,
                        controlBackground: controlStyle.backgroundColor,
                        controlColor: controlStyle.color,
                        controlFocus: controlStyle.boxShadow,
                        requiredColor: requiredStyle.color,
                        saveBackground: saveStyle.backgroundColor,
                        saveColor: saveStyle.color,
                        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                    };
                }"""
            )
            assert styles["sectionBackground"] != "rgba(0, 0, 0, 0)", path
            assert styles["sectionBorder"] != "rgba(0, 0, 0, 0)", path
            assert styles["controlBackground"] != "rgba(0, 0, 0, 0)", path
            assert styles["controlColor"] != styles["controlBackground"], path
            assert styles["controlFocus"] != "none", path
            assert styles["requiredColor"] != styles["controlColor"], path
            assert styles["saveBackground"] != "rgba(0, 0, 0, 0)", path
            assert styles["saveColor"] == "rgb(255, 255, 255)", path
            assert styles["overflow"] <= 1, path
            theme_surfaces[theme].append(styles["sectionBackground"])

    assert theme_surfaces["light"] != theme_surfaces["dark"]


@pytest.mark.e2e
@pytest.mark.integration
def test_admin_workspace_accessibility_matrix(
    app,
    db,
    live_server,
    browser_page,
):
    """Exercise zoom, keyboard, motion, long-copy and overflow contracts."""
    _seed_database(app, db)
    # A 1440px desktop exposes 720 CSS pixels at 200% browser zoom.
    browser_page.set_viewport_size({"width": 720, "height": 900})
    browser_page.emulate_media(reduced_motion="reduce")
    browser_page.goto(f"{live_server}/admin/dashboard", wait_until="domcontentloaded")
    _submit_login_form(browser_page, "admin", "AdminPass1!")
    _wait_for_url(browser_page, re.compile(r".*/admin/dashboard$"))

    reduced_motion = browser_page.locator(".admin-dashboard-shell").evaluate(
        """shell => {
            const pulse = shell.querySelector('.pulse');
            const quickCard = shell.querySelector('.quick-card');
            const sidebar = document.querySelector('.admin-layout > .admin-sidebar');
            return {
                pulseAnimation: pulse ? getComputedStyle(pulse).animationName : 'none',
                quickTransition: quickCard ? getComputedStyle(quickCard).transitionDuration : '0s',
                sidebarTransition: sidebar ? getComputedStyle(sidebar).transitionDuration : '0s',
            };
        }"""
    )
    assert reduced_motion["pulseAnimation"] == "none"
    assert reduced_motion["quickTransition"] == "0s"
    assert reduced_motion["sidebarTransition"] == "0s"

    paths = (
        "/admin/demo/",
        "/admin/user/",
        "/admin/organization/",
        "/admin/demo/create_demo",
        "/admin/analytics/overall_24h",
    )
    long_title = (
        "Poikkeuksellisen pitkä ylläpitonäkymän otsikko, joka kertoo selkeästi "
        "mielenosoitusten käyttöoikeuksien ja saavutettavuuden kokonaisuudesta"
    )

    for path in paths:
        browser_page.goto(f"{live_server}{path}", wait_until="domcontentloaded")
        hero = browser_page.locator(".admin-page-hero").first
        hero.wait_for(state="visible")
        hero.locator("h1, h2").first.evaluate(
            "(heading, title) => { heading.textContent = title; }", long_title
        )

        contract = browser_page.evaluate(
            """() => {
                const hero = document.querySelector('.admin-page-hero');
                const heading = hero.querySelector('h1, h2');
                const sticky = document.querySelector('.admin-sticky-actions, .editor-save-bar');
                const dataView = document.querySelector('.admin-data-view__viewport');
                const viewport = document.documentElement.clientWidth;
                const heroRect = hero.getBoundingClientRect();
                const headingRect = heading.getBoundingClientRect();
                const stickyRect = sticky?.getBoundingClientRect();
                return {
                    documentOverflow: document.documentElement.scrollWidth - viewport,
                    heroLeft: heroRect.left,
                    heroRight: heroRect.right,
                    headingLeft: headingRect.left,
                    headingRight: headingRect.right,
                    stickyLeft: stickyRect?.left ?? null,
                    stickyRight: stickyRect?.right ?? null,
                    dataOverflow: dataView ? getComputedStyle(dataView).overflowX : null,
                    viewport,
                };
            }"""
        )
        assert contract["documentOverflow"] <= 1, path
        assert contract["heroLeft"] >= 0, path
        assert contract["heroRight"] <= contract["viewport"] + 1, path
        assert contract["headingLeft"] >= contract["heroLeft"] - 1, path
        assert contract["headingRight"] <= contract["heroRight"] + 1, path
        if contract["stickyLeft"] is not None:
            assert contract["stickyLeft"] >= 0, path
            assert contract["stickyRight"] <= contract["viewport"] + 1, path
        if contract["dataOverflow"] is not None:
            assert contract["dataOverflow"] in ("auto", "scroll"), path

    browser_page.goto(f"{live_server}/admin/demo/create_demo", wait_until="domcontentloaded")
    browser_page.locator("body").click(position={"x": 700, "y": 880})
    focus_is_visible = False
    for _ in range(30):
        browser_page.keyboard.press("Tab")
        focus_contract = browser_page.evaluate(
            """() => {
                const active = document.activeElement;
                const style = active ? getComputedStyle(active) : null;
                return {
                    insideMain: Boolean(active?.closest('main')),
                    outlineStyle: style?.outlineStyle ?? 'none',
                    outlineWidth: parseFloat(style?.outlineWidth ?? '0'),
                    boxShadow: style?.boxShadow ?? 'none',
                };
            }"""
        )
        if focus_contract["insideMain"] and (
            (
                focus_contract["outlineStyle"] != "none"
                and focus_contract["outlineWidth"] >= 2
            )
            or focus_contract["boxShadow"] != "none"
        ):
            focus_is_visible = True
            break
    assert focus_is_visible, "keyboard focus must be visibly indicated inside admin main"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [390, 1440])
@pytest.mark.parametrize(
    "editor_path",
    ["/admin/demo/create_demo", "/admin/recu_demo/create_recu_demo"],
)
def test_admin_organizer_editor_supports_mixed_accessible_rows(
    app,
    db,
    live_server,
    browser_page,
    viewport_width,
    editor_path,
):
    _seed_database(app, db)
    browser_page.set_viewport_size({"width": viewport_width, "height": 1000})
    browser_page.goto(f"{live_server}/admin/dashboard", wait_until="domcontentloaded")
    _submit_login_form(browser_page, "admin", "AdminPass1!")
    _wait_for_url(browser_page, re.compile(r".*/admin/dashboard$"))
    browser_page.goto(f"{live_server}{editor_path}", wait_until="domcontentloaded")
    browser_page.wait_for_load_state("networkidle")

    editor = browser_page.locator("[data-organizer-editor]")
    assert editor.locator("[data-organizer-empty]").is_visible()
    editor.locator("[data-add-freeform-organizer]").click()
    freeform = editor.locator('[data-organizer-kind="freeform"]')
    assert freeform.count() == 1
    freeform_name = freeform.locator('input[name^="organizer_name_"]')
    browser_page.wait_for_function(
        "name => document.activeElement?.name === name",
        arg=freeform_name.get_attribute("name"),
    )
    freeform_name.fill("Vapaa testijärjestäjä")

    organization_select = editor.locator("[data-organization-select]")
    organization_select.select_option(index=1)
    selected_id = organization_select.input_value()
    editor.locator("[data-add-linked-organizer]").click()
    linked = editor.locator('[data-organizer-kind="organization"]')
    assert linked.count() == 1
    assert linked.get_attribute("data-organization-id") == selected_id
    assert editor.locator("[data-organizer-empty]").is_hidden()

    organization_select.select_option(selected_id)
    editor.locator("[data-add-linked-organizer]").click()
    assert editor.locator("[data-organizer-error]").is_visible()
    assert linked.count() == 1

    freeform.locator("[data-remove-organizer]").click()
    assert editor.locator('[data-organizer-kind="freeform"]').count() == 0
    assert browser_page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"
    )


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [390, 1440])
def test_background_job_detail_uses_shared_responsive_theme_contract(
    app,
    db,
    live_server,
    browser_page,
    viewport_width,
):
    _seed_database(app, db)
    jobs = app.extensions["job_manager"].list_jobs()
    assert jobs
    browser_page.set_viewport_size({"width": viewport_width, "height": 1000})
    browser_page.goto(f"{live_server}/admin/dashboard", wait_until="domcontentloaded")
    _submit_login_form(browser_page, "admin", "AdminPass1!")
    _wait_for_url(browser_page, re.compile(r".*/admin/dashboard$"))

    for theme in ("light", "dark"):
        browser_page.goto(
            f"{live_server}/admin/background-jobs/{jobs[0]['key']}",
            wait_until="domcontentloaded",
        )
        browser_page.evaluate(
            """theme => {
                document.documentElement.classList.toggle('dark', theme === 'dark');
                document.documentElement.classList.toggle('light', theme === 'light');
                document.documentElement.setAttribute('data-bs-theme', theme);
            }""",
            theme,
        )
        browser_page.locator(".admin-job-detail__layout").wait_for(state="visible")
        assert browser_page.locator(".admin-page-hero").is_visible()
        assert browser_page.locator(".admin-data-view").count() == 2
        assert browser_page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"
        )


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [390, 1440])
def test_submission_errors_use_shared_responsive_theme_contract(
    app,
    db,
    live_server,
    browser_page,
    viewport_width,
):
    _seed_database(app, db)
    db.demo_submission_errors.insert_one(
        {
            "_id": ObjectId(),
            "created_at": datetime(2026, 9, 23, 12, 0, 0),
            "error_code": "validation_failed",
            "message": "Selainpistokokeen ilmoitusvirhe",
            "status": 400,
            "ip": "127.0.0.1",
            "request_path": "/submit",
            "request_method": "POST",
            "extra": {"field": "email"},
            "form_snapshot": {"title": "Testi"},
        }
    )
    browser_page.set_viewport_size({"width": viewport_width, "height": 1000})
    browser_page.goto(f"{live_server}/admin/dashboard", wait_until="domcontentloaded")
    _submit_login_form(browser_page, "admin", "AdminPass1!")
    _wait_for_url(browser_page, re.compile(r".*/admin/dashboard$"))

    theme_surfaces = {}
    for theme in ("light", "dark"):
        browser_page.goto(
            f"{live_server}/admin/demo/submission_errors",
            wait_until="domcontentloaded",
        )
        browser_page.evaluate(
            """theme => {
                document.documentElement.classList.toggle('dark', theme === 'dark');
                document.documentElement.classList.toggle('light', theme === 'light');
                document.documentElement.setAttribute('data-bs-theme', theme);
            }""",
            theme,
        )
        browser_page.locator(".admin-page-hero").wait_for(state="visible")
        assert browser_page.locator(".admin-filter-bar").is_visible()
        assert browser_page.locator(".admin-data-view").is_visible()
        assert browser_page.locator(".admin-pagination").is_visible()
        details = browser_page.locator(".admin-disclosure").first
        details.evaluate("element => { element.open = true; }")
        assert details.locator(".admin-code-block").first.is_visible()
        assert browser_page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"
        )
        theme_surfaces[theme] = browser_page.locator(".admin-data-view").evaluate(
            "element => getComputedStyle(element).backgroundColor"
        )

    assert theme_surfaces["light"] != theme_surfaces["dark"]


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [390, 1440])
@pytest.mark.parametrize("viewport_height", [640, 844])
def test_report_error_modal_vertical_fit_and_scroll_contract(
    app,
    db,
    live_server,
    browser_page,
    viewport_width,
    viewport_height,
):
    """The report modals must never clip above/below the viewport: the dialog is
    height-capped. On mobile the whole content scrolls as one swipeable region
    (no nested body scroller); on desktop the header/footer stay pinned. Never
    overflow horizontally."""
    _install_bootstrap_modal_test_double(browser_page)
    is_mobile = viewport_width < 1000
    browser_page.set_viewport_size({"width": viewport_width, "height": viewport_height})
    seeded_data = _seed_database(app, db)
    demo_id = seeded_data["demo_id"]

    browser_page.goto(f"{live_server}/demonstration/{demo_id}", wait_until="domcontentloaded")
    browser_page.wait_for_selector(".report-flow-trigger", state="visible")

    for modal_id, next_action in (
        ("#report-choice-modal", True),
        ("#report-modal", False),
    ):
        browser_page.evaluate(
            """() => {
                const m = bootstrap.Modal.getOrCreateInstance(
                    document.getElementById('report-choice-modal')
                );
                m.show();
            }"""
        )
        browser_page.locator("#report-choice-modal").wait_for(state="visible")

        if not next_action:
            browser_page.evaluate(
                """() => {
                    bootstrap.Modal.getOrCreateInstance(document.querySelector('#report-choice-modal')).hide();
                    bootstrap.Modal.getOrCreateInstance(document.querySelector('#report-modal')).show();
                }"""
            )
            browser_page.locator("#report-modal").wait_for(state="visible")

        contract = browser_page.locator(modal_id).evaluate(
            """(modal) => {
                const dialog = modal.querySelector('.modal-dialog');
                const content = modal.querySelector('.modal-content');
                const body = modal.querySelector('.modal-body');
                const header = modal.querySelector('.modal-header');
                const footer = modal.querySelector('.modal-footer');
                const dialogStyle = getComputedStyle(dialog);
                const contentStyle = getComputedStyle(content);
                const bodyStyle = getComputedStyle(body);
                return {
                    isScrollableDialog: dialog.classList.contains('modal-dialog-scrollable'),
                    dialogHeight: dialogStyle.height,
                    contentMaxHeight: contentStyle.maxHeight,
                    contentOverflowX: contentStyle.overflowX,
                    contentOverflowY: contentStyle.overflowY,
                    bodyOverflowY: bodyStyle.overflowY,
                    headerFlexShrink: header ? getComputedStyle(header).flexShrink : null,
                    footerFlexShrink: footer ? getComputedStyle(footer).flexShrink : null,
                    contentOverflowXpx: content.scrollWidth - content.clientWidth,
                    bodyOverflowXpx: body.scrollWidth - body.clientWidth,
                    docScrollWidth: document.documentElement.scrollWidth,
                    viewportW: document.documentElement.clientWidth,
                    viewportH: window.innerHeight,
                };
            }"""
        )
        assert contract["isScrollableDialog"], (
            f"{modal_id} dialog must use the Bootstrap scrollable dialog layout"
        )
        if is_mobile:
            # On mobile the whole modal content scrolls as a single region, so a
            # swipe anywhere (header, hint, cards, footer) scrolls the dialog.
            assert contract["contentOverflowY"] == "auto", (
                f"{modal_id} content must be the mobile scroll region"
            )
            assert contract["bodyOverflowY"] == "visible", (
                f"{modal_id} body must not nest a separate scroll region on mobile"
            )
        else:
            # On desktop the header/footer stay pinned and only the body scrolls.
            assert contract["headerFlexShrink"] == "0", (
                f"{modal_id} header must stay pinned"
            )
            assert contract["footerFlexShrink"] == "0", (
                f"{modal_id} footer must stay pinned"
            )
            assert contract["bodyOverflowY"] == "auto", (
                f"{modal_id} body must be the desktop scroll region"
            )
        # The dialog is capped to the viewport height on mobile, so content can
        # never reach beyond the screen (no top/bottom clipping).
        if is_mobile:
            assert contract["dialogHeight"] not in ("auto",), (
                f"{modal_id} dialog height must be viewport-capped on mobile, "
                f"got {contract['dialogHeight']}"
            )
        # Never overflow horizontally, inside the modal or the document.
        assert contract["contentOverflowXpx"] == 0, (
            f"{modal_id} content overflows horizontally"
        )
        assert contract["bodyOverflowXpx"] == 0, f"{modal_id} body overflows horizontally"
        assert contract["docScrollWidth"] == contract["viewportW"], (
            f"{modal_id} pushes the document wider than the viewport"
        )

        if next_action:
            browser_page.locator("#choose-report-error").click()
            browser_page.locator("#report-modal").wait_for(state="visible")


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [390, 1440])
def test_report_error_modal_buttons_are_not_overridden_by_page_button_styles(
    app,
    db,
    live_server,
    browser_page,
    viewport_width,
):
    """The page-level .btn styles (shimmer ::before, border:none) must not leak
    into the report-error modal buttons, which rely on Bootstrap outline buttons."""
    _install_bootstrap_modal_test_double(browser_page)
    browser_page.set_viewport_size({"width": viewport_width, "height": 1000})
    seeded_data = _seed_database(app, db)
    demo_id = seeded_data["demo_id"]

    browser_page.goto(f"{live_server}/demonstration/{demo_id}", wait_until="domcontentloaded")
    browser_page.wait_for_selector(".report-flow-trigger", state="visible")

    browser_page.evaluate(
        """() => {
            const modal = document.getElementById('report-choice-modal');
            bootstrap.Modal.getOrCreateInstance(modal).show();
        }"""
    )
    choice_modal = browser_page.locator("#report-choice-modal")
    choice_modal.wait_for(state="visible")

    outline_button = choice_modal.locator("#choose-report-error")
    shimmer = outline_button.evaluate(
        """() => {
            const before = getComputedStyle(document.querySelector('#choose-report-error'), '::before');
            const border = getComputedStyle(document.querySelector('#choose-report-error'));
            return {
                content: before.content,
                display: before.display,
                borderWidth: parseFloat(border.borderWidth),
                borderStyle: border.borderStyle,
            };
        }"""
    )
    assert shimmer["content"] == "none", "page .btn::before shimmer must not leak into modal"
    assert shimmer["display"] == "none", "page .btn::before shimmer must not leak into modal"
    assert shimmer["borderWidth"] == 1 and shimmer["borderStyle"] == "solid", (
        "outline button border must be visible inside the modal"
    )

    browser_page.evaluate(
        """() => {
            const reportBtn = document.getElementById('choose-report-error');
            bootstrap.Modal.getOrCreateInstance(document.getElementById('report-choice-modal')).hide();
            bootstrap.Modal.getOrCreateInstance(document.getElementById('report-modal')).show();
        }"""
    )
    browser_page.wait_for_selector("#report-modal.show", state="attached", timeout=10000)
    report_modal = browser_page.locator("#report-modal")
    report_modal.wait_for(state="visible")

    for selector in (".btn-secondary", ".btn-danger"):
        button_styles = report_modal.locator(selector).evaluate(
            """(element) => {
                const before = getComputedStyle(element, '::before');
                return {
                    content: before.content,
                    display: before.display,
                };
            }"""
        )
        assert button_styles["content"] == "none", (
            f"page .btn::before shimmer must not leak into modal {selector}"
        )
        assert button_styles["display"] == "none", (
            f"page .btn::before shimmer must not leak into modal {selector}"
        )
