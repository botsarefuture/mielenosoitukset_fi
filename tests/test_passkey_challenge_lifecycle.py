"""Challenge boundaries against real MongoDB and signed HTTP assertions."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

import pytest
from webauthn.helpers import bytes_to_base64url

from mielenosoitukset_fi.utils import webauthn_utils as webauthn
from tests import _webauthn_sim as sim
from tests.conftest import _client_for_user
from tests.test_passkeys_webauthn import ORIGIN, _elevate, _register_passkey, wapp


@pytest.fixture
def registered_key(wapp, db, seeded_data):
    owner = _client_for_user(wapp, seeded_data["user_id"])
    _elevate(owner, "UserPass1!")
    key = sim.generate_key()
    options = owner.post("/users/auth/api/v2/passkeys/register/options").get_json()["options"]
    response, credential = _register_passkey(owner, options, key)
    assert response.status_code == 200
    return key, credential["id"]


@pytest.mark.parametrize("elapsed", [299, 300, 301])
def test_login_challenge_expires_at_exact_server_deadline(
    wapp, db, seeded_data, registered_key, monkeypatch, elapsed
):
    # Keep the real Mongo TTL monitor from racing this simulated expiry clock.
    issued = datetime(2099, 1, 1, 12, 0)
    monkeypatch.setattr(webauthn, "utcnow", lambda: issued)
    client = wapp.test_client()
    options = client.post("/users/auth/api/v2/passkeys/login/options", json={}).get_json()["options"]
    challenge = db.passkey_challenges.find_one({"challenge": options["challenge"]})
    assert challenge["expires_at"] == issued + timedelta(seconds=300)
    key, credential_id = registered_key
    before = db.user_passkeys.find_one({"credential_id": credential_id})
    assertion = sim.assertion_credential_json(
        options, key, origin=ORIGIN, credential_id=credential_id, counter=0,
    )
    monkeypatch.setattr(webauthn, "utcnow", lambda: issued + timedelta(seconds=elapsed))
    response = client.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion})
    accepted = elapsed < 300
    assert response.status_code == (200 if accepted else 403)
    with client.session_transaction() as login_session:
        if accepted:
            assert login_session["_user_id"] == str(seeded_data["user_id"])
        else:
            assert "_user_id" not in login_session
    after = db.passkey_challenges.find_one({"_id": challenge["_id"]})
    assert after["used"] is accepted
    if not accepted:
        assert "Challenge" in response.get_json()["message"]
        assert db.user_passkeys.find_one({"_id": before["_id"]}) == before


@pytest.mark.parametrize("purpose", ["register", "login", "step_up"])
@pytest.mark.parametrize("bound", [False, True])
def test_challenge_purpose_is_independent_of_user_binding(wapp, db, seeded_data, purpose, bound):
    """Hold user/session/expiry fixed so only the purpose predicate can deny."""
    user_id = seeded_data["user_id"] if bound else None
    with wapp.test_request_context():
        raw = webauthn._create_challenge(user_id=user_id, purpose=purpose)
        encoded = bytes_to_base64url(raw)
        before = db.passkey_challenges.find_one({"challenge": encoded})
        for wrong_purpose in {"register", "login", "step_up"} - {purpose}:
            assert webauthn.consume_challenge(encoded, wrong_purpose, user_id) is False
            assert db.passkey_challenges.find_one({"_id": before["_id"]}) == before
        assert webauthn.consume_challenge(encoded, purpose, user_id) is True
        assert db.passkey_challenges.find_one({"_id": before["_id"]})["used"] is True


def test_simultaneous_counterless_login_has_one_challenge_winner(
    wapp, db, seeded_data, registered_key, monkeypatch
):
    first = wapp.test_client()
    options = first.post("/users/auth/api/v2/passkeys/login/options", json={}).get_json()["options"]
    second = wapp.test_client()
    cookie_name = wapp.config["SESSION_COOKIE_NAME"]
    second.set_cookie(cookie_name, first.get_cookie(cookie_name).value)
    key, credential_id = registered_key
    assertion = sim.assertion_credential_json(
        options, key, origin=ORIGIN, credential_id=credential_id, counter=0,
    )
    gate = Barrier(2)
    collection_type = type(db.passkey_challenges)
    original = collection_type.find_one_and_update

    def simultaneous_consume(collection, query, *args, **kwargs):
        if collection.name == "passkey_challenges" and query.get("challenge") == options["challenge"]:
            gate.wait(timeout=10)
        return original(collection, query, *args, **kwargs)

    monkeypatch.setattr(collection_type, "find_one_and_update", simultaneous_consume)

    def verify(client):
        response = client.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion})
        with client.session_transaction() as login_session:
            identity = login_session.get("_user_id")
        return response.status_code, identity

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(verify, client) for client in (first, second)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(results, key=lambda result: result[0]) == [
        (200, str(seeded_data["user_id"])), (403, None),
    ]
    stored = db.passkey_challenges.find_one({"challenge": options["challenge"]})
    assert stored["used"] is True
    assert stored["used_at"] is not None
    assert db.user_passkeys.find_one({"credential_id": credential_id})["sign_count"] == 0
