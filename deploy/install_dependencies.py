"""Acknowledge successful dependency deltas independently of checkout movement.

Legacy system environments are read-only. Their unrelated package drift is
reported, not silently normalized. New installations require an owned venv.
"""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def parse_pins(text):
    pins = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)", line)
        if not match:
            raise ValueError("Production requirements must use plain exact package pins")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        if name in pins:
            raise ValueError("Duplicate production requirement")
        pins[name] = match[2]
    if not pins:
        raise ValueError("Empty production requirements")
    return pins


def installed_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def runtime_identity():
    return {"executable": sys.executable, "prefix": sys.prefix, "base_prefix": sys.base_prefix}


def is_virtual_environment():
    return sys.prefix != sys.base_prefix


def install_pins(repo, pins):
    subprocess.run(["bash", str(repo / "deploy/bootstrap_python_trust.sh"), sys.executable], check=True)
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir",
        *[f"{name}=={version}" for name, version in sorted(pins.items())],
    ], check=True)
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)


def write_receipt(path, receipt):
    # Default location is root-owned outside the app checkout. Never acknowledge
    # failed installation, or let a partial JSON file count as success.
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".dependencies-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(receipt, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def ensure_dependencies(repo, receipt_path, baseline_sha_file):
    desired = parse_pins((repo / "requirements.txt").read_text(encoding="utf-8"))
    identity = runtime_identity()
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict) or receipt.get("schema") != 1 or receipt.get("runtime") != identity:
            raise ValueError("Dependency receipt belongs to a different schema/runtime; prepare this environment explicitly")
        baseline = receipt["manifest"]
        managed = receipt["managed_pins"]
        if not isinstance(baseline, dict) or not isinstance(managed, dict):
            raise ValueError("Invalid dependency receipt")
        # Re-parse persisted names/versions before they can reach pip arguments.
        baseline = parse_pins("\n".join(f"{name}=={version}" for name, version in baseline.items()))
        if managed:
            managed = parse_pins("\n".join(f"{name}=={version}" for name, version in managed.items()))
        managed = {name: version for name, version in managed.items() if name in desired}
        if any(baseline.get(name) != version for name, version in managed.items()):
            raise ValueError("Invalid managed dependency receipt")
    elif not is_virtual_environment():
        # HEAD may already be a failed checkout. The last worker build marker is
        # the migration baseline, never the current checkout's old_sha.
        sha = baseline_sha_file.read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("A verified deployment baseline is required")
        previous = subprocess.check_output(
            ["git", "show", f"{sha}:requirements.txt"], cwd=repo, text=True,
        )
        baseline = parse_pins(previous)
        managed = {}
    else:
        # A fresh owned venv has no proven legacy baseline. Verify/install the
        # whole manifest, rather than inheriting an unrelated system receipt.
        baseline, managed = {}, {}

    changed = {name: version for name, version in desired.items() if baseline.get(name) != version}
    managed.update(changed)
    # Recheck managed pins even on an exact-manifest retry. A receipt alone is
    # not permission to ignore a reverted or removed installed package.
    missing = {name: desired[name] for name in managed if installed_version(name) != desired[name]}
    drift = {name: installed_version(name) for name, version in desired.items()
             if name not in managed and installed_version(name) != version}
    if drift:
        print("Preserving pre-existing unmanaged package drift:", json.dumps(drift, sort_keys=True))

    if missing:
        if not is_virtual_environment():
            raise RuntimeError("Dependency changes need an application-owned virtual environment; system Python is read-only")
        install_pins(repo, missing)
    if any(installed_version(name) != desired[name] for name in managed):
        raise RuntimeError("Installed dependency versions do not match the requested delta")

    write_receipt(receipt_path, {
        "schema": 1, "runtime": identity, "manifest": desired,
        "managed_pins": {name: desired[name] for name in managed},
    })
    print("Dependency delta verified; installation receipt saved")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--baseline-sha-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        ensure_dependencies(args.repo, args.receipt, args.baseline_sha_file)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Dependency verification failed ({type(error).__name__}); no success receipt written", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
