"""Pride map and embedded listing preserve public scope and useful failure states."""
from copy import deepcopy
from datetime import date, timedelta
from html.parser import HTMLParser
import json
from urllib.parse import parse_qs, urlsplit

from bson import ObjectId
import pytest
from playwright.sync_api import expect


class IslandConfig(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current_id = None
        self.scripts = {}
        self.islands = {}
        self.headings = []
        self.legacy_renderer = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'script':
            self.current_id = values.get('id') if values.get('type') == 'application/json' else None
            if self.current_id:
                self.scripts[self.current_id] = []
            self.legacy_renderer |= 'demo-card-render.js' in values.get('src', '')
        if 'data-react-island' in values:
            self.islands[values['data-react-island']] = values.get('data-props-id')
        if tag in {'h1', 'h2'}:
            self.headings.append((tag, values.get('id')))

    def handle_data(self, value):
        if self.current_id:
            self.scripts[self.current_id].append(value)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.current_id = None

    def props(self, name):
        return json.loads(''.join(self.scripts[self.islands[name]]))


def pride_events(db, seeded_data, count=105):
    """Use the real public API and pagination with future/public and excluded controls."""
    prototype = db.demonstrations.find_one({'_id': seeded_data['demo_id']})
    db.demonstrations.delete_many({})
    db.recurring_demonstrations.delete_many({})
    rows = []
    for index in range(count):
        row = deepcopy(prototype)
        event_date = date.today() + timedelta(days=index + 5)
        row.update(
            _id=ObjectId(), title=f'Pride Event {index:03d}',
            date=event_date.isoformat(), formatted_date=event_date.strftime('%d.%m.%Y'),
            tags=['pride'], approved=True, hide=False, rejected=False, cancelled=False,
            in_past=False, parent=None, start_time='12:00', end_time='14:00',
            city='Helsinki' if index % 2 == 0 else 'Turku', address='Public square',
            latitude='60.1699' if index % 2 == 0 else '60.4518',
            longitude='24.9384' if index % 2 == 0 else '22.2666',
            running_number=9000 + index, slug=f'pride-test-{index}',
            cover_picture='', cover_image='', preview_image='', img='',
        )
        invalid = {
            1: {'latitude': None}, 2: {'longitude': None},
            3: {'latitude': 91}, 4: {'longitude': 181},
            5: {'latitude': '60.1x'}, 6: {'latitude': True},
            7: {'latitude': '   '},
        }
        row.update(invalid.get(index, {}))
        rows.append(row)
    excluded = []
    for label, values in (
        ('Foreign', {'tags': ['climate']}), ('Hidden', {'hide': True}),
        ('Unapproved', {'approved': False}), ('Rejected', {'rejected': True}),
        ('Cancelled', {'cancelled': True}),
        ('Past', {'date': (date.today() - timedelta(days=1)).isoformat(), 'in_past': True}),
    ):
        row = deepcopy(rows[0])
        row.update(_id=ObjectId(), title=f'{label} control', slug=f'pride-excluded-{label}', **values)
        excluded.append(row)
    db.demonstrations.insert_many(rows + excluded)
    return rows, excluded


def map_payload(rows, *, page=1, total=None, total_pages=1):
    return {'page': page, 'per_page': 100, 'total_pages': total_pages,
            'total': len(rows) if total is None else total, 'results': rows}


def is_map_request(request):
    query = parse_qs(urlsplit(request.url).query)
    return query.get('scope') == ['pride_map']


def manual_pagination(page):
    page.add_init_script("Object.defineProperty(navigator, 'connection', {value: {saveData: true}})")


def assert_pride_scope(requests):
    assert requests
    for query in requests:
        assert query['tag'] == ['pride']
        assert query['per_page'] == ['100']
        assert 'organization_id' not in query
        assert 'parent_id' not in query
        assert 'search' not in query
        assert 'max_days_till' not in query
        assert 'in_past' not in query
        assert 'include_cancelled' not in query


@pytest.mark.parametrize('path', ['/pride-nakyvaksi', '/pride/', '/pride'])
def test_pride_aliases_use_shared_listing_and_scoped_map_config(client, path):
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    page = IslandConfig()
    page.feed(html)
    listing = page.props('demonstration-listing')
    mapping = page.props('pride-map')
    assert listing['fixed'] == {'tag': 'pride'}
    assert listing['headingLevel'] == 2
    assert mapping['tag'] == 'pride'
    assert mapping['endpoint'] == listing['endpoint']
    assert len([tag for tag, _ in page.headings if tag == 'h1']) == 1
    assert ('h2', 'listing-title') in page.headings
    assert not page.legacy_renderer
    assert 'pride-hearts' not in html
    assert 'Pride 2026' not in html
    assert '∞' not in html
    assert 'id="demo-guidelines"' in html
    assert 'id="demos"' in html
    assert 'id="pride-map-section"' in html
    assert '/submit' in html and '/terms' in html


def test_pride_public_api_keeps_visibility_and_paginates_at_the_real_cap(client, db, seeded_data):
    rows, excluded = pride_events(db, seeded_data)
    first = client.get('/api/demonstrations?tag=pride&per_page=100&page=1').json
    second = client.get('/api/demonstrations?tag=pride&per_page=100&page=2').json
    assert first['total'] == second['total'] == 105
    assert first['total_pages'] == second['total_pages'] == 2
    assert first['per_page'] == second['per_page'] == 100
    assert len(first['results']) == 100 and len(second['results']) == 5
    ids = [row['_id'] for row in first['results'] + second['results']]
    assert ids == [str(row['_id']) for row in rows]
    assert not set(ids).intersection(str(row['_id']) for row in excluded)
    assert any(row['date'] > (date.today() + timedelta(days=60)).isoformat() for row in second['results'])


@pytest.mark.e2e
@pytest.mark.integration
def test_real_map_reads_all_pride_pages_and_listing_filters_do_not_change_its_scope(client, db, seeded_data, live_server, browser_page):
    rows, _ = pride_events(db, seeded_data)
    page = browser_page
    manual_pagination(page)
    # Technical state check only: local PNG responses avoid the fixture's deliberate
    # external-tile failure. Visual acceptance separately captures real OSM tiles.
    page.route('**://*.tile.openstreetmap.org/**', lambda route: route.fulfill(
        path='mielenosoitukset_fi/static/leaflet/images/layers.png', content_type='image/png'))
    requested = []
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: requested.append(parse_qs(urlsplit(request.url).query))
            if urlsplit(request.url).path == '/api/demonstrations' and is_map_request(request) else None)
    page.goto(live_server + '/pride-nakyvaksi?tag=climate&organization_id=000000000000000000000001&max_days_till=60', wait_until='networkidle')
    summary = page.locator('#pride-map-summary')
    expect(summary).to_have_attribute('data-event-count', '105')
    expect(summary).to_have_attribute('data-city-count', '2')
    expect(summary).to_have_attribute('data-mapped-count', '98')
    expect(page.locator('#pride-map path.leaflet-interactive')).to_have_count(98)
    expect(page.locator('#pride-map-retry')).to_be_hidden()
    expect(page.locator('.demo-card')).to_have_count(12)
    assert_pride_scope(requested)
    assert [query['page'] for query in requested] == [['1'], ['2']]

    page.locator('#demo-search').fill('Pride Event 104')
    page.locator('#search-form').get_by_role('button', name='Hae', exact=True).click()
    expect(page.locator('.demo-card-title a')).to_have_text('Pride Event 104')
    expect(summary).to_have_attribute('data-event-count', '105')
    expect(page.locator('#pride-map path.leaflet-interactive')).to_have_count(98)
    assert len(requested) == 2
    assert errors == []


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('failure', ['http', 'malformed-json', 'invalid-schema', 'network'])
def test_map_failures_show_retry_without_hiding_the_independent_listing(client, db, seeded_data, live_server, browser_page, failure):
    rows, _ = pride_events(db, seeded_data, count=2)
    page = browser_page
    manual_pagination(page)
    calls = []

    def serve(route):
        if not is_map_request(route.request):
            return route.continue_()
        calls.append(parse_qs(urlsplit(route.request.url).query))
        if len(calls) == 1:
            if failure == 'network':
                return route.abort()
            if failure == 'http':
                return route.fulfill(status=503, content_type='application/json', body='{"error":"Temporary outage"}')
            body = '{' if failure == 'malformed-json' else '{"page":1,"total_pages":1,"total":1,"results":{}}'
            return route.fulfill(status=200, content_type='application/json', body=body)
        route.continue_()

    page.route('**/api/demonstrations?*', serve)
    page.goto(live_server + '/pride-nakyvaksi', wait_until='networkidle')
    expect(page.locator('#pride-map-error')).to_be_visible()
    expect(page.locator('#pride-map-empty')).to_be_hidden()
    expect(page.locator('.demo-card')).to_have_count(2)
    expect(page.locator('#pride-map-retry')).to_be_enabled()
    page.locator('#pride-map-retry').click()
    expect(page.locator('#pride-map-error')).to_be_hidden()
    expect(page.locator('#pride-map-summary')).to_have_attribute('data-event-count', '2')
    expect(page.locator('#pride-map path.leaflet-interactive')).to_have_count(1)
    expect(page.locator('.demo-card')).to_have_count(2)
    assert len(calls) == 2
    assert_pride_scope(calls)


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('mode', ['empty', 'no-coordinates'])
def test_empty_map_is_distinct_from_events_without_coordinates(client, db, seeded_data, live_server, browser_page, mode):
    rows, _ = pride_events(db, seeded_data, count=2)
    page = browser_page
    manual_pagination(page)
    if mode == 'empty':
        db.demonstrations.delete_many({})
    else:
        db.demonstrations.update_many({'tags': 'pride'}, {'$unset': {'latitude': '', 'longitude': ''}})
    page.goto(live_server + '/pride-nakyvaksi', wait_until='networkidle')
    summary = page.locator('#pride-map-summary')
    expect(summary).to_have_attribute('data-event-count', '0' if mode == 'empty' else '2')
    expect(summary).to_have_attribute('data-mapped-count', '0')
    expect(page.locator('#pride-map-empty')).to_be_visible()
    expect(page.locator('#pride-map-error')).to_be_hidden()
    expect(page.locator('#pride-map path.leaflet-interactive')).to_have_count(0)
    if mode == 'empty':
        expect(page.locator('#no-results')).to_be_visible()
    else:
        expect(page.locator('.demo-card')).to_have_count(2)
        expect(page.locator('#no-results')).to_be_hidden()


