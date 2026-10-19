"""Content rollback must not replay authority or moderation from history."""

from copy import deepcopy
from html.parser import HTMLParser
from inspect import unwrap

import pytest
from bson import ObjectId

from tests.conftest import _client_for_user
from tests.test_city_scoped_admin import _create_scoped_admin
from tests.test_demo_decision_service import _capture_decision_email


def _rollback(client, history_id):
    with client.session_transaction() as session:
        session["demo_rollback_csrf_token"] = "synthetic-rollback-csrf"
    return client.post(f"/admin/demo/rollback_demo/{history_id}", data={
        "csrf_token": "synthetic-rollback-csrf",
    })


def _patch_demo_handler(monkeypatch, client, endpoint, name, replacement):
    # The app also supports historical import aliases. Patch the globals of
    # the function actually registered in this app, not a second module copy.
    handler = unwrap(client.application.view_functions[endpoint])
    assert name in handler.__globals__
    monkeypatch.setitem(handler.__globals__, name, replacement)


def _history_outage(monkeypatch, db, stage):
    control = {"active": True}
    collection_type = type(db.demo_edit_history)
    original_update = collection_type.update_one
    original_insert = collection_type.insert_one

    def update(collection, query, changes, *args, **kwargs):
        if control["active"]:
            if stage == "projection" and collection.name == "demo_edit_history" and kwargs.get("upsert"):
                raise RuntimeError("synthetic history outage")
            if stage == "cleanup" and collection.name == "demonstrations" and "_pending_rollback_history" in changes.get("$unset", {}):
                raise RuntimeError("synthetic cleanup outage")
        return original_update(collection, query, changes, *args, **kwargs)

    def insert(collection, *args, **kwargs):
        if control["active"] and stage == "projection" and collection.name == "demo_edit_history":
            raise RuntimeError("synthetic history outage")
        return original_insert(collection, *args, **kwargs)

    monkeypatch.setattr(collection_type, "update_one", update)
    monkeypatch.setattr(collection_type, "insert_one", insert)
    return control


@pytest.mark.parametrize("stage", ["projection", "cleanup"])
def test_rollback_history_failure_retains_exact_event_and_retry_is_idempotent(
    admin_client, db, seeded_data, monkeypatch, stage
):
    demo_id, history_id = seeded_data["demo_id"], seeded_data["history_id"]
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Durably restored title"},
    }})
    before = db.demonstrations.find_one({"_id": demo_id})
    outage = _history_outage(monkeypatch, db, stage)
    assert _rollback(admin_client, history_id).status_code == 503
    committed = db.demonstrations.find_one({"_id": demo_id})
    receipt = committed.pop("_pending_rollback_history")
    assert committed["title"] == "Durably restored title"
    assert receipt["old_demo"] == before
    assert receipt["new_demo"] == committed
    assert receipt["edited_by"] == str(seeded_data["admin_id"])
    assert receipt["rollbacked_from"] == history_id
    assert "_pending_rollback_history" not in receipt["old_demo"]
    assert "_pending_rollback_history" not in receipt["new_demo"]
    assert _rollback(admin_client, history_id).status_code == 503
    assert db.demonstrations.find_one({"_id": demo_id})["_pending_rollback_history"] == receipt
    outage["active"] = False
    for _ in range(2):
        assert _rollback(admin_client, history_id).status_code == 302
    assert db.demonstrations.find_one({"_id": demo_id}) == committed
    assert db.demo_edit_history.find_one({"_id": receipt["_id"]}) == receipt
    assert db.demo_edit_history.count_documents({"rollbacked_from": history_id}) == 1


def test_authorized_history_read_recovers_pending_rollback_only_after_scope_check(
    admin_client, user_client, db, seeded_data, monkeypatch
):
    demo_id, history_id = seeded_data["demo_id"], seeded_data["history_id"]
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Read-recovered rollback"},
    }})
    outage = _history_outage(monkeypatch, db, "projection")
    assert _rollback(admin_client, history_id).status_code == 503
    pending = db.demonstrations.find_one({"_id": demo_id})
    outage["active"] = False
    assert user_client.get(f"/admin/demo/edit_history/{demo_id}").status_code == 403
    assert db.demonstrations.find_one({"_id": demo_id}) == pending
    assert admin_client.get(f"/admin/demo/edit_history/{demo_id}").status_code == 200
    assert "_pending_rollback_history" not in db.demonstrations.find_one({"_id": demo_id})
    assert db.demo_edit_history.find_one({"_id": pending["_pending_rollback_history"]["_id"]}) == pending["_pending_rollback_history"]


