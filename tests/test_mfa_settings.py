import pyotp
import hashlib
import time
import importlib
from pymongo.collection import Collection
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from bson import ObjectId
from flask import session

from mielenosoitukset_fi.users.models import User, UserMFA, PendingMFA
from tests.conftest import _client_for_user
from mielenosoitukset_fi.users.BPs.auth import (
    _consume_pending_mfa_login,
    MFA_PENDING_LOGIN_MAX_ATTEMPTS,
)

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


def _invalid_totp_code(secret):
    """Avoid a random collision with any code accepted by the MFA window."""
    totp = pyotp.TOTP(secret)
    now = int(time.time())
    accepted = {totp.at(now + offset * 30) for offset in range(-6, 7)}
    return next(f"{value:06d}" for value in range(1000000) if f"{value:06d}" not in accepted)


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
        json={"step": "verify_code", "code": _invalid_totp_code(secret), "secret": secret, "device_name": "Unit-Test"},
    )
    assert r.status_code == 400  # wrong code rejected

    unissued_secret = pyotp.random_base32()
    while _totp_code(unissued_secret) == _totp_code(secret):
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
        challenge = login_session["mfa_pending_login"]
        assert isinstance(challenge, str)
        pending = db.mfa_login_challenges.find_one({
            "_id": hashlib.sha256(challenge.encode()).hexdigest(),
        })
        assert pending["user_id"] == user_id
        assert "password" not in pending
        assert "password_hash" not in pending
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
        challenge = login_session["mfa_pending_login"]
    from datetime import datetime
    db.mfa_login_challenges.update_one(
        {"_id": hashlib.sha256(challenge.encode()).hexdigest()},
        {"$set": {"expires_at": datetime(2000, 1, 1)}},
    )

    response = client.post(
        "/users/auth/login",
        data={"2fa_code": _totp_code(secret)},
    )
    assert response.status_code == 302
    with client.session_transaction() as login_session:
        assert "_user_id" not in login_session
        assert "mfa_pending_login" not in login_session


def _pending_login(app, db):
    """Create a real first-factor challenge for an MFA-enabled test account."""
    user_id = _create_mfa_user(db)
    secret = UserMFA(user_id).add_device()
    db.users.update_one({"_id": user_id}, {"$set": {"mfa_enabled": True}})
    user = User.from_db(db.users.find_one({"_id": user_id}))
    client = app.test_client()
    response = client.post(
        "/users/auth/2fa_check",
        data={"username": user.username, "password": TEST_PASSWORD},
    )
    assert response.get_json() == {"enabled": True, "valid": True}
    return client, user, secret


def test_copied_pending_cookie_cannot_replay_successful_mfa(app, db):
    client, user, secret = _pending_login(app, db)
    old_cookie = client.get_cookie(app.config["SESSION_COOKIE_NAME"]).value
    response = client.post("/users/auth/login", data={"2fa_code": _totp_code(secret)})
    assert response.status_code == 302
    with client.session_transaction() as login_session:
        assert login_session["_user_id"] == user.id

    replay = app.test_client()
    replay.set_cookie(app.config["SESSION_COOKIE_NAME"], old_cookie)
    replay.post("/users/auth/login", data={"2fa_code": _totp_code(secret)})
    with replay.session_transaction() as login_session:
        assert "_user_id" not in login_session


def test_password_change_revokes_pending_first_factor(app, db):
    client, user, secret = _pending_login(app, db)
    user._change_password("ReplacementPassword1!")
    client.post("/users/auth/login", data={"2fa_code": _totp_code(secret)})
    with client.session_transaction() as login_session:
        assert "_user_id" not in login_session
        assert "mfa_pending_login" not in login_session
    assert db.mfa_login_challenges.count_documents({"user_id": user._id}) == 0


def test_reset_after_mfa_user_load_does_not_call_login_user(app, db, monkeypatch):
    client, user, secret = _pending_login(app, db)
    auth = importlib.import_module("mielenosoitukset_fi.users.BPs.auth")
    verify = UserMFA.verify_token
    login_calls = []

    def verify_then_reset(self, code):
        result = verify(self, code)
        user._change_password("ReplacementPassword1!")
        return result

    monkeypatch.setattr(UserMFA, "verify_token", verify_then_reset)
    monkeypatch.setattr(auth, "login_user", lambda user: login_calls.append(user.id))
    client.post("/users/auth/login", data={"2fa_code": _totp_code(secret)})
    assert login_calls == []
    with client.session_transaction() as login_session:
        assert "_user_id" not in login_session


def test_reset_between_persisted_read_and_atomic_authorization_is_rejected(app, db, monkeypatch):
    client, user, secret = _pending_login(app, db)
    update = Collection.find_one_and_update
    reset_ran = []

    def reset_before_update(collection, query, change, *args, **kwargs):
        if collection.name == "users" and "last_mfa_login_at" in change.get("$set", {}):
            user._change_password("ReplacementPassword1!")
            reset_ran.append(True)
        return update(collection, query, change, *args, **kwargs)

    monkeypatch.setattr(Collection, "find_one_and_update", reset_before_update)
    client.post("/users/auth/login", data={"2fa_code": _totp_code(secret)})
    assert reset_ran == [True]
    with client.session_transaction() as login_session:
        assert "_user_id" not in login_session


