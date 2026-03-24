import pytest


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
