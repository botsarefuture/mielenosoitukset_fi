from bson import ObjectId


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
    assert "Luo muokkauslinkki" not in page
    assert 'id="duplicate-demo-btn"' in page
    assert 'id="child-demos"' in page
    assert "Päivitä lapsimielenosoituksia" in page
    assert 'class="editor-save-bar"' in page
    assert '<option value="weekly" selected>' in page


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


def test_recu_demo_dashboard_renders_client_side_pagination(admin_client, db, seeded_data):
    response = admin_client.get("/admin/recu_demo/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'data-admin-pagination' in page
    assert 'id="page-size"' in page
    assert 'data-admin-pagination-current' in page
    assert 'data-admin-pagination-total' in page


def test_recu_demo_dashboard_filters_approval_state(admin_client, db, seeded_data):
    existing = db.recu_demos.find_one({"_id": seeded_data["recu_demo_id"]})
    pending = {**existing, "_id": ObjectId(), "title": "Pending recurring series", "approved": False}
    db.recu_demos.insert_one(pending)

    all_page = admin_client.get("/admin/recu_demo/?approved=all").get_data(as_text=True)
    approved_page = admin_client.get("/admin/recu_demo/?approved=true").get_data(as_text=True)
    pending_page = admin_client.get("/admin/recu_demo/?approved=false").get_data(as_text=True)

    assert "Recurring Test Series" in all_page
    assert "Pending recurring series" in all_page
    assert "Recurring Test Series" in approved_page
    assert "Pending recurring series" not in approved_page
    assert "Recurring Test Series" not in pending_page
    assert "Pending recurring series" in pending_page