@pytest.mark.e2e
@pytest.mark.integration
def test_map_popup_treats_event_fields_as_text_and_rejects_external_detail_urls(client, db, seeded_data, live_server, browser_page):
    pride_events(db, seeded_data, count=1)
    page = browser_page
    malicious = {'_id': '000000000000000000000001', 'title': '<img src=x onerror=alert(1)>',
                 'date': '2099-01-01', 'formatted_date': '<strong>unsafe date</strong>',
                 'address': '<svg onload=alert(1)>', 'city': 'Helsinki',
                 'latitude': '60.1699', 'longitude': '24.9384',
                 'detail_url': 'https://foreign.example.test/trap'}

    def serve(route):
        if is_map_request(route.request):
            route.fulfill(content_type='application/json', body=json.dumps(map_payload([malicious])))
        else:
            route.continue_()

    page.route('**/api/demonstrations?*', serve)
    page.goto(live_server + '/pride-nakyvaksi', wait_until='networkidle')
    expect(page.locator('#pride-map-summary')).to_have_attribute('data-event-count', '1')
    page.locator('#pride-map path.leaflet-interactive').dispatch_event('click')
    popup = page.locator('.leaflet-popup-content')
    expect(popup).to_be_visible()
    assert popup.locator('img,svg,script').count() == 0
    assert malicious['title'] in popup.inner_text()
    assert malicious['formatted_date'] in popup.inner_text()
    assert malicious['address'] in popup.inner_text()
    anchors = popup.locator('a').all()
    assert anchors
    assert any(urlsplit(anchor.get_attribute('href')).path.startswith('/demonstration/') for anchor in anchors)
    for anchor in anchors:
        target = urlsplit(anchor.get_attribute('href'))
        assert target.hostname in {None, urlsplit(live_server).hostname}
        assert target.path != '/trap'


