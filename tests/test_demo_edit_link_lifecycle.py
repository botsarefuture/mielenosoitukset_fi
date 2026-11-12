from datetime import timedelta
from importlib import import_module
from urllib.parse import urlsplit

import pytest


CSRF_SESSION_KEY = "demo_edit_link_csrf_token"


def _csrf_headers(client):
    with client.session_transaction() as session:
        session[CSRF_SESSION_KEY] = "edit-link-test-csrf"
    return {"X-CSRF-Token": "edit-link-test-csrf"}


def _token_from_url(edit_link):
    return urlsplit(edit_link).path.rsplit("/", 1)[-1]


def _patch_demo_email_sender(monkeypatch, method, replacement):
    modules = {
        import_module("mielenosoitukset_fi.admin.admin_demo_bp"),
        import_module("admin.admin_demo_bp"),
    }
    for module in modules:
        monkeypatch.setattr(module.email_sender, method, replacement)


@pytest.mark.parametrize('duration,seconds', [('1h', 3600), ('24h', 86400), ('7d', 604800)])
def test_edit_link_duration_is_allowlisted_and_registry_expiry_matches(
    admin_client, db, seeded_data, duration, seconds
):
    response = admin_client.post(
        f"/admin/demo/generate_edit_link/{seeded_data['demo_id']}",
        json={"duration": duration},
        headers=_csrf_headers(admin_client),
    )

    assert response.status_code == 200
    payload = response.get_json()
    token = _token_from_url(payload["edit_link"])
    from mielenosoitukset_fi.admin.admin_demo_bp import _hash_token

    token_doc = db.magic_links.find_one({"token_hash": _hash_token(token)})
    assert token_doc["duration_seconds"] == seconds
    assert token_doc["expires_at"] - token_doc["created_at"] == timedelta(seconds=seconds)
    assert payload["expires_at"] == token_doc["expires_at"].isoformat()
    assert payload['duration'] == duration
    assert token not in repr(token_doc)
    count = db.magic_links.count_documents({})

    rejected = admin_client.post(
        f"/admin/demo/generate_edit_link/{seeded_data['demo_id']}",
        json={"duration": "30d"},
        headers=_csrf_headers(admin_client),
    )
    assert rejected.status_code == 400
    assert db.magic_links.count_documents({}) == count


def test_each_edit_link_is_unique_and_revocation_blocks_anonymous_access(
    app, admin_client, db, seeded_data
):
    headers = _csrf_headers(admin_client)
    first = admin_client.post(
        f"/admin/demo/generate_edit_link/{seeded_data['demo_id']}",
        json={"duration": "24h"},
        headers=headers,
    ).get_json()
    second = admin_client.post(
        f"/admin/demo/generate_edit_link/{seeded_data['demo_id']}",
        json={"duration": "24h"},
        headers=headers,
    ).get_json()

    assert first["edit_link"] != second["edit_link"]
    first_path = urlsplit(first["edit_link"]).path
    visitor = app.test_client()
    assert visitor.get(first_path).status_code == 200
    with visitor.session_transaction() as session:
        csrf = session[CSRF_SESSION_KEY]
    original_title = db.demonstrations.find_one({'_id': seeded_data['demo_id']})['title']

    from mielenosoitukset_fi.admin.admin_demo_bp import _hash_token

    token_doc = db.magic_links.find_one(
        {"token_hash": _hash_token(_token_from_url(first["edit_link"]))}
    )
    revoked = admin_client.post(
        f"/admin/demo/edit-links/{seeded_data['demo_id']}/revoke/{token_doc['_id']}",
        data={"csrf_token": "edit-link-test-csrf"},
        follow_redirects=False,
    )
    assert revoked.status_code == 302
    unavailable = app.test_client().get(first_path)
    assert unavailable.status_code == 403
    assert "mitätöity" in unavailable.get_data(as_text=True).lower()
    denied = visitor.post(first_path, data={'csrf_token': csrf, 'title': 'Revoked update'})
    assert denied.status_code == 403
    assert db.demonstrations.find_one({'_id': seeded_data['demo_id']})['title'] == original_title
    assert app.test_client().get(urlsplit(second['edit_link']).path).status_code == 200

    edit_page = admin_client.get(
        f"/admin/demo/edit_demo/{seeded_data['demo_id']}"
    ).get_data(as_text=True)
    assert "Mitätöi kaikki aktiiviset muokkauslinkit" in edit_page


