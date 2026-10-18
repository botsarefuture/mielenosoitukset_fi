"""Permission, confirmation and replay protection for account status changes."""

import html
import re
import pytest
from itsdangerous import TimestampSigner, URLSafeTimedSerializer

from tests.conftest import _client_for_user


STATUS_COPY = {
    'fi': [
        'Käyttäjän käyttötila', 'Käyttötila', 'Aktivoi käyttäjä', 'Sulje käyttäjätili',
        'Vahvista kirjautumisoikeuden muutos.', 'Käyttäjän käyttötila päivitetty.',
        'Aktivointi sallii kirjautumisen ja poistaa mahdollisen käyttöeston. Rooli ja käyttöoikeudet säilyvät ennallaan.',
        'Sulkeminen estää kirjautumisen ja suojattujen sivujen käytön nykyisillä sessioilla. Käyttäjän tietoja ei poisteta.',
    ],
    'en': [
        'User account status', 'Account status', 'Activate user', 'Disable account',
        'Confirm the change to sign-in access.', 'User account status updated.',
        'Activation allows sign-in and removes any account ban. The role and permissions stay unchanged.',
        'Disabling blocks sign-in and access to protected pages through existing sessions. User data is not deleted.',
    ],
    'sv': [
        'Användarkontots status', 'Kontostatus', 'Aktivera användare', 'Inaktivera konto',
        'Bekräfta ändringen av inloggningsåtkomsten.', 'Användarkontots status har uppdaterats.',
        'Aktivering tillåter inloggning och tar bort eventuell kontoblockering. Rollen och behörigheterna ändras inte.',
        'Inaktivering blockerar inloggning och åtkomst till skyddade sidor via befintliga sessioner. Användarens uppgifter raderas inte.',
    ],
}


@pytest.mark.parametrize('locale', ['fi', 'en', 'sv'])
def test_compiled_account_status_copy_is_present_and_translated(locale):
    import gettext
    from pathlib import Path

    with Path(f'mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.mo').open('rb') as stream:
        catalog = gettext.GNUTranslations(stream)
    # FI must be compiled too, not merely appear correct through gettext fallback.
    assert all(key in catalog._catalog for key in STATUS_COPY['fi'])
    assert [catalog.gettext(key) for key in STATUS_COPY['fi']] == STATUS_COPY[locale]


@pytest.mark.parametrize('locale', ['fi', 'en', 'sv'])
@pytest.mark.parametrize('enable', [False, True])
def test_account_status_confirmation_and_success_follow_session_locale(app, admin_client, db, seeded_data, locale, enable):
    app.config.update(BABEL_PUBLIC_LOCALES=['fi', 'en', 'sv'])
    with admin_client.session_transaction() as session:
        session['locale'] = locale
    target = seeded_data['user_id']
    db.users.update_one({'_id': target}, {'$set': {'active': not enable, 'banned': False}})
    response = admin_client.get(f'/admin/user/account_status/{target}')
    assert response.status_code == 200
    source = html.unescape(response.get_data(as_text=True))
    copy = STATUS_COPY[locale]
    for index in [0, 1, 4, 2 if enable else 3, 6 if enable else 7]:
        assert copy[index] in source
        if locale != 'fi':
            assert STATUS_COPY['fi'][index] not in source
    token = re.search(r'name="status_token" value="([^"]+)"', source).group(1)
    result = admin_client.post(f'/admin/user/account_status/{target}', data={'status_token': token})
    assert result.status_code == 302
    assert db.users.find_one({'_id': target})['active'] is enable
    with admin_client.session_transaction() as session:
        assert any(copy[5] in str(message) for _, message in session['_flashes'])


def _confirmation(client, user_id):
    response = client.get(f"/admin/user/account_status/{user_id}")
    assert response.status_code == 200
    return html.unescape(re.search(
        r'name="status_token" value="([^"]+)"', response.get_data(as_text=True),
    ).group(1))