def test_rollback_pipeline_preserves_literal_dollar_prefixed_content(admin_client, db, seeded_data):
    demo_id, history_id = seeded_data["demo_id"], seeded_data["history_id"]
    content = {"title": "$title", "tags": ["$tag"], "translations": {"fi": {"title": "$translated"}}}
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {"old_demo": content}})
    assert _rollback(admin_client, history_id).status_code == 302
    after = db.demonstrations.find_one({"_id": demo_id})
    assert all(after[key] == value for key, value in content.items())
    entry = db.demo_edit_history.find_one({"rollbacked_from": history_id})
    assert entry["new_demo"] == after


def test_demo_read_apis_do_not_expose_pending_rollback_receipts(
    app_factory, admin_client, db, seeded_data
):
    from tests.test_admin_mcp import _mcp_client, _mcp_headers, _rpc

    demo_id = seeded_data["demo_id"]
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {
        "_pending_rollback_history": {"old_demo": {"title": "PRIVATE RECEIPT"}},
    }})
    response = admin_client.get(f"/api/admin/demonstrations/{demo_id}")
    assert response.status_code == 200
    assert response.get_json()["title"]
    assert "_pending_rollback_history" not in response.get_json()
    client, token, _ = _mcp_client(app_factory, seeded_data)
    response = client.post("/api/admin/mcp", headers=_mcp_headers(token), json=_rpc(
        "tools/call", {"name": "get_demo", "arguments": {"demo_id": str(demo_id)}}
    ))
    assert response.status_code == 200
    payload = response.get_json()["result"]["structuredContent"]
    assert payload["title"]
    assert "_pending_rollback_history" not in payload
    assert "PRIVATE RECEIPT" not in response.get_data(as_text=True)


@pytest.mark.parametrize("action", ["delete", "merge-primary", "merge-secondary"])
def test_destructive_admin_actions_cannot_drop_pending_rollback(
    admin_client, db, seeded_data, monkeypatch, action
):
    demo_id, history_id = seeded_data["demo_id"], seeded_data["history_id"]
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Protected pending restore"},
    }})
    outage = _history_outage(monkeypatch, db, "projection")
    assert _rollback(admin_client, history_id).status_code == 503
    before = list(db.demonstrations.find({}).sort("_id", 1))
    if action == "delete":
        response = admin_client.post("/admin/demo/delete_demo", data={"demo_id": str(demo_id)})
    else:
        other_id = seeded_data["pending_demo_id"]
        response = admin_client.post("/admin/demo/merge", data={
            "demo_ids": [str(demo_id), str(other_id)],
            "primary_demo_id": str(demo_id if action == "merge-primary" else other_id),
        })
    assert response.status_code == 503
    assert list(db.demonstrations.find({}).sort("_id", 1)) == before
    outage["active"] = False
    from mielenosoitukset_fi.demonstrations.rollback import flush_rollback_history

    assert flush_rollback_history(db, demo_id) is True
    receipt = next(row for row in before if row["_id"] == demo_id)["_pending_rollback_history"]
    assert db.demo_edit_history.find_one({"_id": receipt["_id"]}) == receipt


def test_recurring_cleanup_retains_pending_rollback_until_delivery(
    admin_client, db, seeded_data, monkeypatch
):
    from mielenosoitukset_fi.scripts import repeat_v2

    demo_id, history_id = seeded_data["demo_id"], seeded_data["history_id"]
    parent = {"_id": ObjectId()}
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"parent": parent["_id"]}})
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Pending invalid recurring child"},
    }})
    outage = _history_outage(monkeypatch, db, "projection")
    assert _rollback(admin_client, history_id).status_code == 503
    before = db.demonstrations.find_one({"_id": demo_id})
    monkeypatch.setattr(repeat_v2, "db", db)
    monkeypatch.setattr(repeat_v2, "demonstrations_collection", db.demonstrations)
    monkeypatch.setattr(repeat_v2, "DRY_RUN", False)
    monkeypatch.setattr(repeat_v2, "runtime_actions", [])
    repeat_v2.remove_invalid_child_demonstrations(parent, [], None)
    assert db.demonstrations.find_one({"_id": demo_id}) == before
    assert repeat_v2.runtime_actions == []
    outage["active"] = False
    repeat_v2.remove_invalid_child_demonstrations(parent, [], None)
    assert db.demonstrations.find_one({"_id": demo_id}) is None
    receipt = before["_pending_rollback_history"]
    assert db.demo_edit_history.find_one({"_id": receipt["_id"]}) == receipt
    assert [action["action"] for action in repeat_v2.runtime_actions] == ["delete"]


