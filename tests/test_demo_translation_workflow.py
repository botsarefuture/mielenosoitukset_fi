def test_translator_can_access_translation_dashboard(translator_client):
    response = translator_client.get("/admin/demo/translations")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Demojen käännökset" in body


def test_translator_can_open_translation_editor(translator_client, seeded_data):
    response = translator_client.get(f"/admin/demo/{seeded_data['demo_id']}/translations?language=en")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Käännösehdotus" in body


def test_translator_can_submit_demo_translation_proposal(translator_client, db, seeded_data):
    demo_id = seeded_data["demo_id"]

    response = translator_client.post(
        f"/admin/demo/{demo_id}/translations",
        data={
            "language": "en",
            "translated_title": "Climate March Helsinki in English",
            "translated_description": "An English translation proposal.",
            "translated_tags": "climate, march",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    demo_doc = db.demonstrations.find_one({"_id": demo_id})
    proposal = demo_doc["translation_proposals"]["en"]
    assert proposal["status"] == "pending"
    assert proposal["title"] == "Climate March Helsinki in English"
    assert proposal["description"] == "An English translation proposal."
    assert proposal["tags"] == ["climate", "march"]
    assert proposal["submitted_by"] == str(seeded_data["translator_id"])


def test_admin_can_approve_demo_translation_proposal(admin_client, db, seeded_data):
    demo_id = seeded_data["demo_id"]
    db.demonstrations.update_one(
        {"_id": demo_id},
        {
            "$set": {
                "translation_proposals.en": {
                    "language": "en",
                    "title": "Climate March Helsinki in English",
                    "description": "Approved English translation.",
                    "tags": ["climate", "march"],
                    "status": "pending",
                    "submitted_by": str(seeded_data["translator_id"]),
                    "submitted_by_name": "Translator User",
                }
            }
        },
    )

    response = admin_client.post(
        f"/admin/demo/{demo_id}/translations/en/approve",
        data={"review_notes": "Looks good."},
        follow_redirects=False,
    )

    assert response.status_code == 302

    demo_doc = db.demonstrations.find_one({"_id": demo_id})
    assert demo_doc["translations"]["en"]["title"] == "Climate March Helsinki in English"
    assert demo_doc["translation_proposals"]["en"]["status"] == "approved"
    assert demo_doc["translation_proposals"]["en"]["review_notes"] == "Looks good."


def test_regular_user_cannot_access_translation_dashboard(user_client):
    response = user_client.get("/admin/demo/translations")
    assert response.status_code == 403
