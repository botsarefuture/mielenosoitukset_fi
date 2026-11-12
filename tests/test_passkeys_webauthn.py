"""End-to-end WebAuthn passkey tests.

These use a simulated authenticator (``tests/_webauthn_sim``) to produce real
registration and assertion credentials, so the full register → login flow is
exercised against the actual ``py-webauthn`` verifier — no mocking of the
crypto boundary.
"""

import pytest
from bson import ObjectId

from mielenosoitukset_fi.users.models import User
from tests import _webauthn_sim as sim
from tests.conftest import _cleanup_app_resources, _client_for_user
from webauthn.helpers import base64url_to_bytes

ORIGIN = "http://localhost"
RP_ID = "localhost"


@pytest.fixture
def wapp(app_factory):
    app = app_factory(WEBAUTHN_ORIGIN=ORIGIN, WEBAUTHN_RP_ID=RP_ID)
    try:
        yield app
    finally:
        _cleanup_app_resources(app)


def _elevate(client, password):
    r = client.post("/users/auth/api/v2/step-up/password", json={"password": password})
    assert r.status_code == 200, r.get_data(as_text=True)


def _register_passkey(client, options, key):
    """POST a simulated registration credential; returns credential dict."""
    credential = sim.registration_credential_json(
        options, key, origin=ORIGIN, transports=["usb"]
    )
    r = client.post(
        "/users/auth/api/v2/passkeys/register/verify",
        json={"credential": credential, "name": "Test Key"},
    )
    return r, credential


def test_passkey_register_and_login_end_to_end(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(client, "UserPass1!")

    key = sim.generate_key()

    r = client.post("/users/auth/api/v2/passkeys/register/options")
    assert r.status_code == 200, r.get_data(as_text=True)
    options = r.get_json()["options"]
    assert options["rp"]["id"] == RP_ID
    assert "challenge" in options

    r, credential = _register_passkey(client, options, key)
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["status"] == "success"

    stored = db.user_passkeys.find_one({"user_id": seeded_data["user_id"]})
    assert stored is not None
    assert stored["credential_id"] == credential["id"]
    assert stored["name"] == "Test Key"

    # register options now exclude the already-registered credential
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options2 = r.get_json()["options"]
    assert any(
        desc["id"] == credential["id"] for desc in options2.get("excludeCredentials", [])
    )

    # --- password-less login with a fresh anonymous session ---------------
    anon = wapp.test_client()
    r = anon.post("/users/auth/api/v2/passkeys/login/options", json={})
    assert r.status_code == 200, r.get_data(as_text=True)
    assertion = sim.assertion_credential_json(
        r.get_json()["options"], key, origin=ORIGIN, credential_id=credential["id"], counter=1
    )

    r = anon.post(
        "/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion}
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["status"] == "success"
    assert r.get_json()["redirect"]

    # now authenticated as alice
    r = anon.get("/users/auth/api/v2/passkeys")
    assert r.status_code == 200
    assert len(r.get_json()["passkeys"]) == 1

    # sign counter was bumped
    assert db.user_passkeys.find_one({"_id": stored["_id"]})["sign_count"] == 1


def test_passkey_login_verifies_the_assertion_bound_challenge(
    wapp, db, seeded_data
):
    """A second options request must not invalidate an earlier assertion."""
    client = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(client, "UserPass1!")
    key = sim.generate_key()
    options = client.post("/users/auth/api/v2/passkeys/register/options").get_json()[
        "options"
    ]
    response, credential = _register_passkey(client, options, key)
    assert response.status_code == 200

    anon = wapp.test_client()
    first_options = anon.post(
        "/users/auth/api/v2/passkeys/login/options", json={}
    ).get_json()["options"]
    second_options = anon.post(
        "/users/auth/api/v2/passkeys/login/options", json={}
    ).get_json()["options"]
    assert first_options["challenge"] != second_options["challenge"]

    assertion = sim.assertion_credential_json(
        first_options,
        key,
        origin=ORIGIN,
        credential_id=credential["id"],
        counter=1,
    )
    response = anon.post(
        "/users/auth/api/v2/passkeys/login/verify",
        json={"credential": assertion},
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    assert db.passkey_challenges.find_one(
        {"challenge": first_options["challenge"]}
    )["used"] is True
    assert db.passkey_challenges.find_one(
        {"challenge": second_options["challenge"]}
    )["used"] is False


def test_passkey_registration_requires_step_up(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    assert r.status_code == 403
    assert r.get_json()["error"] == "step_up_required"


def test_passkey_register_verify_without_pending_challenge_rejected(
    wapp, db, seeded_data
):
    client = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(client, "UserPass1!")
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    # burn every pending challenge server-side, then try to use one
    db.passkey_challenges.update_many({}, {"$set": {"used": True}})
    credential = sim.registration_credential_json(
        options, sim.generate_key(), origin=ORIGIN
    )
    r = client.post(
        "/users/auth/api/v2/passkeys/register/verify",
        json={"credential": credential},
    )
    assert r.status_code == 400
    assert "Challenge" in r.get_json()["message"]


def test_passkey_rejects_unknown_credential_at_login(wapp, db, seeded_data):
    key = sim.generate_key()
    anon = wapp.test_client()
    r = anon.post("/users/auth/api/v2/passkeys/login/options", json={})
    options = r.get_json()["options"]
    assertion = sim.assertion_credential_json(
        options,
        key,
        origin=ORIGIN,
        credential_id="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        counter=1,
    )
    r = anon.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion})
    assert r.status_code == 403
    with anon.session_transaction() as login_session:
        assert "_user_id" not in login_session


def test_passkey_login_requires_confirmed_account(wapp, db):
    user_id = ObjectId()
    user_doc = User.create_user(
        username="ghost", password="GhostPass1!", email="ghost@example.test"
    )
    user_doc.update({"_id": user_id, "confirmed": False, "active": True})
    db.users.insert_one(user_doc)

    client = _client_for_user(wapp, user_id)
    _elevate(client, "GhostPass1!")
    key = sim.generate_key()
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    _register_passkey(client, options, key)

    anon = wapp.test_client()
    r = anon.post("/users/auth/api/v2/passkeys/login/options", json={})
    options = r.get_json()["options"]
    stored = db.user_passkeys.find_one({"user_id": user_id})
    assertion = sim.assertion_credential_json(
        options, key, origin=ORIGIN, credential_id=stored["credential_id"], counter=1
    )
    r = anon.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion})
    assert r.status_code == 403
    assert "sähköposti" in r.get_json()["message"].lower()
    with anon.session_transaction() as login_session:
        assert "_user_id" not in login_session