def test_reset_after_consumption_before_session_creation_is_rejected(app, db, monkeypatch):
    client, user, secret = _pending_login(app, db)
    auth = importlib.import_module("mielenosoitukset_fi.users.BPs.auth")
    clear = auth._clear_pending_mfa_login
    login_calls = []

    def clear_then_reset():
        clear()
        user._change_password("ReplacementPassword1!")

    monkeypatch.setattr(auth, "_clear_pending_mfa_login", clear_then_reset)
    monkeypatch.setattr(auth, "login_user", lambda user: login_calls.append(user.id))
    client.post("/users/auth/login", data={"2fa_code": _totp_code(secret)})
    assert login_calls == []
    with client.session_transaction() as login_session:
        assert "_user_id" not in login_session


def test_reset_at_session_creation_revokes_the_response_cookie(app, db, monkeypatch):
    client, user, secret = _pending_login(app, db)
    auth = importlib.import_module("mielenosoitukset_fi.users.BPs.auth")
    sign_in = auth.login_user

    def sign_in_then_reset(current):
        result = sign_in(current)
        user._change_password("ReplacementPassword1!")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(auth, "login_user", sign_in_then_reset)
        response = client.post("/users/auth/login", data={"2fa_code": _totp_code(secret)})
    assert response.status_code == 302
    protected = client.get("/users/auth/api/v2/passkeys")
    assert protected.status_code == 302
    assert "/users/auth/login" in protected.headers["Location"]

    # A new login with current credentials must replace the invalid binding.
    client.post("/users/auth/login", data={
        "username": user.username, "password": "ReplacementPassword1!",
        "2fa_code": _totp_code(secret),
    })
    assert client.get("/users/auth/api/v2/passkeys").status_code == 200


def test_parallel_pending_challenge_consumption_has_one_winner(app, db):
    client, user, _secret = _pending_login(app, db)
    with client.session_transaction() as login_session:
        challenge = login_session["mfa_pending_login"]
    barrier = Barrier(2)

    def consume():
        with app.test_request_context():
            session["mfa_pending_login"] = challenge
            barrier.wait(timeout=5)
            return bool(_consume_pending_mfa_login(user))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: consume(), range(2)))
    assert sorted(outcomes) == [False, True]


def test_pending_mfa_attempt_limit_cannot_be_reset_by_cookie_replay(app, db, monkeypatch):
    client, _user, secret = _pending_login(app, db)
    old_cookie = client.get_cookie(app.config["SESSION_COOKIE_NAME"]).value
    original_verify = UserMFA.verify_token
    monkeypatch.setattr(UserMFA, "verify_token", lambda self, token: False)
    for _ in range(MFA_PENDING_LOGIN_MAX_ATTEMPTS):
        retry = app.test_client()
        retry.set_cookie(app.config["SESSION_COOKIE_NAME"], old_cookie)
        retry.post("/users/auth/login", data={"2fa_code": "000000"})
        with retry.session_transaction() as login_session:
            assert "_user_id" not in login_session
    monkeypatch.setattr(UserMFA, "verify_token", original_verify)
    retry = app.test_client()
    retry.set_cookie(app.config["SESSION_COOKIE_NAME"], old_cookie)
    retry.post("/users/auth/login", data={"2fa_code": _totp_code(secret)})
    with retry.session_transaction() as login_session:
        assert "_user_id" not in login_session


def test_verify_mfa_route_does_not_500(app, db):
    user_id = _create_mfa_user(db)
    secret = UserMFA(user_id).add_device()
    client = _client_for_user(app, user_id)
    with client.session_transaction() as session:
        session["mfa_required"] = True
    r = client.post(
        "/users/auth/verify_mfa",
        data={"token": _totp_code(secret)},
        follow_redirects=False,
    )
    assert r.status_code == 307
    assert "/users/auth/login" in r.headers["Location"]
    with client.session_transaction() as login_session:
        assert login_session["_user_id"] == str(user_id)


def test_password_login_without_javascript_renders_mfa_step(app, db):
    _client, user, secret = _pending_login(app, db)
    client = app.test_client()
    response = client.post(
        "/users/auth/login",
        data={"username": user.username, "password": TEST_PASSWORD},
        follow_redirects=True,
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'class="auth-container" id="2fa"' in page
    assert 'id="mfapass"' not in page
    with client.session_transaction() as login_session:
        assert "_user_id" not in login_session
    client.post("/users/auth/login", data={"2fa_code": _totp_code(secret)})
    with client.session_transaction() as login_session:
        assert login_session["_user_id"] == user.id


def test_legacy_mfa_flag_does_not_replace_first_factor_proof(app, db):
    user_id = _create_mfa_user(db)
    secret = UserMFA(user_id).add_device()
    client = app.test_client()
    with client.session_transaction() as login_session:
        login_session["mfa_required"] = True
    response = client.post(
        "/users/auth/verify_mfa",
        data={"token": _totp_code(secret)},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with client.session_transaction() as login_session:
        assert "_user_id" not in login_session
