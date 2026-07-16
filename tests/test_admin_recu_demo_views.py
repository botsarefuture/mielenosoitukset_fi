def test_create_recu_demo_uses_shared_admin_form(admin_client):
    response = admin_client.get("/admin/recu_demo/create_recu_demo")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'name="cover_picture"' in page
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
    assert 'id="child-demos"' in page
    assert "Päivitä lapsimielenosoituksia" in page
    assert 'class="editor-save-bar"' in page
    assert '<option value="weekly" selected>' in page


def test_recu_demo_dashboard_lists_demos_with_migrated_city_key(
    admin_client, db, seeded_data
):
    db.recu_demos.update_one(
        {"_id": seeded_data["recu_demo_id"]},
        {"$set": {"city_key": "helsinki"}},
    )

    response = admin_client.get("/admin/recu_demo/")

    assert response.status_code == 200
    assert "Recurring Test Series" in response.get_data(as_text=True)
