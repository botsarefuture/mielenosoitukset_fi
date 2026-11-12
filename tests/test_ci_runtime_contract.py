"""Keep the CI host workaround scoped without downgrading/skipping tests."""

from pathlib import Path
import shlex

import yaml


def test_mongo_compatible_runner_keeps_database_and_required_suite():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/tests.yml").read_text())
    compose = yaml.safe_load((root / "compose.test.yml").read_text())
    job = workflow["jobs"]["python-tests"]
    # GitHub-hosted ubuntu-22.04 stays the default and the only host for fork
    # PRs; the MOSO_CI_RUNS_ON variable may opt same-repo runs into moso-ci.
    runs_on = job["runs-on"]
    assert "github.event.pull_request.head.repo.full_name != github.repository) && 'ubuntu-22.04'" in runs_on
    assert "fromJSON(vars.MOSO_CI_RUNS_ON || '\"ubuntu-22.04\"')" in runs_on
    assert compose["services"]["mongo"]["image"] == "mongo:8"
    assert not job.get("continue-on-error", False)
    assert job["timeout-minutes"] == 30
    setup = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python@"))
    assert setup["with"]["python-version"] == "3.12"
    steps = {step["name"]: step for step in job["steps"]}
    assert "mongo redis mailpit localstack" in steps["Start disposable test services"]["run"]
    assert "--with-deps chromium" in steps["Install Chromium for Playwright"]["run"]
    for name in ("Wait for test services", "Run test suite"):
        assert not steps[name].get("continue-on-error", False)
        assert "if" not in steps[name]
    assert shlex.split(steps["Run test suite"]["run"]) == [
        "python", "-u", "-m", "pytest", "-o", "addopts=", "-v", "--tb=short",
        "--durations=25", "--timeout=180", "--timeout-method=thread",
        "-o", "faulthandler_timeout=120",
    ]

    concurrency = workflow["concurrency"]
    assert "github.event.pull_request.number" in concurrency["group"]
    assert concurrency["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"