def test_login_options_respect_username_scope(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(client, "UserPass1!")
    key = sim.generate_key()
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    r, credential = _register_passkey(client, options, key)
    assert r.status_code == 200

    anon = wapp.test_client()
    r = anon.post(
        "/users/auth/api/v2/passkeys/login/options", json={"username": "alice"}
    )
    data = r.get_json()
    allow = data["options"].get("allowCredentials", [])
    assert any(desc["id"] == credential["id"] for desc in allow)

    # unknown username → no credential-scoped restriction
    r = anon.post(
        "/users/auth/api/v2/passkeys/login/options", json={"username": "nobody"}
    )
    assert r.get_json()["options"].get("allowCredentials") in (None, [])


def test_passkey_duplicate_registration_rejected(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(client, "UserPass1!")
    key = sim.generate_key()
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    r, credential = _register_passkey(client, options, key)
    assert r.status_code == 200

    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    # same credential id as the first registration → server must reject
    duplicate = sim.registration_credential_json(
        options,
        key,
        origin=ORIGIN,
        credential_id=base64url_to_bytes(credential["id"]),
    )
    r = client.post(
        "/users/auth/api/v2/passkeys/register/verify",
        json={"credential": duplicate},
    )
    assert r.status_code == 400
    assert "jo rekisteröity" in r.get_json()["message"]


def test_passkey_list_rename_delete(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(client, "UserPass1!")
    key = sim.generate_key()
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    _register_passkey(client, options, key)

    r = client.get("/users/auth/api/v2/passkeys")
    passkeys = r.get_json()["passkeys"]
    assert len(passkeys) == 1
    passkey_id = passkeys[0]["id"]

    # rename requires elevation
    bare = _client_for_user(wapp, seeded_data["user_id"])
    r = bare.post(
        "/users/auth/api/v2/passkeys/rename",
        json={"id": passkey_id, "name": "Hacked"},
    )
    assert r.status_code == 403

    r = client.post(
        "/users/auth/api/v2/passkeys/rename",
        json={"id": passkey_id, "name": "Laptop"},
    )
    assert r.status_code == 200
    assert db.user_passkeys.find_one({"_id": ObjectId(passkey_id)})["name"] == "Laptop"

    r = client.post(
        "/users/auth/api/v2/passkeys/rename",
        json={"id": passkey_id, "name": "   "},
    )
    assert r.status_code == 400

    r = client.post(
        "/users/auth/api/v2/passkeys/rename",
        json={"id": passkey_id, "name": "  Security key  "},
    )
    assert r.status_code == 200
    renamed_passkey = db.user_passkeys.find_one({"_id": ObjectId(passkey_id)})
    assert renamed_passkey["name"] == "Security key"

    r = client.post("/users/auth/api/v2/passkeys/delete", json={"id": str(ObjectId())})
    assert r.status_code == 404

    r = client.post("/users/auth/api/v2/passkeys/delete", json={"id": passkey_id})
    assert r.status_code == 200
    assert db.user_passkeys.count_documents({"user_id": seeded_data["user_id"]}) == 0


def test_passkeys_are_isolated_between_users(wapp, db, seeded_data):
    client = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(client, "UserPass1!")
    key = sim.generate_key()
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    _register_passkey(client, r.get_json()["options"], key)

    other = _client_for_user(wapp, seeded_data["friend_id"])
    r = other.get("/users/auth/api/v2/passkeys")
    assert r.get_json()["passkeys"] == []

    identity = wapp.test_client()
    r = identity.post(
        "/users/auth/api/v2/step-up/options", follow_redirects=True
    )
    assert r.status_code == 200  # redirects to the login page
    assert b"Mielenosoitukset" in r.data  # no elevation API JSON leaked


@pytest.mark.parametrize("action", ["rename", "delete"])
def test_elevated_passkey_mutations_are_owner_scoped(wapp, db, seeded_data, action):
    owner = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(owner, "UserPass1!")
    options = owner.post("/users/auth/api/v2/passkeys/register/options").get_json()["options"]
    response, credential = _register_passkey(owner, options, sim.generate_key())
    assert response.status_code == 200
    before = db.user_passkeys.find_one({"credential_id": credential["id"]})

    other = _client_for_user(wapp, seeded_data["friend_id"])
    _elevate(other, "FriendPass1!")
    payload = {"id": str(before["_id"]), "name": "Foreign rename"}
    response = other.post(f"/users/auth/api/v2/passkeys/{action}", json=payload)
    assert response.status_code == 404
    assert response.get_json()["status"] == "error"
    assert db.user_passkeys.find_one({"_id": before["_id"]}) == before

    # The same valid operation works for the elevated owner, not just nobody.
    response = owner.post(f"/users/auth/api/v2/passkeys/{action}", json=payload)
    assert response.status_code == 200
    after = db.user_passkeys.find_one({"_id": before["_id"]})
    if action == "delete":
        assert after is None
    else:
        assert after == {**before, "name": payload["name"]}


@pytest.mark.parametrize("mismatch", ["origin", "rp_id"])
def test_signed_passkey_assertion_rejects_wrong_relying_party(
    wapp, db, seeded_data, mismatch
):
    owner = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(owner, "UserPass1!")
    key = sim.generate_key()
    options = owner.post("/users/auth/api/v2/passkeys/register/options").get_json()["options"]
    response, credential = _register_passkey(owner, options, key)
    assert response.status_code == 200
    before = db.user_passkeys.find_one({"credential_id": credential["id"]})

    anon = wapp.test_client()
    options = anon.post("/users/auth/api/v2/passkeys/login/options", json={}).get_json()["options"]
    if mismatch == "rp_id":
        options = {**options, "rpId": "other.example.test"}
    assertion = sim.assertion_credential_json(
        options, key, origin="https://other.example.test" if mismatch == "origin" else ORIGIN,
        credential_id=credential["id"], counter=1,
    )
    response = anon.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion})
    assert response.status_code == 403
    assert response.get_json()["message"] == "Virheellinen vahvistusvastaus."
    with anon.session_transaction() as login_session:
        assert "_user_id" not in login_session
    assert db.user_passkeys.find_one({"_id": before["_id"]}) == before
    assert db.passkey_challenges.find_one({"challenge": options["challenge"]})["used"] is True

    # Rejection must be about RP/origin: the same key with fresh valid options works.
    options = anon.post("/users/auth/api/v2/passkeys/login/options", json={}).get_json()["options"]
    assertion = sim.assertion_credential_json(
        options, key, origin=ORIGIN, credential_id=credential["id"], counter=1,
    )
    assert anon.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion}).status_code == 200
    with anon.session_transaction() as login_session:
        assert login_session["_user_id"] == str(seeded_data["user_id"])


