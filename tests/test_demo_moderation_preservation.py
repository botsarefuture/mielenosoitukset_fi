"""Ordinary edits must not erase server-owned moderation identity."""

import pytest

from tests.test_demo_decision_service import _capture_decision_email


@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_model_content_save_preserves_moderation_state(
    admin_client, db, seeded_data, monkeypatch, status
):
    from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration

    queued = _capture_decision_email(monkeypatch)
    demo_id = seeded_data["pending_demo_id"]
    endpoint = "approve" if status == "approved" else "deny"
    assert admin_client.post(f"/api/admin/demo/{demo_id}/{endpoint}").status_code == 200
    before = db.demonstrations.find_one({"_id": demo_id})
    model = Demonstration.from_dict(before)
    model.title = "Updated content, same moderation decision"
    model.description = None
    model.save()
    after = db.demonstrations.find_one({"_id": demo_id})
    assert after["title"] == model.title
    assert after["description"] is None
    assert after.get("moderation_decision") == before["moderation_decision"]
    assert after.get("approved") is (status == "approved")
    assert after.get("rejected") is (status == "rejected")
    repeated = admin_client.post(f"/api/admin/demo/{demo_id}/{endpoint}")
    assert repeated.status_code == 200
    assert repeated.get_json()["changed"] is False
    assert len(queued) == 1


def test_model_creation_still_inserts_complete_content(app, db):
    from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration

    model = Demonstration.from_dict({
        "title": "New model creation", "date": "2099-01-01", "city": "Helsinki",
        "start_time": "12:00", "address": "Testikatu 1", "aliases": [],
    })
    model.save()
    stored = db.demonstrations.find_one({"_id": model._id})
    assert stored["title"] == model.title
    assert stored["city"] == "Helsinki"
    assert stored["approved"] is False
    assert "moderation_decision" not in stored


def test_form_content_edit_keeps_approval_identity_and_case_history(
    admin_client, db, seeded_data, monkeypatch
):
    queued = _capture_decision_email(monkeypatch)
    demo_id = seeded_data["pending_demo_id"]
    assert admin_client.post(f"/api/admin/demo/{demo_id}/approve").status_code == 200
    before = db.demonstrations.find_one({"_id": demo_id})
    before_case = db.cases.find_one({"_id": seeded_data["case_id"]})
    response = admin_client.post(f"/admin/demo/edit_demo/{demo_id}", data={
        "title": "Changed title, no new decision", "date": before["date"],
        "city": before["city"], "approved": "on",
    })
    assert response.status_code == 302
    after = db.demonstrations.find_one({"_id": demo_id})
    assert after["title"] == "Changed title, no new decision"
    assert after["moderation_decision"] == before["moderation_decision"]
    assert db.cases.find_one({"_id": seeded_data["case_id"]}) == before_case
    assert len(queued) == 1
