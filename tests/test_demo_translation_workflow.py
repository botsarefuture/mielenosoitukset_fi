def test_translator_can_access_translation_dashboard(translator_client):
    response = translator_client.get("/admin/demo/translations")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Demojen käännökset" in body


def test_translation_dashboard_hides_past_demos_by_default(translator_client, db, seeded_data):
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$set": {"date": "2020-01-01", "title": "Past Translation Demo"}},
    )

    response = translator_client.get("/admin/demo/translations")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Past Translation Demo" not in body


def test_translation_dashboard_never_includes_past_demos(translator_client, db, seeded_data):
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$set": {"date": "2020-01-01", "title": "Past Translation Demo"}},
    )

    response = translator_client.get("/admin/demo/translations?include_past=true")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Past Translation Demo" not in body
    assert "Näytä myös menneet mielenosoitukset" not in body


def test_translation_dashboard_hides_unchanged_recurring_children(
    translator_client, db, seeded_data
):
    db.recu_demos.update_one(
        {"_id": seeded_data["recu_demo_id"]},
        {"$set": {"description": "<p>Shared description</p>"}},
    )
    db.demonstrations.update_one(
        {"_id": seeded_data["child_demo_id"]},
        {
            "$set": {
                "date": "2099-05-02",
                "title": "Unchanged Recurring Child",
                "description": "Shared description",
                "parent": seeded_data["recu_demo_id"],
            }
        },
    )

    response = translator_client.get("/admin/demo/translations")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Unchanged Recurring Child" not in body


def test_translation_dashboard_shows_changed_recurring_children(
    translator_client, db, seeded_data
):
    db.recu_demos.update_one(
        {"_id": seeded_data["recu_demo_id"]},
        {"$set": {"description": "Parent description"}},
    )
    db.demonstrations.update_one(
        {"_id": seeded_data["child_demo_id"]},
        {
            "$set": {
                "date": "2099-05-02",
                "title": "Changed Recurring Child",
                "description": "Child-specific description",
                "parent": seeded_data["recu_demo_id"],
            }
        },
    )

    response = translator_client.get("/admin/demo/translations")

    assert response.status_code == 200
    assert "Changed Recurring Child" in response.get_data(as_text=True)


def test_translator_can_open_translation_editor(translator_client, seeded_data):
    response = translator_client.get(f"/admin/demo/{seeded_data['demo_id']}/translations?language=en")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Käännösehdotus" in body
    assert "Tee käännös kolmessa helpossa vaiheessa" in body
    assert "Näytä opastus uudelleen" in body
    assert "translation-description-preview" in body
    assert "translation-editor.js" in body


def test_translation_editor_displays_descriptions_as_markdown(translator_client, db, seeded_data):
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {
            "$set": {
                "description": "<p>Source <strong>bold</strong></p><ul><li>First item</li></ul>",
                "translation_proposals.en": {
                    "language": "en",
                    "title": "English title",
                    "description": "<p>Proposal <em>emphasis</em></p>",
                    "tags": [],
                    "status": "pending",
                },
            }
        },
    )

    response = translator_client.get(f"/admin/demo/{seeded_data['demo_id']}/translations?language=en")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Source **bold**" in body
    assert "- First item" in body
    assert "Proposal *emphasis*" in body
    assert "<p>Source <strong>bold</strong></p>" not in body
    assert "<p>Proposal <em>emphasis</em></p>" not in body


def test_translator_can_generate_cached_deepl_suggestion(translator_client, db, seeded_data, monkeypatch):
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$set": {"date": "2099-05-01"}},
    )

    from mielenosoitukset_fi.utils import demo_translation_cache as cache_module

    suggestion = {
        "title": "DeepL English title",
        "description": "DeepL English description",
        "tags": ["peace", "climate"],
        "_meta": {
            "provider": "deepl",
            "source_language": "fi",
            "target_language": "en",
            "auto_generated": True,
        },
    }

    class _FakeSuggestionsCollection:
        def __init__(self):
            self.docs = []

        def find_one(self, query):
            for doc in self.docs:
                if all(doc.get(key) == value for key, value in query.items()):
                    return dict(doc)
            return None

        def update_one(self, query, update, upsert=False):
            doc = self.find_one(query)
            if doc is None:
                doc = dict(query)
                doc.update(update.get("$setOnInsert", {}))
                self.docs.append(doc)
            doc.update(update.get("$set", {}))
            for index, existing in enumerate(self.docs):
                if all(existing.get(key) == query.get(key) for key in query):
                    self.docs[index] = doc
                    break

        def create_index(self, *args, **kwargs):
            return None

    monkeypatch.setattr(
        cache_module,
        "translation_suggestions_collection",
        _FakeSuggestionsCollection(),
    )
    monkeypatch.setattr(
        cache_module,
        "build_deepl_translation_suggestions",
        lambda source_payload, source_language, target_languages, **kwargs: {
            "en": suggestion
        },
    )

    response = translator_client.post(
        f"/admin/demo/{seeded_data['demo_id']}/translations/en/suggest",
        follow_redirects=True,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "DeepL English title" in body
    assert "Luo DeepL-ehdotus" not in body


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
    assert proposal["description"] == "<p>An English translation proposal.</p>"
    assert proposal["tags"] == ["climate", "march"]
    assert proposal["submitted_by"] == str(seeded_data["translator_id"])


def test_translation_proposal_stores_markdown_as_safe_html(translator_client, db, seeded_data):
    demo_id = seeded_data["demo_id"]

    response = translator_client.post(
        f"/admin/demo/{demo_id}/translations",
        data={
            "language": "en",
            "translated_title": "English title",
            "translated_description": (
                "**Important**\n\n- One\n- Two\n\n<script>alert(1)</script>\n\n"
                "[Unsafe link](javascript:alert(1))"
            ),
            "translated_tags": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    proposal = db.demonstrations.find_one({"_id": demo_id})["translation_proposals"]["en"]
    assert "<strong>Important</strong>" in proposal["description"]
    assert "<li>One</li>" in proposal["description"]
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in proposal["description"]
    assert "<script>" not in proposal["description"]
    assert "javascript:" not in proposal["description"]


def test_translator_proposal_can_record_deepl_provenance(translator_client, db, seeded_data):
    demo_id = seeded_data["demo_id"]

    response = translator_client.post(
        f"/admin/demo/{demo_id}/translations",
        data={
            "language": "en",
            "translated_title": "Climate March Helsinki in English",
            "translated_description": "An English translation proposal.",
            "translated_tags": "climate, march",
            "suggestion_provider": "deepl",
            "suggestion_source_hash": "abc123",
            "suggestion_auto_generated": "true",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    demo_doc = db.demonstrations.find_one({"_id": demo_id})
    proposal = demo_doc["translation_proposals"]["en"]
    assert proposal["_meta"]["provider"] == "deepl"
    assert proposal["_meta"]["source_hash"] == "abc123"
    assert proposal["_meta"]["auto_generated"] is True


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
