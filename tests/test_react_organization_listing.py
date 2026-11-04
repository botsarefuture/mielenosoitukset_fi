"""Organization listings retain their public scope and shared React behavior."""
from copy import deepcopy
from datetime import date, timedelta
from html.parser import HTMLParser
import json
from urllib.parse import parse_qs, urlsplit

from bson import ObjectId
import pytest
from playwright.sync_api import expect


class ListingConfig(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.parts = []
        self.headings = []
        self.legacy_renderer = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'script':
            self.capture = values.get('id') == 'demonstration-listing-props'
            self.legacy_renderer |= 'demo-card-render.js' in values.get('src', '')
        if tag in {'h1', 'h2'}:
            self.headings.append((tag, values.get('id'), values.get('class', '')))

    def handle_data(self, value):
        if self.capture:
            self.parts.append(value)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.capture = False

    @property
    def props(self):
        return json.loads(''.join(self.parts))


def organization_events(db, seeded_data):
    """Seed public scoped records plus foreign and moderated records to exclude."""
    prototype = db.demonstrations.find_one({'_id': seeded_data['demo_id']})
    foreign_org = db.organizations.find_one({'verified': True})['_id']
    db.demonstrations.delete_many({})
    db.recurring_demonstrations.delete_many({})
    rows = []
    for index in range(25):
        row = deepcopy(prototype)
        event_date = date.today() + timedelta(days=120 if index == 24 else index + 5)
        row.update(
            _id=ObjectId(), title=f'Owned Event {index:02d}',
            date=event_date.isoformat(), formatted_date=event_date.strftime('%d.%m.%Y'),
            organizers=[{'name': 'Test Organization', 'organization_id': seeded_data['org_id']}],
            approved=True, hide=False, rejected=False, cancelled=index == 1,
            tags=['organization-scope'], parent=None,
            running_number=8100 + index, slug=f'owned-event-{index}',
            start_time='12:00', end_time='14:00',
            preview_image='', cover_picture='', cover_image='', img='',
        )
        if index == 2:
            row['end_time'] = None
        elif index == 3:
            row['start_time'] = None
        elif index == 4:
            row['start_time'] = row['end_time'] = None
        rows.append(row)
    excluded = []
    for label, changes in (
        ('Foreign', {'organizers': [{'name': 'Other Organization', 'organization_id': foreign_org}]}),
        ('Hidden', {'hide': True}),
        ('Unapproved', {'approved': False}),
        ('Rejected', {'rejected': True}),
        ('Past', {'date': (date.today() - timedelta(days=1)).isoformat(), 'in_past': True}),
    ):
        record = deepcopy(rows[0])
        record.update(_id=ObjectId(), title=f'{label} Event', **changes)
        excluded.append(record)
    db.demonstrations.insert_many(rows + excluded)
    return rows, excluded, foreign_org


def test_organization_listing_reuses_shared_shell_without_replacing_profile(client, db, seeded_data):
    db.organizations.update_one({'_id': seeded_data['org_id']}, {'$set': {'website': ''}})
    response = client.get(f'/organization/{seeded_data["org_id"]}')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    page = ListingConfig()
    page.feed(html)
    assert page.props['fixed'] == {'organization_id': str(seeded_data['org_id'])}
    assert page.props['headingLevel'] == 2
    assert page.props['title'] == 'Mielenosoitukset'
    assert len([heading for heading in page.headings if heading[0] == 'h1']) == 1
    assert any(tag == 'h2' and heading_id == 'listing-title' for tag, heading_id, _ in page.headings)
    assert not page.legacy_renderer
    assert "/static/css/list.css" not in html
    assert 'Test Organization' in html
    assert 'Primary organization used in smoke tests.' in html
    assert 'id="org-follow-btn"' not in html
    assert 'id="toolbox-sidebar"' not in html
    assert f'/organization/{seeded_data["org_id"]}/fill' in html


def test_organization_follow_permissions_and_verified_profile_survive(client, user_client, admin_client, db, seeded_data):
    org_id = seeded_data['org_id']
    authenticated = user_client.get(f'/organization/{org_id}').get_data(as_text=True)
    assert 'id="org-follow-btn"' in authenticated
    assert 'data-following="1"' in authenticated
    assert 'aria-pressed="true"' in authenticated
    assert 'id="toolbox-sidebar"' in authenticated
    assert 'id="toolbox-sidebar"' in admin_client.get(f'/organization/{org_id}').get_data(as_text=True)
    verified_id = db.organizations.find_one({'verified': True})['_id']
    verified = client.get(f'/organization/{verified_id}').get_data(as_text=True)
    assert 'Verified Test Organization' in verified
    assert f'/organization/{verified_id}/fill' not in verified
    assert 'id="toolbox-sidebar"' not in user_client.get(f'/organization/{verified_id}').get_data(as_text=True)


@pytest.mark.parametrize('org_id', ['not-an-id', '0' * 23, 'z' * 24])
def test_malformed_organization_id_is_not_an_unscoped_listing(client, org_id):
    assert client.get('/organization/' + org_id).status_code == 404


def test_unknown_well_formed_organization_keeps_existing_redirect(client):
    response = client.get('/organization/' + str(ObjectId()))
    assert response.status_code == 302
    assert urlsplit(response.location).path == '/'


def test_actual_api_org_scope_preserves_cancelled_nullable_and_distant_events(client, db, seeded_data):
    rows, excluded, _ = organization_events(db, seeded_data)
    org_id = str(seeded_data['org_id'])
    results = []
    for page_number in (1, 2, 3):
        response = client.get(f'/api/demonstrations?organization_id={org_id}&page={page_number}&per_page=12')
        assert response.status_code == 200
        assert response.json['total'] == 25
        assert response.json['total_pages'] == 3
        results.extend(response.json['results'])
    assert [row['_id'] for row in results] == [str(row['_id']) for row in rows]
    assert not {str(row['_id']) for row in excluded}.intersection(row['_id'] for row in results)
    assert results[1]['cancelled'] is True
    assert results[2]['end_time'] is None
    assert results[3]['start_time'] is None
    assert results[4]['start_time'] is None and results[4]['end_time'] is None
    assert results[-1]['date'] == (date.today() + timedelta(days=120)).isoformat()


def use_manual_pagination(page):
    page.add_init_script("Object.defineProperty(navigator, 'connection', {value: {saveData: true}})")


def card_ids(page):
    return page.locator('.demo-card').evaluate_all('cards => cards.map(card => card.dataset.demoId)')


def assert_fixed_queries(requests, org_id):
    assert requests
    for query in requests:
        assert query['organization_id'] == [str(org_id)]
        assert 'parent_id' not in query
        assert 'max_days_till' not in query
        assert 'in_past' not in query


@pytest.mark.e2e
@pytest.mark.integration
def test_org_listing_real_pagination_and_retry_keep_scope_and_rendered_cards(client, db, seeded_data, live_server, browser_page):
    rows, _, foreign_org = organization_events(db, seeded_data)
    page = browser_page
    use_manual_pagination(page)
    requested = []
    attempts = {}
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def scoped_request(route):
        query = parse_qs(urlsplit(route.request.url).query)
        requested.append(query)
        number = int(query['page'][0])
        attempts[number] = attempts.get(number, 0) + 1
        if number in {1, 2} and attempts[number] == 1:
            route.fulfill(status=503, content_type='application/json', body='{"error":"Temporary outage"}')
        else:
            route.continue_()

    page.route('**/api/demonstrations?*', scoped_request)
    page.goto(f'{live_server}/organization/{seeded_data["org_id"]}?organization_id={foreign_org}&parent_id={foreign_org}&max_days_till=60', wait_until='domcontentloaded')
    expect(page.locator('#listing-load-error')).to_be_visible()
    assert page.locator('.public-search-submit').evaluate("e => getComputedStyle(e).backgroundColor") == 'rgb(255, 102, 0)'
    expect(page.locator('.demo-card')).to_have_count(0)
    expect(page.locator('#listing-result-summary')).to_be_hidden()
    page.locator('#listing-load-error button').click()
    expect(page.locator('.demo-card')).to_have_count(12)
    assert card_ids(page) == [str(row['_id']) for row in rows[:12]]
    expect(page.locator('.cancelled-badge')).to_have_text('Peruttu')
    expect(page.locator(f'[data-demo-id="{rows[4]["_id"]}"] .demo-card-time')).to_have_count(0)
    page.locator('#load-more-btn').click()
    expect(page.locator('#listing-load-error')).to_be_visible()
    assert card_ids(page) == [str(row['_id']) for row in rows[:12]]
    assert parse_qs(urlsplit(page.url).query)['page'] == ['1']
    page.locator('#listing-load-error button').click()
    expect(page.locator('.demo-card')).to_have_count(24)
    assert card_ids(page) == [str(row['_id']) for row in rows[:24]]
    page.locator('#load-more-btn').click()
    expect(page.locator('.demo-card')).to_have_count(25)
    expect(page.locator('#load-more-btn')).to_be_hidden()
    expect(page.locator('.demo-card-title a').last).to_have_text('Owned Event 24')
    assert_fixed_queries(requested, seeded_data['org_id'])
    assert parse_qs(urlsplit(page.url).query)['organization_id'] == [str(seeded_data['org_id'])]
    assert errors == []


@pytest.mark.e2e
@pytest.mark.integration
def test_org_search_clear_and_history_never_switch_organization(client, db, seeded_data, live_server, browser_page):
    rows, _, foreign_org = organization_events(db, seeded_data)
    page = browser_page
    use_manual_pagination(page)
    requested = []
    page.on('request', lambda request: requested.append(parse_qs(urlsplit(request.url).query))
            if urlsplit(request.url).path == '/api/demonstrations' else None)
    page.goto(f'{live_server}/organization/{seeded_data["org_id"]}?organization_id={foreign_org}', wait_until='domcontentloaded')
    expect(page.locator('.demo-card')).to_have_count(12)
    page.locator('#demo-search').fill('Owned Event 24')
    page.locator('#search-form').get_by_role('button', name='Hae', exact=True).click()
    expect(page.locator('.demo-card-title a')).to_have_text('Owned Event 24')
    assert card_ids(page) == [str(rows[24]['_id'])]
    page.locator('#demo-search').fill('no-matches')
    page.locator('#search-form').get_by_role('button', name='Hae', exact=True).click()
    expect(page.locator('#no-results')).to_be_visible()
    expect(page.locator('.demo-card')).to_have_count(0)
    page.locator('#clear-filters-btn').click()
    expect(page.locator('.demo-card')).to_have_count(12)
    page.go_back()
    expect(page.locator('#no-results')).to_be_visible()
    expect(page.locator('#demo-search')).to_have_value('no-matches')
    page.go_back()
    expect(page.locator('.demo-card-title a')).to_have_text('Owned Event 24')
    page.evaluate("""foreign => {
      const query = new URLSearchParams({organization_id: foreign, search: 'Owned Event 00'});
      history.pushState({}, '', '?' + query);
      dispatchEvent(new PopStateEvent('popstate'));
    }""", str(foreign_org))
    expect(page.locator('.demo-card-title a')).to_have_text('Owned Event 00')
    assert card_ids(page) == [str(rows[0]['_id'])]
    assert_fixed_queries(requested, seeded_data['org_id'])
    assert parse_qs(urlsplit(page.url).query)['organization_id'] == [str(seeded_data['org_id'])]


@pytest.mark.parametrize('locale,title,message', [
    ('en', 'No upcoming demonstrations', 'This organizer has not announced any upcoming demonstrations yet.'),
    ('sv', 'Inga kommande demonstrationer', 'Den här arrangören har ännu inte anmält några kommande demonstrationer.'),
])
def test_organization_empty_state_uses_compiled_public_translations(app, client, seeded_data, locale, title, message):
    app.config['BABEL_PUBLIC_LOCALES'] = ['fi', 'en', 'sv']
    with client.session_transaction() as session:
        session['locale'] = locale
    response = client.get(f'/organization/{seeded_data["org_id"]}')
    assert response.status_code == 200
    page = ListingConfig()
    page.feed(response.get_data(as_text=True))
    assert page.props['messages']['emptyTitle'] == title
    assert page.props['messages']['empty'] == message
