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
