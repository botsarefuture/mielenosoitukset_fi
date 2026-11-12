"""The admin publication button is the only anonymous-access opt-in."""

import re

import pytest
from pymongo.errors import ConnectionFailure


def _token(client):
    response = client.get('/admin/kampanja/')
    assert response.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))[1]


def _publish(client, action='publish', token=None):
    return client.post('/admin/kampanja/publication', data={
        'publication': action, 'csrf_token': token or _token(client),
    })


@pytest.mark.parametrize('path', ['/keräys', '/kampanja/'])
def test_unpublished_pages_require_login_and_allow_any_logged_in_preview(client, user_client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert '/login' in response.location and 'next=' in response.location
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'
    preview = user_client.get(path)
    assert preview.status_code == 200
    assert preview.headers['Cache-Control'] == 'private, no-store'
    assert preview.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert 'Cookie' in preview.vary


def test_signup_cannot_bypass_unpublished_page_gate(client, user_client, db):
    payload = {'name': 'Example', 'email': 'example@example.test'}
    before = db.volunteers.count_documents({})
    denied = client.post('/kampanja/api/volunteers', json=payload)
    assert denied.status_code == 401
    assert denied.get_json()['success'] is False
    assert db.volunteers.count_documents({}) == before
    assert user_client.post('/kampanja/api/volunteers', json=payload).status_code == 201


def test_admin_can_publish_and_withdraw_without_opening_donations(admin_client, client, db, seeded_data):
    assert _publish(admin_client).status_code == 303
    state = db.campaign_settings.find_one({'_id': 'public_pages'})
    assert state['published'] is True
    assert state['updated_by'] == str(seeded_data['admin_id'])
    assert state['updated_at']
    for path in ['/keräys', '/kampanja/']:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'private, no-store'
        assert 'X-Robots-Tag' not in response.headers
    page = client.get('/keräys').get_data(as_text=True)
    assert 'Lahjoittaminen ei ole vielä avoinna' in page
    assert client.post('/kampanja/api/volunteers', json={
        'name': 'Public Example', 'email': 'public@example.test',
    }).status_code == 201
    assert _publish(admin_client, 'private').status_code == 303
    assert client.get('/keräys').status_code == 302
    assert client.get('/kampanja/').status_code == 302
    events = list(db.admin_logs.find({'action': 'campaign_publication_changed'}))
    assert [event['published'] for event in events] == [True, False]


@pytest.mark.parametrize('csrf', ['', 'forged', 'väärä'])
def test_publication_requires_session_bound_csrf(admin_client, db, csrf):
    _token(admin_client)
    response = admin_client.post('/admin/kampanja/publication', data={
        'publication': 'publish', 'csrf_token': csrf,
    })
    assert response.status_code == 400
    assert db.campaign_settings.find_one({'_id': 'public_pages'}) is None


def test_publication_rejects_foreign_session_token_and_get(admin_client, app, seeded_data, db):
    token = _token(admin_client)
    other = app.test_client()
    with other.session_transaction() as session:
        session['_user_id'] = str(seeded_data['admin_id'])
        session['_fresh'] = True
    assert _publish(other, token=token).status_code == 400
    assert admin_client.get('/admin/kampanja/publication').status_code == 405
    assert db.campaign_settings.find_one({'_id': 'public_pages'}) is None


def test_ordinary_and_scoped_users_cannot_publish(user_client, admin_client, app, seeded_data, db):
    token = _token(user_client) if user_client.get('/admin/kampanja/').status_code == 200 else 'forged'
    assert _publish(user_client, token=token).status_code == 403
    # Permission to view a scoped admin surface is not global publishing authority.
    db.users.update_one({'_id': seeded_data['user_id']}, {'$set': {
        'role': 'admin', 'global_admin': False, 'global_permissions': [],
    }})
    scoped = app.test_client()
    with scoped.session_transaction() as session:
        session['_user_id'] = str(seeded_data['user_id'])
        session['campaign_publication_csrf'] = 'scoped-session-token'
    db.memberships.update_one(
        {'user_id': seeded_data['user_id']}, {'$addToSet': {'permissions': 'KAMPANJA'}}
    )
    page = scoped.get('/admin/kampanja/')
    assert page.status_code == 200
    assert 'name="publication"' not in page.get_data(as_text=True)
    assert _publish(scoped, token='scoped-session-token').status_code == 403
    assert db.campaign_settings.find_one({'_id': 'public_pages'}) is None


def test_publication_fails_closed_on_non_boolean_state_and_database_failure(client, db, monkeypatch):
    db.campaign_settings.insert_one({'_id': 'public_pages', 'published': 'true'})
    assert client.get('/keräys').status_code == 302
    collection = type(db.campaign_settings)
    original = collection.find_one

    def fail_settings(self, *args, **kwargs):
        if self.name == 'campaign_settings':
            raise ConnectionFailure('Synthetic test outage')
        return original(self, *args, **kwargs)

    monkeypatch.setattr(collection, 'find_one', fail_settings)
    assert client.get('/keräys').status_code == 302
    assert client.get('/kampanja/').status_code == 302


def test_private_discovery_and_public_sitemap_follow_publication(admin_client, client, monkeypatch):
    from mielenosoitukset_fi.utils.fundraising import fundraising_details
    globals_ = client.application.view_functions['fundraising'].__wrapped__.__globals__
    monkeypatch.setitem(globals_, 'fundraising_details', lambda: fundraising_details({'show_header_link': True}))
    assert 'class="fundraising-header-link"' not in client.get('/info').get_data(as_text=True)
    assert 'class="fundraising-header-link"' in admin_client.get('/info').get_data(as_text=True)
    sitemap = client.get('/sitemap.xml').get_data(as_text=True)
    assert '/kampanja/' not in sitemap and '/ker%C3%A4ys' not in sitemap
    assert _publish(admin_client).status_code == 303
    assert 'class="fundraising-header-link"' in client.get('/info').get_data(as_text=True)
    sitemap = client.get('/sitemap.xml').get_data(as_text=True)
    assert '/kampanja/' in sitemap and '/ker%C3%A4ys' in sitemap
    assert _publish(admin_client, 'private').status_code == 303
    assert '/kampanja/' not in client.get('/sitemap.xml').get_data(as_text=True)


def test_existing_confirmation_tokens_keep_working_while_private(user_client, client, db):
    assert user_client.post('/kampanja/api/volunteers', json={
        'name': 'Preview', 'email': 'preview@example.test',
    }).status_code == 201
    volunteer = db.volunteers.find_one({'email': 'preview@example.test'})
    response = client.get('/kampanja/confirm/' + volunteer['confirmation_token'])
    assert response.status_code == 200
    assert db.volunteers.find_one({'_id': volunteer['_id']})['confirmed'] is True


def test_publication_write_error_does_not_report_success(admin_client, db, monkeypatch):
    token = _token(admin_client)
    original = type(db.campaign_settings).update_one

    def fail_settings(self, *args, **kwargs):
        if self.name == 'campaign_settings':
            raise ConnectionFailure('Synthetic write failure')
        return original(self, *args, **kwargs)

    monkeypatch.setattr(type(db.campaign_settings), 'update_one', fail_settings)
    response = _publish(admin_client, token=token)
    assert response.status_code == 303
    page = admin_client.get(response.location).get_data(as_text=True)
    assert 'Tallennusta ei voitu varmistaa' in page
    assert 'Kampanja- ja keräyssivut on julkaistu kaikille.' not in page
    assert db.campaign_settings.find_one({'_id': 'public_pages'}) is None
