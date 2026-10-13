"""URL/form/history contract across the actual public collection routes."""
import json
from urllib.parse import parse_qs, urlsplit
import pytest


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path,fixed', [('/demonstrations', {}), ('/city/Helsinki', {'city': 'Helsinki'}), ('/tag/test-tag', {'tag': 'test-tag'})])
def test_public_filter_url_restores_page_and_back_forward(live_server, browser_page, path, fixed):
    requests = []
    attempts = {}
    browser_page.route('https://cdn.jsdelivr.net/npm/flatpickr', lambda route: route.fulfill(
        content_type='application/javascript', body="window.flatpickr = () => ({set(){}});"))

    def serve(route):
        args = {key: values[0] for key, values in parse_qs(urlsplit(route.request.url).query).items()}
        requests.append(args)
        page, size = int(args['page']), int(args['per_page'])
        key = (args.get('search'), page)
        attempts[key] = attempts.get(key, 0) + 1
        if key == ('new search', 3) and attempts[key] == 1:
            route.fulfill(status=503, content_type='application/json', body='{}')
            return
        route.fulfill(content_type='application/json', body=json.dumps({
            'page': page, 'per_page': size, 'total': 8, 'total_pages': 4,
            'result_start': (page - 1) * size + 1,
            'results': [{'_id': str(index), 'title': f"{args.get('search')}-{page}-{index}",
                         'date': '2099-01-01', 'start_time': '12:00', 'city': 'Helsinki', 'tags': []}
                        for index in range(size)],
        }))
    browser_page.route('**/api/demonstrations?*', serve)
    errors = []
    browser_page.on('pageerror', lambda error: errors.append(error.stack))
    browser_page.goto(f'{live_server}{path}?search=initial&city=Tampere&tag=wrong&location=place&date_start=2099-01-01&date_end=2099-01-31&per_page=2&page=3', wait_until='domcontentloaded')
    browser_page.wait_for_function("document.getElementById('listing-result-summary').textContent.includes('5–6')")
    assert browser_page.locator('[name=search]').input_value() == 'initial'
    assert browser_page.locator('[name=display_date_start]').input_value() == '01.01.2099'
    assert browser_page.locator('[name=display_date_end]').input_value() == '31.01.2099'
    assert requests[-1]['page'] == '3' and requests[-1]['per_page'] == '2'
    for key, value in fixed.items():
        assert requests[-1][key] == value

    browser_page.locator('[name=search]').fill('new search')
    browser_page.locator('#search-form button[type=submit]').click()
    browser_page.wait_for_function("document.getElementById('listing-result-summary').textContent.includes('1–2')")
    query = parse_qs(urlsplit(browser_page.url).query)
    assert query['search'] == ['new search'] and query['page'] == ['1']
    assert query['per_page'] == ['2'] and query['date_start'] == ['2099-01-01']
    browser_page.locator('#load-more-btn').click()
    browser_page.wait_for_function("new URLSearchParams(location.search).get('page') === '2'")
    assert '1–4' in browser_page.locator('#listing-result-summary').inner_text()
    browser_page.go_back()
    browser_page.wait_for_function("document.getElementById('listing-result-summary').textContent.includes('5–6')")
    assert browser_page.locator('[name=search]').input_value() == 'initial'
    browser_page.go_forward()
    browser_page.wait_for_function("document.getElementById('listing-result-summary').textContent.includes('3–4')")
    assert browser_page.locator('[name=search]').input_value() == 'new search'
    assert requests[-1]['location'] == 'place' and requests[-1]['date_end'] == '2099-01-31'
    assert requests[-1]['history_restore'] == '1'
    assert 'history_restore' not in parse_qs(urlsplit(browser_page.url).query)
    for key, value in fixed.items():
        assert requests[-1][key] == value
    assert not errors
    browser_page.locator('#load-more-btn').click()
    browser_page.locator('#listing-load-error').wait_for(state='visible')
    assert parse_qs(urlsplit(browser_page.url).query)['page'] == ['2']
    browser_page.locator('#listing-load-error button').click()
    browser_page.wait_for_function("new URLSearchParams(location.search).get('page') === '3'")
    assert '3–6' in browser_page.locator('#listing-result-summary').inner_text()


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path', ['/demonstrations', '/tag/test-tag'])
@pytest.mark.parametrize('theme,width', [('light', 1440), ('dark', 1440), ('light', 390), ('dark', 390)])
def test_restored_city_chip_is_text_safe_and_removal_resets_url(live_server, browser_page, path, theme, width):
    browser_page.set_viewport_size({'width': width, 'height': 1000})
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    browser_page.route('https://cdn.jsdelivr.net/npm/flatpickr', lambda route: route.fulfill(
        content_type='application/javascript', body="window.flatpickr = () => ({set(){}});"))
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(
        content_type='application/json', body=json.dumps({'page': 1, 'total_pages': 1, 'total': 0, 'results': []})))
    browser_page.goto(f'{live_server}{path}?city=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E&date_start=2099-01-01', wait_until='domcontentloaded')
    chip = browser_page.locator('#filters .public-filter-chip')
    assert '<img' in chip.inner_text() and chip.locator('img').count() == 0
    geometry = chip.evaluate('''element => {
      const rect = element.getBoundingClientRect();
      const button = element.querySelector('button').getBoundingClientRect();
      return {left: rect.left, right: rect.right, width: innerWidth, hitWidth: button.width, hitHeight: button.height};
    }''')
    assert geometry['left'] >= 0 and geometry['right'] <= geometry['width'] + 1
    assert geometry['hitWidth'] >= 44 and geometry['hitHeight'] >= 44
    chip.locator('button').focus()
    if path == '/demonstrations' and width == 390:
        chip.screenshot(path=f'/tmp/moso-filter-chip-{theme}.png')
    browser_page.keyboard.press('Enter')
    browser_page.wait_for_function("!new URLSearchParams(location.search).has('city')")
    query = parse_qs(urlsplit(browser_page.url).query)
    assert query['page'] == ['1'] and query['date_start'] == ['2099-01-01']
    assert browser_page.locator('[name=city]').input_value() == ''
    browser_page.locator('[name=display_date_start]').fill('31.02.2099')
    previous_url = browser_page.url
    browser_page.locator('#search-form button[type=submit]').click()
    assert browser_page.url == previous_url
    assert browser_page.locator('#date-error').is_visible()


@pytest.mark.parametrize('query', ['page=bad', 'per_page=bad', 'per_page=0&page=-1'])
def test_tag_page_invalid_pagination_does_not_raise_500(client, query):
    assert client.get(f'/tag/test-tag?{query}').status_code == 200