def test_delete_conflict_does_not_record_successful_deletion(
    admin_client, db, seeded_data, monkeypatch
):
    demo_id = seeded_data["demo_id"]
    before = db.demonstrations.find_one({"_id": demo_id})
    history_count = db.demo_edit_history.count_documents({})
    collection_type = type(db.demonstrations)
    original = collection_type.find_one_and_delete
    receipt = {"_id": ObjectId(), "demo_id": str(demo_id)}

    def interleave(collection, query, *args, **kwargs):
        if collection.name == "demonstrations" and query.get("_id") == demo_id:
            collection.update_one({"_id": demo_id}, {"$set": {"_pending_rollback_history": receipt}})
        return original(collection, query, *args, **kwargs)

    monkeypatch.setattr(collection_type, "find_one_and_delete", interleave)
    response = admin_client.post("/admin/demo/delete_demo", data={"demo_id": str(demo_id)})
    assert response.status_code == 409
    assert db.demonstrations.find_one({"_id": demo_id}) == {**before, "_pending_rollback_history": receipt}
    assert db.demo_edit_history.count_documents({}) == history_count
    assert db.demo_audit_logs.count_documents({"action": "delete_demo"}) == 0


@pytest.mark.parametrize("failure", ["none", "raise", "database"])
def test_delete_history_failure_retains_exact_durable_recovery_copy(
    admin_client, db, seeded_data, monkeypatch, failure
):
    demo_id = seeded_data["demo_id"]
    before = db.demonstrations.find_one({"_id": demo_id})
    if failure == "database":
        collection_type = type(db.demo_edit_history)
        original = collection_type.insert_one

        def fail_insert(collection, *args, **kwargs):
            if collection.name == "demo_edit_history":
                raise RuntimeError("synthetic history insert outage")
            return original(collection, *args, **kwargs)

        monkeypatch.setattr(collection_type, "insert_one", fail_insert)
    else:
        def fail(*args, **kwargs):
            if failure == "raise":
                raise RuntimeError("synthetic history adapter outage")
            return None

        _patch_demo_handler(monkeypatch, admin_client, "admin_demo.delete_demo", "record_demo_change", fail)
    response = admin_client.post("/admin/demo/delete_demo", data={"demo_id": str(demo_id)})
    assert response.status_code == 503
    assert db.demonstrations.find_one({"_id": demo_id}) is None
    backup = db.demo_delete_backups.find_one({"demo_id": str(demo_id)})
    assert backup["preimage"] == before
    assert backup["actor_id"] == str(seeded_data["admin_id"])
    assert backup["phase"] == "history_pending" and backup["state"] == "incomplete"


def test_delete_snapshot_conflict_and_retry_record_actual_latest_document(
    admin_client, db, seeded_data, monkeypatch
):
    demo_id = seeded_data["demo_id"]
    collection_type = type(db.demonstrations)
    original = collection_type.find_one_and_delete
    raced = {"done": False}

    def interleave(collection, query, *args, **kwargs):
        if collection.name == "demonstrations" and not raced["done"]:
            raced["done"] = True
            collection.update_one({"_id": demo_id}, {"$set": {"title": "Latest concurrent title"}})
        return original(collection, query, *args, **kwargs)

    monkeypatch.setattr(collection_type, "find_one_and_delete", interleave)
    assert admin_client.post("/admin/demo/delete_demo", data={"demo_id": str(demo_id)}).status_code == 409
    actual = db.demonstrations.find_one({"_id": demo_id})
    assert actual["title"] == "Latest concurrent title"
    assert db.demo_delete_backups.find_one({})["state"] == "not_applied"
    assert "preimage" not in db.demo_delete_backups.find_one({})
    previous_ids = {row["_id"] for row in db.demo_edit_history.find({})}
    assert admin_client.post("/admin/demo/delete_demo", data={"demo_id": str(demo_id)}).status_code == 302
    assert db.demonstrations.find_one({"_id": demo_id}) is None
    new_history = list(db.demo_edit_history.find({"_id": {"$nin": list(previous_ids)}}))
    assert len(new_history) == 1 and new_history[0]["old_demo"] == actual
    backup = db.demo_delete_backups.find_one({"state": "completed"})
    assert backup["history_id"] == new_history[0]["_id"]
    assert "preimage" not in backup


