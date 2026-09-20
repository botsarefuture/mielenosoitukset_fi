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
