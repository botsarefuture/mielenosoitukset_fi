from bson import ObjectId
from pymongo import DeleteMany, DeleteOne, InsertOne, ReplaceOne, UpdateMany, UpdateOne
import pytest


def _demo_doc(demo_id, title):
    return {
        "_id": demo_id,
        "title": title,
        "date": "2026-05-01",
        "start_time": "12:00",
        "end_time": "14:00",
        "city": "Helsinki",
        "address": "Mannerheimintie 1, Helsinki",
        "approved": False,
        "rejected": False,
        "hide": False,
        "cancelled": False,
        "in_past": False,
        "organizers": [],
        "tags": [],
        "route": [],
    }


def _history_for_demo(db, demo_id):
    return list(db.demo_edit_history.find({"demo_id": str(demo_id)}).sort("edited_at", 1))


def _audit_actions_for_demo(db, demo_id):
    return [doc["action"] for doc in db.demo_audit_logs.find({"demo_id": str(demo_id)})]


@pytest.mark.integration
@pytest.mark.jobs
def test_background_job_manager_executes_prep_job_and_records_audit(app, seeded_data, db):
    job_manager = app.extensions["job_manager"]
    job_manager._ensure_job_documents()

    job_keys = {job["key"] for job in job_manager.list_jobs()}
    assert "prep" in job_keys

    job_manager._execute_job("prep", triggered_by="pytest")

    prepped = list(db.prepped_analytics.find({}))
    assert prepped
    assert {doc["demo_id"] for doc in prepped} >= {
        seeded_data["demo_id"],
        seeded_data["pending_demo_id"],
    }

    job_doc = db.background_jobs.find_one({"_id": "prep"})
    assert job_doc["last_run_status"] == "success"
    assert job_doc["last_run_triggered_by"] == "pytest"

    run_doc = db.background_job_runs.find_one({"job_key": "prep"})
    assert run_doc is not None
    assert run_doc["status"] == "success"


