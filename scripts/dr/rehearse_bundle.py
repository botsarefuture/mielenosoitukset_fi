#!/usr/bin/env python3
"""Prove offline app + DB recovery on the prepared sandbox, without replacing it.

Requires a bundle with app.tar.gz, mongo.archive.gz, requirements.lock, wheels/,
SHA256SUMS.json and build_sha. Uses a disposable DB and localhost port 5004.
The running pentest app, production services and historical backups are untouched.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from urllib.request import urlopen
import uuid

from write_config import configuration
from vendor_assets import ASSETS


def validate_member(member):
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
        raise ValueError("Unsafe application archive member")
    if path.name in {"config.yaml", ".env"} or path.name.startswith(".env."):
        raise ValueError("Application release must not contain environment secrets")


def validate_browser_members(members):
    if len(members) != len(ASSETS) or {member.name for member in members} != set(ASSETS):
        raise ValueError('Browser archive must contain the complete pinned asset set')
    for member in members:
        validate_member(member)
        if not member.isfile() or len(PurePosixPath(member.name).parts) != 1:
            raise ValueError('Unsafe browser asset member')


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_bundle(bundle):
    checksums = json.loads((bundle / "SHA256SUMS.json").read_text())
    required = {"app.tar.gz", "mongo.archive.gz", "requirements.lock", "build_sha", "browser-assets.tar.gz"}
    wheels = list((bundle / "wheels").glob("*.whl"))
    if not wheels:
        raise ValueError("Offline wheelhouse is empty")
    required.update(path.relative_to(bundle).as_posix() for path in wheels)
    missing = required - checksums.keys()
    if missing:
        raise ValueError("Bundle manifest omits: " + ", ".join(sorted(missing)))
    for rel, expected in checksums.items():
        if PurePosixPath(rel).is_absolute() or ".." in PurePosixPath(rel).parts:
            raise ValueError("Unsafe manifest path")
        if digest(bundle / rel) != expected:
            raise ValueError("Bundle integrity failure: " + rel)


def cleanup_rehearsal(client, database, stage, unit, log):
    errors = {}
    actions = [
        ("stop_unit", lambda: subprocess.run(["systemctl", "stop", unit], stdout=log, stderr=log, check=True)),
        ("drop_database", lambda: client.drop_database(database)),
        ("remove_stage", lambda: shutil.rmtree(stage)),
        ("close_client", client.close),
        ("close_log", log.close),
    ]
    for name, action in actions:
        try:
            action()
        except Exception as error:
            errors[name] = type(error).__name__
    return errors


def rehearse(bundle):
    if socket.gethostname() != "mielenosoitukset-pentest" or os.getuid() != 0:
        raise RuntimeError("Run as root on the named sandbox only")
    from pymongo import MongoClient
    started = time.monotonic()
    verify_bundle(bundle)
    identity = uuid.uuid4().hex[:12]
    database = "dr_verify_" + identity
    unit = "dr-verify-" + identity
    stage = Path("/srv/mielenosoitukset-dr/rehearsal-" + identity)
    stage.mkdir(mode=0o750)
    account = pwd.getpwnam("dr-app")
    log = (bundle / ("rehearsal-" + identity + ".log")).open("w")
    client = MongoClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=5000)
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "build_sha": (bundle / "build_sha").read_text().strip(),
              "database": database, "unit": unit, "scope": "prepared host, offline app + DB recovery"}
    failed = False
    try:
        app = stage / "app"
        app.mkdir()
        with tarfile.open(bundle / "app.tar.gz", "r:gz") as archive:
            members = archive.getmembers()
            if sum(member.size for member in members) > 2 * 1024**3:
                raise ValueError("Application release exceeds rehearsal size limit")
            for member in members:
                validate_member(member)
            archive.extractall(app, members=members, filter="data")
        browser_root = app / 'mielenosoitukset_fi/static/dr-vendor'
        browser_root.mkdir(parents=True, exist_ok=True)
        with tarfile.open(bundle / 'browser-assets.tar.gz', 'r:gz') as assets:
            members = assets.getmembers()
            if sum(member.size for member in members) > 32 * 1024**2:
                raise ValueError('Browser assets exceed size limit')
            validate_browser_members(members)
            assets.extractall(browser_root, members=members, filter='data')
        for name, (_, expected) in ASSETS.items():
            if digest(browser_root / name) != expected:
                raise ValueError('Restored browser asset checksum mismatch')
        (app / ".deploy-build-sha").write_text(report["build_sha"] + "\n")
        config = configuration()
        config["MONGO_DBNAME"] = database
        config_path = stage / "config.yaml"
        config_path.write_text(json.dumps(config))
        config_path.chmod(0o600)
        (app / "config.yaml").symlink_to(config_path)
        for name in ["sandbox_wsgi.py", "capture_delivery.py", "copy_urls.py"]:
            shutil.copyfile(Path(__file__).parent / name, stage / name)
        subprocess.run(["python3", "-m", "venv", str(stage / "venv")], check=True, stdout=log, stderr=log)
        subprocess.run([str(stage / "venv/bin/pip"), "install", "--no-index", "--find-links", str(bundle / "wheels"),
                        "-r", str(bundle / "requirements.lock")], check=True, stdout=log, stderr=log)
        assert not client[database].list_collection_names()
        db_started = time.monotonic()
        subprocess.run(["/usr/local/bin/mongorestore", "--host", "127.0.0.1", "--port", "27017", "--gzip",
                        "--archive=" + str(bundle / "mongo.archive.gz"), "--nsInclude=mielenosoitukset.*",
                        "--nsFrom=mielenosoitukset.*", "--nsTo=" + database + ".*", "--stopOnError",
                        "--numParallelCollections=2"], check=True, stdout=log, stderr=log)
        report["database_restore_seconds"] = round(time.monotonic() - db_started, 2)
        for path in [stage, *stage.rglob("*")]:
            if not path.is_symlink():
                os.chown(path, account.pw_uid, account.pw_gid)
        subprocess.run(["systemd-run", "--unit=" + unit, "--collect", "--property=User=dr-app",
                        "--property=IPAddressDeny=any", "--property=IPAddressAllow=localhost",
                        "--property=NoNewPrivileges=true", "--property=PrivateTmp=true",
                        "--property=ProtectSystem=strict", "--property=ProtectHome=true",
                        "--property=UMask=0077", "--property=ReadWritePaths=" + str(stage),
                        "--working-directory=" + str(app), "--setenv=CONFIG_YAML_PATH=" + str(config_path),
                        "--setenv=PYTHONDONTWRITEBYTECODE=1", "--setenv=AWS_EC2_METADATA_DISABLED=true",
                        "--setenv=PYTHONPATH=" + ":".join(map(str, [app, app / "mielenosoitukset_fi", stage])),
                        str(stage / "venv/bin/gunicorn"), "-k", "eventlet", "--workers", "1", "--bind",
                        "127.0.0.1:5004", "--timeout", "90", "sandbox_wsgi:app"], check=True, stdout=log, stderr=log)
        for _ in range(120):
            try:
                with urlopen("http://127.0.0.1:5004/health", timeout=2) as response:
                    health = json.load(response)
                if health.get("build_sha") == report["build_sha"] and health.get("status") == "ok":
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Rehearsal app did not become healthy")
        with urlopen("http://127.0.0.1:5004/api/demonstrations?per_page=3", timeout=15) as response:
            events = json.load(response)
        assert len(events.get("results", [])) == 3
        for path in browser_root.iterdir():
            with urlopen('http://127.0.0.1:5004/static/dr-vendor/' + path.name, timeout=5) as response:
                if hashlib.sha256(response.read()).hexdigest() != digest(path):
                    raise ValueError('Restored browser asset HTTP integrity failure')
        report['browser_assets_verified'] = len(list(browser_root.iterdir()))
        report.update(result="passed", api_events=3, total_seconds=round(time.monotonic() - started, 2),
                      offline_install=True, production_connections=False)
    except BaseException as error:
        failed = True
        report.update(result="failed", error=type(error).__name__)
        raise
    finally:
        errors = cleanup_rehearsal(client, database, stage, unit, log)
        if errors:
            report["cleanup_errors"] = errors
            if not failed:
                report["result"] = "cleanup_failed"
        (bundle / "last-rehearsal.json").write_text(json.dumps(report, indent=2) + "\n")
        if errors and not failed:
            raise RuntimeError("Rehearsal cleanup failed; see private report")
    print(json.dumps(report))


if __name__ == "__main__":
    rehearse(Path(sys.argv[1]).resolve())
