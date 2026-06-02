from datetime import datetime, timezone

from bson import ObjectId


def _insert_admin_user_list_entries(db):
    entries = [
        {
            "_id": ObjectId(),
            "username": "pagination-user-01",
            "displayname": "Pagination User 01",
            "email": "pagination-user-01@example.test",
            "role": "user",
            "confirmed": True,
            "last_login": datetime.now(timezone.utc),
            "global_permissions": [],
        },
        {
            "_id": ObjectId(),
            "username": "pagination-user-02",
            "displayname": "Pagination User 02",
            "email": "pagination-user-02@example.test",
            "role": "user",
            "confirmed": True,
            "last_login": datetime.now(timezone.utc),
            "global_permissions": [],
        },
        {
            "_id": ObjectId(),
            "username": "pagination-user-03",
            "displayname": "Pagination User 03",
            "email": "pagination-user-03@example.test",
            "role": "user",
            "confirmed": True,
            "last_login": datetime.now(timezone.utc),
            "global_permissions": [],
        },
        {
            "_id": ObjectId(),
            "username": "displayname-search-user",
            "displayname": "Friendly Admin",
            "email": "friendly-admin@example.test",
            "role": "user",
            "confirmed": True,
            "last_login": datetime.now(timezone.utc),
            "global_permissions": [],
        },
    ]
    db.users.insert_many(entries)


def test_user_control_paginates_results(admin_client, db, seeded_data):
    _insert_admin_user_list_entries(db)

    first_page = admin_client.get("/admin/user/?search=pagination-user-&page=1&per_page=2")
    second_page = admin_client.get("/admin/user/?search=pagination-user-&page=2&per_page=2")

    assert first_page.status_code == 200
    assert second_page.status_code == 200

    first_body = first_page.get_data(as_text=True)
    second_body = second_page.get_data(as_text=True)

    assert "pagination-user-01" in first_body
    assert "pagination-user-02" in first_body
    assert "pagination-user-03" not in first_body
    assert "Sivu 1 / 2" in first_body

    assert "pagination-user-03" in second_body
    assert "Sivu 2 / 2" in second_body


def test_user_control_searches_display_names(admin_client, db, seeded_data):
    _insert_admin_user_list_entries(db)

    response = admin_client.get("/admin/user/?search=friendly")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Friendly Admin" in body
    assert "displayname-search-user" in body


