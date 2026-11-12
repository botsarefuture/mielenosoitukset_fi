#!/usr/bin/env python3
"""Compare existing Flask detail HTML and Go detail JSON on isolated synthetic data.

Run with project Python3.12 development dependencies, local test services and Go.
This is a response-workload comparison, not an end-to-end page speed claim.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from measure_http_latency import summarize


def probe(request, output, samples, go):
    from bson import ObjectId
    from datetime import date
    from socket import socket
    from tests import conftest as fixtures
    db = request.getfixturevalue("db")
    app = request.getfixturevalue("app")
    if not db.name.startswith("mielenosoitukset_test_"):
        raise RuntimeError("Expected disposable test database")
    event_id = ObjectId()
    db.demonstrations.insert_one({
        "_id": event_id, "title": "Synthetic public demonstration", "description": "Public detail benchmark. " * 30,
        "date": date.today().isoformat(), "start_time": "17:00", "end_time": "18:00", "city": "Helsinki",
        "address": "Test square", "approved": True, "hide": False, "rejected": False, "cancelled": False,
        "latitude": "60.1699", "longitude": "24.9384", "organizers": [], "tags": ["benchmark"],
        "route": [], "recurs": False, "default_language": "fi", "event_type": "STAY_STILL",
    })
    flask = request.getfixturevalue("live_server")
    with socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    out = Path(output)
    binary = out / "go-public-api"
    subprocess.run([go, "build", "-o", str(binary), "."], cwd=ROOT / "go-api", check=True)
    env = {**os.environ, "MONGODB_URI": fixtures.TEST_MONGO_URI, "MONGODB_DATABASE": db.name, "API_ADDR": f"127.0.0.1:{port}"}
    with (out / "go-server.log").open("w") as log:
        server = subprocess.Popen([str(binary)], env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 15
            while True:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    if time.monotonic() >= deadline or server.poll() is not None:
                        raise RuntimeError("Go API did not become healthy")
                    time.sleep(.1)
            urls = {"flask_detail_html": f"{flask}/demonstration/{event_id}", "go_detail_json": f"http://127.0.0.1:{port}/api/demonstrations/{event_id}"}
            timings = {key: [] for key in urls}
            sizes = {}
            cache_headers = {}
            for index in range(samples + 10):
                # Alternate request order to reduce order/time bias.
                order = list(urls) if index % 2 == 0 else list(reversed(urls))
                for key in order:
                    start = time.perf_counter()
                    with urllib.request.urlopen(urls[key], timeout=10) as response:
                        body = response.read(5 * 1024 * 1024)
                        cache_headers[key] = {name: response.headers.get(name) for name in ("X-Cache", "Cache-Control")}
                        if response.status != 200:
                            raise RuntimeError("Unexpected response status")
                    elapsed = (time.perf_counter() - start) * 1000
                    if key == "go_detail_json" and json.loads(body)["title"] != "Synthetic public demonstration":
                        raise RuntimeError("API data mismatch")
                    if key == "flask_detail_html" and b"Synthetic public demonstration" not in body:
                        raise RuntimeError("HTML data mismatch")
                    sizes[key] = len(body)
                    if index >= 10:
                        timings[key].append(elapsed)
            results = {
                "comparison": "Existing Flask HTML response vs new Go JSON response; different payloads/workloads, not Go-only speedup or browser rendering.",
                "samples_per_endpoint": samples, "warmup_per_endpoint": 10, "errors": 0,
                "environment": "loopback, sequential alternating requests, real isolated MongoDB synthetic event; Flask test WSGI and Go net/http",
                "go_version": subprocess.check_output([go, "version"], text=True).strip(),
                "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "working_tree": subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True),
                "cache": {"headers": cache_headers, "flask_config": {key: app.config.get(key) for key in ("TESTING","CACHE_TYPE","CACHE_DEFAULT_TIMEOUT")}},
                "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((ROOT / "go-api").glob("*.go"))},
                "results": {key: {**summarize(values), "response_bytes": sizes[key]} for key, values in timings.items()},
                "limits": ["Not a production load/capacity test", "No browser/assets/LCP/network/CDN", "No frontend integration yet", "No authenticated-user traffic", "Small p99 tail sample; descriptive percentile only"],
            }
            (out / "results.json").write_text(json.dumps(results, indent=2))
        finally:
            server.terminate()
            try:
                server.wait(timeout=12)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--go", default=shutil.which("go") or "/opt/homebrew/bin/go")
    args = parser.parse_args()
    if not 20 <= args.samples <= 1000:
        parser.error("samples must be20..1000")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Reuse the existing test fixtures, overriding only their historical broad cleanup.
    with tempfile.TemporaryDirectory(prefix="moso-detail-api-probe-") as temporary:
        path = Path(temporary)
        (path / "conftest.py").write_text('''import shutil
import pytest
from tests.conftest import *
import tests.conftest as fixtures
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_resources():
    yield
    instance = fixtures.DatabaseManager._instance
    if instance is not None:
        instance.get_db().client.drop_database(fixtures.TEST_DB_NAME)
        instance.close_connection()
        fixtures.DatabaseManager._instance = None
    fixtures.DatabaseManager.close_retired_test_connections()
    fixtures._test_mongo_clients.close()
    fixtures._database_manager_module.MongoClient = fixtures._original_manager_client_factory
    shutil.rmtree(fixtures._CONFIG_DIR, ignore_errors=True)
''')
        (path / "test_probe.py").write_text(f'''import importlib.util

def test_probe(request):
    spec=importlib.util.spec_from_file_location("detail_api_probe", {str(Path(__file__).resolve())!r})
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.probe(request,{str(args.output_dir.resolve())!r},{args.samples!r},{args.go!r})
''')
        subprocess.run([sys.executable, "-m", "pytest", "-c", str(ROOT / "pytest.ini"), str(path / "test_probe.py"), "-o", "addopts=", "-q", "--tb=short"], cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, check=True)
    print((args.output_dir / "results.json").read_text())

if __name__ == "__main__":
    main()
