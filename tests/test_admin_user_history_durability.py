"""User events survive projection failures and attribute only their own write."""

from concurrent.futures import ThreadPoolExecutor
import inspect
from threading import Barrier
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from pymongo.errors import AutoReconnect, OperationFailure

from tests.conftest import _client_for_user
from tests.test_admin_user_history import _profile


@pytest.mark.parametrize("endpoint", ["edit_user", "save_user"])
def test_concurrent_profile_writes_have_one_attributed_winner(app, db, seeded_data, monkeypatch, endpoint):
    target = seeded_data["user_id"]
    db.users.update_one({"_id": seeded_data["friend_id"]}, {"$set": {
        "role": "admin", "global_permissions": ["EDIT_USER"],
    }})
    original = type(db.users).find_one_and_update
    gate = Barrier(2)

    def synchronized(self, query, update, *args, **kwargs):
        if self.name == "users" and "$push" in update:
            gate.wait(timeout=10)
        return original(self, query, update, *args, **kwargs)

    monkeypatch.setattr(type(db.users), "find_one_and_update", synchronized)
    document = db.users.find_one({"_id": target})
    actors = [seeded_data["admin_id"], seeded_data["friend_id"]]

    def submit(index):
        client = _client_for_user(app, actors[index])
        return client.post(f"/admin/user/{endpoint}/{target}", data=_profile(
            document, displayname=f"Writer {index}",
        )).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, range(2)))
    assert sorted(statuses) == [302, 409]
    winner = statuses.index(302)
    stored = db.users.find_one({"_id": target})
    events = list(db.admin_logs.find({"event": "user_details_changed", "entity_id": str(target)}))
    assert len(events) == 1
    assert events[0]["actor_id"] == str(actors[winner])
    assert events[0]["old_state"]["displayname"] == document.get("displayname", "")
    assert events[0]["new_state"]["displayname"] == stored["displayname"] == f"Writer {winner}"


def test_event_does_not_reload_a_later_writers_profile(app, admin_client, db, seeded_data, monkeypatch):
    namespace = inspect.unwrap(app.view_functions["admin_user.edit_user"]).__globals__

    target = seeded_data["user_id"]
    original = namespace["flush_user_history"]

    def later_write(database, user_id):
        doc = database.users.find_one({"_id": user_id})
        if doc.get("_admin_history_pending"):
            database.users.update_one({"_id": user_id}, {"$set": {"displayname": "Later writer"}})
        return original(database, user_id)

    monkeypatch.setitem(namespace, "flush_user_history", later_write)
    document = db.users.find_one({"_id": target})
    assert admin_client.post(f"/admin/user/edit_user/{target}", data=_profile(
        document, displayname="This request's write",
    )).status_code == 302
    event = db.admin_logs.find_one({"entity_id": str(target), "event": "user_details_changed"})
    assert event["new_state"]["displayname"] == "This request's write"
    assert db.users.find_one({"_id": target})["displayname"] == "Later writer"


