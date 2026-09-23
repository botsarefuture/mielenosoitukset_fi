from datetime import timedelta

from mielenosoitukset_fi.utils.time_utils import utcnow


class _JobManagerStub:
    def __init__(self, runs):
        self.runs = runs
        self.calls = []

    def get_job_info(self, job_key):
        if job_key != "example_job":
            raise KeyError(job_key)
        return {
            "key": job_key,
            "name": "Example job",
            "description": "Background job detail test",
            "enabled": True,
            "allow_manual_trigger": True,
            "trigger_args": {"minutes": 15},
            "next_run_at": utcnow() + timedelta(minutes=15),
            "last_run_started_at": utcnow(),
            "last_run_status": "success",
            "last_message": "Completed",
        }

    def count_runs(self, job_key):
        assert job_key == "example_job"
        return len(self.runs)

    def get_recent_runs(self, job_key, *, limit, skip):
        assert job_key == "example_job"
        self.calls.append({"limit": limit, "skip": skip})
        return self.runs[skip : skip + limit]


def test_background_job_detail_uses_shared_server_pagination(
    app, admin_client
):
    now = utcnow()
    runs = [
        {
            "id": f"run-{index}",
            "started_at": now - timedelta(minutes=index),
            "duration_seconds": index / 10,
            "triggered_by": "scheduler",
            "status": "success",
            "message": f"Run {index}",
            "metadata": {},
            "trace": None,
        }
        for index in range(45)
    ]
    manager = _JobManagerStub(runs)
    app.extensions["job_manager"] = manager

    response = admin_client.get(
        "/admin/background-jobs/example_job?page=2&per_page=20&run_id=run-21"
    )

    assert response.status_code == 200
    assert manager.calls == [{"limit": 20, "skip": 20}]
    html = response.get_data(as_text=True)
    assert "Näytetään 21–40 / 45 kirjauksesta" in html
    assert "Sivu 2 / 3" in html
    assert "page=1" in html
    assert "page=3" in html
    assert "per_page=20" in html
    assert "run_id=run-21" in html
    assert 'class="admin-data-view__footer admin-pagination"' in html


def test_background_job_detail_normalizes_legacy_page_size(app, admin_client):
    manager = _JobManagerStub([])
    app.extensions["job_manager"] = manager

    response = admin_client.get(
        "/admin/background-jobs/example_job?limit=25&page=99"
    )

    assert response.status_code == 200
    assert manager.calls == [{"limit": 20, "skip": 0}]
    html = response.get_data(as_text=True)
    assert "Ei lokitapahtumia" in html
    assert "Sivu 1 / 1" in html

