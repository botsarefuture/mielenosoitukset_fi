"""Tests for the self-service translation-project join flow.

Logged-in users can grant themselves the translation capabilities
(TRANSLATE_DEMO / TRANSLATE_UI) used by the translation catalog, without
emailing the project team. Review/admin rights are intentionally NOT granted.
"""
import re

from bson import ObjectId
import pytest


JOIN_URL = "/upcoming/translations/join"
TRANSLATION_PERMISSIONS = {"TRANSLATE_DEMO", "TRANSLATE_UI"}


def _join_token(client):
    response = client.get("/upcoming/translations/")
    assert response.status_code == 200
    forms = re.findall(
        r'<form\b[^>]*action="' + re.escape(JOIN_URL) + r'"[^>]*>(.*?)</form>',
        response.get_data(as_text=True), re.S,
    )
    assert forms
    tokens = []
    for form in forms:
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', form)
        assert match is not None
        tokens.append(match[1])
    assert len(set(tokens)) == 1
    assert len(tokens[0]) == 43
    return tokens[0]


@pytest.fixture
def welcome_calls(app, monkeypatch):
    from mielenosoitukset_fi.translations_join_bp import email_sender

    calls = []
    monkeypatch.setattr(email_sender, "queue_email", lambda **kwargs: calls.append(kwargs))
    return calls


def _perms_for(db, user_id):
    doc = db.users.find_one({"_id": ObjectId(user_id)})
    return list(doc.get("global_permissions", []))


def test_guest_cannot_join(app, client, db, welcome_calls):
    before = list(db.users.find().sort("_id", 1))
    res = client.post(JOIN_URL)
    assert res.status_code == 302
    assert "/users/auth/login" in res.headers["Location"]
    assert list(db.users.find().sort("_id", 1)) == before
    assert welcome_calls == []


def test_logged_in_user_gains_translation_permissions(app, db, user_client, seeded_data, welcome_calls):
    uid = seeded_data["user_id"]
    before = db.users.find_one({"_id": uid})
    first = user_client.post(JOIN_URL, data={"csrf_token": _join_token(user_client)})
    assert first.status_code == 302
    assert first.headers["Location"].endswith("/upcoming/translations/")

    perms = _perms_for(db, uid)
    assert set(perms) == set(before["global_permissions"]) | TRANSLATION_PERMISSIONS
    assert len(welcome_calls) == 1
    assert welcome_calls[0]["template_name"] == "translator_welcome.html"
    assert welcome_calls[0]["recipients"] == [before["email"]]
    assert welcome_calls[0]["context"]["user_name"] == before["displayname"]
    assert welcome_calls[0]["context"]["translations_url"].endswith("/upcoming/translations/")


def test_join_is_idempotent(app, db, user_client, seeded_data, welcome_calls):
    uid = seeded_data["user_id"]
    token = _join_token(user_client)
    for _ in range(2):
        response = user_client.post(JOIN_URL, data={"csrf_token": token})
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/upcoming/translations/")

    perms = _perms_for(db, uid)
    assert perms.count("TRANSLATE_DEMO") == 1
    assert perms.count("TRANSLATE_UI") == 1
    assert len(welcome_calls) == 1


def test_join_grants_no_review_permission(app, db, user_client, seeded_data):
    uid = seeded_data["user_id"]
    before = db.users.find_one({"_id": uid})
    others = list(db.users.find({"_id": {"$ne": uid}}).sort("_id", 1))
    response = user_client.post(JOIN_URL, data={
        "csrf_token": _join_token(user_client),
        "user_id": str(seeded_data["friend_id"]),
        "global_permissions": ["REVIEW_UI_TRANSLATIONS", "EDIT_USER"],
        "role": "admin", "global_admin": "true",
    })
    assert response.status_code == 302
    # confirm permissions are translation-only and role unchanged
    user_doc = db.users.find_one({"_id": ObjectId(uid)})
    perms = user_doc.get("global_permissions", [])
    assert "REVIEW_DEMO_TRANSLATIONS" not in perms
    assert "REVIEW_UI_TRANSLATIONS" not in perms
    assert user_doc.get("role") == "user"
    assert user_doc.get("global_admin") is False
    assert set(perms) == set(before["global_permissions"]) | TRANSLATION_PERMISSIONS
    assert list(db.users.find({"_id": {"$ne": uid}}).sort("_id", 1)) == others


