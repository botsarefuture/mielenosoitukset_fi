"""Keep the CI host workaround scoped without downgrading/skipping tests."""

from pathlib import Path

import yaml


def test_mongo_compatible_runner_keeps_database_and_required_suite():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/tests.yml").read_text())
    compose = yaml.safe_load((root / "compose.test.yml").read_text())
    job = workflow["jobs"]["python-tests"]
    assert job["runs-on"] == "ubuntu-22.04"
    assert compose["services"]["mongo"]["image"] == "mongo:8"
    assert not job.get("continue-on-error", False)
    setup = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python@"))
    assert setup["with"]["python-version"] == "3.12"
    steps = {step["name"]: step for step in job["steps"]}
    assert "mongo redis mailpit localstack" in steps["Start disposable test services"]["run"]
    assert "--with-deps chromium" in steps["Install Chromium for Playwright"]["run"]
    for name in ("Wait for test services", "Run test suite"):
        assert not steps[name].get("continue-on-error", False)
        assert "if" not in steps[name]
    assert "pytest" in steps["Run test suite"]["run"]
