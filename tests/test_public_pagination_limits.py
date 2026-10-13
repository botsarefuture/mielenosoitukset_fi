"""Server-side resource bounds, exercised only with disposable local data."""
from copy import deepcopy
from datetime import date, timedelta
from bson import ObjectId
from flask import template_rendered
import pytest

from mielenosoitukset_fi.utils.public_pagination import PUBLIC_MAX_PER_PAGE, public_page_args


@pytest.mark.parametrize('raw,expected', [
    ('600000', 100), ('999999999999999999999999999999', 100),
    ('100', 100), ('101', 100), ('0', 1), ('-600000', 1),
    ('bad', 20), ('', 20), (None, 20),
])
def test_public_page_size_is_bounded_and_existing_defaults_survive(raw, expected):
    assert public_page_args({'page': '2', 'per_page': raw}) == (2, expected)
    assert public_page_args({}, default_per_page=10) == (1, 10)
    assert PUBLIC_MAX_PER_PAGE == 100


def _many_demos(db, seeded_data):
    original = db.demonstrations.find_one({'_id': seeded_data['demo_id']})
    records = []
    for index in range(105):
        record = deepcopy(original)
        record.update(_id=ObjectId(), title=f'Bounded demo {index}', approved=True,
            hide=False, rejected=False, date=(date.today() + timedelta(days=7)).isoformat(),
            tags=['pagination-limits'])
        records.append(record)
    db.demonstrations.insert_many(records)


@pytest.mark.parametrize('endpoint,key', [
    ('/api/demonstrations', 'results'), ('/api/v1/demonstrations', 'demonstrations'),
])
def test_demo_apis_cap_the_real_query_and_return_bounded_metadata(client, db, seeded_data, endpoint, key):
    _many_demos(db, seeded_data)
    response = client.get(endpoint, query_string={'tag': 'pagination-limits', 'per_page': '600000'})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['per_page'] == 100 and len(payload[key]) == 100
    assert payload['total'] == 105 and payload['total_pages'] == 2
    assert (payload['result_start'], payload['result_end']) == (1, 100)
    if key == 'results':
        assert 'per_page=100' in payload['next_url']
    second = client.get(endpoint, query_string={'tag': 'pagination-limits', 'per_page': '600000', 'page': '2'}).get_json()
    assert len(second[key]) == 5 and second['result_start'] == 101
    assert not ({row['_id'] for row in payload[key]} & {row['_id'] for row in second[key]})


def test_tag_page_materializes_only_the_bounded_page(app, client, db, seeded_data):
    _many_demos(db, seeded_data)
    observed = []
    def capture(_sender, template, context, **_kwargs):
        if template.name == 'tag_list.html':
            observed.append(context)
    template_rendered.connect(capture, app, weak=False)
    try:
        response = client.get('/tag/pagination-limits?tag=pagination-limits&per_page=600000&page=1')
    finally:
        template_rendered.disconnect(capture, app)
    assert response.status_code == 200
    assert len(observed) == 1
    assert len(observed[0]['demonstrations']) == 100
    assert observed[0]['total_pages'] == 2


def test_public_organization_api_cannot_bypass_page_size_limit(client, db):
    db.organizations.insert_many([
        {'_id': ObjectId(), 'name': f'Pagination limit org {index:03}', 'verified': False}
        for index in range(105)
    ])
    response = client.get('/api/v1/organizations?search=Pagination+limit+org&per_page=600000')
    assert response.status_code == 200
    assert len(response.json['organizations']) == 100 and response.json['total_pages'] == 2
    second = client.get('/api/v1/organizations?search=Pagination+limit+org&per_page=600000&page=2')
    assert len(second.json['organizations']) == 5


@pytest.mark.parametrize('endpoint,key', [
    ('/api/demonstrations', 'results'), ('/api/v1/demonstrations', 'demonstrations'),
    ('/api/v1/organizations', 'organizations'), ('/tag/pagination-limits', None),
])
def test_enormous_out_of_range_pages_never_reach_database_skip(client, db, seeded_data, monkeypatch, endpoint, key):
    _many_demos(db, seeded_data)
    db.organizations.insert_one({'name': 'Pagination limit org', 'verified': False})
    cursor_type = type(db.demonstrations.find({}))
    def forbidden_skip(_cursor, _amount):
        raise AssertionError('Out-of-range page attempted a database scan')
    monkeypatch.setattr(cursor_type, 'skip', forbidden_skip)
    response = client.get(endpoint, query_string={'page': '9' * 100, 'per_page': '600000', 'tag': 'pagination-limits'})
    assert response.status_code == 200
    if key:
        assert response.json[key] == []
        if key != 'organizations':
            assert response.json['result_start'] == response.json['result_end'] == 0


def test_public_cache_normalizes_page_sizes_and_excludes_old_unbounded_namespace(app):
    from mielenosoitukset_fi.api.routes import make_cache_key
    with app.test_request_context('/api/demonstrations?tag=test&per_page=600000'):
        excessive = make_cache_key()
    with app.test_request_context('/api/demonstrations?tag=test&per_page=100&page=1'):
        normalized = make_cache_key()
    assert excessive == normalized
    assert excessive.startswith('demonstrations:page-v3:')
    # Resolved request/session language affects localized output even when
    # the URL has no explicit lang parameter.
    with app.test_request_context('/api/demonstrations?per_page=101'):
        finnish = make_cache_key('fi')
    with app.test_request_context('/api/demonstrations?per_page=100'):
        english = make_cache_key('en')
        assert finnish != english
        assert english == make_cache_key('en')


def test_old_oversized_cached_response_cannot_bypass_the_new_limit(client, db, seeded_data, monkeypatch):
    import hashlib
    import json
    _many_demos(db, seeded_data)
    raw = {'tag': 'pagination-limits', 'per_page': '600000'}
    old_key = 'demonstrations:page-v2:' + hashlib.md5(json.dumps(raw, sort_keys=True).encode()).hexdigest()
    requested_keys = []
    class LegacyCache:
        def get(self, key):
            requested_keys.append(key)
            if key == old_key:
                return {'per_page': 600000, 'results': [{'title': 'Oversized legacy cache'}]}
            return None
        def set(self, key, value):
            assert value['per_page'] == 100 and len(value['results']) == 100
    # The application registers the legacy `api.routes` import path. Patch the
    # actual registered view globals, not a second package-qualified module.
    endpoint = next(rule.endpoint for rule in client.application.url_map.iter_rules()
                    if rule.rule == '/api/demonstrations')
    view_globals = client.application.view_functions[endpoint].__globals__
    monkeypatch.setitem(view_globals, 'cache', LegacyCache())
    monkeypatch.setitem(view_globals, 'should_skip_cache', lambda **_kwargs: False)
    # Baseline fixtures publish Finnish only; enable both locales for this
    # actual selector/session isolation test, without mocking get_locale.
    monkeypatch.setitem(client.application.config, 'BABEL_PUBLIC_LOCALES', ['fi', 'en'])
    with client.session_transaction() as state:
        state['locale'] = 'fi'
    response = client.get('/api/demonstrations', query_string=raw)
    assert response.status_code == 200
    assert response.json['per_page'] == 100 and len(response.json['results']) == 100
    assert old_key not in requested_keys
    first_language_key = requested_keys[-1]
    with client.session_transaction() as state:
        state['locale'] = 'en'
    localized = client.get('/api/demonstrations', query_string=raw)
    assert localized.status_code == 200
    assert requested_keys[-1] != first_language_key