def test_translator_page_shows_joined_state(app, db, translator_client, seeded_data):
    # translator already holds TRANSLATE_DEMO and should see the joined state
    res = translator_client.get("/upcoming/translations/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Olet mukana käännöstyössä" in html
    assert "Liity kääntäjäksi" not in html
    assert f'action="{JOIN_URL}"' not in html


def test_guest_page_shows_login_cta(app, client):
    res = client.get("/upcoming/translations/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Kirjaudu sisään liittyäksesi" in html
    assert "/users/auth/login" in html
    assert f'action="{JOIN_URL}"' not in html


def test_unjoined_user_page_shows_join_form(app, db, user_client):
    res = user_client.get("/upcoming/translations/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Liity kääntäjäksi" in html
    assert "/upcoming/translations/join" in html
    assert f'<form method="post" action="{JOIN_URL}"' in html
    assert "Olet mukana käännöstyössä" not in html
    _join_token(user_client)


@pytest.mark.parametrize("token_kind", ["missing", "empty", "wrong", "unicode", "unissued"])
def test_join_rejects_missing_or_invalid_intent_without_side_effects(
    app, db, user_client, welcome_calls, token_kind,
):
    if token_kind != "unissued":
        issued = _join_token(user_client)
    supplied = {
        "missing": None, "empty": "", "wrong": "x" * 43,
        "unicode": "ä" * 43, "unissued": "y" * 43,
    }[token_kind]
    before = list(db.users.find().sort("_id", 1))
    response = user_client.post(JOIN_URL, data={} if supplied is None else {"csrf_token": supplied})
    assert response.status_code == 400
    assert list(db.users.find().sort("_id", 1)) == before
    assert welcome_calls == []
    # A rejected attempt must not break a legitimately issued form.
    token = issued if token_kind != "unissued" else _join_token(user_client)
    valid = user_client.post(JOIN_URL, data={"csrf_token": token})
    assert valid.status_code == 302
    assert len(welcome_calls) == 1


def test_join_token_cannot_cross_sessions_even_for_the_same_user(app, db, user_client, welcome_calls):
    actor_id = None
    with user_client.session_transaction() as session:
        actor_id = session["_user_id"]
    second = app.test_client()
    with second.session_transaction() as session:
        session["_user_id"] = actor_id
        session["_fresh"] = True
    first_token = _join_token(user_client)
    second_token = _join_token(second)
    assert first_token != second_token
    before = list(db.users.find().sort("_id", 1))
    assert second.post(JOIN_URL, data={"csrf_token": first_token}).status_code == 400
    assert list(db.users.find().sort("_id", 1)) == before
    assert welcome_calls == []
    assert second.post(JOIN_URL, data={"csrf_token": second_token}).status_code == 302
    assert len(welcome_calls) == 1


@pytest.mark.e2e
@pytest.mark.parametrize("width,theme", [(390, "light"), (1440, "dark")])
def test_join_form_submits_with_keyboard_without_javascript(
    app, db, user_client, seeded_data, welcome_calls, live_server, playwright_browser, width, theme,
):
    context = playwright_browser.new_context(
        java_script_enabled=False, viewport={"width": width, "height": 1000}, color_scheme=theme,
    )
    try:
        context.route("**/*", lambda route: route.continue_()
                      if route.request.url.startswith(live_server + "/") else route.abort())
        cookie = user_client.get_cookie(app.config["SESSION_COOKIE_NAME"])
        context.add_cookies([{"name": cookie.key, "value": cookie.value, "url": live_server}])
        page = context.new_page()
        assert page.goto(live_server + "/upcoming/translations/").status == 200
        form = page.locator(f'form[action="{JOIN_URL}"]').first
        assert len(form.locator('input[name="csrf_token"]').input_value()) == 43
        button = form.locator('button[type="submit"]')
        assert button.is_visible()
        button.focus()
        with page.expect_navigation(wait_until="domcontentloaded") as navigation:
            button.press("Enter")
        assert navigation.value.status == 200
        assert page.locator(f'form[action="{JOIN_URL}"]').count() == 0
        assert "Olet mukana käännöstyössä" in page.locator("body").inner_text()
        assert TRANSLATION_PERMISSIONS <= set(_perms_for(db, seeded_data["user_id"]))
        assert len(welcome_calls) == 1
    finally:
        context.close()