@pytest.mark.parametrize("failure", ["admin_logs", "super_audit_logs", "acknowledgement"])
def test_failed_projection_keeps_event_and_retry_is_idempotent(admin_client, db, seeded_data, monkeypatch, failure):
    target = seeded_data["user_id"]
    original = type(db.users).update_one

    def unavailable(self, query, update, *args, **kwargs):
        projected = "$setOnInsert" in update and self.name in {"admin_logs", "super_audit_logs"}
        if projected and (self.name == failure or failure == "acknowledgement" and self.name == "admin_logs"):
            if failure == "acknowledgement":
                original(self, query, update, *args, **kwargs)
            raise AutoReconnect("synthetic projection failure")
        return original(self, query, update, *args, **kwargs)

    document = db.users.find_one({"_id": target})
    with monkeypatch.context() as scoped:
        scoped.setattr(type(db.users), "update_one", unavailable)
        assert admin_client.post(f"/admin/user/edit_user/{target}", data=_profile(
            document, displayname="Durable updated name",
        )).status_code == 302
    saved = db.users.find_one({"_id": target})
    assert saved["displayname"] == "Durable updated name"
    assert len(saved["_admin_history_pending"]) == 1
    event = saved["_admin_history_pending"][0]
    assert event["actor_id"] == str(seeded_data["admin_id"])
    assert event["old_state"]["displayname"] == document.get("displayname", "")
    assert event["new_state"]["displayname"] == saved["displayname"]
    assert "password_hash" not in repr(event)
    # A fresh authorized read performs recovery with the original event identity.
    assert admin_client.get(f"/admin/user/history/{target}").status_code == 200
    assert admin_client.get(f"/admin/user/history/{target}").status_code == 200
    assert db.users.find_one({"_id": target})["_admin_history_pending"] == []
    assert db.admin_logs.count_documents({"_id": event["_id"]}) == 1
    assert db.super_audit_logs.count_documents({"_id": event["_id"]}) == 1
    assert db.admin_logs.find_one({"_id": event["_id"]})["actor"] == event["actor"]


@pytest.mark.parametrize("operation", ["profile", "create", "reset", "scope"])
def test_source_write_failure_cannot_lose_its_event(admin_client, db, seeded_data, monkeypatch, operation):
    target = seeded_data["user_id"]
    original_update = type(db.users).find_one_and_update
    original_insert = type(db.users).insert_one

    def fail_update(self, query, update, *args, **kwargs):
        if "$push" in update:
            raise OperationFailure("synthetic atomic write rejection")
        return original_update(self, query, update, *args, **kwargs)

    def fail_insert(self, document, *args, **kwargs):
        if document.get("_admin_history_pending"):
            raise OperationFailure("synthetic atomic insert rejection")
        return original_insert(self, document, *args, **kwargs)

    before = db.users.find_one({"_id": target})
    monkeypatch.setattr(type(db.users), "find_one_and_update", fail_update)
    monkeypatch.setattr(type(db.users), "insert_one", fail_insert)
    with pytest.raises(OperationFailure):
        if operation == "create":
            admin_client.post("/admin/user/create_user", json={
                "username": "atomic-create", "email": "atomic-create@example.test",
            })
        elif operation == "reset":
            admin_client.post("/admin/user/api/force_password_change/", json={"user_id": str(target)})
        else:
            payload = _profile(before)
            if operation == "profile":
                payload["displayname"] = "Must not persist"
            else:
                payload.update({"admin_scope_cities[]": ["helsinki"],
                                "admin_scope_permissions[city][]": ["EDIT_DEMO"]})
            admin_client.post(f"/admin/user/edit_user/{target}", data=payload)
    assert db.users.find_one({"_id": target}) == before
    assert db.users.count_documents({"username": "atomic-create"}) == 0
    assert db.admin_scope_grants.count_documents({"user_id": target}) == 0
    assert db.admin_logs.count_documents({"entity_id": str(target), "event": "user_details_changed"}) == 0


def test_full_pending_outbox_rejects_an_unrecordable_change(app, admin_client, db, seeded_data, monkeypatch):
    namespace = inspect.unwrap(app.view_functions["admin_user.edit_user"]).__globals__

    target = seeded_data["user_id"]
    document = db.users.find_one({"_id": target})
    # Keep delivery unavailable while exercising the actual bounded atomic write.
    monkeypatch.setitem(namespace, "flush_user_history", lambda database, user_id: False)
    db.users.update_one({"_id": target}, {"$set": {"_admin_history_pending": [{"synthetic": True}] * 100}})
    assert admin_client.post(f"/admin/user/edit_user/{target}", data=_profile(
        document, displayname="Cannot change without audit capacity",
    )).status_code == 409
    saved = db.users.find_one({"_id": target})
    assert saved["displayname"] == document.get("displayname", "")
    assert len(saved["_admin_history_pending"]) == 100


