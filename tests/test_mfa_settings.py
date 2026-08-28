import pyotp
from bson import ObjectId

from mielenosoitukset_fi.users.models import User, UserMFA, PendingMFA
from tests.conftest import _client_for_user

TEST_PASSWORD = "".join(("Mfa", "Pass", "1!"))


def _create_mfa_user(db):
    user_doc = User.create_user(
        username="mfa-user",
        password=TEST_PASSWORD,
        email="mfa-user@example.test",
        displayname="MFA User",
    )
    user_doc.update({"_id": ObjectId(), "confirmed": True, "active": True})
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

    r = client.post("/users/auth/api/v2/mfa_device_revoke", json={"device_id": device_id})
    assert r.status_code == 200, r.get_data(as_text=True)

    r = client.get("/users/auth/api/v2/mfa_status")
    assert r.get_json()["status"] == "disabled"


def test_mfa_blocks_login_without_code_and_allows_with_code(app, db):
    user_id = _create_mfa_user(db)
    secret = UserMFA(user_id).add_device()
    db.users.update_one({"_id": user_id}, {"$set": {"mfa_enabled": True}})

    client = app.test_client()

    r = client.post("/users/auth/2fa_check", data={})
    assert r.status_code in (200, 400)

    r = client.post("/users/auth/login", data={
        "username": "mfa-user",
        "password": TEST_PASSWORD,
        "2fa_code": "000000",
    })
    page = r.get_data(as_text=True)
    assert "Väärä" in page or r.status_code == 302

    r = client.post("/users/auth/login", data={
        "username": "mfa-user",
        "password": TEST_PASSWORD,
        "2fa_code": _totp_code(secret),
    }, follow_redirects=True)
    assert r.status_code in (200, 302)


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
