from tests.conftest import _client_for_user


def test_governance_dashboard_collects_admin_tools(app, db, seeded_data):
    client = _client_for_user(app, seeded_data["admin_id"])

    response = client.get("/admin/governance/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Hallinto ja käyttöoikeudet" in page
    assert "Hallituksen hyväksynnät" in page
    assert "Kaupunkihallinta" in page
    assert "Tapahtumaloki" in page


def test_board_clearance_is_persisted_and_audited(app, db, seeded_data):
    client = _client_for_user(app, seeded_data["admin_id"])
    user_id = str(seeded_data["user_id"])

    response = client.post(
        f"/board/api/clearance/{user_id}",
        json={"approved": True},
    )

    assert response.status_code == 200
    clearance = db.board_clearances.find_one({"user_id": user_id})
    assert clearance["approved"] is True
    assert clearance["granted_by"] == "admin"
    assert db.board_audit_logs.find_one(
        {"user_id": user_id, "action": "myönnetty"}
    )

    page = client.get("/admin/governance/clearances").get_data(as_text=True)
    assert "alice" in page
    assert "Hyväksytty" in page


def test_legacy_board_pages_redirect_to_governance(app, seeded_data):
    client = _client_for_user(app, seeded_data["admin_id"])

    clearance_response = client.get("/board/ui")
    audit_response = client.get("/board/audit/ui")

    assert clearance_response.status_code == 302
    assert clearance_response.headers["Location"].endswith(
        "/admin/governance/clearances"
    )
    assert audit_response.status_code == 302
    assert audit_response.headers["Location"].endswith("/admin/governance/audit")


def test_city_management_explains_unsaved_and_risky_changes(app, seeded_data):
    client = _client_for_user(app, seeded_data["admin_id"])

    response = client.get("/admin/cities/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Vain käytössä olevat" in page
    assert "Tallentamattomia muutoksia" in page
    assert "Olet poistamassa käytöstä kaupunkeja" in page
    assert "/admin/governance/" in page


def test_governance_migration_preserves_existing_city_managers(db):
    from mielenosoitukset_fi.utils.migrations.migration_004_admin_governance import (
        migrate_admin_governance,
    )

    db.users.insert_one(
        {
            "username": "legacy-city-manager",
            "global_permissions": ["EDIT_USER"],
        }
    )

    result = migrate_admin_governance(db)

    user = db.users.find_one({"username": "legacy-city-manager"})
    assert "MANAGE_CITIES" in user["global_permissions"]
    assert result["city_permissions_added"] == 1
    assert "user_id_1" in db.board_clearances.index_information()
