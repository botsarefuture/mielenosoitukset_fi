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


def test_user_control_filters_by_city_admin_scope(admin_client, db, seeded_data):
    """The user list can filter users by the city they hold an active admin grant for."""
    # Two users with tampere grant, one with oulu grant only.
    tampere_users = [ObjectId(), ObjectId()]
    oulu_user = ObjectId()
    db.users.insert_many(
        [
            {
                "_id": oid,
                "username": f"tampere-admin-{idx:02d}",
                "role": "city_admin",
                "email": f"tampere-admin-{idx:02d}@example.test",
                "confirmed": True,
            }
            for idx, oid in enumerate(tampere_users)
        ]
    )
    db.users.insert_one(
        {
            "_id": oulu_user,
            "username": "oulu-admin-01",
            "role": "city_admin",
            "email": "oulu-admin-01@example.test",
            "confirmed": True,
        }
    )
    for oid in tampere_users:
        db.admin_scope_grants.insert_one(
            {
                "user_id": oid,
                "scope_type": "city",
                "scope_keys": ["tampere"],
                "permissions": ["LIST_DEMOS"],
            }
        )
    db.admin_scope_grants.insert_one(
        {
            "user_id": oulu_user,
            "scope_type": "city",
            "scope_keys": ["oulu"],
            "permissions": ["LIST_DEMOS"],
        }
    )

    response = admin_client.get("/admin/user/?city=tampere")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "tampere-admin-00" in body
    assert "tampere-admin-01" in body
    assert "oulu-admin-01" not in body
    assert "Kaupunki" in body

    # Normalized key form also works.
    response2 = admin_client.get("/admin/user/?city=Tampere")
    assert response2.status_code == 200
    assert "tampere-admin-00" in response2.get_data(as_text=True)

    # Unknown city falls back to full list.
    response3 = admin_client.get("/admin/user/?city=nowhereville")
    assert response3.status_code == 200
    assert "tampere-admin-00" in response3.get_data(as_text=True)


def test_edit_user_exposes_translator_role_and_auto_assigns_permission(admin_client, db, seeded_data):
    translator_id = seeded_data["translator_id"]

    response = admin_client.get(f"/admin/user/edit_user/{translator_id}")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'value="translator"' in body

    save_response = admin_client.post(
        f"/admin/user/save_user/{translator_id}",
        data={
            "username": "translator",
            "email": "translator@example.test",
            "role": "translator",
            "confirmed": "on",
        },
        follow_redirects=False,
    )
    assert save_response.status_code == 302

    user_doc = db.users.find_one({"_id": translator_id})
    assert user_doc["role"] == "translator"
    assert user_doc["username_canonical"] == "translator"
    assert "TRANSLATE_DEMO" in user_doc.get("global_permissions", [])
    assert "TRANSLATE_UI" in user_doc.get("global_permissions", [])


def test_create_user_can_assign_translator_role(admin_client, db, seeded_data):
    create_page = admin_client.get("/admin/user/")
    body = create_page.get_data(as_text=True)
    assert '<option value="translator">Kääntäjä</option>' in body
    assert '<option value="city_admin">Kaupunkiadmin</option>' in body
    assert 'name="admin_scope_cities[]"' in body

    response = admin_client.post(
        "/admin/user/create_user",
        data={
            "email": "new-translator@example.test",
            "username": "new-translator",
            "displayname": "New Translator",
            "role": "translator",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    user_doc = db.users.find_one({"email": "new-translator@example.test"})
    assert user_doc["role"] == "translator"
    assert set(user_doc["global_permissions"]) >= {"TRANSLATE_DEMO", "TRANSLATE_UI"}


def test_create_user_can_assign_city_admin_scope(admin_client, db, seeded_data):
    response = admin_client.post(
        "/admin/user/create_user",
        data={
            "email": "new-city-admin@example.test",
            "username": "new-city-admin",
            "displayname": "New City Admin",
            "role": "city_admin",
            "admin_scope_cities[]": ["helsinki", "turku"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    user_doc = db.users.find_one({"email": "new-city-admin@example.test"})
    assert user_doc["role"] == "city_admin"
    grant = db.admin_scope_grants.find_one(
        {"user_id": user_doc["_id"], "scope_type": "city", "revoked_at": None}
    )
    assert grant["scope_keys"] == ["helsinki", "turku"]
    assert set(grant["permissions"]) == {
        "LIST_DEMOS",
        "VIEW_DEMO",
        "EDIT_DEMO",
        "ACCEPT_DEMO",
        "CREATE_DEMO",
        "GENERATE_EDIT_LINK",
    }


def test_create_city_admin_requires_city_selection(admin_client, db, seeded_data):
    response = admin_client.post(
        "/admin/user/create_user",
        data={
            "email": "cityless-admin@example.test",
            "username": "cityless-admin",
            "role": "city_admin",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert db.users.find_one({"email": "cityless-admin@example.test"}) is None


def test_create_user_rejects_reserved_admin_identity(admin_client, db, seeded_data):
    response = admin_client.post(
        "/admin/user/create_user",
        data={
            "email": "reserved-admin@example.test",
            "username": "regular-user",
            "displayname": "@Admin",
            "role": "user",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert db.users.find_one({"email": "reserved-admin@example.test"}) is None
