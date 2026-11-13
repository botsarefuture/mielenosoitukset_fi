"""SEC-04: a decided suggestion cannot be decided or applied again."""


def _url(seeded_data, tail):
    return f"/admin/demo/suggestions/{seeded_data['suggestion_id']}/{tail}"


def _suggestion(db, seeded_data):
    return db.demo_suggestions.find_one({"_id": seeded_data["suggestion_id"]})


def test_applied_field_is_not_applied_twice_but_other_fields_still_can_be(
    admin_client, db, seeded_data
):
    db.demo_suggestions.update_one(
        {"_id": seeded_data["suggestion_id"]},
        {"$set": {"suggested_fields": {"title": "T1", "city": "Turku"}}},
    )
    admin_client.post(_url(seeded_data, "apply"), data={"apply_field": ["title"]})
    first = _suggestion(db, seeded_data)
    assert first["status"] == "applied" and first["applied_fields"] == ["title"]
    history = db.demo_edit_history.count_documents({})

    # Replaying the same field changes nothing and writes no history.
    admin_client.post(_url(seeded_data, "apply"), data={"apply_field": ["title"]})
    assert db.demo_edit_history.count_documents({}) == history
    assert _suggestion(db, seeded_data)["applied_at"] == first["applied_at"]

    # Admins can still apply a different field of the same suggestion.
    admin_client.post(_url(seeded_data, "apply"), data={"apply_field": ["city"]})
    after = _suggestion(db, seeded_data)
    assert after["applied_fields"] == ["city", "title"]
    demo = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
    assert demo["title"] == "T1" and demo["city"] == "Turku"


def test_rejected_suggestion_cannot_be_applied(admin_client, db, seeded_data):
    admin_client.post(_url(seeded_data, "status"), data={"status": "rejected"})
    assert _suggestion(db, seeded_data)["status"] == "rejected"
    before = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
    admin_client.post(_url(seeded_data, "apply"), data={"apply_field": ["title"]})
    assert _suggestion(db, seeded_data)["status"] == "rejected"
    assert db.demonstrations.find_one({"_id": seeded_data["demo_id"]}) == before


def test_applied_suggestion_cannot_be_rejected_afterwards(admin_client, db, seeded_data):
    admin_client.post(_url(seeded_data, "apply"), data={"apply_field": ["title"]})
    admin_client.post(_url(seeded_data, "status"), data={"status": "rejected"})
    assert _suggestion(db, seeded_data)["status"] == "applied"
