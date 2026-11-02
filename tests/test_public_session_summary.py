"""The standalone React host reads header state from this read-only endpoint."""

import pytest


PRIVATE_KEYS = {
    "email", "password", "password_hash", "username", "profile_picture",
    "notifications", "permissions", "session", "csrf", "token", "admin",
}


def test_anonymous_summary_is_minimal_and_uncached(client):
    response = client.get("/api/session")

    assert response.status_code == 200
    body = response.get_json()
    assert body["authenticated"] is False
    assert body["role"] == "guest"
    assert body["name"] is None
    assert body["unread"] == 0
    assert body["locale"] in {"fi", "en", "sv"}
    assert isinstance(body["locales"], list) and body["locales"]
    assert all(entry["code"] in {"fi", "en", "sv"} and entry["name"] for entry in body["locales"])
    assert body["locale"] in {entry["code"] for entry in body["locales"]}
    assert PRIVATE_KEYS.isdisjoint(body)
    assert response.headers["Cache-Control"] == "no-store"
    assert "Cookie" in response.headers["Vary"]


@pytest.mark.parametrize("locale", ["fi", "en", "sv"])
def test_summary_uses_the_existing_session_locale(client, app, locale):
    if locale not in app.config["BABEL_PUBLIC_LOCALES"]:
        pytest.skip(f"{locale} is not a public locale in this configuration")
    with client.session_transaction() as session:
        session["locale"] = locale

    body = client.get("/api/session").get_json()

    assert body["locale"] == locale


def test_unsupported_session_locale_falls_back_to_finnish(client):
    with client.session_transaction() as session:
        session["locale"] = "de"

    body = client.get("/api/session").get_json()

    assert body["locale"] == "fi"


def test_authenticated_summary_exposes_only_header_fields(user_client, db, seeded_data):
    body = user_client.get("/api/session").get_json()

    assert body["authenticated"] is True
    assert body["role"]
    assert isinstance(body["name"], str) and body["name"]
    assert isinstance(body["unread"], int)
    assert PRIVATE_KEYS.isdisjoint(body)


def test_organization_summary_is_scoped_private_and_does_not_expose_invitations(client, user_client, db, seeded_data):
    org_id = seeded_data['org_id']
    email = db.users.find_one({'_id': seeded_data['user_id']})['email']
    db.organizations.update_one({'_id': org_id}, {'$set': {'invitations': [email, 'other-person@example.test']}})
    response = user_client.get(f'/api/session?organization_id={org_id}')
    scoped = response.json['organization']
    assert scoped['id'] == str(org_id)
    assert scoped['invited'] is True
    assert scoped['permissions'] == {
        'VIEW_ORGANIZATION': True, 'EDIT_ORGANIZATION': True,
        'DELETE_ORGANIZATION': False, 'INVITE_TO_ORGANIZATION': True,
    }
    assert email not in response.get_data(as_text=True)
    assert 'other-person' not in response.get_data(as_text=True)
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'Cookie' in response.headers['Vary']
    assert 'organization' not in client.get(f'/api/session?organization_id={org_id}').json
    assert 'organization' not in user_client.get('/api/session').json
    other_id = db.organizations.find_one({'verified': True})['_id']
    other = user_client.get(f'/api/session?organization_id={other_id}').json['organization']
    assert other['invited'] is False
    assert not any(other['permissions'].values())


@pytest.mark.parametrize('query', ['organization_id=bad', 'organization_id=' + 'a' * 24 + '&organization_id=' + 'b' * 24])
def test_invalid_organization_summary_scope_is_uncached(client, query):
    response = client.get('/api/session?' + query)
    assert response.status_code == 400
    assert response.headers['Cache-Control'] == 'no-store'


def test_native_organization_invite_feedback_survives_react_session_reads(user_client, db, seeded_data):
    from bson import ObjectId

    org_id = ObjectId()
    email = db.users.find_one({'_id': seeded_data['user_id']})['email']
    db.organizations.insert_one({'_id': org_id, 'name': 'Invitation Organization', 'description': '',
                                 'email': 'org@example.test', 'invitations': [email], 'verified': False})
    response = user_client.post(f'/users/orgs/accept_invite/{org_id}',
                                headers={'Referer': f'http://localhost/organization/{org_id}'})
    assert response.status_code == 302
    assert db.memberships.find_one({'organization_id': org_id, 'user_id': seeded_data['user_id']})
    scoped = user_client.get(f'/api/session?organization_id={org_id}').json['organization']
    assert scoped['invited'] is False
    assert scoped['has_messages'] is True
    feedback = user_client.get('/get_flash_messages')
    assert feedback.headers['Cache-Control'] == 'no-store'
    assert any('Liityit organisaatioon Invitation Organization' in item['message'] for item in feedback.json['messages'])
    assert user_client.get('/get_flash_messages').json['messages'] == []
