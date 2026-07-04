from bson import ObjectId


def test_create_demo_hides_edit_only_controls(admin_client):
    response = admin_client.get("/admin/demo/create_demo")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'name="cover_picture"' in page
    assert "Luo muokkauslinkki" not in page
    assert "Luo kopio mielenosoituksesta" not in page


def test_edit_demo_shows_edit_only_controls(admin_client, seeded_data):
    response = admin_client.get(f"/admin/demo/edit_demo/{seeded_data['demo_id']}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Luo muokkauslinkki" in page
    assert "Luo kopio mielenosoituksesta" in page
    assert 'class="editor-save-bar"' in page
    assert 'class="editor-section-nav"' in page


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
