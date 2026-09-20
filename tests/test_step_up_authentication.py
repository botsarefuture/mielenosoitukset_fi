"""Step-up (sudo) authentication tests.

Covers the guard decorator behaviour, the password + TOTP fallback, the
WebAuthn step-up flow, session binding, and the default timeout.
"""

import time

import pytest
import pyotp
from bson import ObjectId

from mielenosoitukset_fi.users.models import User
from tests import _webauthn_sim as sim
from tests.conftest import _cleanup_app_resources, _client_for_user

ORIGIN = "http://localhost"
RP_ID = "localhost"


@pytest.fixture
def wapp(app_factory):
    app = app_factory(WEBAUTHN_ORIGIN=ORIGIN, WEBAUTHN_RP_ID=RP_ID)
    try:
        yield app
    finally:
        _cleanup_app_resources(app)


def _create_user(db, username, password="Passw0rd1!", mfa_secret=None, confirmed=True):
    user_id = ObjectId()
    user_doc = User.create_user(
        username=username,
        password=password,
        email=f"{username}@example.test",
        displayname=username.title(),
    )
    user_doc.update({"_id": user_id, "confirmed": confirmed, "active": True})
    db.users.insert_one(user_doc)
    if mfa_secret:
        db.mfas.insert_one({"user_id": user_id, "secret": mfa_secret, "device_name": "Test"})
        db.users.update_one({"_id": user_id}, {"$set": {"mfa_enabled": True}})
    return user_id


def _set_elevation_timestamp(client, user_id, age_seconds):
    with client.session_transaction() as sess:
        sess["sudo"] = {
            "authenticated_at": time.time() - age_seconds,
            "method": "password_totp",
            "user_id": str(user_id),
        }


def test_step_up_password_grants_elevation(wapp, db):
    user_id = _create_user(db, "elev-user")
    client = _client_for_user(wapp, user_id)

    # not elevated yet
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    assert r.status_code == 403
    assert r.get_json()["error"] == "step_up_required"

    r = client.post(
        "/users/auth/api/v2/step-up/password", json={"password": "Passw0rd1!"}
    )
    assert r.status_code == 200, r.get_data(as_text=True)

    r = client.post("/users/auth/api/v2/passkeys/register/options")
    assert r.status_code == 200


def test_step_up_rejects_wrong_password(wapp, db):
    user_id = _create_user(db, "elev-user2")
    client = _client_for_user(wapp, user_id)
    r = client.post(
        "/users/auth/api/v2/step-up/password", json={"password": "nope"}
    )
    assert r.status_code == 403

    r = client.get("/users/auth/api/v2/step-up/status")
    assert r.get_json()["elevated"] is False


def test_step_up_requires_totp_when_mfa_enabled(wapp, db):
    secret = pyotp.random_base32()
    user_id = _create_user(db, "mfa-user", mfa_secret=secret)
    client = _client_for_user(wapp, user_id)

    r = client.post(
        "/users/auth/api/v2/step-up/password", json={"password": "Passw0rd1!"}
    )
    assert r.status_code == 400
    assert r.get_json()["error"] == "totp_required"

    r = client.post(
        "/users/auth/api/v2/step-up/password",
        json={"password": "Passw0rd1!", "totp_code": pyotp.TOTP(secret).now()},
    )
    assert r.status_code == 200, r.get_data(as_text=True)

    r = client.get("/users/auth/api/v2/step-up/status")
    assert r.get_json()["elevated"] is True


