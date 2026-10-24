"""Tests for the self-service translation-project join flow.

Logged-in users can grant themselves the translation capabilities
(TRANSLATE_DEMO / TRANSLATE_UI) used by the translation catalog, without
emailing the project team. Review/admin rights are intentionally NOT granted.
"""
from bson import ObjectId
import pytest


JOIN_URL = "/upcoming/translations/join"
TRANSLATION_PERMISSIONS = {"TRANSLATE_DEMO", "TRANSLATE_UI"}


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
    first = user_client.post(JOIN_URL)
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
    for _ in range(2):
        response = user_client.post(JOIN_URL)
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
