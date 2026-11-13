#!/usr/bin/env python3
"""Check monotonic deployment ancestry and record verified origin activation."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def valid_sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Deployment state requires a full commit SHA.")
    return value


def baseline(receipt, fallback):
    if receipt.exists():
        data = json.loads(receipt.read_text())
        if data.get("schema") != 1:
            raise ValueError("Unsupported successful-deployment receipt.")
        return valid_sha(data["commit"])
    return valid_sha(fallback.read_text().strip())


def check_target(repo, previous, target):
    valid_sha(previous)
    valid_sha(target)
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", previous, target], cwd=repo,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        raise ValueError("Target would replace a newer or unrelated deployed revision.")


def record(receipt, previous, target, routing):
    valid_sha(previous)
    valid_sha(target)
    receipt.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".release-", dir=receipt.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump({"schema": 1, "commit": target, "previous": previous,
                       "routing": routing, "release": f"release-{target}",
                       "verified_at": datetime.now(timezone.utc).isoformat()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, receipt)
    finally:
        Path(name).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--fallback-file", type=Path)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--previous")
    parser.add_argument("--routing", action="store_true")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", metavar="SHA")
    modes.add_argument("--record", metavar="SHA")
    args = parser.parse_args(argv)
    try:
        if args.check:
            if not args.repo or not args.fallback_file:
                parser.error("--check requires --repo and --fallback-file")
            previous = baseline(args.receipt, args.fallback_file)
            check_target(args.repo, previous, args.check)
            print(previous)
        else:
            record(args.receipt, args.previous, args.record, args.routing)
    except (ValueError, KeyError, OSError):
        print("Deployment state invalid or non-monotonic; inspect the successful receipt before retrying.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