def test_admin_can_disable_and_reenable_with_audited_confirmation(admin_client, db, seeded_data):
    target = seeded_data["user_id"]
    token = _confirmation(admin_client, target)
    response = admin_client.post(f"/admin/user/account_status/{target}", data={"status_token": token})
    assert response.status_code == 302
    assert db.users.find_one({"_id": target})["active"] is False
    event = db.admin_logs.find_one({"event": "user_account_status_changed", "entity_id": str(target)})
    assert event["new_state"]["active"] is False
    assert token not in repr(list(db.admin_logs.find({"event": {"$in": [
        "user_account_status_changed", "user_account_status_request",
    ]}})))
    db.users.update_one({"_id": target}, {"$set": {"banned": True}})
    token = _confirmation(admin_client, target)
    admin_client.post(f"/admin/user/account_status/{target}", data={"status_token": token})
    doc = db.users.find_one({"_id": target})
    assert doc["active"] is True and doc["banned"] is False


def test_independent_confirmation_tabs_keep_their_nonces(admin_client, db, seeded_data):
    targets = [seeded_data['user_id'], seeded_data['friend_id']]
    tokens = [_confirmation(admin_client, target) for target in targets]
    for target, token in zip(targets, tokens):
        assert admin_client.post(f'/admin/user/account_status/{target}', data={'status_token': token}).status_code == 302
        assert db.users.find_one({'_id': target})['active'] is False
    with admin_client.session_transaction() as session:
        assert session['account_status_nonces'] == []


def test_confirmation_nonce_collection_is_bounded(admin_client, seeded_data):
    target = seeded_data['user_id']
    tokens = [_confirmation(admin_client, target) for _ in range(9)]
    with admin_client.session_transaction() as session:
        assert len(session['account_status_nonces']) == 8
    assert admin_client.post(f'/admin/user/account_status/{target}', data={'status_token': tokens[0]}).status_code == 400
    assert admin_client.post(f'/admin/user/account_status/{target}', data={'status_token': tokens[-1]}).status_code == 302


def test_superuser_can_list_and_change_ordinary_account_status(admin_client, db, seeded_data):
    db.users.update_one({'_id': seeded_data['admin_id']}, {'$set': {'role': 'superuser'}})
    assert admin_client.get('/admin/user/').status_code == 200
    target = seeded_data['user_id']
    token = _confirmation(admin_client, target)
    assert admin_client.post(f'/admin/user/account_status/{target}', data={'status_token': token}).status_code == 302


@pytest.mark.parametrize('locale,labels', [('en', ['Banned', 'Disabled', 'Active']), ('sv', ['Blockerad', 'Inaktiverad', 'Aktiv']), ('fi', ['Estetty', 'Suljettu', 'Aktiivinen'])])
def test_compiled_status_labels_have_distinct_gettext_context(locale, labels):
    import gettext
    from pathlib import Path
    with Path(f'mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.mo').open('rb') as stream:
        catalog = gettext.GNUTranslations(stream)
    assert [catalog.pgettext('account-status', label) for label in ['Estetty', 'Suljettu', 'Aktiivinen']] == labels
    if locale in {'en', 'sv'}:
        assert catalog.gettext('Suljettu') != labels[1]


@pytest.mark.parametrize("target_kind", ["self", "peer", "higher"])
def test_admin_cannot_change_self_or_peer_or_higher_status(admin_client, db, seeded_data, target_kind):
    target = seeded_data["admin_id"] if target_kind == "self" else seeded_data["user_id"]
    if target_kind != "self":
        db.users.update_one({"_id": target}, {"$set": {"role": "admin" if target_kind == "peer" else "god"}})
    assert admin_client.get(f"/admin/user/account_status/{target}").status_code == 403
    assert admin_client.post(f"/admin/user/account_status/{target}", data={}).status_code == 403


