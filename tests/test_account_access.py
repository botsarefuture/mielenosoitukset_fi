"""Account status must gate every login and existing protected session."""

import pytest
import pyotp

from mielenosoitukset_fi.users.models import User, UserMFA
from tests.conftest import _client_for_user

DISABLED_STATES = [{"active": False}, {"banned": True}]


@pytest.mark.parametrize("status", DISABLED_STATES)
@pytest.mark.parametrize("mfa_enabled", [False, True])
def test_password_and_mfa_login_reject_disabled_account(app, db, seeded_data, status, mfa_enabled):
    user_id = seeded_data["user_id"]
    secret = UserMFA(user_id).add_device() if mfa_enabled else None
    db.users.update_one(
        {"_id": user_id}, {"$set": {**status, "mfa_enabled": mfa_enabled}},
    )
    client = app.test_client()
    data = {"username": "alice", "password": "UserPass1!"}
    if secret:
        data["2fa_code"] = pyotp.TOTP(secret).now()
    response = client.post("/users/auth/login", data=data)
    assert response.status_code == 302
    assert "/users/auth/login" in response.headers["Location"]
    with client.session_transaction() as login_session:
        assert "_user_id" not in login_session
    check = client.post("/users/auth/2fa_check", data=data)
    assert check.get_json() == {"enabled": False, "valid": False}


@pytest.mark.parametrize("status", DISABLED_STATES)
def test_existing_session_loses_access_after_account_disabled(app, db, seeded_data, status):
    user_id = seeded_data["user_id"]
    client = _client_for_user(app, user_id)
    assert client.get("/users/auth/api/v2/passkeys").status_code == 200
    db.users.update_one({"_id": user_id}, {"$set": status})
    response = client.get("/users/auth/api/v2/passkeys")
    assert response.status_code == 302
    assert "/users/auth/login" in response.headers["Location"]


def test_legacy_account_without_active_field_remains_enabled(app, db, seeded_data):
    db.users.update_one({"_id": seeded_data["user_id"]}, {"$unset": {"active": ""}})
    user = User.from_db(db.users.find_one({"_id": seeded_data["user_id"]}))
    assert user.is_active
    client = app.test_client()
    client.post("/users/auth/login", data={"username": "alice", "password": "UserPass1!"})
    with client.session_transaction() as login_session:
        assert login_session["_user_id"] == str(seeded_data["user_id"])