def test_delete_user_removes_direct_personal_data(admin_client, db, seeded_data):
    user_id = seeded_data["user_id"]
    user_id_str = str(user_id)
    pending_demo_id = seeded_data["pending_demo_id"]

    db.user_settings.insert_one({"user_id": user_id, "language": "fi"})
    db.password_changes.insert_one({"email": "alice@example.test", "token": "raw-reset-token"})
    db.password_changes.insert_one({"user_id": user_id, "method": "settings_page", "ip": "127.0.0.1"})
    db.demo_reminders.insert_one({"demonstration_id": pending_demo_id, "user_email": "alice@example.test", "user_ip": "127.0.0.1"})
    db.reports.insert_one({"demo_id": pending_demo_id, "user": user_id, "reporter_email": "alice@example.test"})
    db.malicious_reports.insert_one({"user_email": "alice@example.test", "ip": "127.0.0.1"})
    db.demo_submission_errors.insert_one(
        {
            "user": {"id": user_id_str, "username": "alice"},
            "form_snapshot": {"submitter_email": "alice@example.test"},
        }
    )
    db.api_token_requests.insert_one({"user_id": user_id, "username": "alice"})
    db.developer_apps.insert_one({"owner_id": user_id, "name": "Alice app"})
    db.developer_scope_requests.insert_one({"user_id": user_id, "scopes": ["write"]})
    db.account_deletion_requests.insert_one({"user_id": user_id, "email": "alice@example.test", "status": "pending"})
    db.demo_submission_tokens.insert_one({"token": "alice-submission", "demo_id": pending_demo_id})
    db.demo_cancellation_tokens.insert_one({"token_hash": "alice-cancel", "demo_id": pending_demo_id})
    db.demo_audit_logs.insert_one({"demo_id": str(pending_demo_id), "action": "created"})
    db.magic_links.insert_one({"demo_id": str(pending_demo_id), "action": "preview"})
    db.users.update_one(
        {"_id": seeded_data["friend_id"]},
        {"$push": {"friend_requests": {"sent_by": user_id, "sent_ip": "127.0.0.1"}}},
    )
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$addToSet": {"editors": user_id_str}},
    )

    response = admin_client.post("/admin/user/delete_user", data={"user_id": user_id_str})

    assert response.status_code == 302
    assert db.users.find_one({"_id": user_id}) is None
    assert db.demonstrations.find_one({"_id": pending_demo_id}) is not None
    assert db.user_settings.count_documents({"user_id": user_id}) == 0
    assert db.login_logs.count_documents({"user_id": user_id}) == 0
    assert db.password_changes.count_documents({"email": "alice@example.test"}) == 0
    assert db.password_changes.count_documents({"user_id": user_id}) == 0
    assert db.demo_reminders.count_documents({"demonstration_id": pending_demo_id}) == 0
    assert db.reports.count_documents({"$or": [{"user": user_id}, {"reporter_email": "alice@example.test"}]}) == 0
    assert db.malicious_reports.count_documents({"user_email": "alice@example.test"}) == 0
    assert db.demo_submission_errors.count_documents({"user.id": user_id_str}) == 0
    assert db.notifications.count_documents({"user_id": user_id}) == 0
    assert db.messages.count_documents({"recipient_id": user_id}) == 0
    assert db.memberships.count_documents({"user_id": user_id}) == 0
    assert db.api_tokens.count_documents({"user_id": user_id}) == 0
    assert db.api_token_requests.count_documents({"user_id": user_id}) == 0
    assert db.developer_apps.count_documents({"owner_id": user_id}) == 0
    assert db.developer_scope_requests.count_documents({"user_id": user_id}) == 0
    assert db.account_deletion_requests.count_documents({"user_id": user_id}) == 0
    assert db.submitters.count_documents({"submitter_email": "alice@example.test"}) == 0
    assert db.demo_suggestions.count_documents({"suggested_by.email": "alice@example.test"}) == 0
    assert db.cases.count_documents({"submitter_id": user_id}) == 0
    assert db.board_audit_logs.count_documents({"user_id": user_id_str}) == 0
    assert db.demo_submission_tokens.count_documents({"demo_id": pending_demo_id}) == 1
    assert db.demo_cancellation_tokens.count_documents({"demo_id": pending_demo_id}) == 1
    assert db.demo_audit_logs.count_documents({"demo_id": str(pending_demo_id)}) == 1
    assert db.magic_links.count_documents({"demo_id": str(pending_demo_id)}) == 1
    assert db.users.count_documents({"friends.user_id": user_id}) == 0
    assert db.users.count_documents({"friend_requests.sent_by": user_id}) == 0
    assert db.demonstrations.count_documents({"editors": user_id}) == 0
    assert db.demonstrations.count_documents({"editors": user_id_str}) == 0


def test_delete_user_impact_reports_submitted_demo_cleanup(admin_client, db, seeded_data):
    user_id = seeded_data["user_id"]
    user_id_str = str(user_id)
    pending_demo_id = seeded_data["pending_demo_id"]

    db.demo_submission_tokens.insert_one({"token": "alice-impact-submission", "demo_id": pending_demo_id})
    db.demo_audit_logs.insert_one({"demo_id": str(pending_demo_id), "action": "created"})
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$addToSet": {"editors": user_id_str}},
    )

    response = admin_client.get(f"/admin/user/delete_user/impact/{user_id}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "OK"
    impact = payload["impact"]
    assert impact["submitted_demonstrations"] == 1
    assert str(pending_demo_id) in impact["submitted_demonstration_ids"]
    assert impact["collections"]["submitters"] == 1
    assert impact["submitted_demonstrations_deleted"] == 0
    assert "demonstrations" not in impact["collections"]
    assert "demo_submission_tokens" not in impact["collections"]
    assert "demo_audit_logs" not in impact["collections"]
    assert impact["demonstration_editor_links"] >= 1


def test_delete_user_requires_top_level_clearance(app, db, seeded_data):
    lower_admin_id = ObjectId()
    db.users.insert_one(
        {
            "_id": lower_admin_id,
            "username": "lower-admin",
            "displayname": "Lower Admin",
            "email": "lower-admin@example.test",
            "password_hash": "unused",
            "role": "admin",
            "global_admin": False,
            "confirmed": True,
            "active": True,
            "global_permissions": ["DELETE_USER"],
        }
    )

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(lower_admin_id)
        session["_fresh"] = True

    target_user_id = seeded_data["user_id"]
    impact_response = client.get(f"/admin/user/delete_user/impact/{target_user_id}")
    delete_response = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target_user_id)},
    )

    assert impact_response.status_code == 403
    assert impact_response.get_json()["status"] == "ERROR"
    assert delete_response.status_code == 403
    assert delete_response.get_json()["status"] == "ERROR"
    assert db.users.find_one({"_id": target_user_id}) is not None