def test_delete_backup_failure_preserves_source_and_history(
    admin_client, db, seeded_data, monkeypatch
):
    demo_id = seeded_data["demo_id"]
    before = db.demonstrations.find_one({"_id": demo_id})
    count = db.demo_edit_history.count_documents({})
    collection_type = type(db.demo_delete_backups)
    original = collection_type.insert_one

    def fail(collection, *args, **kwargs):
        if collection.name == "demo_delete_backups":
            raise RuntimeError("synthetic deletion backup outage")
        return original(collection, *args, **kwargs)

    monkeypatch.setattr(collection_type, "insert_one", fail)
    assert admin_client.post("/admin/demo/delete_demo", data={"demo_id": str(demo_id)}).status_code == 503
    assert db.demonstrations.find_one({"_id": demo_id}) == before
    assert db.demo_edit_history.count_documents({}) == count


@pytest.mark.parametrize("newer_primary", [False, True])
def test_partial_merge_conflict_retains_prewrite_backup(
    admin_client, db, seeded_data, monkeypatch, newer_primary
):
    primary_id, blocked_id = seeded_data["demo_id"], seeded_data["pending_demo_id"]
    deleted_id = db.demonstrations.insert_one({
        "title": "Third merge source", "date": "2099-01-01", "city": "Helsinki",
        "aliases": [],
    }).inserted_id
    selected = [primary_id, deleted_id, blocked_id]
    before = {str(row["_id"]): row for row in db.demonstrations.find({"_id": {"$in": selected}})}
    collection_type = type(db.demonstrations)
    original = collection_type.find_one_and_delete
    receipt = {"_id": ObjectId(), "demo_id": str(blocked_id)}

    def interleave(collection, query, *args, **kwargs):
        if collection.name == "demonstrations" and query.get("_id") == blocked_id:
            backup = db.demo_merge_backups.find_one({"primary_demo_id": str(primary_id)})
            assert backup and backup["demos"] == before
            assert backup["state"] == "incomplete"
            assert db.demonstrations.find_one({"_id": deleted_id}) is None
            collection.update_one({"_id": blocked_id}, {"$set": {"_pending_rollback_history": receipt}})
            if newer_primary:
                collection.update_one({"_id": primary_id}, {"$set": {"title": "Newer primary edit"}})
        return original(collection, query, *args, **kwargs)

    monkeypatch.setattr(collection_type, "find_one_and_delete", interleave)
    response = admin_client.post("/admin/demo/merge", data={
        "demo_ids": [str(oid) for oid in selected], "primary_demo_id": str(primary_id),
    })
    assert response.status_code == (503 if newer_primary else 409)
    backup = db.demo_merge_backups.find_one({"primary_demo_id": str(primary_id)})
    assert backup["state"] == ("incomplete" if newer_primary else "restored")
    assert backup["phase"] == ("recovery_pending" if newer_primary else "secondary_conflict")
    assert backup["deleted_count"] == 1
    assert backup["demos"] == before
    assert db.demonstrations.find_one({"_id": deleted_id}) == before[str(deleted_id)]
    assert db.demonstrations.find_one({"_id": blocked_id})["_pending_rollback_history"] == receipt
    primary = db.demonstrations.find_one({"_id": primary_id})
    if newer_primary:
        assert primary["title"] == "Newer primary edit"
    else:
        assert primary == before[str(primary_id)]


