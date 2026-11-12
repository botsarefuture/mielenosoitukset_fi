"""Real Git/receipt I/O; package mutation is deliberately simulated, not production acceptance."""

import json
from pathlib import Path
import subprocess

import pytest

from deploy import install_dependencies as installer


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    manifest = repo / "requirements.txt"
    manifest.write_text("Flask==3.1.1\n", encoding="utf-8")
    subprocess.run(["git", "add", "requirements.txt"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                    "commit", "-qm", "Serving baseline"], cwd=repo, check=True)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    baseline = tmp_path / "build-sha"
    baseline.write_text(sha, encoding="utf-8")
    manifest.write_text("Flask==3.1.1\ncertifi==2026.10.19\n", encoding="utf-8")
    subprocess.run(["git", "add", "requirements.txt"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                    "commit", "-qm", "Target checkout already advanced"], cwd=repo, check=True)
    installed = {"flask": "3.1.3", "certifi": "2026.2.25"}
    monkeypatch.setattr(installer, "installed_version", installed.get)
    monkeypatch.setattr(installer, "is_virtual_environment", lambda: False)
    return repo, tmp_path / "state/dependencies.json", baseline, installed


def test_readonly_legacy_adopts_verified_delta_without_downgrading_drift(deployment, monkeypatch, capsys):
    repo, receipt, baseline, installed = deployment
    installed["certifi"] = "2026.10.19"
    monkeypatch.setattr(installer, "install_pins", lambda *_: pytest.fail("System environment must not mutate"))
    installer.ensure_dependencies(repo, receipt, baseline)
    first = json.loads(receipt.read_text())
    assert first["manifest"] == {"flask": "3.1.1", "certifi": "2026.10.19"}
    assert first["managed_pins"] == {"certifi": "2026.10.19"}
    assert installed["flask"] == "3.1.3"
    assert '"flask": "3.1.3"' in capsys.readouterr().out
    assert receipt.stat().st_mode & 0o777 == 0o600
    installer.ensure_dependencies(repo, receipt, baseline)
    assert json.loads(receipt.read_text()) == first
    installed["certifi"] = "2026.2.25"
    with pytest.raises(RuntimeError, match="system Python is read-only"):
        installer.ensure_dependencies(repo, receipt, baseline)
    assert json.loads(receipt.read_text()) == first


def test_failed_same_checkout_retry_requires_install_until_success(deployment, monkeypatch):
    repo, receipt, baseline, installed = deployment
    monkeypatch.setattr(installer, "is_virtual_environment", lambda: True)
    calls = []

    def install(_repo, pins):
        calls.append(pins.copy())
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, ["pip", "install"])
        installed.update(pins)

    monkeypatch.setattr(installer, "install_pins", install)
    with pytest.raises(subprocess.CalledProcessError):
        installer.ensure_dependencies(repo, receipt, baseline)
    assert not receipt.exists()
    installer.ensure_dependencies(repo, receipt, baseline)
    assert calls == [{"flask": "3.1.1", "certifi": "2026.10.19"}] * 2
    assert receipt.exists()
    installer.ensure_dependencies(repo, receipt, baseline)
    assert len(calls) == 2


def test_failed_delta_keeps_previous_receipt_until_same_sha_retry_succeeds(deployment, monkeypatch):
    repo, receipt, baseline, installed = deployment
    installed["certifi"] = "2026.10.19"
    installer.ensure_dependencies(repo, receipt, baseline)
    acknowledged = receipt.read_bytes()
    (repo / "requirements.txt").write_text("Flask==3.1.4\ncertifi==2026.10.19\n")
    monkeypatch.setattr(installer, "is_virtual_environment", lambda: True)
    calls = []

    def install(_repo, pins):
        calls.append(pins.copy())
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, ["pip", "install"])
        installed.update(pins)

    monkeypatch.setattr(installer, "install_pins", install)
    with pytest.raises(subprocess.CalledProcessError):
        installer.ensure_dependencies(repo, receipt, baseline)
    assert receipt.read_bytes() == acknowledged
    installer.ensure_dependencies(repo, receipt, baseline)
    assert calls == [{"flask": "3.1.4"}] * 2
    assert json.loads(receipt.read_text())["managed_pins"] == {"flask": "3.1.4", "certifi": "2026.10.19"}


