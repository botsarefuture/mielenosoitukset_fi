def test_create_demo_hides_edit_only_controls(admin_client):
    response = admin_client.get("/admin/demo/create_demo")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'name="cover_picture"' in page
    assert 'name="default_language"' in page
    assert 'name="translation_en_title"' in page
    assert 'name="translation_sv_description"' in page
    assert "Luo muokkauslinkki" not in page
    assert "Luo kopio mielenosoituksesta" not in page


def test_edit_demo_shows_edit_only_controls(admin_client, seeded_data):
    response = admin_client.get(f"/admin/demo/edit_demo/{seeded_data['demo_id']}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Luo muokkauslinkki" in page
    assert "Luo kopio mielenosoituksesta" in page


def test_edit_demo_prefills_translation_fields(admin_client, db, seeded_data):
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {
            "$set": {
                "default_language": "fi",
                "translations": {
                    "en": {
                        "title": "English Climate March",
                        "description": "English description",
                        "tags": ["peace", "climate"],
                    }
                },
            }
        },
    )

    response = admin_client.get(f"/admin/demo/edit_demo/{seeded_data['demo_id']}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'value="English Climate March"' in page
    assert "English description" in page
    assert 'value="peace, climate"' in page


def test_create_demo_persists_translation_payload(admin_client, db):
    response = admin_client.post(
        "/admin/demo/create_demo",
        data={
            "title": "Solidarity Rally",
            "date": "2026-06-10",
            "start_time": "18:00",
            "end_time": "20:00",
            "city": "Helsinki",
            "address": "Kansalaistori 1",
            "type": "STAY_STILL",
            "description": "Finnish base description",
            "default_language": "fi",
            "translation_en_title": "Solidarity Rally in English",
            "translation_en_description": "English description",
            "translation_en_tags": "peace, rally",
            "translation_sv_title": "Solidaritetsmanifestation",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    created = db.demonstrations.find_one({"title": "Solidarity Rally"})
    assert created is not None
    assert created["default_language"] == "fi"
    assert created["translations"]["en"]["title"] == "Solidarity Rally in English"
    assert created["translations"]["en"]["description"] == "English description"
    assert created["translations"]["en"]["tags"] == ["peace", "rally"]
    assert created["translations"]["sv"]["title"] == "Solidaritetsmanifestation"
