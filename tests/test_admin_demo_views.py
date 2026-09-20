from bson import ObjectId


def test_create_demo_hides_edit_only_controls(admin_client):
    response = admin_client.get("/admin/demo/create_demo")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'name="cover_picture"' in page
    assert 'name="slug"' in page
    assert 'name="img"' in page
    assert 'name="preview_image"' in page
    assert "Linkit ja kuvat" in page
    assert "Luo muokkauslinkki" not in page
    assert "Luo kopio mielenosoituksesta" not in page


def test_edit_demo_shows_edit_only_controls(admin_client, seeded_data):
    response = admin_client.get(f"/admin/demo/edit_demo/{seeded_data['demo_id']}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Luo muokkauslinkki" in page
    assert "Luo kopio mielenosoituksesta" in page
    assert 'class="editor-save-bar"' in page
    assert 'class="admin-page-hero__nav editor-section-nav"' in page


def test_editor_without_accept_permission_cannot_forge_demo_approval(
    friend_client, db, seeded_data
):
    db.users.update_one(
        {"_id": seeded_data["friend_id"]},
        {"$set": {"role": "admin", "global_permissions": ["EDIT_DEMO"]}},
    )

    edit_page = friend_client.get(
        f"/admin/demo/edit_demo/{seeded_data['pending_demo_id']}"
    )
    assert edit_page.status_code == 200
    assert 'id="approval-container"' not in edit_page.get_data(as_text=True)

    response = friend_client.post(
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
    updated = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    assert updated["approved"] is False


def test_demo_dashboard_filters_year_text_and_missing_tag(admin_client, db, seeded_data):
    db.demonstrations.insert_many(
        [
            {
                "_id": ObjectId(),
                "title": "Pride support march",
                "description": "Pride visibility event.",
                "date": "2026-06-28",
                "city": "Helsinki",
                "address": "Kaivokatu 1",
                "approved": True,
                "hide": False,
                "rejected": False,
                "cancelled": False,
                "tags": ["equality"],
                "editors": [seeded_data["user_id"]],
            },
            {
                "_id": ObjectId(),
                "title": "Pride tagged march",
                "description": "Already categorized.",
                "date": "2026-06-29",
                "city": "Helsinki",
                "address": "Mannerheimintie 1",
                "approved": True,
                "hide": False,
                "rejected": False,
                "cancelled": False,
                "tags": ["#pride"],
                "editors": [seeded_data["user_id"]],
            },
            {
                "_id": ObjectId(),
                "title": "Pride old march",
                "description": "Wrong year.",
                "date": "2025-06-29",
                "city": "Helsinki",
                "address": "Mannerheimintie 1",
                "approved": True,
                "hide": False,
                "rejected": False,
                "cancelled": False,
                "tags": ["equality"],
                "editors": [seeded_data["user_id"]],
            },
        ]
    )

    response = admin_client.get("/admin/demo/?search=pride&year=2026&missing_tag=pride")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Pride support march" in page
    assert "Pride tagged march" not in page
    assert "Pride old march" not in page


def test_demo_dashboard_filters_by_required_tag(admin_client, db, seeded_data):
    db.demonstrations.insert_many(
        [
            {
                "_id": ObjectId(),
                "title": "Tagged Pride demo",
                "description": "Has the tag.",
                "date": "2026-06-28",
                "city": "Helsinki",
                "address": "Kaivokatu 1",
                "approved": True,
                "hide": False,
                "rejected": False,
                "cancelled": False,
                "tags": ["#pride"],
                "editors": [seeded_data["user_id"]],
            },
            {
                "_id": ObjectId(),
                "title": "Untagged Pride demo",
                "description": "Does not have the tag.",
                "date": "2026-06-29",
                "city": "Helsinki",
                "address": "Mannerheimintie 1",
                "approved": True,
                "hide": False,
                "rejected": False,
                "cancelled": False,
                "tags": ["equality"],
                "editors": [seeded_data["user_id"]],
            },
        ]
    )

    response = admin_client.get("/admin/demo/?tag=pride")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Tagged Pride demo" in page
    assert "Untagged Pride demo" not in page


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


def test_demo_dashboard_renders_numbered_pagination(admin_client, db, seeded_data):
    db.demonstrations.insert_many(
        [
            {
                "_id": ObjectId(),
                "title": f"Pagination batch demo {index}",
                "description": "Pagination fixture.",
                "date": "2026-08-01",
                "city": "Helsinki",
                "address": "Kansalaistori 1",
                "approved": True,
                "hide": False,
                "rejected": False,
                "cancelled": False,
                "in_past": False,
                "editors": [seeded_data["user_id"]],
            }
            for index in range(22)
        ]
    )

    response = admin_client.get("/admin/demo/?search=Pagination%20batch&per_page=20")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Sivu 1 / 2" in page
    assert "page=2" in page
    assert 'class="page-item active"' in page
    assert "per_page=20" in page


def test_create_demo_persists_translation_payload(admin_client, db):
    response = admin_client.post(
        "/admin/demo/create_demo",
        data={
            "title": "Solidarity Rally",
            "date": "2026-09-10",
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
    assert created["default_language"] == "fi"
    assert created["translations"]["en"]["title"] == "Solidarity Rally in English"
    assert created["translations"]["en"]["tags"] == ["peace", "rally"]
    assert created["translations"]["sv"]["title"] == "Solidaritetsmanifestation"


def test_create_demo_persists_normalized_slug_and_all_image_assets(admin_client, db):
    response = admin_client.post(
        "/admin/demo/create_demo",
        data={
            "title": "Ääni rauhalle",
            "date": "2026-10-10",
            "start_time": "12:00",
            "end_time": "14:00",
            "city": "Helsinki",
            "address": "Kansalaistori 1",
            "type": "STAY_STILL",
            "slug": "  Ääni & Rauha!  ",
            "cover_picture": "https://cdn.example.test/cover.jpg",
            "img": "/static/uploads/original.jpg",
            "preview_image": "https://cdn.example.test/preview.jpg",
            "gallery_images": "https://cdn.example.test/one.jpg\nhttps://cdn.example.test/two.jpg",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    created = db.demonstrations.find_one({"title": "Ääni rauhalle"})
    assert created["slug"] == "aani-rauha"
    assert created["cover_picture"] == "https://cdn.example.test/cover.jpg"
    assert created["img"] == "/static/uploads/original.jpg"
    assert created["preview_image"] == "https://cdn.example.test/preview.jpg"
    assert created["gallery_images"] == [
        "https://cdn.example.test/one.jpg",
        "https://cdn.example.test/two.jpg",
    ]


def test_create_demo_rejects_a_duplicate_normalized_slug(admin_client, db, seeded_data):
    response = admin_client.post(
        "/admin/demo/create_demo",
        data={
            "title": "Duplicate slug demo",
            "date": "2026-10-11",
            "city": "Helsinki",
            "address": "Kansalaistori 1",
            "type": "STAY_STILL",
            "slug": "Climate March Helsinki",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/demo/create_demo")
    assert db.demonstrations.find_one({"title": "Duplicate slug demo"}) is None
