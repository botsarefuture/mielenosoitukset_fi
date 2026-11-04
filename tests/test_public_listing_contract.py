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

    for source in (list_template, city_template, tag_template):
        assert "extends '_layouts/demonstration-list.html'" in source
    layout = (TEMPLATE_ROOT / '_layouts/demonstration-list.html').read_text()
    page = Path('frontend/src/pages/DemonstrationListingPage.tsx').read_text()
    assert "include '_partials/demonstration-listing.html'" in layout
    listing = (TEMPLATE_ROOT / '_partials/demonstration-listing.html').read_text()
    assert 'data-react-island="demonstration-listing"' in listing
    assert 'ListingTools props={props}' in page
    assert 'id="demos-grid"' in page and 'id="load-more-btn"' in page
    assert 'hero_section' not in layout and 'eyebrow' not in layout


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
    source = (TEMPLATE_ROOT / "_partials/demonstration-listing.html").read_text(encoding="utf-8")
    base_source = (TEMPLATE_ROOT / "base.html").read_text(encoding="utf-8")

    assert "setView(view)" not in source
    assert '${_("Kaupunki")}' not in source
    assert "'city': _('Kaupunki')" in source
    assert "'removeFilter': _('Poista suodatin')" in source
    range_source = (Path("mielenosoitukset_fi/static/js/public-date-range.js")).read_text(encoding="utf-8")
    assert "new Intl.DateTimeFormat" in range_source
    assert "activeLocale" in range_source
    assert "public_search_scripts()" in (TEMPLATE_ROOT / "_layouts/demonstration-list.html").read_text()
    assert 'filename=\'js/date.js\'' not in source
    assert '["Sunnuntai", "Maanantai"' not in source
    assert '["Tammikuu", "Helmikuu"' not in source

    theme_source = THEME_JS_PATH.read_text(encoding="utf-8")
    assert "$(" not in theme_source
    assert "document.documentElement.classList" in theme_source
    assert "20261003-theme-1" in base_source


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('count', [1, 3])
@pytest.mark.parametrize(
    ("locale", "city_label", "january_label"),
    [
        ("fi", "Kaupunki", "tammikuu"),
        ("en", "City", "January"),
        ("sv", "Stad", "januari"),
    ],
)
def test_public_list_filters_and_date_picker_follow_active_locale(
    app, live_server, browser_page, locale, city_label, january_label, count
):
    import json
    app.config.update(
        BABEL_SUPPORTED_LOCALES=["fi", "en", "sv"],
        BABEL_PUBLIC_LOCALES=["fi", "en", "sv"],
    )
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(
        content_type='application/json', body=json.dumps({
            'page': 1, 'total_pages': 1, 'total': count,
            'results': [{'_id': str(index), 'title': f'Demo {index}',
                         'date': '2099-01-01', 'start_time': '12:00',
                         'city': 'Helsinki', 'tags': []} for index in range(count)],
        }),
    ))
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

    assert browser_page.locator("#filters .public-filter-chip span").inner_text() == (
        f"{city_label}: Helsinki"
    )
    assert browser_page.locator("#date_start").evaluate(
        "element => element._flatpickr.l10n.months.longhand[0]"
    ) == january_label
    summary_formats = {
        "fi": "Näytetään __START__–__END__ / __COUNT__ mielenosoituksesta",
        "en": "Showing __START__–__END__ of __COUNT__ demonstrations",
        "sv": "Visar __START__–__END__ av totalt __COUNT__",
    }
    errors = {
        "fi": "Mielenosoitusten lataaminen epäonnistui. Yritä uudelleen.",
        "en": "Could not load demonstrations. Please try again.",
        "sv": "Det gick inte att ladda demonstrationer. Försök igen.",
    }
    assert browser_page.locator("#listing-result-summary").get_attribute("data-format") == summary_formats[locale]
    expected_summary = summary_formats[locale].replace('__START__', '1').replace('__END__', str(count)).replace('__COUNT__', str(count))
    browser_page.wait_for_function('(expected) => document.getElementById("listing-result-summary").textContent === expected', arg=expected_summary)
    assert browser_page.locator('#listing-result-summary').inner_text() == expected_summary
    assert browser_page.locator("#listing-load-error p").text_content() == errors[locale]
    assert not [error for error in page_errors if "ResizeObserver" not in error]