def test_passkey_login_challenge_cannot_cross_browser_sessions(wapp, db, seeded_data):
    owner = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(owner, "UserPass1!")
    key = sim.generate_key()
    options = owner.post("/users/auth/api/v2/passkeys/register/options").get_json()["options"]
    response, credential = _register_passkey(owner, options, key)
    assert response.status_code == 200
    before = db.user_passkeys.find_one({"credential_id": credential["id"]})
    original, foreign = wapp.test_client(), wapp.test_client()
    options = original.post("/users/auth/api/v2/passkeys/login/options", json={}).get_json()["options"]
    assertion = sim.assertion_credential_json(
        options, key, origin=ORIGIN, credential_id=credential["id"], counter=1,
    )
    response = foreign.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion})
    assert response.status_code == 403
    with foreign.session_transaction() as login_session:
        assert "_user_id" not in login_session
    assert db.passkey_challenges.find_one({"challenge": options["challenge"]})["used"] is False
    assert db.user_passkeys.find_one({"_id": before["_id"]}) == before
    assert original.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion}).status_code == 200
    with original.session_transaction() as login_session:
        assert login_session["_user_id"] == str(seeded_data["user_id"])


def test_consumed_passkey_assertion_cannot_authenticate_again(wapp, db, seeded_data):
    owner = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(owner, "UserPass1!")
    key = sim.generate_key()
    options = owner.post("/users/auth/api/v2/passkeys/register/options").get_json()["options"]
    response, credential = _register_passkey(owner, options, key)
    assert response.status_code == 200
    anon = wapp.test_client()
    options = anon.post("/users/auth/api/v2/passkeys/login/options", json={}).get_json()["options"]
    assertion = sim.assertion_credential_json(
        options, key, origin=ORIGIN, credential_id=credential["id"], counter=0,
    )
    # Counterless authenticators are valid; counter rejection must not mask replay.
    assert anon.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion}).status_code == 200
    with anon.session_transaction() as login_session:
        assert login_session["_user_id"] == str(seeded_data["user_id"])
        # Preserve the challenge-session binding to isolate single-use enforcement.
        login_session.pop("_user_id")
    before = db.user_passkeys.find_one({"credential_id": credential["id"]})
    response = anon.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion})
    assert response.status_code == 403
    assert "Challenge" in response.get_json()["message"]
    with anon.session_transaction() as login_session:
        assert "_user_id" not in login_session
    assert db.user_passkeys.find_one({"_id": before["_id"]}) == before


