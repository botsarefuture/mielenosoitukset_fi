from tests.conftest import _client_for_user


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


def test_user_city_scope_picker_prioritizes_enabled_cities(app, db, seeded_data):
    client = _client_for_user(app, seeded_data["admin_id"])
    response = client.get(f"/admin/user/edit_user/{seeded_data['user_id']}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Tampere" in page
    assert "Varkaus (ei käytössä)" in page
