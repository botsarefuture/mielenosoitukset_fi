def _set_demo_translation(db, demo_id):
    db.demonstrations.update_one(
        {"_id": demo_id},
        {
            "$set": {
                "date": "2026-05-20",
                "default_language": "fi",
                "translations": {
                    "en": {
                        "title": "English Climate March",
                        "description": "English description for the seeded demonstration.",
                        "tags": ["peace", "climate"],
                    }
                },
            }
        },
    )


def _set_client_locale(client, locale):
    with client.session_transaction() as session:
        session["locale"] = locale


def test_demo_detail_renders_translated_fields_for_active_locale(client, db, seeded_data):
    _set_demo_translation(db, seeded_data["demo_id"])
    _set_client_locale(client, "en")

    response = client.get(f"/demonstration/{seeded_data['demo_id']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "English Climate March" in body
    assert "English description for the seeded demonstration." in body
    assert "Climate March Helsinki" not in body


def test_demo_api_returns_translated_card_fields_for_active_locale(client, db, seeded_data):
    _set_demo_translation(db, seeded_data["demo_id"])
    _set_client_locale(client, "en")

    response = client.get("/api/v1/demonstrations")

    assert response.status_code == 200
    payload = response.get_json()
    matching = next(
        demo
        for demo in payload["demonstrations"]
        if demo["_id"] == str(seeded_data["demo_id"])
    )
    assert matching["title"] == "English Climate March"
    assert matching["description"] == "English description for the seeded demonstration."
    assert matching["tags"] == ["peace", "climate"]


def test_demo_detail_cache_is_split_by_resolved_locale(client, db, seeded_data):
    _set_demo_translation(db, seeded_data["demo_id"])

    english = client.get(
        f"/demonstration/{seeded_data['demo_id']}",
        headers={"Accept-Language": "en"},
    )
    finnish = client.get(
        f"/demonstration/{seeded_data['demo_id']}",
        headers={"Accept-Language": "fi"},
    )

    assert english.status_code == 200
    assert finnish.status_code == 200

    english_body = english.get_data(as_text=True)
    finnish_body = finnish.get_data(as_text=True)
    assert '<h1 class="demo-title">English Climate March</h1>' in english_body
    assert '<h1 class="demo-title">Climate March Helsinki</h1>' in finnish_body


def test_calendar_month_view_renders_translated_demo_titles(client, db, seeded_data):
    _set_demo_translation(db, seeded_data["demo_id"])
    _set_client_locale(client, "en")

    response = client.get("/calendar/2026/5/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "English Climate March" in body
