"""Offline bootstrap contract tests; no claim about real certificate-chain validation."""
import os
from pathlib import Path
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
PIP_REQUIREMENT = (
    "pip @ https://files.pythonhosted.org/packages/3f/06/"
    "3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/"
    "pip-26.2.2-py3-none-any.whl#sha256="
    "fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"
)


@pytest.mark.parametrize("exit_code", [0, 17])
def test_bootstrap_uses_hashed_wheel_and_propagates_failure(tmp_path, exit_code):
    interpreter = tmp_path / "python with spaces"
    interpreter.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@"\nexit "$BOOTSTRAP_TEST_EXIT"\n',
        encoding="utf-8",
    )
    interpreter.chmod(0o700)
    result = subprocess.run(
        ["bash", str(ROOT / "deploy/bootstrap_python_trust.sh"), str(interpreter)],
        env={**os.environ, "BOOTSTRAP_TEST_EXIT": str(exit_code)},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == exit_code
    assert result.stdout.splitlines() == [
        "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir",
        "--upgrade", PIP_REQUIREMENT,
    ]


def test_dependency_entrypoints_bootstrap_before_index_install():
    workflow = yaml.safe_load((ROOT / ".github/workflows/tests.yml").read_text())
    install = next(step["run"] for step in workflow["jobs"]["python-tests"]["steps"]
                   if step.get("name") == "Install dependencies")
    docker = (ROOT / "Dockerfile").read_text()
    assert install.index("bash deploy/bootstrap_python_trust.sh python") < install.index("python -m pip install")
    assert docker.index("COPY deploy/bootstrap_python_trust.sh") < docker.index("RUN bash deploy/bootstrap_python_trust.sh python")
    assert "&& python -m pip install --no-cache-dir -r requirements.txt" in docker
    assert "ca-certificates" in docker
    assert "certifi==2026.10.19" in (ROOT / "requirements.txt").read_text().splitlines()