@pytest.mark.parametrize("step", [
    "_apply_recommendation_choice", "_repoint_related_demo_data", "_handle_cases_after_merge", "record_demo_change", "history_none",
])
def test_merge_followup_failure_retains_confirmed_removed_source_phase(
    admin_client, db, seeded_data, monkeypatch, step
):
    selected = [seeded_data["demo_id"], seeded_data["pending_demo_id"]]
    before = {str(row["_id"]): row for row in db.demonstrations.find({"_id": {"$in": selected}})}

    def fail(*args, **kwargs):
        backup = db.demo_merge_backups.find_one({"primary_demo_id": str(selected[0])})
        assert backup["phase"] == "sources_removed"
        assert backup["deleted_count"] == 1
        if step == "history_none":
            return None
        raise RuntimeError("synthetic followup outage")

    target = "record_demo_change" if step == "history_none" else step
    _patch_demo_handler(monkeypatch, admin_client, "admin_demo.merge_demos", target, fail)
    response = admin_client.post("/admin/demo/merge", data={
        "demo_ids": [str(oid) for oid in selected], "primary_demo_id": str(selected[0]),
    })
    assert response.status_code == 503
    backup = db.demo_merge_backups.find_one({"primary_demo_id": str(selected[0])})
    assert backup["state"] == "incomplete"
    assert backup["phase"] == ("history_pending" if step in {"record_demo_change", "history_none"} else "followup_failed")
    assert backup["demos"] == before
    assert backup["removed_ids"] == [str(selected[1])]
    assert db.demonstrations.find_one({"_id": selected[1]}) is None


@pytest.mark.parametrize("concurrent_change", [
    {"last_modified": "newer", "title": "Newer source"},
    {"cancelled": True},
    {"editors": ["concurrently-authorized-editor"]},
])
def test_primary_merge_conflict_survives_backup_status_failure(
    admin_client, db, seeded_data, monkeypatch, concurrent_change
):
    from datetime import datetime

    selected = [seeded_data["demo_id"], seeded_data["pending_demo_id"]]
    change = deepcopy(concurrent_change)
    if "last_modified" in change:
        change["last_modified"] = datetime(2099, 1, 1)
    collection_type = type(db.demonstrations)
    original_replace, original_update = collection_type.replace_one, collection_type.update_one

    def interleave(collection, query, *args, **kwargs):
        if collection.name == "demonstrations":
            original_update(collection, {"_id": selected[0]}, {"$set": change})
        return original_replace(collection, query, *args, **kwargs)

    def fail_status(collection, *args, **kwargs):
        if collection.name == "demo_merge_backups":
            raise RuntimeError("synthetic status outage")
        return original_update(collection, *args, **kwargs)

    monkeypatch.setattr(collection_type, "replace_one", interleave)
    monkeypatch.setattr(collection_type, "update_one", fail_status)
    response = admin_client.post("/admin/demo/merge", data={
        "demo_ids": [str(oid) for oid in selected], "primary_demo_id": str(selected[0]),
    })
    assert response.status_code == 409
    actual = db.demonstrations.find_one({"_id": selected[0]})
    assert all(actual[key] == value for key, value in change.items())
    assert db.demonstrations.find_one({"_id": selected[1]}) is not None
    assert db.demo_merge_backups.find_one({})["phase"] == "operation_pending"


@pytest.mark.parametrize("failed_phase", ["sources_removed", "completed"])
def test_merge_phase_failure_does_not_claim_completed_operation(
    admin_client, db, seeded_data, monkeypatch, failed_phase
):
    selected = [seeded_data["demo_id"], seeded_data["pending_demo_id"]]
    before = {str(row["_id"]): row for row in db.demonstrations.find({"_id": {"$in": selected}})}
    collection_type = type(db.demo_merge_backups)
    original = collection_type.update_one

    def fail_status(collection, query, update, *args, **kwargs):
        if collection.name == "demo_merge_backups" and update.get("$set", {}).get("phase") == failed_phase:
            raise RuntimeError("synthetic phase outage")
        return original(collection, query, update, *args, **kwargs)

    monkeypatch.setattr(collection_type, "update_one", fail_status)
    response = admin_client.post("/admin/demo/merge", data={
        "demo_ids": [str(oid) for oid in selected], "primary_demo_id": str(selected[0]),
    })
    assert response.status_code == 503
    backup = db.demo_merge_backups.find_one({})
    assert backup["demos"] == before
    if failed_phase == "sources_removed":
        assert backup["state"] == "restored" and backup["phase"] == "phase_write_failed"
        assert {str(row["_id"]): row for row in db.demonstrations.find({"_id": {"$in": selected}})} == before
    else:
        assert backup["state"] == "incomplete" and backup["phase"] == "sources_removed"
        assert db.demonstrations.find_one({"_id": selected[1]}) is None


