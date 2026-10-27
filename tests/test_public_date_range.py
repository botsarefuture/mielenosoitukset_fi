"""Actual pinned picker runtime, not a mock of its lifecycle."""
import hashlib
from datetime import date
from pathlib import Path
import pytest


def test_public_date_vendor_files_match_reviewed_release_hashes():
    root = Path('mielenosoitukset_fi/static/vendor/flatpickr/4.6.13')
    expected = {
        'flatpickr.min.js': 'f8dd3f8f0ef355d62bd21f2a0a8d0c6c1cae055f5610403b5c894ed771687d28',
        'flatpickr.min.css': '847e19bf7d5529fd8a30e26f214a6120c1cc8578df4cea7ae5405be87e76b101',
        'LICENSE.md': '5fd57afc3905651175947ae44818e91ffcf5b605e4c88fac42d9700243bd9095',
    }
    for name, digest in expected.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path', ['/demonstrations', '/city/Helsinki', '/tag/test-tag'])
@pytest.mark.parametrize('locale,january', [('fi', 'tammikuu'), ('en', 'January'), ('sv', 'januari')])
def test_actual_date_picker_locale_bounds_history_and_clear(app, live_server, browser_page, path, locale, january):
    app.config.update(BABEL_SUPPORTED_LOCALES=['fi', 'en', 'sv'], BABEL_PUBLIC_LOCALES=['fi', 'en', 'sv'])
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(
        content_type='application/json', body='{"page":1,"total_pages":1,"total":0,"results":[]}'))
    browser_page.goto(f'{live_server}/set_language/{locale}')
    browser_page.goto(f'{live_server}{path}?date_start=2099-01-05&date_end=2099-01-10', wait_until='domcontentloaded')
    browser_page.wait_for_function("document.getElementById('date_end')._flatpickr?.selectedDates.length === 1")
    assert browser_page.locator('#date_start').evaluate('element => element._flatpickr.l10n.months.longhand[0]') == january
    year_label, month_label = {'fi': ('Vuosi', 'Kuukausi'), 'en': ('Year', 'Month'), 'sv': ('År', 'Månad')}[locale]
    assert browser_page.locator('#date_start-calendar input.cur-year').get_attribute('aria-label') == year_label
    assert browser_page.locator('#date_start-calendar .flatpickr-monthDropdown-months').get_attribute('aria-label') == month_label
    browser_page.evaluate("document.getElementById('date_end')._flatpickr.setDate('20.01.2099', true); document.getElementById('date_start')._flatpickr.setDate('15.01.2099', true)")
    browser_page.locator('#search-form button[type=submit]').click()
    browser_page.wait_for_function("new URLSearchParams(location.search).get('date_start') === '2099-01-15'")
    browser_page.go_back()
    browser_page.wait_for_function("document.getElementById('date_start').value === '05.01.2099'")
    assert browser_page.locator('#date_start').evaluate('element => element._flatpickr.config.maxDate.getDate()') == 10
    assert browser_page.locator('#date_end').evaluate('element => element._flatpickr.config.minDate.getDate()') == 5
    browser_page.locator('#date_start').fill('')
    browser_page.locator('#date_end').fill('')
    browser_page.locator('#search-form button[type=submit]').click()
    browser_page.wait_for_function("!new URLSearchParams(location.search).has('date_start')")
    assert browser_page.locator('#date_start').evaluate('element => element._flatpickr.selectedDates.length') == 0
    assert browser_page.locator('#date_start').evaluate('element => element._flatpickr.config.maxDate === undefined')
    assert browser_page.locator('#date_end').evaluate('element => element._flatpickr.config.minDate.getFullYear()') == date.today().year
    browser_page.locator('#date_start').fill('05.01.2020')
    browser_page.locator('#date_end').fill('10.01.2020')
    browser_page.locator('#search-form button[type=submit]').click()
    browser_page.wait_for_function("new URLSearchParams(location.search).get('date_start') === '2020-01-05'")
    browser_page.goto(f'{live_server}{path}?date_start=2020-01-05&date_end=2020-01-10', wait_until='domcontentloaded')
    browser_page.wait_for_function("document.getElementById('date_start')._flatpickr?.selectedDates[0]?.getFullYear() === 2020")
    assert browser_page.locator('#date_start').input_value() == '05.01.2020'
    assert browser_page.locator('#date_end').input_value() == '10.01.2020'


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path', ['/demonstrations', '/city/Helsinki', '/tag/test-tag'])
@pytest.mark.parametrize('query', ['date_start=2020-01-05&date_end=2020-01-10', 'date_end=2020-01-10'])
def test_restored_historical_range_can_select_an_earlier_start(live_server, browser_page, path, query):
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(
        content_type='application/json', body='{"page":1,"total_pages":1,"total":0,"results":[]}'))
    browser_page.goto(f'{live_server}{path}?{query}', wait_until='domcontentloaded')
    browser_page.wait_for_function("document.getElementById('date_end')._flatpickr?.selectedDates.length === 1")
    assert browser_page.locator('#date_start').evaluate('element => element._flatpickr.config.minDate === undefined')
    browser_page.evaluate("document.getElementById('date_start')._flatpickr.setDate('01.01.2020', true)")
    assert browser_page.locator('#date_start').input_value() == '01.01.2020'
    browser_page.locator('#search-form button[type=submit]').click()
    browser_page.wait_for_function("new URLSearchParams(location.search).get('date_start') === '2020-01-01'")
    browser_page.locator('#date_start').fill('')
    browser_page.locator('#date_end').fill('')
    browser_page.locator('#search-form button[type=submit]').click()
    browser_page.wait_for_function("!new URLSearchParams(location.search).has('date_start')")
    assert browser_page.locator('#date_start').evaluate('element => element._flatpickr.config.minDate.getFullYear()') == date.today().year


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('theme,width', [('light', 1440), ('dark', 1440), ('light', 390), ('dark', 390)])
def test_actual_calendar_is_theme_safe_and_keyboard_reachable(live_server, browser_page, theme, width):
    browser_page.set_viewport_size({'width': width, 'height': 1000})
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(
        content_type='application/json', body='{"page":1,"total_pages":1,"total":0,"results":[]}'))
    browser_page.goto(f'{live_server}/demonstrations', wait_until='domcontentloaded')
    browser_page.wait_for_function("document.getElementById('date_start')?._flatpickr")
    browser_page.evaluate("document.getElementById('date_start')._flatpickr.setDate(new Date(), false)")
    browser_page.locator('#date_start').focus()
    browser_page.keyboard.press('ArrowDown')
    calendar = browser_page.locator('.public-date-calendar.open')
    calendar.wait_for(state='visible')
    assert calendar.get_attribute('role') == 'dialog'
    assert browser_page.locator('#date_start').get_attribute('aria-expanded') == 'true'
    assert calendar.locator('.flatpickr-day:focus').count() == 1
    rect = calendar.bounding_box()
    assert rect['x'] >= 0 and rect['x'] + rect['width'] <= width + 1
    assert calendar.evaluate('element => getComputedStyle(element).backgroundColor') == ('rgb(255, 255, 255)' if theme == 'light' else 'rgb(32, 37, 45)')
    selected = calendar.locator('.flatpickr-day.selected')
    selected.hover()
    assert selected.evaluate('element => getComputedStyle(element).color') == 'rgb(255, 255, 255)'
    assert selected.evaluate('element => getComputedStyle(element).backgroundColor') == ('rgb(0, 51, 160)' if theme == 'light' else 'rgb(49, 94, 168)')
    calendar.screenshot(path=f'/tmp/moso-date-calendar-{theme}.png')
    browser_page.keyboard.press('Escape')
    assert calendar.is_hidden()
    assert browser_page.evaluate('document.activeElement.id') == 'date_start'
    assert browser_page.locator('#date_start').get_attribute('aria-expanded') == 'false'


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path', ['/demonstrations', '/city/Helsinki', '/tag/test-tag'])
def test_public_dates_remain_manually_usable_if_picker_asset_fails(live_server, browser_page, path):
    browser_page.route('**/vendor/flatpickr/4.6.13/flatpickr.min.js', lambda route: route.abort())
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(
        content_type='application/json', body='{"page":1,"total_pages":1,"total":0,"results":[]}'))
    errors = []
    browser_page.on('pageerror', lambda error: errors.append(error.stack))
    browser_page.goto(f'{live_server}{path}', wait_until='domcontentloaded')
    browser_page.locator('#date_start').fill('05.01.2099')
    browser_page.locator('#date_end').fill('10.01.2099')
    browser_page.locator('#search-form button[type=submit]').click()
    browser_page.wait_for_function("new URLSearchParams(location.search).get('date_start') === '2099-01-05'")
    assert browser_page.locator('#date_start').evaluate('element => !element._flatpickr')
    assert not errors