@pytest.mark.e2e
@pytest.mark.integration
def test_blocked_map_entry_keeps_readable_fallback_and_working_listing(client, db, seeded_data, live_server, browser_page):
    pride_events(db, seeded_data, count=2)
    page = browser_page
    page.route('**/frontend/assets/pride-*.js', lambda route: route.abort())
    page.goto(live_server + '/pride-nakyvaksi', wait_until='networkidle')
    expect(page.get_by_role('heading', level=1)).to_have_text('Pride näkyväksi')
    expect(page.locator('.pride-map-fallback')).to_be_visible()
    expect(page.locator('.demo-card')).to_have_count(2)
    expect(page.locator('#demo-guidelines')).to_be_visible()


@pytest.mark.e2e
@pytest.mark.integration
def test_tile_delivery_failure_has_its_own_warning_without_losing_event_markers(client, db, seeded_data, live_server, browser_page):
    pride_events(db, seeded_data, count=1)
    page = browser_page
    # The technical browser fixture deliberately blocks external OSM tile requests.
    page.goto(live_server + '/pride-nakyvaksi', wait_until='networkidle')
    expect(page.locator('#pride-map-summary')).to_have_attribute('data-event-count', '1')
    expect(page.locator('.pride-map-tile-warning')).to_be_visible()
    expect(page.locator('#pride-map path.leaflet-interactive')).to_have_count(1)
    expect(page.locator('#pride-map-error')).to_be_hidden()
    expect(page.locator('.demo-card')).to_have_count(1)


