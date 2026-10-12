"""Permission, confirmation and replay protection for account status changes."""

import html
import re
import pytest
from itsdangerous import TimestampSigner, URLSafeTimedSerializer

from tests.conftest import _client_for_user


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
        nonce = source["account_status_nonce"]
    with other.session_transaction() as destination:
        destination["account_status_nonce"] = nonce
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
