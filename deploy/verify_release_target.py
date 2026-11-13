#!/usr/bin/env python3
"""Admit only the current main SHA with successful trusted full-suite evidence."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


def get_json(repository, path):
    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/{path}"], capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError("Could not verify release evidence through GitHub.")
    return json.loads(result.stdout)


def eligible_run(run, repository, sha):
    return (
        run.get("head_sha") == sha
        and run.get("event") in ("merge_group", "push")
        and run.get("conclusion") == "success"
        and run.get("head_repository", {}).get("full_name") == repository
        and run.get("path", "").split("@")[0] == ".github/workflows/tests.yml"
        and (run["event"] == "merge_group" or run.get("head_branch") == "main")
    )


def verify(repository, sha, fetch=get_json):
    if fetch(repository, "commits/main")["sha"] != sha:
        return False, "Superseded before admission; no production deployment requested."
    payload = fetch(repository, f"actions/workflows/tests.yml/runs?head_sha={sha}&status=success&per_page=100")
    for run in payload["workflow_runs"]:
        if not eligible_run(run, repository, sha):
            continue
        jobs = fetch(repository, f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs?per_page=100")
        if any(job["name"] == "python-tests" and job["conclusion"] == "success" for job in jobs["jobs"]):
            return True, f"Verified exact SHA by Tests run {run['id']} attempt {run['run_attempt']}."
    raise RuntimeError("No successful trusted full python-tests run for this exact main SHA.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository) or not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("A repository slug and full lowercase commit SHA are required.")
    try:
        admitted, message = verify(args.repository, args.sha)
    except (RuntimeError, ValueError, KeyError):
        print("::error::Release admission failed: trusted exact-SHA verification is unavailable.")
        return 1
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
            stream.write(f"eligible={str(admitted).lower()}\n")
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
