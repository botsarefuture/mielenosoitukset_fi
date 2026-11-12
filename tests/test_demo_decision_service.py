from importlib import import_module


def _demo_routes_module():
    """Import the route module, not the Blueprint exported by admin.__init__."""
    return import_module("mielenosoitukset_fi.admin.admin_demo_bp")


def _patch_demo_email_sender(monkeypatch, method, replacement):
    """Patch both module aliases registered by the application test harness."""
    modules = {
        _demo_routes_module(),
        import_module("admin.admin_demo_bp"),
    }
    for module in modules:
        monkeypatch.setattr(module.email_sender, method, replacement)


def _capture_decision_email(monkeypatch):
    queued = []

    def capture(**kwargs):
        queued.append(kwargs)

    _patch_demo_email_sender(monkeypatch, "queue_email", capture)
    return queued


def _assert_single_decision_record(db, demo_id, decision_id, action):
    assert db.demo_edit_history.count_documents(
        {"demo_id": str(demo_id), "new_demo.moderation_decision.id": decision_id}
    ) == 1
    assert db.demo_audit_logs.count_documents(
        {"demo_id": str(demo_id), "action": action,
         "details.decision_id": decision_id}
    ) == 1


def test_legacy_approval_is_idempotent_and_reconciles_all_side_effects(
    admin_client, db, seeded_data, monkeypatch
):
    from bson import ObjectId

    queued = _capture_decision_email(monkeypatch)
    original_case = db.cases.find_one({"_id": seeded_data["case_id"]})
    string_case = {
        **original_case, "_id": ObjectId(), "running_num": 100002,
        "demo_id": str(seeded_data["pending_demo_id"]),
    }
    unrelated_case = {
        **original_case, "_id": ObjectId(), "running_num": 100003,
        "demo_id": seeded_data["demo_id"],
    }
    db.cases.insert_many([string_case, unrelated_case])
    path = f"/admin/demo/accept_demo/{seeded_data['pending_demo_id']}"
    reference_token = db.magic_links.find_one(
        {"demo_id": str(seeded_data["pending_demo_id"])}
    )
    db.magic_links.insert_one(
        {
            "_id": ObjectId(),
            "token_hash": "test-edit-link-hash",
            "demo_id": str(seeded_data["pending_demo_id"]),
            "action": "edit",
            "created_at": reference_token["created_at"],
            "expires_at": reference_token["expires_at"],
            "used_at": None,
            "revoked": False,
        }
    )

    first = admin_client.post(
        path, json={}, headers={"Content-Type": "application/json"}
    )
    original_decision = db.demonstrations.find_one(
        {"_id": seeded_data["pending_demo_id"]}
    )["moderation_decision"]
    second = admin_client.post(
        f"/api/admin/demo/{seeded_data['pending_demo_id']}/approve"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["changed"] is True
    assert second.get_json()["changed"] is False

    demo = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    decision_id = demo["moderation_decision"]["id"]
    assert demo["approved"] is True
    assert demo["rejected"] is False
    assert demo["moderation_decision"]["status"] == "approved"
    assert demo["moderation_decision"]["source"] == "legacy_api"
    assert demo["moderation_decision"] == original_decision

    assert len(queued) == 1
    assert queued[0]["template_name"] == "demo_submitter_approved.html"
    assert queued[0]["context"]["url"] == first.request.host_url.rstrip("/") + (
        f"/demonstration/{seeded_data['pending_demo_id']}"
    )
    assert db.demo_decision_notifications.count_documents(
        {"decision_id": decision_id}
    ) == 1
    assert db.demo_edit_history.count_documents(
        {
            "demo_id": str(seeded_data["pending_demo_id"]),
            "new_demo.moderation_decision.id": decision_id,
        }
    ) == 1

    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert case["status"] == "Hyväksytty"
    assert case["outcome"] == "approved"
    assert case["resolution"] == "approved"
    assert case["meta"]["decision_id"] == decision_id
    assert sum(
        entry.get("metadata", {}).get("decision_id") == decision_id
        for entry in case["case_history"]
    ) == 1

    decision_tokens = list(
        db.magic_links.find(
            {"demo_id": str(seeded_data["pending_demo_id"])}
        )
    )
    assert {token["action"] for token in decision_tokens} == {
        "preview",
        "approve",
        "reject",
        "edit",
    }
    assert all(token["revoked"] is True for token in decision_tokens)
    assert all(token.get("decision_id") == decision_id for token in decision_tokens)
    for case_id in [seeded_data["case_id"], string_case["_id"]]:
        linked = db.cases.find_one({"_id": case_id})
        assert linked["meta"]["closed"] is True
        assert linked["meta"]["closed_at"] == original_decision["at"]
        assert linked["outcome"] == linked["resolution"] == "approved"
        entries = [
            entry for entry in linked["case_history"]
            if entry.get("metadata", {}).get("decision_id") == decision_id
        ]
        assert len(entries) == 1
        assert entries[0]["metadata"]["source"] == "legacy_api"
        assert entries[0]["user"] == original_decision["actor"]["username"]
        assert entries[0]["timestamp"] == original_decision["at"]
    assert db.cases.find_one({"_id": unrelated_case["_id"]}) == unrelated_case
    _assert_single_decision_record(db, demo["_id"], decision_id, "approve_demo")


def test_token_rejection_consumes_used_token_and_revokes_siblings(
    client, db, seeded_data, monkeypatch
):
    queued = _capture_decision_email(monkeypatch)
    response = client.post(
        f"/admin/demo/reject_demo_with_token/{seeded_data['reject_token']}",
        follow_redirects=False,
    )

    assert response.status_code == 302
    demo = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    assert demo["approved"] is False
    assert demo["rejected"] is True
    assert demo["moderation_decision"]["source"] == "token"
    assert len(queued) == 1
    assert queued[0]["template_name"] == "demo_submitter_rejected.html"

    from mielenosoitukset_fi.admin.admin_demo_bp import _hash_token

    used = db.magic_links.find_one(
        {"token_hash": _hash_token(seeded_data["reject_token"])}
    )
    assert used["used_at"] is not None
    assert used["revoked"] is False
    siblings = list(
        db.magic_links.find(
            {
                "demo_id": str(seeded_data["pending_demo_id"]),
                "_id": {"$ne": used["_id"]},
            }
        )
    )
    assert {token["action"] for token in siblings} == {"preview", "approve"}
    assert all(token["revoked"] is True for token in siblings)
    replay = client.post(
        f"/admin/demo/reject_demo_with_token/{seeded_data['reject_token']}"
    )
    # Used links intentionally render the existing friendly 200 page, not expiry.
    assert replay.status_code == 200
    assert "on jo käytetty" in replay.get_data(as_text=True)
    assert db.magic_links.find_one({"_id": used["_id"]})["used_at"] == used["used_at"]
    assert len(queued) == 1
    after_replay = db.demonstrations.find_one({"_id": demo["_id"]})
    assert after_replay["moderation_decision"] == demo["moderation_decision"]
    _assert_single_decision_record(
        db, demo["_id"], demo["moderation_decision"]["id"], "reject_demo"
    )


def test_form_approval_uses_canonical_decision_service(
    admin_client, db, seeded_data, monkeypatch
):
    queued = _capture_decision_email(monkeypatch)
    response = admin_client.post(
        f"/admin/demo/edit_demo/{seeded_data['pending_demo_id']}",
        data={
            "title": "Pending Demonstration",
            "date": "2026-05-01",
            "city": "Helsinki",
            "approved": "on",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    demo = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    assert demo["approved"] is True
    assert demo["rejected"] is False
    assert demo["moderation_decision"]["source"] == "admin_form"
    assert len(queued) == 1
    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert case["meta"]["closed"] is True
    assert case["outcome"] == case["resolution"] == "approved"
    assert case["meta"]["decision_id"] == demo["moderation_decision"]["id"]
    _assert_single_decision_record(
        db, demo["_id"], demo["moderation_decision"]["id"], "approve_demo"
    )


def test_admin_api_rejection_is_idempotent(admin_client, db, seeded_data, monkeypatch):
    queued = _capture_decision_email(monkeypatch)
    path = f"/api/admin/demo/{seeded_data['pending_demo_id']}/deny"

    first = admin_client.post(path)
    original_decision = db.demonstrations.find_one(
        {"_id": seeded_data["pending_demo_id"]}
    )["moderation_decision"]
    second = admin_client.post(path)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["changed"] is True
    assert second.get_json()["changed"] is False
    assert len(queued) == 1
    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert case["status"] == "Hylätty"
    assert case["outcome"] == "rejected"
    assert case["resolution"] == "rejected"
    assert sum(
        entry.get("metadata", {}).get("decision") == "rejected"
        for entry in case["case_history"]
    ) == 1
    demo = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    assert demo["approved"] is False and demo["rejected"] is True
    assert demo["moderation_decision"] == original_decision
    assert case["meta"]["closed"] is True
    _assert_single_decision_record(db, demo["_id"], original_decision["id"], "reject_demo")


def test_notification_delivery_can_retry_without_repeating_decision_effects(
    admin_client, db, seeded_data, monkeypatch
):
    attempts = []

    def flaky_queue(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise RuntimeError("temporary mail failure")

    _patch_demo_email_sender(monkeypatch, "queue_email", flaky_queue)
    legacy_path = f"/admin/demo/accept_demo/{seeded_data['pending_demo_id']}"
    failed = admin_client.post(
        legacy_path, json={}, headers={"Content-Type": "application/json"}
    )
    failed_demo = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    assert failed.status_code == 500
    assert failed_demo["approved"] is True and failed_demo["rejected"] is False
    assert db.demo_decision_notifications.count_documents({
        "decision_id": failed_demo["moderation_decision"]["id"]
    }) == 0
    retried = admin_client.post(
        f"/api/admin/demo/{seeded_data['pending_demo_id']}/approve"
    )

    assert failed.status_code == 500
    assert retried.status_code == 200
    assert retried.get_json()["changed"] is False
    assert len(attempts) == 2
    demo = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    decision_id = demo["moderation_decision"]["id"]
    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert sum(
        entry.get("metadata", {}).get("decision_id") == decision_id
        for entry in case["case_history"]
    ) == 1
    assert db.demo_decision_notifications.count_documents(
        {"decision_id": decision_id}
    ) == 1
    assert demo["moderation_decision"] == failed_demo["moderation_decision"]
    assert attempts[0] == attempts[1]
    notification = db.demo_decision_notifications.find_one({"decision_id": decision_id})
    assert notification["queued_at"] is not None
    assert admin_client.post(legacy_path, json={}).status_code == 200
    assert len(attempts) == 2
    assert db.cases.find_one({"_id": seeded_data["case_id"]}) == case
    _assert_single_decision_record(db, demo["_id"], decision_id, "approve_demo")


def test_bulk_decision_uses_same_service_and_reports_each_result(
    admin_client, db, seeded_data, monkeypatch
):
    queued = _capture_decision_email(monkeypatch)
    with admin_client.session_transaction() as session:
        session["demo_edit_link_csrf_token"] = "bulk-decision-csrf"
    response = admin_client.post(
        "/api/admin/demo/bulk_decide",
        json={
            "decision": "approved",
            "demo_ids": [
                str(seeded_data["pending_demo_id"]),
                str(seeded_data["pending_demo_id"]),
                "not-an-object-id",
            ],
        },
        headers={"X-CSRF-Token": "bulk-decision-csrf"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["changed_count"] == 1
    assert len(payload["results"]) == 2
    assert payload["results"][0]["status"] == "changed"
    assert payload["results"][1]["status"] == "invalid_id"
    assert len(queued) == 1
    demo = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    assert demo["moderation_decision"]["source"] == "admin_bulk"
    retried = admin_client.post(
        "/api/admin/demo/bulk_decide",
        json={"decision": "approved", "demo_ids": [str(demo["_id"])]},
        headers={"X-CSRF-Token": "bulk-decision-csrf"},
    )
    assert retried.status_code == 200
    assert retried.get_json()["changed_count"] == 0
    assert retried.get_json()["results"] == [
        {"demo_id": str(demo["_id"]), "status": "unchanged"}
    ]
    assert len(queued) == 1
    _assert_single_decision_record(
        db, demo["_id"], demo["moderation_decision"]["id"], "approve_demo"
    )
