"""The React route emits metadata promptly without hydrating the legacy model."""
import json
import re
from datetime import date, timedelta

import pytest
from bson import ObjectId

from mielenosoitukset_fi.utils.classes import Demonstration


@pytest.fixture
def public_detail(app, db):
    app.config['PUBLIC_DETAIL_REACT_ENABLED'] = True
    app.config['PUBLIC_DEMONSTRATION_API_URL'] = 'http://127.0.0.1:8091/api/demonstrations'
    record = {
        '_id': ObjectId(), 'title': 'React detail fixture',
        'description': '<p>Public description</p>', 'date': date.today().isoformat(),
        'start_time': '17:00', 'end_time': None, 'city': 'Helsinki', 'address': 'Test square',
        'approved': True, 'hide': False, 'rejected': False, 'cancelled': False,
        'slug': 'react-detail-fixture', 'running_number': 987654321,
        'latitude': '60.17', 'longitude': '24.94', 'organizers': [],
        'submitter_email': 'private@example.test', 'moderation': {'token': 'private-token'},
        'translations': {'en': {'title': 'English title'}},
    }
    db.demonstrations.insert_one(record)
    return record


def props_from(response):
    match = re.search(r'<script type="application/json" id="demonstration-detail-props">(.*?)</script>', response.text, re.S)
    assert match
    return json.loads(match.group(1))


