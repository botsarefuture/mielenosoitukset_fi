from pathlib import Path

import pytest


TEMPLATE_ROOT = Path("mielenosoitukset_fi/templates")
CSS_PATH = Path("mielenosoitukset_fi/static/css/user-workspace.css")
JS_PATH = Path("mielenosoitukset_fi/static/js/user-pagination.js")
THEME_JS_PATH = Path("mielenosoitukset_fi/static/js/theme.js")


def test_public_listing_family_uses_shared_hero_and_pagination_markup():
    list_template = (TEMPLATE_ROOT / "list.html").read_text(encoding="utf-8")
    city_template = (TEMPLATE_ROOT / "city.html").read_text(encoding="utf-8")
    tag_template = (TEMPLATE_ROOT / "tag_list.html").read_text(encoding="utf-8")

    assert "from '_macros/_hero.html' import hero_section" in list_template
    assert "from '_macros/_hero.html' import hero_section" in city_template
    assert "from '_macros/_hero.html' import hero_section" in tag_template
    assert "load_more_button()" in list_template
    assert "load_more_button()" in city_template
    assert "load_more_button()" in tag_template
    assert "listing_end_message()" not in city_template


def test_public_listing_pagination_controller_supports_buttons_and_sentinels():
    source = JS_PATH.read_text(encoding="utf-8")

    assert "sentinel = null" in source
    assert "new IntersectionObserver" in source
    assert "button.hidden = currentPage >= totalPages" in source
    assert "async function reload" in source


def test_public_workspace_styles_cover_listing_end_message():
    stylesheet = CSS_PATH.read_text(encoding="utf-8")

    assert ".end-of-content-message" in stylesheet
    assert ".end-of-content-message[hidden]" in stylesheet


def test_public_list_runtime_uses_defined_localized_browser_contracts():
    source = (TEMPLATE_ROOT / "list.html").read_text(encoding="utf-8")
    base_source = (TEMPLATE_ROOT / "base.html").read_text(encoding="utf-8")

    assert "setView(view)" not in source
    assert '${_("Kaupunki")}' not in source
    assert "publicListI18n.city" in source
    assert "publicListI18n.removeFilter" in source
    assert "new Intl.DateTimeFormat" in source
    assert "activeLocale" in source
    assert 'filename=\'js/date.js\'' not in source
    assert '["Sunnuntai", "Maanantai"' not in source
    assert '["Tammikuu", "Helmikuu"' not in source

    theme_source = THEME_JS_PATH.read_text(encoding="utf-8")
    assert "$(" not in theme_source
    assert "document.documentElement.classList" in theme_source
    assert "20261003-theme-1" in base_source


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize(
    ("locale", "city_label", "january_label"),
    [
        ("fi", "Kaupunki", "tammikuu"),
        ("en", "City", "January"),
        ("sv", "Stad", "januari"),
    ],
)
def test_public_list_filters_and_date_picker_follow_active_locale(
    app, live_server, browser_page, locale, city_label, january_label
):
    app.config.update(
        BABEL_SUPPORTED_LOCALES=["fi", "en", "sv"],
        BABEL_PUBLIC_LOCALES=["fi", "en", "sv"],
    )
    browser_page.route(
        "https://cdn.jsdelivr.net/npm/flatpickr",
        lambda route: route.fulfill(
            content_type="application/javascript",
            body=(
                "window.flatpickr = (selector, config) => {"
                "const element = document.querySelector(selector);"
                "const instance = {l10n: config.locale, set() {}};"
                "element._flatpickr = instance;"
                "return instance;"
                "};"
            ),
        ),
    )
    browser_page.goto(f"{live_server}/set_language/{locale}")
    page_errors = []
    browser_page.on(
        "pageerror", lambda error: page_errors.append(getattr(error, "stack", str(error)))
    )
    browser_page.goto(f"{live_server}/demonstrations", wait_until="domcontentloaded")
    browser_page.wait_for_function(
        "document.getElementById('date_start')?._flatpickr?.l10n?.months?.longhand?.length === 12"
    )

    browser_page.locator("#city_input").fill("Hel")
    browser_page.locator("#city_suggestions .suggestion-item", has_text="Helsinki").click()

    assert browser_page.locator("#filters .filter span").inner_text() == (
        f"{city_label}: Helsinki"
    )
    assert browser_page.locator("#date_start").evaluate(
        "element => element._flatpickr.l10n.months.longhand[0]"
    ) == january_label
    assert not [error for error in page_errors if "ResizeObserver" not in error]