@pytest.mark.parametrize('approved', [True, False])
def test_anonymous_edit_token_can_save_with_session_csrf(app, db, seeded_data, approved):
    db.demonstrations.update_one({'_id': seeded_data['demo_id']}, {'$set': {'approved': approved}})
    client = app.test_client()
    path = f"/admin/demo/edit_demo_with_token/{seeded_data['edit_token']}"

    page = client.get(path)
    assert page.status_code == 200
    with client.session_transaction() as session:
        csrf_token = session[CSRF_SESSION_KEY]

    original_title = db.demonstrations.find_one({'_id': seeded_data['demo_id']})['title']
    fields = {
        "title": "Tokenilla päivitetty mielenosoitus",
        "date": "2026-05-01",
        "city": "Helsinki",
        "approved": "" if approved else "on",
    }
    for csrf in [None, 'wrong']:
        denied = client.post(path, data=fields if csrf is None else {**fields, 'csrf_token': csrf})
        assert denied.status_code == 403
        assert db.demonstrations.find_one({'_id': seeded_data['demo_id']})['title'] == original_title

    response = client.post(
        path,
        data={**fields, 'csrf_token': csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
    assert updated["title"] == "Tokenilla päivitetty mielenosoitus"
    assert updated["approved"] is approved
    assert seeded_data["edit_token"] not in str(list(db.super_audit_logs.find()))


def test_send_edit_link_ignores_client_url_and_does_not_use_persistent_queue(
    app, admin_client, monkeypatch, seeded_data
):
    sent = {}

    def capture_send_now(**kwargs):
        sent.update(kwargs)
        return True

    _patch_demo_email_sender(monkeypatch, "send_now", capture_send_now)
    _patch_demo_email_sender(
        monkeypatch,
        "queue_email",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("bearer link was queued")),
    )

    response = admin_client.post(
        f"/admin/demo/send_edit_link_email/{seeded_data['demo_id']}",
        json={
            "email": "recipient@example.test",
            "duration": "7d",
            "edit_link": "https://attacker.example/credential",
        },
        headers=_csrf_headers(admin_client),
    )

    assert response.status_code == 200
    assert sent["recipients"] == ["recipient@example.test"]
    assert sent["raise_on_error"] is True
    generated = urlsplit(sent['context']['edit_link'])
    assert generated.scheme == 'http' and generated.netloc == 'localhost'
    assert generated.path.startswith('/admin/demo/edit_demo_with_token/')
    assert app.test_client().get(generated.path).status_code == 200


@pytest.mark.parametrize('duration,age,status', [
    ('1h', 3599, 200), ('1h', 3600, 410), ('24h', 3601, 200),
    ('24h', 86400, 410), ('7d', 86401, 200), ('7d', 604800, 410), ('7d', 604801, 410),
])
def test_edit_link_lifetime_applies_to_anonymous_get_and_post(app, admin_client, db, seeded_data, monkeypatch, duration, age, status):
    # Patch only the registered edit serializer/domain clock, not cookie signing.
    namespace = app.view_functions['admin_demo.edit_demo_with_token'].__globals__
    clock = [namespace['_now_utc']().replace(microsecond=0)]
    monkeypatch.setitem(namespace, '_now_utc', lambda: clock[0])
    serializer = namespace['serializer']
    original_make_signer = serializer.make_signer

    def make_signer(salt=None):
        signer = original_make_signer(salt)
        signer.get_timestamp = lambda: int(clock[0].timestamp())
        return signer

    monkeypatch.setattr(serializer, 'make_signer', make_signer)
    generated = admin_client.post(
        f"/admin/demo/generate_edit_link/{seeded_data['demo_id']}",
        json={'duration': duration}, headers=_csrf_headers(admin_client),
    )
    assert generated.status_code == 200
    path = urlsplit(generated.get_json()['edit_link']).path
    visitor = app.test_client()
    assert visitor.get(path).status_code == 200
    with visitor.session_transaction() as session:
        csrf = session[CSRF_SESSION_KEY]
    original = db.demonstrations.find_one({'_id': seeded_data['demo_id']})
    clock[0] += timedelta(seconds=age)
    page = visitor.get(path)
    assert page.status_code == status
    if status == 410:
        assert 'vanhentunut' in page.get_data(as_text=True).lower()
    saved = visitor.post(path, data={
        'csrf_token': csrf, 'title': 'Scoped link update', 'city': original['city'], 'date': original['date'],
    })
    assert saved.status_code == (302 if status == 200 else 410)
    title = db.demonstrations.find_one({'_id': seeded_data['demo_id']})['title']
    assert title == ('Scoped link update' if status == 200 else original['title'])


@pytest.mark.parametrize('action', ['generate', 'send', 'revoke', 'revoke-all'])
@pytest.mark.parametrize('wrong', [False, True])
def test_edit_link_management_rejects_missing_or_wrong_csrf(app, admin_client, db, seeded_data, monkeypatch, action, wrong):
    generated = admin_client.post(
        f"/admin/demo/generate_edit_link/{seeded_data['demo_id']}",
        json={'duration': '24h'}, headers=_csrf_headers(admin_client),
    )
    assert generated.status_code == 200
    token = _token_from_url(generated.get_json()['edit_link'])
    namespace = app.view_functions['admin_demo.edit_demo_with_token'].__globals__
    record = db.magic_links.find_one({'token_hash': namespace['_hash_token'](token)})
    routes = {
        'generate': f"/admin/demo/generate_edit_link/{seeded_data['demo_id']}",
        'send': f"/admin/demo/send_edit_link_email/{seeded_data['demo_id']}",
        'revoke': f"/admin/demo/edit-links/{seeded_data['demo_id']}/revoke/{record['_id']}",
        'revoke-all': f"/admin/demo/edit-links/{seeded_data['demo_id']}/revoke-all",
    }
    sent = []
    _patch_demo_email_sender(monkeypatch, 'send_now', lambda **kwargs: sent.append(True))
    count = db.magic_links.count_documents({})
    response = admin_client.post(routes[action], json={'duration': '24h', 'email': 'recipient@example.test'},
        headers={'X-CSRF-Token': 'wrong'} if wrong else {})
    assert response.status_code == 403
    assert db.magic_links.count_documents({}) == count
    assert db.magic_links.find_one({'_id': record['_id']})['revoked'] is False
    assert sent == []


def test_revoke_all_edit_links_is_demo_scoped_and_blocks_existing_sessions(app, admin_client, db, seeded_data):
    payloads = []
    for demo_id in [seeded_data['demo_id'], seeded_data['demo_id'], seeded_data['pending_demo_id']]:
        response = admin_client.post(f'/admin/demo/generate_edit_link/{demo_id}',
            json={'duration': '24h'}, headers=_csrf_headers(admin_client))
        assert response.status_code == 200
        payloads.append(response.get_json())
    visitor = app.test_client()
    first_path = urlsplit(payloads[0]['edit_link']).path
    assert visitor.get(first_path).status_code == 200
    with visitor.session_transaction() as session:
        csrf = session[CSRF_SESSION_KEY]
    title = db.demonstrations.find_one({'_id': seeded_data['demo_id']})['title']
    unaffected = {doc['_id']: doc.get('revoked') for doc in db.magic_links.find({'action': {'$ne': 'edit'}})}
    response = admin_client.post(f"/admin/demo/edit-links/{seeded_data['demo_id']}/revoke-all",
        data={'csrf_token': 'edit-link-test-csrf'})
    assert response.status_code == 302
    for payload in payloads[:2]:
        assert app.test_client().get(urlsplit(payload['edit_link']).path).status_code == 403
    assert visitor.post(first_path, data={'csrf_token': csrf, 'title': 'Revoked bulk update'}).status_code == 403
    assert db.demonstrations.find_one({'_id': seeded_data['demo_id']})['title'] == title
    assert app.test_client().get(urlsplit(payloads[2]['edit_link']).path).status_code == 200
    assert {doc['_id']: doc.get('revoked') for doc in db.magic_links.find({'action': {'$ne': 'edit'}})} == unaffected


@pytest.mark.parametrize('fault', ['tampered', 'missing', 'wrong-action', 'wrong-demo'])
def test_edit_link_requires_matching_signature_and_registry_before_get_or_post(app, db, seeded_data, fault):
    token = seeded_data['edit_token']
    path = f'/admin/demo/edit_demo_with_token/{token}'
    visitor = app.test_client()
    assert visitor.get(path).status_code == 200
    with visitor.session_transaction() as session:
        csrf = session[CSRF_SESSION_KEY]
    namespace = app.view_functions['admin_demo.edit_demo_with_token'].__globals__
    record = db.magic_links.find_one({'token_hash': namespace['_hash_token'](token)})
    if fault == 'tampered':
        path += 'tampered'
    elif fault == 'missing':
        db.magic_links.delete_one({'_id': record['_id']})
    elif fault == 'wrong-action':
        db.magic_links.update_one({'_id': record['_id']}, {'$set': {'action': 'approve'}})
    else:
        db.magic_links.update_one({'_id': record['_id']}, {'$set': {'demo_id': str(seeded_data['pending_demo_id'])}})
    original = db.demonstrations.find_one({'_id': seeded_data['demo_id']})['title']
    assert visitor.get(path).status_code == 400
    assert visitor.post(path, data={'csrf_token': csrf, 'title': 'Invalid proof update'}).status_code == 400
    assert db.demonstrations.find_one({'_id': seeded_data['demo_id']})['title'] == original


def test_recurring_editor_does_not_offer_regular_demo_edit_links(
    admin_client, seeded_data
):
    response = admin_client.get(
        f"/admin/recu_demo/edit_recu_demo/{seeded_data['recu_demo_id']}"
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "generate-edit-link-btn" not in page
    assert "send_edit_link_email" not in page
    assert "duplicate-demo-btn" in page
