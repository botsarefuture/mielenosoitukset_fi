"""The deploy script can learn the application virtual environment from a root-owned file."""

import os
import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path("deploy/production_deploy.sh").read_text(encoding="utf-8")
FUNCTION = re.search(r"^load_deploy_env\(\) \{.*?^\}", SCRIPT, re.S | re.M).group(0)
DEFAULT_RECEIPT = "/var/lib/mielenosoitukset-fi-deploy/dependencies.json"


def _load(path, **env):
    result = subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + FUNCTION + '\nload_deploy_env "$1"', "_", str(path)],
        capture_output=True, text=True, timeout=10,
        env={"PATH": os.environ["PATH"], **env},
    )
    return result.returncode, result.stdout.splitlines(), result.stderr


def test_missing_file_keeps_system_python_defaults(tmp_path):
    assert _load(tmp_path / "absent") == (0, ["python3", DEFAULT_RECEIPT], "")


def test_file_selects_the_venv_and_its_own_receipt(tmp_path):
    python = tmp_path / "venv-python"
    python.write_text("#!/bin/sh\n"); python.chmod(0o755)
    config = tmp_path / "deploy.env"
    config.write_text(f"# venv\n\nPRODUCTION_PYTHON={python}\nPRODUCTION_DEPENDENCY_RECEIPT=/var/lib/x/venv.json\n")
    config.chmod(0o644)
    assert _load(config) == (0, [str(python), "/var/lib/x/venv.json"], "")


def test_environment_still_wins_over_the_file(tmp_path):
    python = tmp_path / "venv-python"
    python.write_text("#!/bin/sh\n"); python.chmod(0o755)
    config = tmp_path / "deploy.env"
    config.write_text(f"PRODUCTION_PYTHON={python}\n"); config.chmod(0o600)
    code, values, _ = _load(config, PRODUCTION_PYTHON="/usr/bin/python3")
    assert code == 0 and values[0] == "/usr/bin/python3"


@pytest.mark.parametrize("content,mode,message", [
    ("PRODUCTION_PYTHON=/usr/bin/python3; rm -rf /\n", 0o644, "unsupported line"),
    ("PRODUCTION_PYTHON=$(id)\n", 0o644, "unsupported line"),
    ("export PRODUCTION_PYTHON=/usr/bin/python3\n", 0o644, "unsupported line"),
    ("PATH=/tmp\n", 0o644, "unsupported setting"),
    ("PRODUCTION_PYTHON=/nonexistent/python\n", 0o644, "not executable"),
    ("PRODUCTION_PYTHON=/usr/bin/python3\n", 0o666, "group- or world-writable"),
    ("PRODUCTION_PYTHON=/usr/bin/python3\n", 0o620, "group- or world-writable"),
])
def test_unsafe_or_unknown_settings_are_refused(tmp_path, content, mode, message):
    config = tmp_path / "deploy.env"
    config.write_text(content); config.chmod(mode)
    code, values, error = _load(config)
    assert code == 2 and values == [] and message in error


def test_symlinked_settings_file_is_refused(tmp_path):
    target = tmp_path / "real.env"
    target.write_text("PRODUCTION_PYTHON=/usr/bin/python3\n"); target.chmod(0o644)
    link = tmp_path / "deploy.env"
    link.symlink_to(target)
    code, _, error = _load(link)
    assert code == 2 and "regular file" in error


def test_script_resolves_python_before_any_use():
    assert SCRIPT.index("load_deploy_env \"$deploy_env\"") < SCRIPT.index('"$production_python" "$repo_dir/deploy/install_dependencies.py"')
    assert '|| exit 2' in SCRIPT.split('load_deploy_env "$deploy_env"')[1].splitlines()[0]