@pytest.mark.parametrize("revoke", [False, True])
def test_scope_outbox_survives_projection_failure(admin_client, db, seeded_data, monkeypatch, revoke):
    target = seeded_data["user_id"]
    endpoint = f"/admin/user/edit_user/{target}"
    grant = {"admin_scope_cities[]": ["helsinki"], "admin_scope_permissions[city][]": ["EDIT_DEMO"]}
    if revoke:
        assert admin_client.post(endpoint, data=_profile(db.users.find_one({"_id": target}), **grant)).status_code == 302
    original = type(db.users).update_one

    def unavailable(self, query, update, *args, **kwargs):
        if self.name == "admin_logs" and "$setOnInsert" in update:
            raise AutoReconnect("synthetic scope projection failure")
        return original(self, query, update, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(type(db.users), "update_one", unavailable)
        payload = _profile(db.users.find_one({"_id": target}), **({} if revoke else grant))
        assert admin_client.post(endpoint, data=payload).status_code == 302
    stored = db.admin_scope_grants.find_one({"user_id": target})
    assert bool(stored.get("revoked_at")) is revoke
    entry = stored["_admin_history_pending"][0]
    assert entry["new_state"]["city_scope_keys"] == ([] if revoke else ["helsinki"])
    assert admin_client.get(f"/admin/user/history/{target}").status_code == 200
    assert db.admin_scope_grants.find_one({"_id": stored["_id"]})["_admin_history_pending"] == []
    assert db.admin_logs.count_documents({"_id": entry["_id"]}) == 1


@pytest.mark.parametrize("operation", ["create", "reset"])
def test_creation_and_reset_outbox_survive_projection_failure(admin_client, db, seeded_data, monkeypatch, operation):
    original = type(db.users).update_one

    def unavailable(self, query, update, *args, **kwargs):
        if self.name == "admin_logs" and "$setOnInsert" in update:
            raise AutoReconnect("synthetic creation/reset projection failure")
        return original(self, query, update, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(type(db.users), "update_one", unavailable)
        if operation == "create":
            assert admin_client.post("/admin/user/create_user", json={
                "username": "durable-created", "email": "durable-created@example.test",
            }).status_code == 302
            saved = db.users.find_one({"username": "durable-created"})
        else:
            target = seeded_data["user_id"]
            assert admin_client.post("/admin/user/api/force_password_change/", json={"user_id": str(target)}).status_code == 200
            saved = db.users.find_one({"_id": target})
    assert saved["forced_pwd_reset"] is True
    entry = saved["_admin_history_pending"][0]
    assert entry["event"] == ("user_created" if operation == "create" else "user_password_reset_required")
    assert "password_hash" not in repr(entry)
    assert admin_client.get(f"/admin/user/history/{saved['_id']}").status_code == 200
    assert db.admin_logs.count_documents({"_id": entry["_id"]}) == 1


@pytest.mark.parametrize("locale,expected", [
    ("fi", "Muutoshistorian välitys on kesken."),
    ("en", "Change history delivery is pending."),
    ("sv", "Leveransen av ändringshistoriken väntar."),
])
def test_deletion_cannot_drop_pending_history_or_reuse_fresh_auth(app, admin_client, db, seeded_data, monkeypatch, locale, expected):
    app.config.update(BABEL_PUBLIC_LOCALES=["fi", "en", "sv"])
    with admin_client.session_transaction() as session:
        session["locale"] = locale
    target = seeded_data["user_id"]
    original = type(db.users).update_one

    def unavailable(self, query, update, *args, **kwargs):
        if self.name == "admin_logs" and "$setOnInsert" in update:
            raise AutoReconnect("synthetic delivery outage during deletion")
        return original(self, query, update, *args, **kwargs)

    def fresh_proof():
        assert admin_client.post("/users/auth/api/v2/step-up/fresh/options", json={
            "action": "delete_user", "target_id": str(target),
        }).status_code == 200
        response = admin_client.post("/users/auth/api/v2/step-up/fresh/password", json={
            "password": "AdminPass1!",
        })
        assert response.status_code == 200
        return response.get_json()["fresh_step_up_token"]

    with monkeypatch.context() as scoped:
        scoped.setattr(type(db.users), "update_one", unavailable)
        assert admin_client.post(f"/admin/user/edit_user/{target}", data=_profile(
            db.users.find_one({"_id": target}), displayname="Retain this recorded change",
        )).status_code == 302
        event = db.users.find_one({"_id": target})["_admin_history_pending"][0]
        token = fresh_proof()
        failed = admin_client.post("/admin/user/delete_user", json={
            "user_id": str(target), "fresh_step_up_token": token,
        })
        assert failed.status_code == 503
        assert failed.is_json and failed.get_json()["status"] == "ERROR"
        assert failed.get_json()["message"].startswith(expected)
        assert db.users.find_one({"_id": target})["_admin_history_pending"][0]["_id"] == event["_id"]
    assert admin_client.get(f"/admin/user/history/{target}").status_code == 200
    assert admin_client.post("/admin/user/delete_user", json={
        "user_id": str(target), "fresh_step_up_token": token,
    }).status_code == 403
    assert admin_client.post("/admin/user/delete_user", json={
        "user_id": str(target), "fresh_step_up_token": fresh_proof(),
    }).status_code == 200
    assert db.users.find_one({"_id": target}) is None
    assert db.admin_logs.count_documents({"_id": event["_id"]}) == 1


@pytest.mark.parametrize("json_mode", [False, True])
@pytest.mark.parametrize("locale,expected", [
    ("fi", "Käyttäjää muutettiin samanaikaisesti."),
    ("en", "The user was changed concurrently."),
    ("sv", "Användaren ändrades samtidigt."),
])
def test_delete_conflict_returns_matching_response_format(app, admin_client, db, seeded_data, monkeypatch, json_mode, locale, expected):
    app.config.update(BABEL_PUBLIC_LOCALES=["fi", "en", "sv"])
    with admin_client.session_transaction() as session:
        session["locale"] = locale
    target = seeded_data["user_id"]
    assert admin_client.post("/users/auth/api/v2/step-up/fresh/options", json={
        "action": "delete_user", "target_id": str(target),
    }).status_code == 200
    proof = admin_client.post("/users/auth/api/v2/step-up/fresh/password", json={
        "password": "AdminPass1!",
    })
    assert proof.status_code == 200
    token = proof.get_json()["fresh_step_up_token"]
    original = type(db.users).delete_one
    event = {"_id": ObjectId(), "event": "user_details_changed", "entity_type": "user",
             "entity_id": str(target), "actor_id": str(seeded_data["admin_id"]),
             "actor": {"username": "admin"}, "timestamp": datetime.now(timezone.utc),
             "old_state": {}, "new_state": {"displayname": "Concurrent change"}}

    def interleave(self, query, *args, **kwargs):
        if self.name == "users" and query.get("_id") == target:
            self.update_one({"_id": target}, {"$set": {"displayname": "Concurrent change"},
                                             "$push": {"_admin_history_pending": event}})
        return original(self, query, *args, **kwargs)

    monkeypatch.setattr(type(db.users), "delete_one", interleave)
    payload = {"user_id": str(target), "fresh_step_up_token": token}
    failed = admin_client.post("/admin/user/delete_user", **({"json": payload} if json_mode else {"data": payload}))
    assert failed.status_code == 409
    if json_mode:
        assert failed.is_json and failed.get_json()["status"] == "ERROR"
        assert failed.get_json()["message"].startswith(expected)
    else:
        assert not failed.is_json
        assert "text/html" in failed.content_type
    saved = db.users.find_one({"_id": target})
    assert saved["displayname"] == "Concurrent change"
    assert saved["_admin_history_pending"][0]["_id"] == event["_id"]
    assert admin_client.post("/admin/user/delete_user", json=payload).status_code == 403
