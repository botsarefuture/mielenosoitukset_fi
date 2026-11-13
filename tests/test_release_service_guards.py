"""Isolated checks for public release decisions and immutable API artifacts."""

import hashlib
import json
import shlex
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


def _shell_function(path, name):
    source = path.read_text()
    return source.split(f"{name}() {{\n", 1)[1].split("\n}\n", 1)[0]


@pytest.mark.parametrize("status,payload,expected", [
    (200, {"status": "ok", "build_sha": SHA}, SHA),
    (200, {"status": "degraded", "build_sha": SHA}, ""),
    (503, {"status": "ok", "build_sha": SHA}, ""),
    (200, {"status": "ok", "build_sha": "A" * 40}, ""),
    (200, {"status": "ok", "build_sha": "g" * 40}, ""),
])
def test_deployed_sha_requires_successful_healthy_full_sha(status, payload, expected):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, *_args):
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = _shell_function(ROOT / "deploy/release_public.sh", "deployed_sha")
            shell = f'production_python={sys.executable!r}\ndeployed_sha() {{\n{body}\n}}\ndeployed_sha "$1"'
            result = subprocess.run(
                ["bash", "-c", shell, "bash", f"http://127.0.0.1:{server.server_port}/health"],
                capture_output=True, text=True, check=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
    assert result.stdout.strip() == expected


def _api_release_prefix(tmp_path, existing=None):
    source = (ROOT / "deploy/go-api/deploy.sh").read_text()
    guard = source.split("release_dir=", 1)[1].split("\nbackup_dir=", 1)[0]
    release_dir = tmp_path / SHA
    release_dir.mkdir()
    if existing is not None:
        (release_dir / "api").write_bytes(existing)
    binary = b"reviewed-api-binary"
    digest = hashlib.sha256(binary).hexdigest()
    verifier = (
        "import hashlib,sys; expected,path=sys.stdin.readline().strip().split('  ',1); "
        "sys.exit(0 if hashlib.sha256(open(path,'rb').read()).hexdigest()==expected else 1)"
    )
    shell = ("set -euo pipefail\n"
             f"sha256sum() {{ {shlex.quote(sys.executable)} -c {shlex.quote(verifier)}; }}\n"
             f"binary_sha={digest}\nrelease_dir={shlex.quote(str(release_dir))}\n"
             f"{guard.split(chr(10), 1)[1]}\n")
    return shell, release_dir, binary


def test_existing_sha_rejects_different_binary_before_release_side_effects(tmp_path):
    shell, release_dir, _ = _api_release_prefix(tmp_path, b"different-binary")
    result = subprocess.run(["bash", "-c", shell], capture_output=True, text=True)
    assert result.returncode != 0
    assert "refusing overwrite" in result.stderr
    assert (release_dir / "api").read_bytes() == b"different-binary"
    assert sorted(path.name for path in tmp_path.iterdir()) == [SHA]


def test_matching_sha_retry_preserves_executable_inode(tmp_path):
    binary = b"reviewed-api-binary"
    shell, release_dir, _ = _api_release_prefix(tmp_path, binary)
    executable = release_dir / "api"
    before = executable.stat().st_ino
    source = (ROOT / "deploy/go-api/deploy.sh").read_text()
    install_line = next(line for line in source.splitlines() if '"$script_dir/api" "$release_dir/api"' in line)
    shell += f'install() {{ printf called > {tmp_path / "install-called"}; }}\nscript_dir={tmp_path}\n{install_line}\n'
    result = subprocess.run(["bash", "-c", shell], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert executable.stat().st_ino == before
    assert executable.read_bytes() == binary
    assert not (tmp_path / "install-called").exists()