def test_viewer_without_edit_permission_cannot_change_status(app, db, seeded_data):
    actor = seeded_data["friend_id"]
    db.users.update_one({"_id": actor}, {"$set": {
        "role": "city_admin", "global_admin": False, "global_permissions": ["LIST_USERS"],
    }})
    client = _client_for_user(app, actor)
    target = seeded_data["user_id"]
    assert client.get(f"/admin/user/account_status/{target}").status_code == 403
    assert client.post(f"/admin/user/account_status/{target}", data={}).status_code == 403


def test_status_confirmation_rejects_missing_tampered_or_wrong_target_proof(admin_client, seeded_data):
    target = seeded_data["user_id"]
    endpoint = f"/admin/user/account_status/{target}"
    assert admin_client.post(endpoint, data={}).status_code == 400
    token = _confirmation(admin_client, target)
    assert admin_client.post(endpoint, data={"status_token": token + "tampered"}).status_code == 400
    assert admin_client.post(
        f"/admin/user/account_status/{seeded_data['friend_id']}", data={"status_token": token},
    ).status_code == 400


def test_saved_status_form_cannot_replay_after_disable_enable_cycle(app, admin_client, seeded_data):
    target = seeded_data["user_id"]
    endpoint = f"/admin/user/account_status/{target}"
    original = _confirmation(admin_client, target)
    cookie = admin_client.get_cookie(app.config["SESSION_COOKIE_NAME"]).value
    assert admin_client.post(endpoint, data={"status_token": original}).status_code == 302
    fresh = _confirmation(admin_client, target)
    assert admin_client.post(endpoint, data={"status_token": fresh}).status_code == 302
    replay = app.test_client()
    replay.set_cookie(app.config["SESSION_COOKIE_NAME"], cookie)
    assert replay.post(endpoint, data={"status_token": original}).status_code == 409


def test_user_list_and_editor_show_account_status(admin_client, db, seeded_data):
    target = seeded_data["user_id"]
    db.users.update_one({"_id": target}, {"$set": {"active": False}})
    page = admin_client.get("/admin/user/?search=alice").get_data(as_text=True)
    assert "Suljettu" in page and "Käyttötila" in page
    editor = admin_client.get(f"/admin/user/edit_user/{target}")
    assert editor.status_code == 200
    assert "Suljettu" in editor.get_data(as_text=True)


def test_same_status_token_has_one_winner_under_concurrent_submit(app, admin_client, db, seeded_data, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    target = seeded_data['user_id']
    endpoint = f'/admin/user/account_status/{target}'
    token = _confirmation(admin_client, target)
    cookie = admin_client.get_cookie(app.config['SESSION_COOKIE_NAME']).value
    collection_type = type(db.users)
    original = collection_type.update_one
    both_have_snapshot = Barrier(2)

    def synchronized_update(collection, query, update, *args, **kwargs):
        if (collection.full_name == db.users.full_name and query.get('_id') == target
                and update.get('$inc', {}).get('account_status_version') == 1):
            both_have_snapshot.wait(timeout=10)
        return original(collection, query, update, *args, **kwargs)

    monkeypatch.setattr(collection_type, 'update_one', synchronized_update)
    def submit(_index):
        with app.test_client() as client:
            client.set_cookie(app.config['SESSION_COOKIE_NAME'], cookie)
            return client.post(endpoint, data={'status_token': token}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, range(2))) == [302, 409]
    doc = db.users.find_one({'_id': target})
    assert doc['active'] is False and doc['account_status_version'] == 1
    assert db.admin_logs.count_documents({'event': 'user_account_status_changed', 'entity_id': str(target)}) == 1


