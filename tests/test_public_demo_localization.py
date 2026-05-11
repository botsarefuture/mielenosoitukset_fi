def _set_client_locale(client, locale):
    with client.session_transaction() as session:
        session["locale"] = locale


def test_demo_detail_renders_translated_fields_and_language_switcher(client, db, seeded_data):
    demo_id = seeded_data["demo_id"]
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
    _set_client_locale(client, "en")

    response = client.get(f"/demonstration/{demo_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "English Climate March" in body
    assert "English description for the seeded demonstration." in body
    assert "Climate March Helsinki" not in body
    assert "/set_language/fi" in body
    assert "/set_language/en" in body
