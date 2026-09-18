from tests.conftest import _client_for_user
from mielenosoitukset_fi.utils.time_utils import utcnow


def test_public_cities_lists_enabled_contact_cities_and_demo_cities(app, db, seeded_data):
    response = app.test_client().get("/cities")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Tampere" in page
    assert "Helsinki" in page
    assert "Varkaus" not in page


def test_admin_city_control_can_toggle_enabled_city(app, db, seeded_data):
    client = _client_for_user(app, seeded_data["admin_id"])

    response = client.post(
        "/admin/cities/",
        data={"enabled_cities[]": ["tampere", "oulu"]},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert db.city_settings.find_one({"city_key": "tampere"})["enabled"] is True
    assert db.city_settings.find_one({"city_key": "oulu"})["enabled"] is True
    assert db.city_settings.find_one({"city_key": "turku"})["enabled"] is False


def test_admin_city_control_aggregates_counts_and_offers_bulk_tools(app, db, seeded_data):
    db.demonstrations.insert_one(
        {
            "title": "City-key demonstration",
            "city": "Helsinki",
            "city_key": "helsinki",
        }
    )
    db.admin_scope_grants.insert_one(
        {
            "user_id": seeded_data["user_id"],
            "scope_type": "city",
            "scope_keys": ["helsinki", "turku"],
            "permissions": ["LIST_DEMOS"],
        }
    )
    client = _client_for_user(app, seeded_data["admin_id"])

    response = client.get("/admin/cities/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'data-city-name="Helsinki" data-demo-count="4" data-grant-count="1"' in page
    assert 'data-city-name="Turku" data-demo-count="0" data-grant-count="1"' in page
    assert '<option value="relevant" selected>' in page
    assert "Ota näkyvät käyttöön" in page
    assert "Poista näkyvät käytöstä" in page
    assert "Näytetään" in page


def test_admin_city_control_grant_count_links_to_filtered_user_list(app, db, seeded_data):
    admin_id = seeded_data["admin_id"]
    user_id = seeded_data["user_id"]
    db.admin_scope_grants.insert_one(
        {
            "user_id": user_id,
            "scope_type": "city",
            "scope_keys": ["varkaus"],
            "permissions": ["LIST_DEMOS"],
        }
    )
    client = _client_for_user(app, admin_id)

    response = client.get("/admin/cities/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert f'href="/admin/user/?city=varkaus"' in page
    # The grant count for Varkaus is rendered as a link because it is > 0.
    assert 'data-city-name="varkaus"' in page


def test_user_city_scope_picker_prioritizes_enabled_cities(app, db, seeded_data):
    client = _client_for_user(app, seeded_data["admin_id"])
    response = client.get(f"/admin/user/edit_user/{seeded_data['user_id']}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Tampere" in page
    assert "Varkaus (ei käytössä)" in page


def test_create_city_admin_auto_activates_inactive_city(app, db, seeded_data):
    client = _client_for_user(app, seeded_data["admin_id"])

    response = client.post(
        "/admin/user/create_user",
        data={
            "email": "new-city-admin@example.test",
            "username": "new-city-admin",
            "displayname": "New City Admin",
            "role": "city_admin",
            "admin_scope_cities[]": ["helsinki", "varkaus"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    user_doc = db.users.find_one({"email": "new-city-admin@example.test"})
    assert user_doc["role"] == "city_admin"
    assert db.city_settings.find_one({"city_key": "varkaus"})["enabled"] is True


def test_edit_user_city_grant_auto_activates_inactive_city(app, db, seeded_data):
    client = _client_for_user(app, seeded_data["admin_id"])

    response = client.post(
        f"/admin/user/edit_user/{seeded_data['user_id']}",
        data={
            "username": "alice",
            "email": "alice@example.test",
            "displayname": "Alice Tester",
            "role": "user",
            "confirmed": "on",
            "admin_scope_cities[]": ["varkaus"],
            "admin_scope_permissions[city][]": ["ACCEPT_DEMO"],
        },
    )

    assert response.status_code == 302
    grant = db.admin_scope_grants.find_one(
        {"user_id": seeded_data["user_id"], "scope_type": "city", "revoked_at": None}
    )
    assert grant["scope_keys"] == ["varkaus"]
    assert db.city_settings.find_one({"city_key": "varkaus"})["enabled"] is True


def test_edit_user_revoking_city_grant_does_not_deactivate_city(app, db, seeded_data):
    db.admin_scope_grants.insert_one(
        {
            "user_id": seeded_data["user_id"],
            "scope_type": "city",
            "scope_keys": ["varkaus"],
            "permissions": ["ACCEPT_DEMO"],
            "created_at": utcnow(),
            "granted_by": str(seeded_data["admin_id"]),
            "revoked_at": None,
        }
    )
    db.city_settings.update_one(
        {"city_key": "varkaus"},
        {"$set": {"enabled": True}},
        upsert=True,
    )
    client = _client_for_user(app, seeded_data["admin_id"])

    response = client.post(
        f"/admin/user/edit_user/{seeded_data['user_id']}",
        data={
            "username": "alice",
            "email": "alice@example.test",
            "displayname": "Alice Tester",
            "role": "user",
            "confirmed": "on",
        },
    )

    assert response.status_code == 302
    grant = db.admin_scope_grants.find_one(
        {"user_id": seeded_data["user_id"], "scope_type": "city"}
    )
    assert grant["revoked_at"] is not None
    assert db.city_settings.find_one({"city_key": "varkaus"})["enabled"] is True
