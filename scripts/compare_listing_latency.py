#!/usr/bin/env python3
"""Compare two Git refs over loopback HTTP using isolated real test fixtures.

Example (development dependencies and MongoDB required)::
    python scripts/compare_listing_latency.py --before d79adc03 --after HEAD \
        --output-dir /tmp/moso-listing-latency

Requires Python 3.12+ and the project development dependencies.
Only generated disposable databases and local servers are used. This measures
HTTP responses, not browser rendering, assets, LCP or production capacity.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

# Share the existing interpolation and reporting rules.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_http_latency import MAX_RESPONSE_BYTES, summarize

TAG = "latency-baseline"
ORGANIZATION_ID = "00000000000000000000e001"
OTHER_ORGANIZATION_ID = "00000000000000000000e002"
ORGANIZATION_NAME = "Latency Organization"
LIMITS = [
    "Loopback HTTP only: no browser rendering, JavaScript, images, CSS, LCP or user network.",
    "Single sequential client and Werkzeug test WSGI server; not production capacity.",
    "Synthetic data in separate disposable MongoDB databases on the same local service.",
    "Warm responses, anonymous requests without cookies; local cache behavior applies.",
    "Percentiles are descriptive estimates, not statistical hypothesis-test p-values.",
    "Shared-host load and small tail sample sizes can influence results; no production target inferred.",
    "Page HTML and API responses have different work/payloads across the migration; compare semantics too.",
]


def serve_fixture(request, state_dir):
    """Run inside a separate pytest process rooted in an exported source tree."""
    from bson import ObjectId

    state = Path(state_dir)
    client = request.getfixturevalue("client")
    db = request.getfixturevalue("db")
    settings = request.getfixturevalue("test_settings")
    if not db.name.startswith("mielenosoitukset_test_"):
        raise RuntimeError("Refusing to seed a non-test database")
    documents = json.loads((state / "documents.json").read_text())
    for record in documents:
        record["_id"] = ObjectId(record["_id"])
        for organizer in record.get("organizers", []):
            organizer["organization_id"] = ObjectId(organizer["organization_id"])
    db.demonstrations.delete_many({})
    db.recurring_demonstrations.delete_many({})
    db.demonstrations.insert_many(documents)
    if any(record.get("organizers") for record in documents):
        for organization_id, name in ((ORGANIZATION_ID, ORGANIZATION_NAME), (OTHER_ORGANIZATION_ID, "Other benchmark organizer")):
            db.organizations.insert_one({"_id": ObjectId(organization_id), "name": name, "description": "Synthetic benchmark profile.", "email": "benchmark@example.test", "verified": True})
    base_url = request.getfixturevalue("live_server")
    app = client.application
    metadata = {
        "url": base_url,
        "document_count": db.demonstrations.count_documents({}),
        "document_sha256": hashlib.sha256((state / "documents.json").read_bytes()).hexdigest(),
        "python": sys.version,
        "database": db.name,
        "config": {key: app.config.get(key) for key in (
            "TESTING", "DEBUG", "CACHE_TYPE", "CACHE_DEFAULT_TIMEOUT",
            "ENFORCE_RATELIMIT", "DISABLE_BACKGROUND_JOBS", "ENABLE_CHAT",
            "ENABLE_EMAIL_WORKER", "DEFAULT_TIMEZONE", "BABEL_DEFAULT_LOCALE",
        )},
        "services": {key: settings[key] for key in (
            "mongo_uri", "redis_host", "redis_port", "mail_host", "mail_port", "s3_endpoint",
        )},
    }
    # Never emit credentials from optional test-service overrides.
    from urllib.parse import urlsplit
    for key in ("mongo_uri", "s3_endpoint"):
        parsed = urlsplit(metadata["services"][key])
        metadata["services"][key] = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or ''}"
    (state / "ready.json").write_text(json.dumps(metadata, indent=2, default=str))
    while not (state / "stop").exists():
        time.sleep(0.1)


PROBE_TEST = '''import importlib.util
import shutil
import pytest
import tests.conftest as fixtures

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_resources():
    # Override the broad historical cleanup: only drop this process's own DB.
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

def test_latency_probe(request):
    spec = importlib.util.spec_from_file_location("listing_latency_harness", {script!r})
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    harness.serve_fixture(request, {state!r})
'''


def export_ref(root, revision, destination):
    archive = destination.parent / f"{destination.name}.tar"
    with archive.open("wb") as output:
        subprocess.run(["git", "archive", revision], cwd=root, stdout=output, check=True)
    destination.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(destination, filter="data")
    archive.unlink()


def request_sample(url, timeout):
    result = subprocess.run([
        "curl", "--disable", "--silent", "--show-error", "--noproxy", "*",
        "--proto", "=http", "--max-time", str(timeout),
        "--max-filesize", str(MAX_RESPONSE_BYTES),
        "--user-agent", "mielenosoitukset-fi-local-comparison/1.0",
        "--output", "/dev/null", "--write-out",
        "%{http_code}\t%{time_total}\t%{time_starttransfer}\t%{size_download}", "--", url,
    ], capture_output=True, text=True, timeout=timeout + 1, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "curl request failed")
    status, total, first_byte, size = result.stdout.split("\t")
    if int(status) != 200:
        raise RuntimeError(f"Expected HTTP 200, got {status}: {url}")
    return {"status": int(status), "total_ms": float(total) * 1000,
            "ttfb_ms": float(first_byte) * 1000, "response_bytes": int(size)}


class PageContract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = None
        self.text = {"title": [], "h1": [], "h2": []}
        self.search_input = False
        self.submit_form = False
        self.fields = set()

    def handle_starttag(self, tag, attrs):
        if tag in self.text:
            self.active = tag
        attributes = dict(attrs)
        if tag == "form":
            self.submit_form |= attributes.get("id") == "myForm" and attributes.get("method", "").upper() == "POST"
        if tag in {"input", "select", "textarea"} and attributes.get("name"):
            self.fields.add(attributes["name"])
        if tag == "input":
            self.search_input |= attributes.get("name") == "search" or attributes.get("type") == "search"

    def handle_endtag(self, tag):
        if tag == self.active:
            self.active = None

    def handle_data(self, data):
        if self.active:
            self.text[self.active].append(data)


def verify_responses(base_url, routes, documents, output, side, timeout):
    """Check real response content once before warming and timing either side."""
    evidence = {}
    scoped_documents = [row for row in documents if any(org.get("organization_id") == ORGANIZATION_ID for org in row.get("organizers", []))]
    expected = sorted(documents, key=lambda item: (item["date"], item["start_time"], item["_id"]))[:12]
    for index, route in enumerate(routes):
        response = subprocess.run([
            "curl", "--disable", "--silent", "--show-error", "--fail", "--noproxy", "*",
            "--proto", "=http", "--max-time", str(timeout),
            "--max-filesize", str(MAX_RESPONSE_BYTES), "--", base_url + route,
        ], capture_output=True, timeout=timeout + 1, check=True)
        body = response.stdout.decode("utf-8")
        suffix = "json" if route.startswith("/api/") else "html"
        (output / f"{side}-route-{index}.{suffix}").write_text(body)
        contract = {"response_sha256": hashlib.sha256(response.stdout).hexdigest(), "bytes": len(response.stdout)}
        if suffix == "json":
            payload = json.loads(body)
            results = payload["results"]
            selected = scoped_documents if "organization_id=" in route else documents
            expected = sorted(selected, key=lambda item: (item["date"], item["start_time"], item["_id"]))[:12]
            if [item["_id"] for item in results] != [item["_id"] for item in expected]:
                raise RuntimeError(f"{side} API returned unexpected seeded IDs/order")
            if payload["total"] != len(selected) or any(
                item["city"] != "Helsinki" or TAG not in item["tags"] for item in results
            ):
                raise RuntimeError(f"{side} API did not preserve scoped seed values/count")
            contract.update(result_count=len(results), total=payload["total"], ids=[item["_id"] for item in results])
        else:
            page = PageContract()
            page.feed(body)
            title = " ".join(page.text["title"]).strip()
            heading = " ".join(page.text["h1"] + page.text["h2"]).strip()
            is_organization = route.startswith("/organization/")
            valid_title = ORGANIZATION_NAME in title and ORGANIZATION_NAME in heading if is_organization else "mielenosoit" in title.casefold()
            if not title or not heading or not valid_title or (route != "/submit" and not is_organization and not page.search_input):
                raise RuntimeError(f"{side} page title/heading/search contract failed: {route}")
            fixed = "Helsinki" if route.startswith("/city/") else TAG if route.startswith("/tag/") else None
            if fixed and fixed not in title:
                raise RuntimeError(f"{side} scoped page title missing {fixed}")
            if is_organization:
                if ORGANIZATION_ID not in body:
                    raise RuntimeError(f"{side} organization page lost its fixed scope")
                contract.update(title=title, heading=heading, organization_id=ORGANIZATION_ID)
            elif route == "/submit":
                required = {"title", "date", "city", "description", "submission_token", "accept_terms", "submitter_email"}
                if not page.submit_form or not required.issubset(page.fields):
                    raise RuntimeError(f"{side} submit form contract failed")
                contract.update(title=title, heading=heading, submit_form=True, fields=sorted(page.fields))
            else:
                contract.update(title=title, heading=heading, search_input=True)
        evidence[route] = contract
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("listings", "submit", "organization"), default="listings")
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=500)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--documents", type=int, default=120)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--startup-timeout", type=float, default=180)
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error("Python 3.12+ is required")
    if min(args.attempts, args.documents) < 1 or args.warmup < 0 or min(args.timeout, args.startup_timeout) <= 0:
        parser.error("attempts/documents/timeouts must be positive; warmup cannot be negative")
    if not shutil.which("curl"):
        parser.error("curl is required")
    root = Path(__file__).resolve().parents[1]
    refs = {side: subprocess.check_output(
        ["git", "rev-parse", f"{getattr(args, side)}^{{commit}}"], cwd=root, text=True,
    ).strip() for side in ("before", "after")}
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error("output directory must be empty, preserving previous results")
    benchmark_day = date.today()
    documents = []
    for number in range(args.documents):
        day = benchmark_day + timedelta(days=5 + number % 25)
        documents.append({
            "_id": f"{number + 1:024x}", "title": f"Latency demonstration {number + 1:03d}",
            "date": day.isoformat(), "formatted_date": day.strftime("%d.%m.%Y"),
            "start_time": "12:00", "end_time": "14:00", "city": "Helsinki",
            "address": "Mannerheimintie 1, Helsinki", "description": "Deterministic local benchmark event.",
            "approved": True, "hide": False, "rejected": False, "cancelled": False,
            "in_past": False, "organizers": [], "tags": [TAG], "route": [],
            "preview_image": "", "cover_picture": "", "gallery_images": [],
            "running_number": 5000 + number, "slug": f"latency-demonstration-{number + 1}",
            "latitude": "60.1699", "longitude": "24.9384", "type": "other",
            "event_type": "other", "editors": [],
        })
    if args.scope == "organization":
        for number, record in enumerate(documents):
            record["organizers"] = [{"name": ORGANIZATION_NAME, "organization_id": OTHER_ORGANIZATION_ID if number % 6 == 0 else ORGANIZATION_ID}]
    document_json = json.dumps(documents, indent=2, sort_keys=True)
    (output / "documents.json").write_text(document_json)
    routes = ["/demonstrations", "/city/Helsinki", f"/tag/{TAG}",
              f"/api/demonstrations?tag={TAG}&city=Helsinki&page=1&per_page=12&max_days_till=60"]
    if args.scope == "submit":
        routes = ["/submit"]
    elif args.scope == "organization":
        routes = [f"/organization/{ORGANIZATION_ID}", f"/api/demonstrations?organization_id={ORGANIZATION_ID}&page=1&per_page=12"]
    metadata = {"started_at": datetime.now(timezone.utc).isoformat(), "refs": refs,
                "arguments": {**vars(args), "output_dir": str(output)}, "routes": routes,
                "runtime": {"platform": platform.platform(), "python": sys.version,
                            "packages": {name: version(name) for name in ("Flask", "Werkzeug", "pymongo", "pytest")},
                            "curl": subprocess.check_output(["curl", "--version"], text=True).splitlines()[0]},
                "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "order": "Alternating AB/BA within each route and round; rotating route order each round",
                "limits": LIMITS, "servers": {}}
    children = []
    logs = []
    states = []
    samples = []
    try:
        with tempfile.TemporaryDirectory(prefix="moso-latency-comparison-") as temporary:
            temp = Path(temporary)
            try:
                for side in ("before", "after"):
                    tree, state = temp / side, temp / f"{side}-state"
                    export_ref(root, refs[side], tree)
                    state.mkdir()
                    states.append(state)
                    (state / "documents.json").write_text(document_json)
                    probe = tree / "tests" / "test_local_latency_probe.py"
                    probe.write_text(PROBE_TEST.format(script=str(Path(__file__).resolve()), state=str(state)))
                    log = (output / f"{side}-server.log").open("w")
                    logs.append(log)
                    env = {**os.environ, "PYTHONPATH": str(tree), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
                    children.append(subprocess.Popen(
                        [sys.executable, "-m", "pytest", "-s", "-q", str(probe)],
                        cwd=tree, env=env, stdout=log, stderr=subprocess.STDOUT,
                    ))
                deadline = time.monotonic() + args.startup_timeout
                while not all((state / "ready.json").exists() for state in states):
                    if any(child.poll() is not None for child in children):
                        raise RuntimeError("Fixture server exited; inspect server logs")
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Fixture startup timed out; inspect server logs")
                    time.sleep(0.2)
                for side, state in zip(("before", "after"), states):
                    metadata["servers"][side] = json.loads((state / "ready.json").read_text())
                before, after = metadata["servers"].values()
                for key in ("document_sha256", "document_count", "config", "services", "python"):
                    if before[key] != after[key]:
                        raise RuntimeError(f"Fixture comparison differs: {key}")
                metadata["content_checks"] = {
                    side: verify_responses(server["url"], routes, documents, output, side, args.timeout)
                    for side, server in metadata["servers"].items()
                }
                for round_number in range(args.warmup + args.attempts):
                    for offset in range(len(routes)):
                        route_index = (offset + round_number) % len(routes)
                        route = routes[route_index]
                        order = ("before", "after") if (round_number + route_index) % 2 == 0 else ("after", "before")
                        for side in order:
                            try:
                                sample = request_sample(metadata["servers"][side]["url"] + route, args.timeout)
                            except Exception as exc:
                                raise RuntimeError(f"{side} round {round_number}, {route}: {exc}") from exc
                            if round_number >= args.warmup:
                                samples.append({"side": side, "route": route, "round": round_number - args.warmup,
                                                "sequence": len(samples), **sample})
                    if round_number % 25 == 0:
                        print(f"Completed round {round_number + 1}/{args.warmup + args.attempts}", flush=True)
            finally:
                for state in states:
                    (state / "stop").touch()
                for child in children:
                    try:
                        child.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        child.terminate()
                        child.wait(timeout=10)
    except Exception as exc:
        metadata["error"] = str(exc)
    finally:
        for log in logs:
            log.close()
        metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))
        (output / "samples.json").write_text(json.dumps(samples, indent=2))
    if "error" in metadata:
        print(metadata["error"], file=sys.stderr)
        return 1
    results = {}
    lines = [f"# Local {args.scope} HTTP comparison", "", f"Before: `{refs['before']}`", f"After: `{refs['after']}`", "",
             f"{args.attempts} measured samples per route and side, following {args.warmup} warmup rounds.", "",
             "| Route | Side | p50 ms | p95 ms | p99 ms | median bytes |", "| --- | --- | ---: | ---: | ---: | ---: |"]
    for route in routes:
        results[route] = {}
        for side in ("before", "after"):
            subset = [sample for sample in samples if sample["side"] == side and sample["route"] == route]
            total = summarize([sample["total_ms"] for sample in subset])
            first_byte = summarize([sample["ttfb_ms"] for sample in subset])
            size = summarize([sample["response_bytes"] for sample in subset])["p50_ms"]
            results[route][side] = {"total": total, "ttfb": first_byte, "median_response_bytes": size}
            lines.append(f"| `{route}` | {side} | {total['p50_ms']} | {total['p95_ms']} | {total['p99_ms']} | {size:g} |")
    lines += ["", *[f"- {limit}" for limit in LIMITS], ""]
    (output / "summary.json").write_text(json.dumps(results, indent=2))
    (output / "report.md").write_text("\n".join(lines))
    print(output / "report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