@pytest.mark.integration
@pytest.mark.jobs
def test_background_job_audit_records_history_for_all_demo_write_paths(db):
    from mielenosoitukset_fi.background_jobs.audit import job_audit_context

    insert_one_id = ObjectId()
    insert_many_ids = [ObjectId(), ObjectId()]
    update_one_id = ObjectId()
    update_many_ids = [ObjectId(), ObjectId()]
    replace_one_id = ObjectId()
    find_replace_id = ObjectId()
    find_update_id = ObjectId()
    delete_one_id = ObjectId()
    delete_many_ids = [ObjectId(), ObjectId()]
    find_delete_id = ObjectId()
    bulk_insert_id = ObjectId()
    bulk_update_ids = [ObjectId(), ObjectId()]
    bulk_replace_id = ObjectId()
    bulk_delete_one_id = ObjectId()
    bulk_delete_many_ids = [ObjectId(), ObjectId()]

    seed_docs = [
        _demo_doc(update_one_id, "Update One"),
        _demo_doc(update_many_ids[0], "Update Many A"),
        _demo_doc(update_many_ids[1], "Update Many B"),
        _demo_doc(replace_one_id, "Replace One"),
        _demo_doc(find_replace_id, "Find Replace"),
        _demo_doc(find_update_id, "Find Update"),
        _demo_doc(delete_one_id, "Delete One"),
        _demo_doc(delete_many_ids[0], "Delete Many A"),
        _demo_doc(delete_many_ids[1], "Delete Many B"),
        _demo_doc(find_delete_id, "Find Delete"),
        _demo_doc(bulk_update_ids[0], "Bulk Update A"),
        _demo_doc(bulk_update_ids[1], "Bulk Update B"),
        _demo_doc(bulk_replace_id, "Bulk Replace"),
        _demo_doc(bulk_delete_one_id, "Bulk Delete One"),
        _demo_doc(bulk_delete_many_ids[0], "Bulk Delete Many A"),
        _demo_doc(bulk_delete_many_ids[1], "Bulk Delete Many B"),
    ]
    db.demonstrations.insert_many(seed_docs)

    with job_audit_context("pytest_job", ObjectId()):
        db.demonstrations.insert_one(_demo_doc(insert_one_id, "Insert One"))
        db.demonstrations.insert_many([
            _demo_doc(insert_many_ids[0], "Insert Many A"),
            _demo_doc(insert_many_ids[1], "Insert Many B"),
        ])
        db.demonstrations.update_one({"_id": update_one_id}, {"$set": {"title": "Update One Changed"}})
        db.demonstrations.update_many(
            {"_id": {"$in": update_many_ids}},
            {"$set": {"city": "Espoo"}},
        )
        db.demonstrations.replace_one(
            {"_id": replace_one_id},
            _demo_doc(replace_one_id, "Replace One Changed"),
        )
        db.demonstrations.find_one_and_replace(
            {"_id": find_replace_id},
            _demo_doc(find_replace_id, "Find Replace Changed"),
        )
        db.demonstrations.find_one_and_update(
            {"_id": find_update_id},
            {"$set": {"address": "Kaivokatu 1, Helsinki"}},
        )
        db.demonstrations.delete_one({"_id": delete_one_id})
        db.demonstrations.delete_many({"_id": {"$in": delete_many_ids}})
        db.demonstrations.find_one_and_delete({"_id": find_delete_id})
        db.demonstrations.bulk_write(
            [
                InsertOne(_demo_doc(bulk_insert_id, "Bulk Insert")),
                UpdateOne({"_id": bulk_update_ids[0]}, {"$set": {"title": "Bulk Update A Changed"}}),
                UpdateMany({"_id": {"$in": bulk_update_ids}}, {"$set": {"approved": True}}),
                ReplaceOne({"_id": bulk_replace_id}, _demo_doc(bulk_replace_id, "Bulk Replace Changed")),
                DeleteOne({"_id": bulk_delete_one_id}),
                DeleteMany({"_id": {"$in": bulk_delete_many_ids}}),
            ]
        )

    expected_actions = {
        "pytest_job:insert_one",
        "pytest_job:insert_many",
        "pytest_job:update_one",
        "pytest_job:update_many",
        "pytest_job:replace_one",
        "pytest_job:find_one_and_replace",
        "pytest_job:find_one_and_update",
        "pytest_job:delete_one",
        "pytest_job:delete_many",
        "pytest_job:find_one_and_delete",
        "pytest_job:bulk_write.insert_one",
        "pytest_job:bulk_write.update_one",
        "pytest_job:bulk_write.update_many",
        "pytest_job:bulk_write.replace_one",
        "pytest_job:bulk_write.delete_one",
        "pytest_job:bulk_write.delete_many",
    }

    actions = {doc["action"] for doc in db.demo_audit_logs.find({"username": "[JOB] pytest_job"})}
    assert expected_actions <= actions

    for demo_id in [insert_one_id, *insert_many_ids, update_one_id, *update_many_ids, replace_one_id]:
        history = _history_for_demo(db, demo_id)
        assert history
        assert history[-1]["demo_id"] == str(demo_id)


@pytest.mark.integration
@pytest.mark.jobs
def test_background_job_history_preserves_demo_id_on_replace_and_update(db):
    from mielenosoitukset_fi.background_jobs.audit import job_audit_context

    demo_id = ObjectId()
    db.demonstrations.insert_one(_demo_doc(demo_id, "Stable ID Demo"))

    with job_audit_context("id_stability_job", ObjectId()):
        db.demonstrations.replace_one(
            {"_id": demo_id},
            _demo_doc(demo_id, "Stable ID Demo Replaced"),
        )
        db.demonstrations.find_one_and_update(
            {"_id": demo_id},
            {"$set": {"city": "Vantaa"}},
        )

    history = _history_for_demo(db, demo_id)
    assert len(history) == 2
    for entry in history:
        assert entry["demo_id"] == str(demo_id)
        assert entry["old_demo"]["_id"] == demo_id
        assert entry["new_demo"]["_id"] == demo_id

    assert _audit_actions_for_demo(db, demo_id) == [
        "id_stability_job:replace_one",
        "id_stability_job:find_one_and_update",
    ]


