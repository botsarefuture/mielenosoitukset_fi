"""Regression tests for commit-aware production health verification."""

from deploy import verify_health_sha
from mielenosoitukset_fi.utils import build_info


SHA = "a" * 40
OLD_SHA = "b" * 40


def test_build_sha_is_captured_from_environment(monkeypatch):
    monkeypatch.setenv("MIELENOSOITUKSET_BUILD_SHA", SHA)
    assert build_info.resolve_build_sha() == SHA


def test_build_sha_file_rejects_partial_or_invalid_values(monkeypatch, tmp_path):
    build_file = tmp_path / "build-sha"
    build_file.write_text("abc123\n", encoding="utf-8")
    monkeypatch.delenv("MIELENOSOITUKSET_BUILD_SHA", raising=False)
    monkeypatch.setenv("MIELENOSOITUKSET_BUILD_SHA_FILE", str(build_file))
    assert build_info.resolve_build_sha() == "unknown"

    build_file.write_text(f"{SHA}\n", encoding="utf-8")
    assert build_info.resolve_build_sha() == SHA


def test_health_endpoint_publishes_uncached_worker_build(app):
    app.config["BUILD_SHA"] = SHA
    response = app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "build_sha": SHA}
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Build-SHA"] == SHA


def test_verifier_waits_past_old_worker_for_replacement(monkeypatch):
    observed = iter([OLD_SHA, OLD_SHA, SHA])
    monkeypatch.setattr(
        verify_health_sha,
        "fetch_build_sha",
        lambda _url, _timeout: next(observed),
    )
    monkeypatch.setattr(verify_health_sha.time, "sleep", lambda _delay: None)

    assert verify_health_sha.wait_for_build(
        SHA,
        "https://example.test/health",
        attempts=3,
        delay=0,
        timeout=1,
    )


def test_verifier_rejects_plain_200_without_matching_metadata(monkeypatch):
    monkeypatch.setattr(
        verify_health_sha,
        "fetch_build_sha",
        lambda _url, _timeout: None,
    )
    monkeypatch.setattr(verify_health_sha.time, "sleep", lambda _delay: None)

    assert not verify_health_sha.wait_for_build(
        SHA,
        "https://example.test/health",
        attempts=2,
        delay=0,
        timeout=1,
    )


def test_production_deploy_contract_is_sha_bound():
    deploy_script = open("deploy/production_deploy.sh", encoding="utf-8").read()
    workflow = open(".github/workflows/production-deploy.yml", encoding="utf-8").read()
    documentation = open("docs/production-deployment.md", encoding="utf-8").read()

    assert ".deploy-build-sha" in deploy_script
    assert "deploy/verify_health_sha.py" in deploy_script
    assert "deploy/verify_health_sha.py" in workflow
    assert "?deploy=" not in workflow
    assert 'restrict,command="' in documentation
    assert "no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty" in documentation
