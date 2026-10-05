import pyotp
from bson import ObjectId

from mielenosoitukset_fi.users.models import User, UserMFA, PendingMFA
from tests.conftest import _client_for_user

TEST_PASSWORD = "".join(("Mfa", "Pass", "1!"))


def _create_mfa_user(db):
    user_id = ObjectId()
    identity_suffix = str(user_id)[-8:]
    user_doc = User.create_user(
        username=f"mfa-user-{identity_suffix}",
        password=TEST_PASSWORD,
        email=f"mfa-user-{identity_suffix}@example.test",
        displayname="MFA User",
    )
    user_doc.update({"_id": user_id, "confirmed": True, "active": True})
    db.users.insert_one(user_doc)
    return user_doc["_id"]


def _totp_code(secret):
    return pyotp.TOTP(secret).now()


def test_mfa_enable_flow_end_to_end(app, db):
    user_id = _create_mfa_user(db)
    client = _client_for_user(app, user_id)

    r = client.post("/users/auth/api/v2/mfa", json={"step": "request_activation"})
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data["status"] == "pending"
    secret = data["secret"]
    assert data["qr_code"].startswith("data:image/png;base64,")

    r = client.post(
        "/users/auth/api/v2/mfa",
        json={"step": "verify_code", "code": "000000", "secret": secret, "device_name": "Unit-Test"},
    )
    assert r.status_code == 400  # wrong code rejected

    unissued_secret = pyotp.random_base32()
    r = client.post(
        "/users/auth/api/v2/mfa",
        json={
            "step": "verify_code",
            "code": _totp_code(unissued_secret),
            "secret": unissued_secret,
            "device_name": "Forged device",
        },
    )
    assert r.status_code == 400

    r = client.post(
        "/users/auth/api/v2/mfa",
        json={"step": "verify_code", "code": _totp_code(secret), "secret": secret, "device_name": "Unit-Test"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["status"] == "success"

    r = client.get("/users/auth/api/v2/mfa_status")
    data = r.get_json()
    assert data["status"] == "enabled"
    assert len(data["devices"]) == 1

    device_id = data["devices"][0]["id"]

    # Removing an MFA device is sensitive → step up first (password + TOTP).
    r = client.post(
        "/users/auth/api/v2/step-up/password",
        json={"password": TEST_PASSWORD, "totp_code": _totp_code(secret)},
    )
    assert r.status_code == 200, r.get_data(as_text=True)

    r = client.post("/users/auth/api/v2/mfa_device_revoke", json={"device_id": device_id})
    assert r.status_code == 200, r.get_data(as_text=True)

    r = client.get("/users/auth/api/v2/mfa_status")
    assert r.get_json()["status"] == "disabled"


def test_mfa_device_rename_requires_step_up_and_updates_name(app, db):
    user_id = _create_mfa_user(db)
    secret = UserMFA(user_id).add_device()
    db.users.update_one({"_id": user_id}, {"$set": {"mfa_enabled": True}})
    client = _client_for_user(app, user_id)

    r = client.get("/users/auth/api/v2/mfa_status")
    device_id = r.get_json()["devices"][0]["id"]

    # Sensitive action → refused without elevation.
    r = client.post(
        "/users/auth/api/v2/mfa_device_rename",
        json={"device_id": device_id, "name": "YubiKey 5C"},
    )
    assert r.status_code == 403, r.get_data(as_text=True)

    r = client.post(
        "/users/auth/api/v2/step-up/password",
        json={"password": TEST_PASSWORD, "totp_code": _totp_code(secret)},
    )
    assert r.status_code == 200, r.get_data(as_text=True)

    r = client.post(
        "/users/auth/api/v2/mfa_device_rename",
        json={"device_id": device_id, "name": "YubiKey 5C"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["status"] == "success"

    r = client.get("/users/auth/api/v2/mfa_status")
    devices = r.get_json()["devices"]
    assert devices[0]["name"] == "YubiKey 5C"
    assert len(devices) == 1

    r = client.post(
        "/users/auth/api/v2/mfa_device_rename",
        json={"device_id": device_id, "name": "   "},
    )
    assert r.status_code == 400

    r = client.post(
        "/users/auth/api/v2/mfa_device_rename",
        json={"device_id": device_id, "name": "  Desk key  "},
    )
    assert r.status_code == 200
    renamed_devices = client.get("/users/auth/api/v2/mfa_status").get_json()["devices"]
    assert renamed_devices[0]["name"] == "Desk key"

    # Missing fields / unknown device are rejected cleanly.
    r = client.post("/users/auth/api/v2/mfa_device_rename", json={"device_id": device_id})
    assert r.status_code == 400

    r = client.post(
        "/users/auth/api/v2/mfa_device_rename",
        json={"device_id": str(ObjectId()), "name": "Ghost"},
    )
    assert r.status_code == 404


def test_mfa_login_uses_short_lived_server_side_pending_state(app, db):
    user_id = _create_mfa_user(db)
    secret = UserMFA(user_id).add_device()
    db.users.update_one({"_id": user_id}, {"$set": {"mfa_enabled": True}})
    username = db.users.find_one({"_id": user_id})["username"]

    client = app.test_client()

    login_page = client.get("/users/auth/login").get_data(as_text=True)
    assert 'id="mfauser"' not in login_page
    assert 'id="mfapass"' not in login_page

    response = client.post(
        "/users/auth/2fa_check",
        data={"username": username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    assert response.get_json() == {"enabled": True, "valid": True}
    with client.session_transaction() as login_session:
        pending = login_session["mfa_pending_login"]
        assert pending["user_id"] == str(user_id)
        assert "password" not in pending
        assert "username" not in pending

    response = client.post(
        "/users/auth/login",
        data={"2fa_code": _totp_code(secret)},
    )
    assert response.status_code == 302
    with client.session_transaction() as login_session:
        assert login_session["_user_id"] == str(user_id)
        assert "mfa_pending_login" not in login_session


def test_expired_pending_mfa_login_requires_password_again(app, db):
    user_id = _create_mfa_user(db)
    secret = UserMFA(user_id).add_device()
    db.users.update_one({"_id": user_id}, {"$set": {"mfa_enabled": True}})
    username = db.users.find_one({"_id": user_id})["username"]
    client = app.test_client()

    response = client.post(
        "/users/auth/2fa_check",
        data={"username": username, "password": TEST_PASSWORD},
    )
    assert response.get_json() == {"enabled": True, "valid": True}
    with client.session_transaction() as login_session:
        pending = dict(login_session["mfa_pending_login"])
        pending["created_at"] = 0
        login_session["mfa_pending_login"] = pending

    response = client.post(
        "/users/auth/login",
        data={"2fa_code": _totp_code(secret)},
    )
    assert response.status_code == 302
    with client.session_transaction() as login_session:
        assert "_user_id" not in login_session
        assert "mfa_pending_login" not in login_session


def test_verify_mfa_route_does_not_500(app, db):
    user_id = _create_mfa_user(db)
    secret = UserMFA(user_id).add_device()
    client = _client_for_user(app, user_id)
    with client.session_transaction() as session:
        session["mfa_required"] = True
    r = client.post(
        "/users/auth/verify_mfa",
        data={"token": _totp_code(secret)},
        follow_redirects=True,
    )
    assert r.status_code != 500, r.get_data(as_text=True)[:2000]
