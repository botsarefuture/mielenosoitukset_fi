"""Tests for the self-service translation-project join flow.

Logged-in users can grant themselves the translation capabilities
(TRANSLATE_DEMO / TRANSLATE_UI) used by the translation catalog, without
emailing the project team. Review/admin rights are intentionally NOT granted.
"""
from bson import ObjectId


JOIN_URL = "/upcoming/translations/join"


def _perms_for(db, user_id):
    doc = db.users.find_one({"_id": ObjectId(user_id)})
    return list(doc.get("global_permissions", []))


def test_guest_cannot_join(app, client):
    res = client.post(JOIN_URL)
    assert res.status_code == 302
    assert "/users/auth/login" in res.headers["Location"]


def test_logged_in_user_gains_translation_permissions(app, db, user_client, seeded_data):
    uid = seeded_data["user_id"]
    first = user_client.post(JOIN_URL)
    assert first.status_code == 302
    assert first.headers["Location"].endswith("/upcoming/translations/")

    perms = _perms_for(db, uid)
    assert "TRANSLATE_DEMO" in perms
    assert "TRANSLATE_UI" in perms


def test_join_is_idempotent(app, db, user_client, seeded_data):
    uid = seeded_data["user_id"]
    user_client.post(JOIN_URL)
    user_client.post(JOIN_URL)

    perms = _perms_for(db, uid)
    assert perms.count("TRANSLATE_DEMO") == 1
    assert perms.count("TRANSLATE_UI") == 1


def test_join_grants_no_review_permission(app, db, user_client, seeded_data):
    uid = seeded_data["user_id"]
    user_client.post(JOIN_URL)
    # confirm permissions are translation-only and role unchanged
    user_doc = db.users.find_one({"_id": ObjectId(uid)})
    perms = user_doc.get("global_permissions", [])
    assert "REVIEW_DEMO_TRANSLATIONS" not in perms
    assert "REVIEW_UI_TRANSLATIONS" not in perms
    assert user_doc.get("role") == "user"


def test_translator_page_shows_joined_state(app, db, translator_client, seeded_data):
    # translator already holds TRANSLATE_DEMO and should see the joined state
    res = translator_client.get("/upcoming/translations/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Olet mukana käännöstyössä" in html
    assert "Liity kääntäjäksi" not in html


def test_guest_page_shows_login_cta(app, client):
    res = client.get("/upcoming/translations/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Kirjaudu sisään liittyäksesi" in html


def test_unjoined_user_page_shows_join_form(app, db, user_client):
    res = user_client.get("/upcoming/translations/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Liity kääntäjäksi" in html
    assert "/upcoming/translations/join" in html
