def test_create_recu_demo_uses_shared_admin_form(admin_client):
    response = admin_client.get("/admin/recu_demo/create_recu_demo")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'name="cover_picture"' in page
    assert 'name="default_language"' in page
    assert 'name="translation_en_title"' in page
    assert 'id="organization"' in page
    assert "Lisäkuvat" in page
    assert "Luo muokkauslinkki" not in page
    assert "js/ckeditor-init.js" in page


def test_edit_recu_demo_renders_shared_admin_form_with_org_selector(admin_client, seeded_data):
    response = admin_client.get(
        f"/admin/recu_demo/edit_recu_demo/{seeded_data['recu_demo_id']}"
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'id="organization"' in page
    assert "Luo muokkauslinkki" in page


def test_edit_recu_demo_prefills_translation_fields(admin_client, db, seeded_data):
    db.recu_demos.update_one(
        {"_id": seeded_data["recu_demo_id"]},
        {
            "$set": {
                "default_language": "fi",
                "translations": {
                    "en": {
                        "title": "Recurring demo in English",
                        "description": "English recurring demo description",
                        "tags": ["recurring", "peace"],
                    }
                },
            }
        },
    )

    response = admin_client.get(
        f"/admin/recu_demo/edit_recu_demo/{seeded_data['recu_demo_id']}"
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'value="Recurring demo in English"' in page
    assert "English recurring demo description" in page
    assert 'value="recurring, peace"' in page
