"""React listing ownership preserves the existing API/window behavior."""
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect


def result(page=1, *, search='', size=1, total_pages=20, rows=None):
    return {'page': page, 'per_page': size, 'total_pages': total_pages, 'total': size * total_pages,
            'result_start': (page - 1) * size + 1, 'result_end': page * size,
            'results': rows if rows is not None else [{'_id': f'{search or "base"}-{page}',
                'title': f'{search or "Event"} {page}', 'date': '2099-01-01', 'city': 'Helsinki', 'tags': []}]}


def serve_list(route):
    query = parse_qs(urlsplit(route.request.url).query)
    route.fulfill(content_type='application/json', body=json.dumps(result(
        int(query['page'][0]), search=query.get('search', [''])[0])))


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path', ['/demonstrations', '/city/Helsinki', '/tag/null-clock-test'])
@pytest.mark.parametrize('field', ['start_time', 'end_time'])
def test_actual_api_null_times_do_not_remove_the_card_batch(client, db, seeded_data, live_server, browser_page, path, field):
    """A valid nullable API clock must not crash the React root for its whole page."""
    db.demonstrations.update_one({'_id': seeded_data['demo_id']}, {
        '$set': {'start_time': '12:34:56', 'end_time': '14:00:00', field: None,
                 'city': 'Helsinki', 'tags': ['null-clock-test']},
    })
    response = client.get('/api/demonstrations?tag=null-clock-test&per_page=12')
    assert response.status_code == 200
    assert response.json['results'][0][field] is None
    errors = []
    browser_page.on('pageerror', lambda error: errors.append(str(error)))
    browser_page.set_viewport_size({'width': 390, 'height': 1000})
    browser_page.goto(live_server + path, wait_until='networkidle')
    card = browser_page.locator(f'[data-demo-id="{seeded_data["demo_id"]}"]')
    expect(card).to_be_visible()
    expect(card.locator('.demo-card-title a')).not_to_be_empty()
    expect(browser_page.locator('#listing-result-summary')).to_be_visible()
    assert errors == []


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path', ['/demonstrations', '/city/Helsinki', '/tag/react-test'])
@pytest.mark.parametrize('width', [390, 1440])
def test_listing_uses_available_width_and_one_branded_search_group(live_server, browser_page, path, width):
    browser_page.set_viewport_size({'width': width, 'height': 1000})
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(content_type='application/json', body=json.dumps(result(total_pages=1))))
    browser_page.goto(live_server + path, wait_until='domcontentloaded')
    expect(browser_page.locator('.demo-card-title a')).to_have_text('Event 1')
    expect(browser_page.locator('.public-list-tools #search-form')).to_be_visible()
    assert browser_page.locator('.public-list-tools h1').count() == 1
    assert browser_page.locator('.site-hero, .page-banner, .site-hero__eyebrow').count() == 0
    geometry = browser_page.locator('#main-content').evaluate('e => ({width:e.getBoundingClientRect().width, scroll:document.documentElement.scrollWidth})')
    assert geometry['width'] >= width - 1 and geometry['scroll'] <= width + 1
    # Brand typography belongs to the tools; shared cards retain their existing font.
    assert browser_page.locator('.public-list-tools').evaluate("e => getComputedStyle(e).fontFamily").startswith('Roboto')
    assert browser_page.locator('.demo-card-title').first.evaluate("e => getComputedStyle(e).fontFamily").startswith('Inter')
    assert browser_page.locator('.public-search-submit').evaluate("e => getComputedStyle(e).backgroundColor") == 'rgb(255, 102, 0)'
    if path != '/demonstrations':
        expect(browser_page.locator('.public-list-all')).to_be_visible()
        assert browser_page.locator('.public-list-all').evaluate("e => getComputedStyle(e).textDecorationLine") == 'none'


@pytest.mark.e2e
@pytest.mark.integration
def test_card_content_is_text_safe_and_uses_real_internal_links(live_server, browser_page):
    rows = [{'_id': 'safe', 'title': '<img src=x onerror=alert(1)>', 'city': 'Helsinki',
             'date': '2099-01-01', 'tags': ['<script>'], 'detail_url': 'https://example.test/external'},
            {'_id': 'series', 'title': 'Selected date', 'date': '2099-01-01', 'tags': [],
             'detail_url': '/demonstration/series/children?occurrence=selected'}]
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(content_type='application/json', body=json.dumps(result(total_pages=1, size=2, rows=rows))))
    browser_page.goto(live_server + '/demonstrations', wait_until='domcontentloaded')
    expect(browser_page.locator('.demo-card-title a').first).to_have_text('<img src=x onerror=alert(1)>')
    expect(browser_page.locator('.demo-card-title a').first).to_have_attribute('href', '#')
    assert browser_page.locator('.demo-card-title img, .demo-card-tags script').count() == 0
    expect(browser_page.locator('.demo-card-title a').last).to_have_attribute('href', '/demonstration/series/children?occurrence=selected')
    expect(browser_page.locator('.demo-card-tag')).to_have_attribute('href', '/tag/%3Cscript%3E')
    browser_page.locator('.demo-card-title a').last.focus()
    expect(browser_page.locator('.demo-card-title a').last).to_be_focused()