@pytest.mark.integration
def test_submit_route_is_idempotent_and_does_not_create_duplicate_demo(client, db):
    form_data = {
        "title": "Idempotent Submission Demo",
        "date": "2026-08-15",
        "description": "Regression test for duplicate submission handling.",
        "start_time": "15:00",
        "end_time": "17:00",
        "facebook": "",
        "city": "Helsinki",
        "address": "Testikatu 1, Helsinki",
        "type": "other",
        "tags": "test,idempotent",
        "submitter_role": "organizer",
        "submitter_email": "submitter@example.test",
        "submitter_name": "Submitter Example",
        "accept_terms": "on",
        "submission_token": "stable-submission-token",
    }

    first_response = client.post(
        "/submit",
        data=form_data,
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    second_response = client.post(
        "/submit",
        data=form_data,
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.get_json()["success"] is True
    assert second_response.get_json()["duplicate"] is True
    assert second_response.get_json()["reason"] in {"token", "fingerprint"}

    matching_demos = list(db.demonstrations.find({"title": "Idempotent Submission Demo"}))
    assert len(matching_demos) == 1

    submitters = list(db.submitters.find({"demonstration_id": matching_demos[0]["_id"]}))
    assert len(submitters) == 1

    token_doc = db.demo_submission_tokens.find_one({"token": "stable-submission-token"})
    assert token_doc is not None
    assert token_doc["status"] == "completed"
    assert token_doc["demo_id"] == matching_demos[0]["_id"]


@pytest.mark.integration
@pytest.mark.jobs
def test_merge_duplicate_submissions_repoints_references_and_audits(db):
    from mielenosoitukset_fi.scripts.merge_duplicate_submissions import merge_duplicate_submissions

    primary_id = ObjectId()
    duplicate_id = ObjectId()
    duplicate_demo = _demo_doc(duplicate_id, "Duplicate Pending Demo")
    primary_demo = _demo_doc(primary_id, "Duplicate Pending Demo")
    primary_demo["created_datetime"] = duplicate_demo["created_datetime"] = None
    primary_demo["approved"] = duplicate_demo["approved"] = False

    db.demonstrations.insert_many([primary_demo, duplicate_demo])
    db.submitters.insert_one({"_id": ObjectId(), "demonstration_id": primary_id, "submitter_email": "a@example.test"})
    db.demo_notifications_queue.insert_one({"_id": ObjectId(), "demo_id": duplicate_id, "status": "pending"})
    db.cases.insert_one({"_id": ObjectId(), "demo_id": duplicate_id})
    db.demo_reminders.insert_one({"_id": ObjectId(), "demonstration_id": duplicate_id})
    db.demo_cancellation_tokens.insert_one({"_id": ObjectId(), "demo_id": duplicate_id})

    merged = merge_duplicate_submissions(db=db)

    assert merged == 1

    hidden_duplicate = db.demonstrations.find_one({"_id": duplicate_id})
    assert hidden_duplicate["merged_into"] == primary_id
    assert hidden_duplicate["hide"] is True

    assert db.demo_notifications_queue.find_one({"demo_id": primary_id}) is not None
    assert db.cases.find_one({"demo_id": primary_id}) is not None
    assert db.demo_reminders.find_one({"demonstration_id": primary_id}) is not None
    assert db.demo_cancellation_tokens.find_one({"demo_id": primary_id}) is not None

    primary_actions = _audit_actions_for_demo(db, primary_id)
    duplicate_actions = _audit_actions_for_demo(db, duplicate_id)
    assert "merge_duplicate_submission" in primary_actions
    assert "merged_into_duplicate_submission" in duplicate_actions