def test_merge_backup_failure_prevents_all_content_writes(
    admin_client, db, seeded_data, monkeypatch
):
    selected = [seeded_data["demo_id"], seeded_data["pending_demo_id"]]
    before = list(db.demonstrations.find({}).sort("_id", 1))
    collection_type = type(db.demo_merge_backups)
    original = collection_type.insert_one

    def fail(collection, *args, **kwargs):
        if collection.name == "demo_merge_backups":
            raise RuntimeError("synthetic backup outage")
        return original(collection, *args, **kwargs)

    monkeypatch.setattr(collection_type, "insert_one", fail)
    response = admin_client.post("/admin/demo/merge", data={
        "demo_ids": [str(oid) for oid in selected], "primary_demo_id": str(selected[0]),
    })
    assert response.status_code == 503
    assert list(db.demonstrations.find({}).sort("_id", 1)) == before
    assert db.demo_merge_backups.count_documents({}) == 0


@pytest.mark.parametrize("decision", ["approve", "deny"])
def test_rollback_preserves_current_decision_scope_and_metadata(
    admin_client, db, seeded_data, monkeypatch, decision
):
    queued = _capture_decision_email(monkeypatch)
    demo_id = seeded_data["pending_demo_id"]
    assert admin_client.post(f"/api/admin/demo/{demo_id}/{decision}").status_code == 200
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {
        "server_owned": {"keep": True}, "cancelled": True,
        "editors": [str(seeded_data["friend_id"])],
    }})
    before = db.demonstrations.find_one({"_id": demo_id})
    cases = list(db.cases.find({}))
    links = list(db.magic_links.find({}))
    historical = deepcopy(before)
    historical.update({
        "_id": ObjectId(), "title": "Restored content", "description": None,
        "approved": decision != "approve", "rejected": decision == "approve",
        "moderation_decision": {"obsolete": True}, "server_owned": "obsolete",
        "city": "Turku", "city_key": "turku", "organizers": [], "editors": [],
        "cancelled": False, "hide": not before.get("hide", False),
        "slug": "obsolete-slug", "parent": ObjectId(),
    })
    history_id = db.demo_edit_history.insert_one({
        "demo_id": str(demo_id), "old_demo": historical,
    }).inserted_id
    response = _rollback(admin_client, history_id)
    assert response.status_code == 302
    after = db.demonstrations.find_one({"_id": demo_id})
    assert after["title"] == "Restored content"
    assert after["description"] is None
    assert after["last_modified"] >= before.get("last_modified", after["last_modified"])
    assert {k: v for k, v in after.items() if k not in {"title", "description", "last_modified"}} == {
        k: v for k, v in before.items() if k not in {"title", "description", "last_modified"}
    }
    assert list(db.cases.find({})) == cases
    assert list(db.magic_links.find({})) == links
    assert len(queued) == 1
    entry = db.demo_edit_history.find_one({"rollbacked_from": history_id})
    assert entry["old_demo"] == before
    assert entry["new_demo"] == after
    assert entry["edited_by"] == str(seeded_data["admin_id"])
    # Repeating the same restore has no content change and creates no duplicate.
    assert _rollback(admin_client, history_id).status_code == 302
    assert db.demo_edit_history.count_documents({"rollbacked_from": history_id}) == 1


def test_rollback_sparse_history_and_undo_use_actual_content(admin_client, db, seeded_data):
    demo_id = seeded_data["demo_id"]
    before = db.demonstrations.find_one({"_id": demo_id})
    history_id = seeded_data["history_id"]
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Sparse historical title"},
    }})
    assert _rollback(admin_client, history_id).status_code == 302
    after = db.demonstrations.find_one({"_id": demo_id})
    assert after["title"] == "Sparse historical title"
    assert {k: v for k, v in after.items() if k not in {"title", "last_modified"}} == {
        k: v for k, v in before.items() if k not in {"title", "last_modified"}
    }
    entry = db.demo_edit_history.find_one({"rollbacked_from": history_id})
    assert _rollback(admin_client, entry['_id']).status_code == 302
    assert db.demonstrations.find_one({"_id": demo_id})["title"] == before["title"]