@pytest.mark.e2e
@pytest.mark.integration
def test_react_attendance_request_lifetime_follows_page_eviction(live_server, browser_page, user_client):
    browser_page.add_init_script("Object.defineProperty(navigator,'connection',{value:{saveData:true}})")
    browser_page.context.add_cookies([{'name':'session','value':user_client.get_cookie('session').value,'url':live_server}])
    browser_page.route('**/api/demonstrations?*', serve_list)
    pending = {}
    aborted = []
    def attendance(route):
        pending[route.request.post_data_json['demo_ids'][0]] = route
    browser_page.route('**/api/friends-attending', attendance)
    browser_page.on('requestfailed', lambda request: aborted.append(request.post_data_json['demo_ids'][0])
                    if '/api/friends-attending' in request.url else None)
    browser_page.goto(live_server + '/demonstrations?per_page=1', wait_until='domcontentloaded')
    expect(browser_page.locator('.demo-card')).to_have_count(1)
    for page in range(2, 7):
        browser_page.locator('#load-more-btn').click()
        browser_page.wait_for_function('(n) => publicListWindow.last === n', arg=page)
    assert browser_page.locator('.public-list-page').count() == 5
    assert 'base-1' in aborted and not set(aborted).intersection({f'base-{n}' for n in range(2, 7)})
    pending['base-2'].fulfill(content_type='application/json', body=json.dumps({'base-2':[{'name':'<img src=x>', 'avatar':'/static/icons/icon_favicon-32x32.png'}]}))
    expect(browser_page.locator('[data-list-page="2"] .friends-text')).to_contain_text('<img src=x>')
    assert browser_page.locator('[data-list-page="2"] .friends-text img').count() == 0
    browser_page.locator('#demo-search').fill('replacement')
    browser_page.locator('#search-form button[type=submit]').click()
    expect(browser_page.locator('.demo-card-title a')).to_have_text('replacement 1')
    assert {f'base-{n}' for n in range(3, 7)}.issubset(set(aborted))
    assert browser_page.locator('.public-list-page').count() == 1


@pytest.mark.e2e
@pytest.mark.integration
def test_delayed_react_append_does_not_replace_a_new_search(live_server, browser_page):
    browser_page.add_init_script("Object.defineProperty(navigator,'connection',{value:{saveData:true}})")
    old = []
    def serve(route):
        query = parse_qs(urlsplit(route.request.url).query)
        if query.get('page') == ['2'] and not query.get('search'):
            old.append(route)
        else:
            serve_list(route)
    browser_page.route('**/api/demonstrations?*', serve)
    browser_page.goto(live_server + '/demonstrations?per_page=1', wait_until='domcontentloaded')
    expect(browser_page.locator('.demo-card')).to_have_count(1)
    browser_page.locator('#load-more-btn').click()
    expect(browser_page.locator('#load-more-btn')).to_be_disabled()
    browser_page.locator('#demo-search').fill('current')
    browser_page.locator('#search-form button[type=submit]').click()
    expect(browser_page.locator('.demo-card-title a')).to_have_text('current 1')
    assert len(old) == 1
    old[0].fulfill(content_type='application/json', body=json.dumps(result(2)))
    browser_page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    expect(browser_page.locator('.demo-card-title a')).to_have_text('current 1')
    assert browser_page.locator('.public-list-page').count() == 1


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('locale,filtered,empty', [
    ('en', 'No demonstrations matched these filters.', 'There are no visible demonstrations with this tag.'),
    ('sv', 'Inga demonstrationer matchade dessa filter.', 'Det finns inga synliga demonstrationer med denna tagg.'),
])
def test_react_tag_empty_feedback_is_localized_and_clear_preserves_scope(app, live_server, browser_page, locale, filtered, empty):
    app.config['BABEL_PUBLIC_LOCALES'] = ['fi', 'en', 'sv']
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(content_type='application/json', body=json.dumps({'page':1, 'total_pages':1, 'total':0, 'results':[]})))
    browser_page.goto(live_server + '/set_language/' + locale)
    browser_page.goto(live_server + '/tag/react-test?search=missing', wait_until='domcontentloaded')
    expect(browser_page.locator('.no-results-text')).to_contain_text(filtered)
    browser_page.locator('#clear-filters-btn').click()
    expect(browser_page.locator('.no-results-text')).to_have_text(empty)
    assert parse_qs(urlsplit(browser_page.url).query)['tag'] == ['react-test']
    assert 'search' not in parse_qs(urlsplit(browser_page.url).query)


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('field', ['cover_picture', 'cover_image', 'preview_image', 'img'])
@pytest.mark.parametrize('path', ['/demonstrations', '/city/Helsinki', '/tag/react-image-test'])
def test_actual_api_image_fields_load_in_react_cards(client, db, seeded_data, live_server, browser_page, field, path):
    """Follow actual Mongo -> API -> card -> decoded image bytes, without a mocked API."""
    image = '/static/kampanja/og-banner.png'
    image_fields = ('cover_picture', 'cover_image', 'preview_image', 'img')
    db.demonstrations.update_one({'_id': seeded_data['demo_id']}, {
        '$set': {field: image, 'tags': ['react-image-test']},
        '$unset': {key: '' for key in image_fields if key != field},
    })
    response = client.get('/api/demonstrations?tag=react-image-test&per_page=12')
    assert response.status_code == 200
    row = next(row for row in response.json['results'] if row['_id'] == str(seeded_data['demo_id']))
    assert row[field] == image
    browser_page.set_viewport_size({'width': 390, 'height': 1000})
    browser_page.goto(live_server + path, wait_until='domcontentloaded')
    picture = browser_page.locator(f'[data-demo-id="{seeded_data["demo_id"]}"] .demo-card-image img')
    expect(picture).to_have_attribute('src', image)
    picture.scroll_into_view_if_needed()
    browser_page.wait_for_function('(selector) => {const image=document.querySelector(selector); return image?.complete && image.naturalWidth > 0;}', arg=f'[data-demo-id="{seeded_data["demo_id"]}"] .demo-card-image img')
    assert picture.evaluate("e => getComputedStyle(e).objectFit") == 'contain'
    assert picture.bounding_box()['width'] <= browser_page.locator(f'[data-demo-id="{seeded_data["demo_id"]}"]').bounding_box()['width']