@pytest.mark.e2e
@pytest.mark.integration
def test_map_loading_avoids_fake_counts_and_double_retry_requests(client, db, seeded_data, live_server, browser_page):
    pride_events(db, seeded_data, count=1)
    page = browser_page
    pending = []

    def wait_for_pending(count):
        for _ in range(100):
            if len(pending) >= count:
                break
            page.wait_for_timeout(50)
        assert len(pending) == count

    def serve(route):
        if is_map_request(route.request):
            pending.append(route)
        else:
            route.continue_()

    page.route('**/api/demonstrations?*', serve)
    page.goto(live_server + '/pride-nakyvaksi', wait_until='domcontentloaded')
    expect(page.locator('.demo-card')).to_have_count(1)
    summary = page.locator('#pride-map-summary')
    assert summary.get_attribute('data-event-count') is None
    expect(page.locator('#pride-map-error')).to_be_hidden()
    expect(page.locator('#pride-map-empty')).to_be_hidden()
    wait_for_pending(1)
    pending[0].fulfill(status=503, content_type='application/json', body='{"error":"Temporary outage"}')
    expect(page.locator('#pride-map-error')).to_be_visible()
    page.evaluate("() => {const button=document.querySelector('#pride-map-retry');button.click();button.click();}")
    expect(page.locator('#pride-map-retry')).to_be_disabled()
    wait_for_pending(2)
    pending[1].fulfill(content_type='application/json', body=json.dumps(map_payload([
        {'_id': '000000000000000000000001', 'title': 'Retried event', 'date': '2099-01-01',
         'latitude': '60.1699', 'longitude': '24.9384', 'city': 'Helsinki'}
    ])))
    expect(summary).to_have_attribute('data-event-count', '1')
    expect(page.locator('#pride-map-error')).to_be_hidden()
    assert len(pending) == 2


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('failure', ['wrong-page', 'missing-id'])
def test_map_rejects_inconsistent_pagination_instead_of_showing_partial_totals(client, db, seeded_data, live_server, browser_page, failure):
    pride_events(db, seeded_data, count=1)
    page = browser_page
    requests = []
    rows = [{'_id': f'{index + 1:024x}', 'title': f'Pride {index}', 'date': '2099-01-01',
             'city': 'Helsinki', 'latitude': 60.1699, 'longitude': 24.9384}
            for index in range(105)]

    def serve(route):
        if not is_map_request(route.request):
            return route.continue_()
        query = parse_qs(urlsplit(route.request.url).query)
        requests.append(query)
        page_number = int(query['page'][0])
        body = map_payload(rows[:100] if page_number == 1 else rows[100:],
                           page=page_number, total=105, total_pages=2)
        if page_number == 2:
            if failure == 'wrong-page':
                body['page'] = 1
            else:
                del body['results'][0]['_id']
        route.fulfill(content_type='application/json', body=json.dumps(body))

    page.route('**/api/demonstrations?*', serve)
    page.goto(live_server + '/pride-nakyvaksi', wait_until='networkidle')
    expect(page.locator('#pride-map-error')).to_be_visible()
    expect(page.locator('#pride-map-retry')).to_be_enabled()
    expect(page.locator('#pride-map-empty')).to_be_hidden()
    assert page.locator('#pride-map-summary').get_attribute('data-event-count') is None
    expect(page.locator('.demo-card')).to_have_count(1)
    assert [query['page'] for query in requests] == [['1'], ['2']]