def test_step_up_password_without_mfa_and_without_totp_works(wapp, db):
    user_id = _create_user(db, "plain-user")
    client = _client_for_user(wapp, user_id)
    r = client.post(
        "/users/auth/api/v2/step-up/password", json={"password": "Passw0rd1!"}
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "success"


def test_step_up_options_reflect_methods(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    r = client.post("/users/auth/api/v2/step-up/options")
    methods = r.get_json()["methods"]
    assert [m["type"] for m in methods] == ["password_totp"]

    # add a passkey → webauthn becomes the preferred method
    key = sim.generate_key()
    _elevate_with_password(client, password="UserPass1!")
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    credential = sim.registration_credential_json(options, key, origin=ORIGIN)
    r = client.post(
        "/users/auth/api/v2/passkeys/register/verify",
        json={"credential": credential},
    )
    assert r.status_code == 200

    r = client.post("/users/auth/api/v2/step-up/options")
    methods = r.get_json()["methods"]
    assert methods[0]["type"] == "webauthn"
    assert methods[0]["preferred"] is True


def test_step_up_webauthn_flow(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    _elevate_with_password(client, password="UserPass1!")

    key = sim.generate_key()
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    trigger = sim.registration_credential_json(options, key, origin=ORIGIN)
    r = client.post(
        "/users/auth/api/v2/passkeys/register/verify",
        json={"credential": trigger},
    )
    credential_id = trigger["id"]
    assert r.status_code == 200

    # fresh session (no elevation) then step up with the passkey
    fresh = _client_for_user(wapp, seeded_data["user_id"])
    r = fresh.post("/users/auth/api/v2/passkeys/register/options")
    assert r.status_code == 403

    r = fresh.post("/users/auth/api/v2/step-up/webauthn/options")
    options = r.get_json()["options"]
    r = fresh.post("/users/auth/api/v2/step-up/password", json={"password": "UserPass1!"})
    assert r.status_code == 200  # password fallback already works

    fresh2 = _client_for_user(wapp, seeded_data["user_id"])
    r = fresh2.post("/users/auth/api/v2/step-up/webauthn/options")
    options = r.get_json()["options"]
    assertion = sim.assertion_credential_json(
        options, key, origin=ORIGIN, credential_id=credential_id, counter=1
    )
    r = fresh2.post(
        "/users/auth/api/v2/step-up/webauthn/verify", json={"credential": assertion}
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    r = fresh2.post("/users/auth/api/v2/passkeys/register/options")
    assert r.status_code == 200


def test_elevation_times_out(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    _elevate_with_password(client, password="UserPass1!")
    _set_elevation_timestamp(client, seeded_data["user_id"], age_seconds=2000)

    r = client.post("/users/auth/api/v2/passkeys/register/options")
    assert r.status_code == 403

    r = client.get("/users/auth/api/v2/step-up/status")
    assert r.get_json()["elevated"] is False


def test_elevation_does_not_leak_across_sessions(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    _elevate_with_password(client, password="UserPass1!")

    other = _client_for_user(wapp, seeded_data["friend_id"])
    r = other.post("/users/auth/api/v2/passkeys/register/options")
    assert r.status_code == 403

    r = other.get("/users/auth/api/v2/step-up/status")
    assert r.get_json()["elevated"] is False


def test_sudo_required_redirects_anonymous_to_login(wapp):
    anon = wapp.test_client()
    r = anon.post("/users/auth/api/v2/passkeys/register/options")
    assert r.status_code == 302
    assert "/users/auth/login" in r.headers["Location"]


def test_logout_clears_elevation(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    _elevate_with_password(client, password="UserPass1!")

    r = client.get("/users/auth/logout")
    assert r.status_code == 302

    # a brand-new session for the same user starts without elevation
    again = _client_for_user(wapp, seeded_data["user_id"])
    r = again.get("/users/auth/api/v2/step-up/status")
    assert r.get_json()["elevated"] is False


def test_change_password_requires_step_up(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    r = client.post(
        "/users/auth/api/v2/change_password",
        json={"current": "UserPass1!", "new": "NewPass1!", "confirm": "NewPass1!"},
    )
    assert r.status_code == 403
    assert r.get_json()["error"] == "step_up_required"

    _elevate_with_password(client, password="UserPass1!")
    r = client.post(
        "/users/auth/api/v2/change_password",
        json={"current": "UserPass1!", "new": "NewPass1!", "confirm": "NewPass1!"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)


def _elevate_with_password(client, password="Passw0rd1!"):
    r = client.post(
        "/users/auth/api/v2/step-up/password", json={"password": password}
    )
    assert r.status_code == 200, r.get_data(as_text=True)