@pytest.mark.parametrize("field,old_value,new_value", [
    ("latitude", "60.1699", "61.4978"),
    ("longitude", "24.9384", "23.7610"),
    ("img", "old-image.png", "new-image.png"),
    ("cover_source", "user", "automatic"),
    ("event_type", "MARCH", "STAY_STILL"),
])
def test_rollback_restores_canonical_location_and_media_content(
    admin_client, db, seeded_data, field, old_value, new_value
):
    demo_id = seeded_data["demo_id"]
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {field: new_value}})
    before = db.demonstrations.find_one({"_id": demo_id})
    history_id = db.demo_edit_history.insert_one({
        "demo_id": str(demo_id), "old_demo": {field: old_value},
    }).inserted_id
    assert _rollback(admin_client, history_id).status_code == 302
    after = db.demonstrations.find_one({"_id": demo_id})
    assert after[field] == old_value
    assert {key: value for key, value in after.items() if key not in {field, "last_modified"}} == {
        key: value for key, value in before.items() if key not in {field, "last_modified"}
    }
    entry = db.demo_edit_history.find_one({"rollbacked_from": history_id})
    assert entry["old_demo"] == before
    assert entry["new_demo"] == after
    assert _rollback(admin_client, entry["_id"]).status_code == 302
    assert db.demonstrations.find_one({"_id": demo_id})[field] == new_value


@pytest.mark.parametrize("field,value", [
    ("latitude", "61.4978"), ("longitude", "23.7610"),
    ("img", "concurrent.png"), ("cover_source", "automatic"), ("event_type", "MARCH"),
])
def test_rollback_guards_canonical_location_and_media_changes(
    admin_client, db, seeded_data, monkeypatch, field, value
):
    demo_id = seeded_data["demo_id"]
    db.demonstrations.update_one({"_id": demo_id}, {"$unset": {field: ""}})
    before = db.demonstrations.find_one({"_id": demo_id})
    history_id = db.demo_edit_history.insert_one({
        "demo_id": str(demo_id), "old_demo": {"title": "Must not cross content versions"},
    }).inserted_id
    collection_type = type(db.demonstrations)
    original = collection_type.find_one_and_update

    def interleave(collection, query, *args, **kwargs):
        if collection.name == "demonstrations" and query.get("_id") == demo_id:
            collection.update_one({"_id": demo_id}, {"$set": {field: value}})
        return original(collection, query, *args, **kwargs)

    monkeypatch.setattr(collection_type, "find_one_and_update", interleave)
    assert _rollback(admin_client, history_id).status_code == 409
    assert db.demonstrations.find_one({"_id": demo_id}) == {**before, field: value}
    assert db.demo_edit_history.count_documents({"rollbacked_from": history_id}) == 0


@pytest.mark.parametrize("foreign", [False, True])
def test_rollback_checks_current_city_scope(app, db, seeded_data, foreign):
    actor = _create_scoped_admin(db, ["helsinki"], ["EDIT_DEMO"])
    client = _client_for_user(app, actor)
    demo_id = seeded_data["demo_id"]
    # A historical in-scope city cannot grant access to a foreign current target.
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {
        "city": "Turku" if foreign else "Helsinki",
        "city_key": "turku" if foreign else "helsinki", "editors": [],
    }})
    history_id = seeded_data["history_id"]
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Scoped restore", "city": "Helsinki"},
    }})
    before = db.demonstrations.find_one({"_id": demo_id})
    response = _rollback(client, history_id)
    assert response.status_code == (403 if foreign else 302)
    after = db.demonstrations.find_one({"_id": demo_id})
    if foreign:
        assert after == before
        assert db.demo_edit_history.count_documents({"rollbacked_from": history_id}) == 0
    else:
        assert after["title"] == "Scoped restore"
        assert after["city_key"] == "helsinki"


@pytest.mark.parametrize("change", [{"title": "Concurrent edit"}, {"city_key": "turku"}])
def test_rollback_conflict_does_not_write_or_record_success(
    admin_client, db, seeded_data, monkeypatch, change
):
    demo_id = seeded_data["demo_id"]
    history_id = seeded_data["history_id"]
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Must not overwrite a concurrent change"},
    }})
    collection = db.demonstrations
    original = type(collection).find_one_and_update

    def interleave(self, query, update, *args, **kwargs):
        if self.name == "demonstrations" and "$and" in query:
            self.update_one({"_id": demo_id}, {"$set": change})
        return original(self, query, update, *args, **kwargs)

    monkeypatch.setattr(type(collection), "find_one_and_update", interleave)
    response = _rollback(admin_client, history_id)
    assert response.status_code == 409
    after = db.demonstrations.find_one({"_id": demo_id})
    assert all(after[key] == value for key, value in change.items())
    assert after["title"] != "Must not overwrite a concurrent change"
    assert db.demo_edit_history.count_documents({"rollbacked_from": history_id}) == 0