@pytest.mark.e2e
@pytest.mark.integration
def test_map_counts_unique_events_and_normalizes_city_names(client, db, seeded_data, live_server, browser_page):
    pride_events(db, seeded_data, count=1)
    page = browser_page
    rows = [
        {'_id': '000000000000000000000001', 'title': 'First event', 'city': ' Helsinki ',
         'latitude': '60.1699', 'longitude': '24.9384'},
        {'_id': '000000000000000000000001', 'title': 'Duplicate event', 'city': 'Extra city',
         'latitude': None, 'longitude': None},
        {'_id': '000000000000000000000002', 'title': 'Second event', 'city': 'helsinki',
         'latitude': None, 'longitude': None},
        {'_id': '000000000000000000000003', 'title': 'Third event', 'city': '   ',
         'latitude': '60.4518', 'longitude': '22.2666'},
    ]

    def serve(route):
        if is_map_request(route.request):
            route.fulfill(content_type='application/json', body=json.dumps(map_payload(rows)))
        else:
            route.continue_()

    page.route('**/api/demonstrations?*', serve)
    page.goto(live_server + '/pride-nakyvaksi', wait_until='networkidle')
    summary = page.locator('#pride-map-summary')
    expect(summary).to_have_attribute('data-event-count', '3')
    expect(summary).to_have_attribute('data-city-count', '1')
    expect(summary).to_have_attribute('data-mapped-count', '2')
    expect(page.locator('#pride-map path.leaflet-interactive')).to_have_count(2)
    expect(page.locator('#pride-map-error')).to_be_hidden()


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('later_page_count', [1, 999999])
def test_map_traversal_uses_first_page_bound_when_live_totals_change(client, db, seeded_data, live_server, browser_page, later_page_count):
    pride_events(db, seeded_data, count=1)
    page = browser_page
    requests = []
    rows = [{'_id': f'{index + 1:024x}', 'title': f'Pride {index}', 'date': '2099-01-01',
             'city': 'Helsinki', 'latitude': 60.1699, 'longitude': 24.9384}
            for index in range(105)]

    def serve(route):
        if not is_map_request(route.request):
            return route.continue_()
        query = parse_qs(urlsplit(route.request.url).query)
        requests.append(query)
        page_number = int(query['page'][0])
        body = map_payload(rows[:100] if page_number == 1 else rows[100:],
                           page=page_number, total=105,
                           total_pages=2 if page_number == 1 else later_page_count)
        route.fulfill(content_type='application/json', body=json.dumps(body))

    page.route('**/api/demonstrations?*', serve)
    page.goto(live_server + '/pride-nakyvaksi', wait_until='networkidle')
    expect(page.locator('#pride-map-summary')).to_have_attribute('data-event-count', '105')
    expect(page.locator('#pride-map-summary')).to_have_attribute('data-mapped-count', '105')
    expect(page.locator('#pride-map-error')).to_be_hidden()
    assert [query['page'] for query in requests] == [['1'], ['2']]
