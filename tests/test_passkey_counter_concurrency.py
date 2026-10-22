"""Distinct challenges must not roll back credential state or revive deletion."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, local

import pytest

from mielenosoitukset_fi.utils import webauthn_utils as webauthn
from tests import _webauthn_sim as sim
from tests.test_passkey_challenge_lifecycle import registered_key
from tests.test_passkeys_webauthn import ORIGIN, wapp


@pytest.mark.parametrize("counters,expected", [
    ((2, 1), (200, 403)),
    ((1, 1), (200, 403)),
    ((1, 2), (200, 403)),
    ((0, 0), (200, 200)),
])
def test_distinct_challenges_cannot_overwrite_newer_credential_counter(
    wapp, db, seeded_data, registered_key, monkeypatch, counters, expected
):
    key, credential_id = registered_key
    clients = [wapp.test_client(), wapp.test_client()]
    options = [client.post("/users/auth/api/v2/passkeys/login/options", json={}).get_json()["options"]
               for client in clients]
    assert options[0]["challenge"] != options[1]["challenge"]
    assertions = [sim.assertion_credential_json(
        option, key, origin=ORIGIN, credential_id=credential_id, counter=count,
    ) for option, count in zip(options, counters)]
    gate, first_written, worker = Barrier(2), Event(), local()
    real_verify = webauthn.verify_authentication_response
    collection_type = type(db.user_passkeys)
    real_update = collection_type.update_one

    def verified_together(**kwargs):
        verified = real_verify(**kwargs)
        # Both signatures really pass against the same observed counter.
        assert kwargs["credential_current_sign_count"] == 0
        gate.wait(timeout=10)
        return verified

    def ordered_update(collection, query, changes, *args, **kwargs):
        if collection.name != "user_passkeys" or "sign_count" not in changes.get("$set", {}):
            return real_update(collection, query, changes, *args, **kwargs)
        if worker.index == 1:
            assert first_written.wait(timeout=10)
        try:
            return real_update(collection, query, changes, *args, **kwargs)
        finally:
            if worker.index == 0:
                first_written.set()

    monkeypatch.setattr(webauthn, "verify_authentication_response", verified_together)
    monkeypatch.setattr(collection_type, "update_one", ordered_update)

    def verify(index):
        worker.index = index
        client = clients[index]
        response = client.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertions[index]})
        with client.session_transaction() as session:
            identity = session.get("_user_id")
        return response.status_code, identity

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(verify, index) for index in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert tuple(status for status, _ in results) == expected
    for (status, identity), option in zip(results, options):
        assert identity == (str(seeded_data["user_id"]) if status == 200 else None)
        assert db.passkey_challenges.find_one({"challenge": option["challenge"]})["used"] is True
    assert db.user_passkeys.find_one({"credential_id": credential_id})["sign_count"] == counters[0]


def test_deleted_passkey_cannot_complete_previously_verified_login(
    wapp, db, registered_key, monkeypatch
):
    key, credential_id = registered_key
    client = wapp.test_client()
    options = client.post("/users/auth/api/v2/passkeys/login/options", json={}).get_json()["options"]
    assertion = sim.assertion_credential_json(
        options, key, origin=ORIGIN, credential_id=credential_id, counter=1,
    )
    collection_type = type(db.user_passkeys)
    original = collection_type.update_one

    def delete_before_commit(collection, query, changes, *args, **kwargs):
        if collection.name == "user_passkeys" and "sign_count" in changes.get("$set", {}):
            assert collection.delete_one({"credential_id": credential_id}).deleted_count == 1
        return original(collection, query, changes, *args, **kwargs)

    monkeypatch.setattr(collection_type, "update_one", delete_before_commit)
    response = client.post("/users/auth/api/v2/passkeys/login/verify", json={"credential": assertion})
    assert response.status_code == 403
    with client.session_transaction() as session:
        assert "_user_id" not in session
    assert db.user_passkeys.count_documents({"credential_id": credential_id}) == 0
    assert db.passkey_challenges.find_one({"challenge": options["challenge"]})["used"] is True
