"""Visible and programmatic labels use the same public search component."""
import re
import pytest


@pytest.mark.parametrize('path,field_count', [('/demonstrations', 5), ('/city/Helsinki', 4), ('/tag/test-tag', 5)])
@pytest.mark.parametrize('locale', ['fi', 'en', 'sv'])
def test_public_search_labels_are_explicit_and_unique(app, client, path, field_count, locale):
    app.config.update(BABEL_SUPPORTED_LOCALES=['fi', 'en', 'sv'], BABEL_PUBLIC_LOCALES=['fi', 'en', 'sv'])
    client.get(f'/set_language/{locale}')
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    form = re.search(r'<form[^>]*id="search-form"[^>]*>(.*?)</form>', html, re.S).group(1)
    labels = re.findall(r'<label for="([^"]+)">([^<]+)</label>', form)
    assert len(re.findall(r'<input type="text"', form)) == field_count
    expected = {
        'fi': ['Hae mielenosoituksia', 'Alkupäivä (pp.kk.vvvv)', 'Loppupäivä (pp.kk.vvvv)'],
        'en': ['Search for demonstrations', 'Start date (dd.mm.yyyy)', 'End date (dd.mm.yyyy)'],
        'sv': ['Sök demonstrationer', 'Startdatum (dd.mm.åååå)', 'Slutdatum (dd.mm.åååå)'],
    }
    label_map = dict(labels)
    assert [label_map['demo-search'], label_map['date_start'], label_map['date_end']] == expected[locale]
    assert len(labels) == field_count and len({target for target, _ in labels}) == field_count
    for target, text in labels:
        assert text.strip()
        assert len(re.findall(rf'id="{re.escape(target)}"', html)) == 1
        assert re.search(rf'<input[^>]*id="{re.escape(target)}"', form)
    assert 'role="alert"' in form and 'aria-describedby="date-error"' in form
    assert 'name="date_start"' in form and 'name="date_end"' in form
    if path.startswith('/city/'):
        assert 'id="city_input"' not in form and 'name="city" value="Helsinki"' in form


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path', ['/demonstrations', '/city/Helsinki', '/tag/test-tag'])
@pytest.mark.parametrize('theme,width', [('light', 1440), ('dark', 1440), ('light', 390), ('dark', 390)])
def test_public_search_fields_are_visible_aligned_and_focusable(live_server, browser_page, path, theme, width):
    browser_page.set_viewport_size({'width': width, 'height': 1000})
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    browser_page.route('https://cdn.jsdelivr.net/npm/flatpickr', lambda route: route.fulfill(
        content_type='application/javascript', body="window.flatpickr = () => ({set(){}});"))
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(
        content_type='application/json', body='{"page":1,"total_pages":1,"total":0,"results":[]}'))
    browser_page.goto(f'{live_server}{path}', wait_until='domcontentloaded')
    labels = browser_page.locator('#search-form label')
    for index in range(labels.count()):
        label = labels.nth(index)
        assert label.is_visible()
        target = label.get_attribute('for')
        label.click()
        assert browser_page.evaluate('document.activeElement.id') == target
        rect = browser_page.locator(f'#{target}').bounding_box()
        label_rect = label.bounding_box()
        assert abs(label_rect['x'] - rect['x']) <= 1
        assert rect['height'] >= 44
        assert rect['x'] >= 0 and rect['x'] + rect['width'] <= width + 1
    browser_page.locator('#demo-search').focus()
    browser_page.keyboard.press('Tab')
    assert browser_page.evaluate('document.activeElement.id') == ('demo-location' if path.startswith('/city/') else 'city_input')
    if path == '/demonstrations':
        browser_page.locator('#search-form').screenshot(path=f'/tmp/moso-search-form-{theme}-{width}.png')
