from datetime import datetime, timedelta, timezone


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


def _issue_read_token(db, user_id):
    from bson import ObjectId

    from mielenosoitukset_fi.utils.tokens import _hash_token

    token = "integration-read-token"
    db.api_tokens.insert_one(
        {
            "_id": ObjectId(),
            "user_id": user_id,
            "token": _hash_token(token),
            "type": "short",
            "category": "user",
            "scopes": ["read"],
            "expires_at": datetime.now(timezone.utc) + timedelta(days=2),
            "created_at": datetime.now(timezone.utc),
        }
    )
    return token


def test_demo_detail_renders_translated_fields_and_language_switcher(
    client, db, seeded_data
):
    _set_demo_translation(db, seeded_data["demo_id"])
    _set_client_locale(client, "en")

    response = client.get(f"/demonstration/{seeded_data['demo_id']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '<h1 class="demo-title">English Climate March</h1>' in body
    assert "English description for the seeded demonstration." in body
    assert '<h1 class="demo-title">Climate March Helsinki</h1>' not in body
    assert "/set_language/fi" in body
    assert "/set_language/en" in body

    _set_client_locale(client, "fi")
    finnish_response = client.get(f"/demonstration/{seeded_data['demo_id']}")

    assert finnish_response.status_code == 200
    finnish_body = finnish_response.get_data(as_text=True)
    assert '<h1 class="demo-title">Climate March Helsinki</h1>' in finnish_body
    assert '<h1 class="demo-title">English Climate March</h1>' not in finnish_body


def test_demo_api_returns_translated_card_fields_for_active_locale(
    client, db, seeded_data
):
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
    assert matching["resolved_language"] == "en"
    assert matching["available_languages"] == ["en", "fi"]


def test_demo_api_v1_search_matches_translated_fields(client, db, seeded_data):
    _set_demo_translation(db, seeded_data["demo_id"])

    response = client.get("/api/v1/demonstrations?search=english")

    assert response.status_code == 200
    payload = response.get_json()
    assert any(
        demo["_id"] == str(seeded_data["demo_id"])
        for demo in payload["demonstrations"]
    )


def test_demo_api_blueprint_returns_localized_results_for_requested_language(
    client, db, seeded_data
):
    _set_demo_translation(db, seeded_data["demo_id"])

    response = client.get("/api/demonstrations?lang=en")

    assert response.status_code == 200
    payload = response.get_json()
    matching = next(
        demo for demo in payload["results"] if demo["_id"] == str(seeded_data["demo_id"])
    )
    assert matching["title"] == "English Climate March"
    assert matching["description"] == "English description for the seeded demonstration."
    assert matching["tags"] == ["peace", "climate"]
    assert matching["resolved_language"] == "en"
    assert matching["available_languages"] == ["en", "fi"]
    assert "translations" not in matching


def test_demo_api_blueprint_uses_session_locale_when_lang_missing(client, db, seeded_data):
    _set_demo_translation(db, seeded_data["demo_id"])
    _set_client_locale(client, "en")

    response = client.get("/api/demonstrations")

    assert response.status_code == 200
    payload = response.get_json()
    matching = next(
        demo for demo in payload["results"] if demo["_id"] == str(seeded_data["demo_id"])
    )
    assert matching["title"] == "English Climate March"
    assert matching["resolved_language"] == "en"


def test_demo_api_blueprint_can_include_translation_map(client, db, seeded_data):
    _set_demo_translation(db, seeded_data["demo_id"])

    response = client.get("/api/demonstrations?lang=en&include_translations=true")

    assert response.status_code == 200
    payload = response.get_json()
    matching = next(
        demo for demo in payload["results"] if demo["_id"] == str(seeded_data["demo_id"])
    )
    assert matching["translations"]["en"]["title"] == "English Climate March"


def test_demo_api_blueprint_detail_returns_localized_payload(client, db, seeded_data):
    _set_demo_translation(db, seeded_data["demo_id"])
    token = _issue_read_token(db, seeded_data["user_id"])

    response = client.get(
        f"/api/demonstrations/{seeded_data['demo_id']}?lang=en",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["title"] == "English Climate March"
    assert payload["description"] == "English description for the seeded demonstration."
    assert payload["resolved_language"] == "en"
    assert payload["available_languages"] == ["en", "fi"]
    assert "translations" not in payload


def test_demo_api_blueprint_detail_can_include_translation_map(
    client, db, seeded_data
):
    _set_demo_translation(db, seeded_data["demo_id"])
    token = _issue_read_token(db, seeded_data["user_id"])

    response = client.get(
        f"/api/demonstrations/{seeded_data['demo_id']}?lang=en&include_translations=true",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["translations"]["en"]["title"] == "English Climate March"


def test_demo_api_blueprint_search_and_tag_filters_match_translations(
    client, db, seeded_data
):
    _set_demo_translation(db, seeded_data["demo_id"])

    response = client.get("/api/demonstrations?search=english&tag=peace")

    assert response.status_code == 200
    payload = response.get_json()
    assert any(
        demo["_id"] == str(seeded_data["demo_id"])
        for demo in payload["results"]
    )


def test_calendar_month_view_renders_translated_demo_titles(client, db, seeded_data):
    _set_demo_translation(db, seeded_data["demo_id"])
    _set_client_locale(client, "en")

    response = client.get("/calendar/2026/5/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "English Climate March" in body


def test_set_language_redirects_back_to_safe_next_path(client):
    response = client.get("/set_language/en?next=/demonstrations?search=climate")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/demonstrations?search=climate")