@pytest.mark.parametrize("kind", ["invalid", "missing", "invalid-target", "missing-target"])
def test_rollback_invalid_identifiers_are_not_server_errors(admin_client, db, kind):
    history_id = "not-an-id" if kind == "invalid" else ObjectId()
    if kind.endswith("target"):
        db.demo_edit_history.insert_one({
            "_id": history_id,
            "demo_id": "invalid" if kind == "invalid-target" else str(ObjectId()),
            "old_demo": {"title": "No target"},
        })
    assert admin_client.post(f"/admin/demo/rollback_demo/{history_id}").status_code == 404


def test_rollback_keeps_concurrent_unrelated_metadata(admin_client, db, seeded_data, monkeypatch):
    demo_id = seeded_data["demo_id"]
    history_id = seeded_data["history_id"]
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Restored content with fresh metadata"},
    }})
    collection = db.demonstrations
    original = type(collection).find_one_and_update

    def interleave(self, query, update, *args, **kwargs):
        if self.name == "demonstrations" and "$and" in query:
            self.update_one({"_id": demo_id}, {"$set": {"server_owned": "fresh metadata"}})
        return original(self, query, update, *args, **kwargs)

    monkeypatch.setattr(type(collection), "find_one_and_update", interleave)
    assert _rollback(admin_client, history_id).status_code == 302
    after = db.demonstrations.find_one({"_id": demo_id})
    assert after["title"] == "Restored content with fresh metadata"
    assert after["server_owned"] == "fresh metadata"
    entry = db.demo_edit_history.find_one({"rollbacked_from": history_id})
    assert entry["old_demo"]["server_owned"] == "fresh metadata"
    assert entry["new_demo"] == after


def test_rollback_requires_edit_permission_and_csrf(app, admin_client, user_client, db, seeded_data):
    history_id = seeded_data["history_id"]
    before = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
    assert user_client.post(f"/admin/demo/rollback_demo/{history_id}").status_code == 403
    assert admin_client.post(f"/admin/demo/rollback_demo/{history_id}").status_code == 400
    for invalid_token in ("incorrect-token", "väärä-token"):
        assert admin_client.post(f"/admin/demo/rollback_demo/{history_id}", data={
            "csrf_token": invalid_token,
        }).status_code == 400
    page = admin_client.get(f"/admin/demo/view_demo_diff/{history_id}").get_data(as_text=True)
    class RollbackForm(HTMLParser):
        in_form = False
        token = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "form":
                self.in_form = attrs.get("action") == f"/admin/demo/rollback_demo/{history_id}"
            elif self.in_form and tag == "input" and attrs.get("name") == "csrf_token":
                self.token = attrs.get("value")

        def handle_endtag(self, tag):
            if tag == "form":
                self.in_form = False

    form = RollbackForm()
    form.feed(page)
    token = form.token
    assert token
    assert db.demonstrations.find_one({"_id": seeded_data["demo_id"]}) == before
    assert admin_client.post(f"/admin/demo/rollback_demo/{history_id}", data={"csrf_token": token}).status_code == 302


@pytest.mark.parametrize("locale,expected", [
    ("fi", "Palautus koskee vain versioon tallennettua tapahtumasisältöä."),
    ("en", "Only event content recorded in this version is restored."),
    ("sv", "Endast evenemangsinnehåll som sparats i versionen återställs."),
])
def test_rollback_explanation_uses_compiled_locale(app, admin_client, seeded_data, locale, expected):
    app.config.update(BABEL_PUBLIC_LOCALES=["fi", "en", "sv"])
    with admin_client.session_transaction() as session:
        session["locale"] = locale
    response = admin_client.get(f"/admin/demo/view_demo_diff/{seeded_data['history_id']}")
    assert response.status_code == 200
    assert expected in response.get_data(as_text=True)
    if locale == "sv":
        assert "Godkännande, status som inställt, synlighet" in response.get_data(as_text=True)