@pytest.mark.parametrize("failure", ["system", "no_baseline", "wrong_runtime", "bad_receipt", "unsupported", "lying_install", "receipt_write"])
def test_dependency_gate_fails_closed(deployment, monkeypatch, failure):
    repo, receipt, baseline, installed = deployment
    attempts = []
    monkeypatch.setattr(installer, "install_pins", lambda *_: attempts.append("install"))
    if failure == "no_baseline":
        baseline.unlink()
    elif failure == "wrong_runtime":
        receipt.parent.mkdir()
        receipt.write_text(json.dumps({"schema": 1, "runtime": {}}))
    elif failure == "bad_receipt":
        receipt.parent.mkdir()
        receipt.write_text("partial JSON")
    elif failure == "unsupported":
        (repo / "requirements.txt").write_text("-r secret.env\n")
    elif failure == "lying_install":
        monkeypatch.setattr(installer, "is_virtual_environment", lambda: True)
    elif failure == "receipt_write":
        installed["certifi"] = "2026.10.19"

        def fail_replace(*_args):
            raise OSError("Simulated receipt persistence failure")

        monkeypatch.setattr(installer.os, "replace", fail_replace)
    old = receipt.read_bytes() if receipt.exists() else None
    with pytest.raises((RuntimeError, ValueError, OSError)):
        installer.ensure_dependencies(repo, receipt, baseline)
    assert (receipt.read_bytes() if receipt.exists() else None) == old
    assert attempts == (["install"] if failure == "lying_install" else [])
    assert not list(receipt.parent.glob(".dependencies-*"))


@pytest.mark.parametrize("pins", ["", "requests>=2", "requests==2\nRequests==2", "pkg==1.*", "pkg @ https://example.test/x"])
def test_production_manifest_requires_unambiguous_exact_pins(pins):
    with pytest.raises(ValueError):
        installer.parse_pins(pins)


def test_repository_requirements_follow_deployment_pin_contract():
    text = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text()
    pins = installer.parse_pins(text)
    assert "flask" in pins and "certifi" in pins


def test_production_dependency_gate_precedes_index_reload_and_health():
    source = (Path(__file__).resolve().parents[1] / "deploy/production_deploy.sh").read_text()
    assert "git diff --quiet" not in source
    assert source.index("deploy/install_dependencies.py") < source.index("provision_public_indexes")
    assert source.index("deploy/install_dependencies.py") < source.index('systemctl reload "$service_name"')
    assert '"$production_python" "$repo_dir/deploy/install_dependencies.py"' in source
    assert '"$production_python" -m mielenosoitukset_fi.scripts.provision_public_indexes' in source
    assert '"$production_python" "$repo_dir/deploy/verify_health_sha.py"' in source


@pytest.mark.parametrize("fail_at", [None, 1, 2])
def test_owned_install_bootstraps_then_installs_and_checks_without_system_bypass(monkeypatch, tmp_path, fail_at):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs == {"check": True}
        if len(calls) == fail_at:
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(installer.subprocess, "run", run)
    if fail_at:
        with pytest.raises(subprocess.CalledProcessError):
            installer.install_pins(tmp_path, {"certifi": "2026.10.19"})
    else:
        installer.install_pins(tmp_path, {"certifi": "2026.10.19"})
    expected = [
        ["bash", str(tmp_path / "deploy/bootstrap_python_trust.sh"), installer.sys.executable],
        [installer.sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir", "certifi==2026.10.19"],
        [installer.sys.executable, "-m", "pip", "check"],
    ]
    expected_calls = expected if fail_at is None else expected[:fail_at]
    assert calls == expected_calls
