"""Regression tests for commit-aware production health verification."""

import io
import socketserver
import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError

import pytest

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
    assert '--unix-socket "$health_socket"' in deploy_script
    assert "PRODUCTION_HEALTH_SOCKET" in deploy_script
    assert "https://mielenosoitukset.fi/health" in workflow
    assert "--unix-socket" not in workflow
    assert "id: deploy_origin" in workflow
    assert 'echo "verified_sha=$GITHUB_SHA" >> "$GITHUB_OUTPUT"' in workflow
    assert '--origin-verified-sha "${{ steps.deploy_origin.outputs.verified_sha }}"' in workflow
    assert workflow.index('"deploy $GITHUB_SHA"') < workflow.index('echo "verified_sha=')
    assert "?deploy=" not in workflow
    assert 'restrict,command="' in documentation
    assert "no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty" in documentation


@pytest.mark.parametrize("status,body,expected", [
    (200, '{"status":"ok","build_sha":"' + SHA + '"}', SHA),
    (503, '{"status":"ok","build_sha":"' + SHA + '"}', None),
    (200, "not JSON", None),
    (200, '{"status":"unhealthy","build_sha":"' + SHA + '"}', None),
    (200, '{"status":"ok","build_sha":"abc123"}', None),
])
@pytest.mark.parametrize("scheme", ["http", "https"])
def test_verifier_reads_origin_socket_without_proxy(monkeypatch, status, body, expected, scheme):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, self.headers.get("Host")))
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *_args):
            pass

    # Short paths avoid platform-specific Unix socket path-length limits.
    with tempfile.TemporaryDirectory(prefix="health-test-", dir="/tmp") as directory:
        socket_path = str(Path(directory) / "app.sock")
        with socketserver.UnixStreamServer(socket_path, Handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
            monkeypatch.setenv("https_proxy", "http://127.0.0.1:1")
            monkeypatch.setattr(verify_health_sha, "urlopen", lambda *_a, **_k: pytest.fail("Origin probe used public transport"))
            try:
                assert verify_health_sha.fetch_build_sha(
                    f"{scheme}://mielenosoitukset.fi/health", 1, unix_socket=socket_path,
                ) == expected
                monkeypatch.setattr("sys.argv", ["verify", SHA,
                    f"{scheme}://mielenosoitukset.fi/health", "--unix-socket", socket_path,
                    "--attempts", "1", "--timeout", "1"])
                assert verify_health_sha.main() == (0 if expected == SHA else 1)
            finally:
                server.shutdown()
                thread.join(timeout=2)
    assert requests == [("/health", "mielenosoitukset.fi")] * 2


def test_verifier_reports_cloudflare_challenge_without_body_or_url(monkeypatch, capsys):
    def blocked(*_args, **_kwargs):
        raise HTTPError("https://private.invalid/?secret=redact", 403, "Forbidden", {
            "cf-mitigated": "challenge",
        }, io.BytesIO(b"private response body"))

    monkeypatch.setattr(verify_health_sha, "urlopen", blocked)
    assert verify_health_sha.fetch_build_sha("https://example.test/health", 1) is None
    error = capsys.readouterr().err
    assert "HTTP 403 (Cloudflare challenge)" in error
    assert "private" not in error
    assert "secret" not in error


def test_verifier_reports_missing_origin_socket(capsys):
    with tempfile.TemporaryDirectory(prefix="health-test-", dir="/tmp") as directory:
        assert verify_health_sha.fetch_build_sha(
            "http://mielenosoitukset.fi/health", 1,
            unix_socket=str(Path(directory) / "missing.sock"),
        ) is None
    assert "FileNotFoundError" in capsys.readouterr().err


def test_verifier_passes_socket_while_waiting_for_new_worker(monkeypatch):
    observed = iter([OLD_SHA, SHA])
    sockets = []

    def probe(_url, _timeout, *, unix_socket):
        sockets.append(unix_socket)
        return next(observed)

    monkeypatch.setattr(verify_health_sha, "fetch_build_sha", probe)
    monkeypatch.setattr(verify_health_sha.time, "sleep", lambda _delay: None)
    assert verify_health_sha.wait_for_build(
        SHA, "http://mielenosoitukset.fi/health", attempts=2, delay=0, timeout=1,
        unix_socket="/example/app.sock",
    )
    assert sockets == ["/example/app.sock", "/example/app.sock"]


@pytest.mark.parametrize("url", ["ftp://example.test/health", "http://user:password@example.test/health", "https://user:password@example.test/health"])
def test_verifier_rejects_unsupported_or_credentialed_socket_urls(monkeypatch, url):
    monkeypatch.setattr("sys.argv", ["verify", SHA, url, "--unix-socket", "/example/app.sock"])
    with pytest.raises(SystemExit) as exc:
        verify_health_sha.main()
    assert exc.value.code == 2


@pytest.mark.parametrize("socket_args", [[], ["--unix-socket", ""]])
def test_verifier_distinguishes_empty_from_omitted_socket(monkeypatch, capsys, socket_args):
    probes = []

    def probe(*args, **kwargs):
        probes.append(kwargs["unix_socket"])
        return True

    monkeypatch.setattr(verify_health_sha, "wait_for_build", probe)
    monkeypatch.setattr("sys.argv", ["verify", SHA, "https://example.test/health", *socket_args])
    if socket_args:
        with pytest.raises(SystemExit) as exc:
            verify_health_sha.main()
        assert exc.value.code == 2
        assert "--unix-socket requires a nonempty path" in capsys.readouterr().err
        assert probes == []
    else:
        assert verify_health_sha.main() == 0
        assert probes == [None]


@pytest.mark.parametrize("status,challenge,body,origin_proof,expected", [
    (403, True, "private challenge body", True, 0),
    (403, True, "private challenge body", False, 1),
    (403, False, "private denied body", True, 1),
    (503, True, "private unavailable body", True, 1),
    (200, False, '{"status":"ok","build_sha":"' + SHA + '"}', True, 0),
    (200, False, '{"status":"ok","build_sha":"' + OLD_SHA + '"}', True, 1),
    (200, False, '{"status":"unhealthy","build_sha":"' + SHA + '"}', True, 1),
    (200, False, 'not JSON', True, 1),
    (None, False, '', True, 1),
])
def test_public_challenge_warning_requires_verified_origin(
    monkeypatch, capsys, status, challenge, body, origin_proof, expected
):
    from urllib.error import URLError

    def response(*_args, **_kwargs):
        if status is None:
            raise URLError("private network failure")
        if status != 200:
            raise HTTPError("https://private.invalid/?secret=redact", status, "Error", {
                "cf-mitigated": "challenge" if challenge else "other",
            }, io.BytesIO(body.encode()))
        return io.BytesIO(body.encode())

    monkeypatch.setattr(verify_health_sha, "urlopen", response)
    args = ["verify", SHA, "https://example.test/health", "--attempts", "1"]
    if origin_proof:
        args.extend(["--origin-verified-sha", SHA])
    monkeypatch.setattr("sys.argv", args)
    assert verify_health_sha.main() == expected
    captured = capsys.readouterr()
    warning = status == 403 and challenge and origin_proof
    assert ("::warning::" in captured.out) == warning
    if warning:
        assert "public reachability is NOT verified" in captured.out
        assert "serving expected build" not in captured.out
    assert "private" not in captured.out + captured.err
    assert "secret" not in captured.out + captured.err


@pytest.mark.parametrize("proof,url,extra", [
    (OLD_SHA, "https://example.test/health", []),
    ("", "https://example.test/health", []),
    (SHA, "http://example.test/health", []),
    (SHA, "https://user:password@example.test/health", []),
    (SHA, "https://example.test/health", ["--unix-socket", "/example/app.sock"]),
])
def test_public_origin_receipt_must_match_expected_https_build(monkeypatch, proof, url, extra):
    monkeypatch.setattr(verify_health_sha, "wait_for_build", lambda *_a, **_k: pytest.fail("Invalid receipt probed"))
    monkeypatch.setattr("sys.argv", ["verify", SHA, url, "--origin-verified-sha", proof, *extra])
    with pytest.raises(SystemExit) as error:
        verify_health_sha.main()
    assert error.value.code == 2


@pytest.mark.parametrize("first_body", [
    '{"status":"ok","build_sha":"' + OLD_SHA + '"}',
    '{"status":"unhealthy","build_sha":"' + SHA + '"}',
])
def test_later_challenge_cannot_hide_previous_bad_public_health(monkeypatch, capsys, first_body):
    responses = iter([io.BytesIO(first_body.encode()), None])

    def response(*_args, **_kwargs):
        payload = next(responses)
        if payload is not None:
            return payload
        raise HTTPError("https://example.test/health", 403, "Forbidden", {
            "cf-mitigated": "challenge",
        }, io.BytesIO(b"challenge"))

    monkeypatch.setattr(verify_health_sha, "urlopen", response)
    monkeypatch.setattr("sys.argv", ["verify", SHA, "https://example.test/health",
        "--origin-verified-sha", SHA, "--attempts", "2", "--delay", "0"])
    assert verify_health_sha.main() == 1
    assert "::warning::" not in capsys.readouterr().out