def test_shell_uses_only_metadata_and_no_legacy_model(client, app, public_detail, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('React shell must not construct the legacy model')
    monkeypatch.setattr(Demonstration, 'load_by_id', forbidden)
    response = client.get(f"/demonstration/{public_detail['_id']}")
    assert response.status_code == 200
    assert response.headers['X-Detail-Renderer'] == 'react'
    props = props_from(response)
    assert props['id'] == str(public_detail['_id'])
    assert props['endpoint'] == app.config['PUBLIC_DEMONSTRATION_API_URL']
    assert 'title' not in props and 'description' not in props
    assert '__EVENT_ID__' in props['urls']['calendar']
    assert 'legacyUrl' not in props
    assert '<noscript>' in response.text and 'application/ld+json' in response.text
    assert 'private@example.test' not in response.text and 'private-token' not in response.text
    assert '<link rel="canonical" href="http://localhost/demonstration/react-detail-fixture">' in response.text


@pytest.mark.parametrize('identifier', ['slug', 'running_number'])
def test_existing_identifiers_resolve_to_api_object_id(client, public_detail, identifier):
    response = client.get(f"/demonstration/{public_detail[identifier]}")
    assert response.status_code == 200
    assert props_from(response)['id'] == str(public_detail['_id'])


def test_alias_and_hidden_original_precedence(client, db, public_detail):
    alias = ObjectId()
    db.demonstrations.update_one({'_id': public_detail['_id']}, {'$set': {'aliases': [alias]}})
    assert props_from(client.get(f'/demonstration/{alias}'))['id'] == str(public_detail['_id'])
    db.demonstrations.insert_one({'_id': alias, 'approved': False})
    assert client.get(f'/demonstration/{alias}').status_code == 404


@pytest.mark.parametrize('update', [
    {'approved': False}, {'hide': True}, {'rejected': True}, {'hide': None},
    {'approved': [True]}, {'rejected': [False]},
])
def test_shell_never_includes_nonpublic_metadata(client, db, public_detail, update):
    db.demonstrations.update_one({'_id': public_detail['_id']}, {'$set': update})
    response = client.get(f"/demonstration/{public_detail['_id']}")
    assert response.status_code == 404
    assert 'React detail fixture' not in response.text


def test_cancelled_public_event_stays_readable(client, db, public_detail):
    db.demonstrations.update_one({'_id': public_detail['_id']}, {'$set': {'cancelled': True}})
    assert client.get(f"/demonstration/{public_detail['_id']}").status_code == 200


def test_series_redirect_and_selected_occurrence_preserved(client, db, public_detail):
    parent = ObjectId()
    db.recu_demos.insert_one({'_id': parent, 'approved': True, 'hide': False, 'rejected': False, 'title': 'Public series'})
    db.demonstrations.update_one({'_id': public_detail['_id']}, {'$set': {'parent': parent}})
    response = client.get(f"/demonstration/{public_detail['_id']}")
    assert response.status_code == 301
    assert f'/demonstration/{parent}/children?occurrence=react-detail-fixture' in response.location
    selected = client.get(response.location)
    assert selected.status_code == 200
    props = props_from(selected)
    assert props['id'] == str(public_detail['_id'])
    assert any(row['id'] == props['id'] for row in props['series']['occurrences'])


def test_missing_event_returns_404_and_far_future_noindex(client, db, public_detail):
    assert client.get(f'/demonstration/{ObjectId()}').status_code == 404
    db.demonstrations.update_one({'_id': public_detail['_id']}, {'$set': {'date': (date.today() + timedelta(days=900)).isoformat()}})
    response = client.get(f"/demonstration/{public_detail['_id']}")
    assert response.headers['X-Robots-Tag'] == 'noindex, follow'


def test_old_layout_parameters_do_not_create_another_public_view(client, public_detail):
    client.set_cookie('demo_detail_layout', 'classic')
    response = client.get(f"/demonstration/{public_detail['_id']}?legacy=1&detail_layout=classic")
    assert response.status_code == 200
    assert response.headers['X-Detail-Renderer'] == 'react'
    assert 'detail-layout-preference' not in response.text


def test_signed_in_users_share_the_same_react_view(user_client, public_detail):
    response = user_client.get(f"/demonstration/{public_detail['_id']}")
    assert response.status_code == 200
    assert response.headers['X-Detail-Renderer'] == 'react'
    props = props_from(response)
    assert props['authenticated'] is True
    assert '__EVENT_ID__' in props['urls']['invite']


def test_past_and_cancelled_series_choices_are_not_lost(client, db, public_detail):
    parent = ObjectId()
    db.recu_demos.insert_one({'_id': parent, 'approved': True, 'title': 'Series'})
    db.demonstrations.update_one({'_id': public_detail['_id']}, {'$set': {'parent': parent}})
    past = {**public_detail, '_id': ObjectId(), 'parent': parent, 'date': (date.today() - timedelta(days=2)).isoformat(), 'slug': 'past-occurrence', 'cancelled': True}
    db.demonstrations.insert_one(past)
    response = client.get(f'/demonstration/{parent}/children')
    props = props_from(response)
    assert any(row['id'] == str(past['_id']) and row['cancelled'] for row in props['series']['occurrences'])


@pytest.mark.parametrize('translations', ['invalid', {'fi': 'invalid'}, {'fi': {'title': {'secret': 'private@example.test'}}}])
def test_malformed_translations_do_not_break_or_leak_metadata(client, db, public_detail, translations):
    db.demonstrations.update_one({'_id':public_detail['_id']},{'$set':{'translations':translations}})
    response=client.get(f"/demonstration/{public_detail['_id']}")
    assert response.status_code==200
    assert 'React detail fixture' in response.text
    assert 'private@example.test' not in response.text


def test_json_report_has_explicit_acknowledgement_and_validation(client, db, public_detail, monkeypatch):
    from mielenosoitukset_fi.utils.classes import Case
    monkeypatch.setattr(Case, 'create_new', lambda **kwargs: None)
    before=db.reports.count_documents({})
    headers={'Accept':'application/json'}
    invalid=client.post('/report',data={'type':'demonstration','demo_id':str(public_detail['_id']),'error':' '},headers=headers)
    assert invalid.status_code==400 and db.reports.count_documents({})==before
    result=client.post('/report',data={'type':'demonstration','demo_id':str(public_detail['_id']),'error':'Wrong time'},headers=headers)
    assert result.status_code==200 and result.json['status']=='OK'
    assert db.reports.count_documents({})==before+1