@pytest.mark.parametrize('kind,visible', [('lower', True), ('self', False), ('peer', False), ('higher', False)])
def test_status_action_visibility_uses_shared_hierarchy(app, admin_client, db, seeded_data, kind, visible):
    from types import SimpleNamespace
    from mielenosoitukset_fi.admin.admin_user_bp import can_change_account_status
    from mielenosoitukset_fi.users.models import User
    target = seeded_data['admin_id'] if kind == 'self' else seeded_data['user_id']
    role = 'admin' if kind in {'self', 'peer'} else 'god' if kind == 'higher' else 'user'
    with app.test_request_context():
        actor = User.from_db(db.users.find_one({'_id': seeded_data['admin_id']}))
        assert can_change_account_status(actor, SimpleNamespace(_id=target, role=role)) is visible
    if kind == 'lower':
        restricted = SimpleNamespace(_id=actor._id, role=actor.role,
            has_full_permissions=lambda: False, global_permissions=[],
            has_permission=lambda _permission: True)
        assert not can_change_account_status(restricted, SimpleNamespace(_id=target, role=role))
        page = admin_client.get(f'/admin/user/edit_user/{target}').get_data(as_text=True)
        assert f'/admin/user/account_status/{target}' in page
    else:
        from flask import render_template
        # Isolate visibility from the edit route's own stricter authorization.
        subject = User.from_db(dict(db.users.find_one({'_id': target}), role=role))
        with app.test_request_context():
            from flask_login import login_user
            login_user(actor)
            page = render_template('admin_V2/user/edit.html', user=subject, can_change_status=False,
                PERMISSIONS_GROUPS={}, city_list=[], enabled_city_list=[], city_name_to_key={},
                city_scope_grant=None, city_admin_permissions=[])
            assert f'/admin/user/account_status/{subject.id}' not in page


def test_status_confirmation_expires(admin_client, seeded_data):
    target = seeded_data["user_id"]
    token = _confirmation(admin_client, target)
    serializer = URLSafeTimedSerializer(
        admin_client.application.secret_key, salt="admin-account-status",
    )

    class ExpiredSigner(TimestampSigner):
        def get_timestamp(self):
            return 1

    expired = URLSafeTimedSerializer(
        admin_client.application.secret_key, salt="admin-account-status", signer=ExpiredSigner,
    )
    token = expired.dumps(serializer.loads(token))
    response = admin_client.post(
        f"/admin/user/account_status/{target}", data={"status_token": token},
    )
    assert response.status_code == 400


def test_confirmation_is_bound_to_the_authenticated_actor(app, admin_client, db, seeded_data):
    target = seeded_data["user_id"]
    token = _confirmation(admin_client, target)
    actor = seeded_data["friend_id"]
    db.users.update_one({"_id": actor}, {"$set": {"role": "god", "global_admin": True}})
    other = _client_for_user(app, actor)
    with admin_client.session_transaction() as source:
        nonces = source["account_status_nonces"]
    with other.session_transaction() as destination:
        destination["account_status_nonces"] = nonces
    response = other.post(
        f"/admin/user/account_status/{target}", data={"status_token": token},
    )
    assert response.status_code == 400
    assert db.users.find_one({"_id": target})["active"] is True


@pytest.mark.e2e
def test_confirmation_layout_and_keyboard_actions_in_both_themes(
    app, admin_client, live_server, browser_page, seeded_data,
):
    cookie = admin_client.get_cookie(app.config["SESSION_COOKIE_NAME"])
    browser_page.context.add_cookies([{
        "name": cookie.key, "value": cookie.value, "url": live_server,
    }])
    for width in (390, 1440):
        browser_page.set_viewport_size({"width": width, "height": 900})
        browser_page.goto(f"{live_server}/admin/user/account_status/{seeded_data['user_id']}")
        for theme in ("light", "dark"):
            browser_page.evaluate("""theme => {
                document.documentElement.classList.toggle('dark', theme === 'dark');
                document.documentElement.dataset.bsTheme = theme;
                document.documentElement.style.colorScheme = theme;
            }""", theme)
            submit = browser_page.locator(".admin-sticky-actions button")
            assert submit.is_visible()
            assert browser_page.locator(".admin-page-hero h1").is_visible()
            assert browser_page.evaluate("document.body.scrollWidth <= innerWidth + 1")
            browser_page.locator(".admin-sticky-actions a").focus()
            browser_page.keyboard.press("Tab")
            assert submit.evaluate("element => element === document.activeElement")
