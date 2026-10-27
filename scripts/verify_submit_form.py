#!/usr/bin/env python3
"""Run focused submit checks and real Flask captures locally, outside CI.

Use Python 3.12+ with project development dependencies and Node 22.12+.
Technical success does not replace independent in-conversation visual review.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = (
    "tests/test_react_submit.py",
    "tests/test_submit_feedback_contract.py",
    "tests/test_submit_draft_reliability.py",
    "tests/test_submit_organization_search_security.py",
    "tests/test_submit_multilinguality.py",
    "tests/test_facebook_event_import.py",
    "tests/test_background_jobs.py::test_submit_route_is_idempotent_and_does_not_create_duplicate_demo",
    "tests/test_background_jobs.py::test_submit_duplicate_conflict_can_match_existing_translation_title",
    "tests/test_frontend_assets.py",
    "tests/test_react_header.py",
    "tests/test_product_design_tokens.py",
)
CAPTURE_TEST = "tests/test_submit_draft_reliability.py::test_clean_submit_page_preserves_server_defaults"


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(shlex.join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "capture", "all"))
    parser.add_argument("--node", default=os.environ.get("MOSO_QA_NODE", "node"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--stage", choices=("before", "final"), default="final")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error("Use Python 3.12+ with the project development dependencies.")
    if args.mode in ("capture", "all") and args.output_dir is None:
        parser.error("--output-dir is required for capture/all.")
    try:
        if args.mode in ("check", "all"):
            version = subprocess.check_output([args.node, "-p", "process.versions.node"], text=True).strip()
            major, minor = map(int, version.split(".")[:2])
            if major < 22 or (major == 22 and minor < 12):
                parser.error(f"Node 22.12+ required; selected Node reports {version}.")
            run([args.node, "node_modules/typescript/bin/tsc", "--noEmit"])
            run([args.node, "node_modules/vite/bin/vite.js", "build", "--config", "frontend/vite.config.ts"])
            run([args.node, "frontend/prerender.mjs"])
            run([sys.executable, "-m", "pytest", *TEST_FILES, "-o", "addopts=", "-q", "--tb=short"])
        if args.mode in ("capture", "all"):
            output = args.output_dir.expanduser().resolve()
            output.mkdir(parents=True, exist_ok=True)
            run_id = uuid.uuid4().hex
            env = os.environ.copy()
            env.update(MOSO_SUBMIT_CAPTURE_DIR=str(output), MOSO_SUBMIT_CAPTURE_STAGE=args.stage,
                       MOSO_SUBMIT_CAPTURE_RUN=run_id)
            env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(ROOT), env.get("PYTHONPATH"))))
            run([sys.executable, "-m", "pytest", CAPTURE_TEST, "-p", "scripts.submit_visual_capture",
                 "-o", "addopts=", "-q", "--tb=short"], env=env)
            metadata_path = output / f"{args.stage}-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("run_id") != run_id or not metadata.get("images") or not metadata.get("completed"):
                parser.error("Capture metadata is stale or empty; visual acceptance remains open.")
            if metadata.get("errors"):
                parser.error(f"Uncaught page errors recorded; inspect {metadata_path}")
            print(f"Capture metadata: {metadata_path}", flush=True)
        return 0
    except FileNotFoundError as error:
        parser.error(str(error))
    except subprocess.CalledProcessError as error:
        return error.returncode
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