@pytest.mark.parametrize("status", [{"active": False}, {"banned": True}])
def test_passkey_rejects_disabled_accounts(wapp, db, status):
    """A valid cryptographic assertion cannot bypass disabled account status."""
    user_id = ObjectId()
    suffix = str(user_id)[-8:]
    user_doc = User.create_user(
        username=f"ghost-{suffix}", password="GhostPass1!", email=f"ghost-{suffix}@example.test"
    )
    user_doc.update({"_id": user_id, "confirmed": True, "active": True})
    db.users.insert_one(user_doc)

    client = _client_for_user(wapp, user_id)
    _elevate(client, "GhostPass1!")
    key = sim.generate_key()
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    _register_passkey(client, r.get_json()["options"], key)
    db.users.update_one({"_id": user_id}, {"$set": status})

    anon = wapp.test_client()
    r = anon.post("/users/auth/api/v2/passkeys/login/options", json={})
    assertion = sim.assertion_credential_json(
        r.get_json()["options"],
        key,
        origin=ORIGIN,
        credential_id=db.user_passkeys.find_one({"user_id": user_id})["credential_id"],
        counter=1,
    )
    r = anon.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion})
    assert r.status_code == 403
    assert r.get_json()["status"] == "error"
    with anon.session_transaction() as login_session:
        assert "_user_id" not in login_session
