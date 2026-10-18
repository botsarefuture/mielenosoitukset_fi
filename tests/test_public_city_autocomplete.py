"""Shared city combobox on actual listing routes; API traffic is isolated."""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path', ['/demonstrations', '/tag/test-tag'])
@pytest.mark.parametrize('theme,width', [('light', 1440), ('dark', 1440), ('light', 390), ('dark', 390)])
def test_city_combobox_keyboard_selection_preserves_route_contract(live_server, browser_page, tmp_path, path, theme, width):
    from playwright.sync_api import expect

    browser_page.set_viewport_size({'width': width, 'height': 1000})
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    requests = []
    errors = []
    browser_page.on('pageerror', lambda error: errors.append(error.stack))

    def serve(route):
        requests.append(parse_qs(urlsplit(route.request.url).query))
        route.fulfill(content_type='application/json', body=json.dumps({
            'page': 1, 'total_pages': 1, 'total': 0, 'results': []}))

    browser_page.route('**/api/demonstrations?*', serve)
    browser_page.goto(f'{live_server}{path}?city=Tampere&search=kept', wait_until='domcontentloaded')
    browser_page.wait_for_function('window.publicListHistory !== undefined')
    field = browser_page.locator('#city_input')
    field.fill('hels')
    assert field.get_attribute('role') == 'combobox'
    assert field.get_attribute('aria-expanded') == 'true'
    option = browser_page.get_by_role('option', name='Helsinki', exact=True)
    assert option.is_visible()
    rect = option.bounding_box()
    assert rect['height'] >= 44 and rect['x'] + rect['width'] <= width + 1
    browser_page.keyboard.press('ArrowDown')
    assert browser_page.evaluate('document.activeElement.id') == 'city_input'
    active_id = field.get_attribute('aria-activedescendant')
    assert active_id
    active_option = browser_page.locator('#' + active_id)
    assert active_option.get_attribute('aria-selected') == 'true'
    expect(active_option).to_have_css('background-color', 'rgb(0, 51, 160)' if theme == 'light' else 'rgb(49, 94, 168)')
    expect(active_option).to_have_css('color', 'rgb(255, 255, 255)')
    if (theme, width) in [('light', 390), ('dark', 1440)]:
        browser_page.locator('#search-form').screenshot(path=str(tmp_path / f'city-combobox-{theme}-{width}.png'))
    browser_page.keyboard.press('End')
    browser_page.keyboard.press('Home')
    browser_page.keyboard.press('Escape')
    assert field.get_attribute('aria-expanded') == 'false'
    assert field.get_attribute('aria-activedescendant') is None
    assert field.input_value() == 'hels'
    browser_page.keyboard.press('ArrowDown')
    # Choose a known option using the same active-descendant selection contract.
    for _ in range(20):
        active_id = field.get_attribute('aria-activedescendant')
        assert active_id
        active = browser_page.locator('#' + active_id)
        if active.inner_text() == 'Helsinki':
            break
        browser_page.keyboard.press('ArrowDown')
    assert active.inner_text() == 'Helsinki'
    browser_page.keyboard.press('Enter')
    assert browser_page.locator('#city').input_value() == 'Tampere,Helsinki'
    assert field.input_value() == '' and field.get_attribute('aria-expanded') == 'false'
    assert browser_page.locator('#filters').inner_text().count('Helsinki') == 1
    if path == '/demonstrations':
        assert parse_qs(urlsplit(browser_page.url).query)['city'] == ['Tampere']
        browser_page.locator('#search-form button[type=submit]').click()
    browser_page.wait_for_function("new URLSearchParams(location.search).get('city') === 'Tampere,Helsinki'")
    query = parse_qs(urlsplit(browser_page.url).query)
    assert query['search'] == ['kept'] and query['page'] == ['1']
    if path.startswith('/tag/'):
        assert query['tag'] == ['test-tag']
    field.fill('hels')
    assert browser_page.get_by_role('option', name='Helsinki', exact=True).count() == 0
    browser_page.keyboard.press('Tab')
    assert field.get_attribute('aria-expanded') == 'false'
    assert browser_page.evaluate('document.activeElement.id') == 'demo-location'
    assert not errors


@pytest.mark.e2e
def test_city_combobox_treats_html_and_regex_as_plain_text_and_bounds_options(browser_page):
    browser_page.set_content('''<input id="city_input" role="combobox" aria-controls="city_suggestions" aria-expanded="false">
      <input id="city" type="hidden"><div id="city_suggestions" role="listbox"></div>''')
    browser_page.add_script_tag(path=str(Path('mielenosoitukset_fi/static/js/public-city-autocomplete.js')))
    browser_page.evaluate('''() => {
      window.publicListHistory = {renderCities: () => { window.rendered = true; }};
      publicCityAutocomplete({cities: ['<img src=x onerror="window.injected=true">[town]',
        'Locale ä', 'Locale z', 'Locale å', 'Locale a',
        ...Array.from({length: 100}, (_, index) => 'Town ' + String(99 - index).padStart(3, '0'))]});
    }''')
    field = browser_page.locator('#city_input')
    field.fill('[town]')
    option = browser_page.get_by_role('option')
    assert option.count() == 1
    assert option.locator('img').count() == 0
    option.click()
    assert browser_page.locator('#city').input_value() == '<img src=x onerror="window.injected=true">[town]'
    assert browser_page.evaluate('Boolean(window.injected)') is False
    assert browser_page.evaluate('window.rendered') is True
    field.fill('town')
    assert browser_page.get_by_role('option').all_text_contents() == [
        f'Town {index:03d}' for index in range(20)
    ]
    field.fill('locale')
    expected = browser_page.evaluate('''() => ['Locale ä', 'Locale z', 'Locale å', 'Locale a']
      .sort(new Intl.Collator().compare)''')
    assert browser_page.get_by_role('option').all_text_contents() == expected
    field.blur()
    assert browser_page.get_by_role('option').count() == 0
