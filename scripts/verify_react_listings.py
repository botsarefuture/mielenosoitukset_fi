#!/usr/bin/env python3
"""Run the local React listing checks and real-application visual captures.

Examples:
    python3.12 scripts/verify_react_listings.py check --node /path/to/node
    python3.12 scripts/verify_react_listings.py capture --output-dir /tmp/listing-qa
    python3.12 scripts/verify_react_listings.py all --output-dir /tmp/listing-qa

This is a local convenience command, not another CI workflow or test suite.
Capture mode reuses one existing test to obtain its isolated Flask/Mongo/browser
fixtures. The independent visual verdict still happens in the conversation.
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
    "tests/test_react_listing.py",
    "tests/test_public_listing_contract.py",
    "tests/test_public_demo_localization.py",
    "tests/test_public_list_filter_history.py",
    "tests/test_public_windowed_loading.py",
    "tests/test_public_date_range.py",
    "tests/test_public_search_fields.py",
    "tests/test_tag_list_localization_contract.py",
    "tests/test_demo_card_i18n_contract.py",
    "tests/test_public_inline_style_contract.py",
    "tests/test_product_design_tokens.py",
    "tests/test_react_header.py",
    "tests/test_public_chrome_contract.py",
    "tests/test_frontend_assets.py",
    "tests/test_public_pagination_limits.py",
    "tests/test_api_contract.py",
)
CAPTURE_TEST = (
    "tests/test_public_listing_contract.py::"
    "test_public_listing_pagination_controller_supports_buttons_and_sentinels"
)


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(shlex.join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "capture", "all"))
    parser.add_argument("--node", default=os.environ.get("MOSO_QA_NODE", "node"))
    parser.add_argument("--output-dir", type=Path, help="Directory for screenshots and capture metadata")
    parser.add_argument("--stage", choices=("before", "final"), default="final")
    parser.add_argument("--scenario", choices=("standard", "missing-times", "continuous-grid"), default="standard")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error("Use Python 3.12 or newer with the project's development dependencies installed.")
    if args.mode in ("capture", "all") and args.output_dir is None:
        parser.error("--output-dir is required for capture or all mode.")
    try:
        if args.mode in ("check", "all"):
            version = subprocess.check_output([args.node, "-p", "process.versions.node"], text=True).strip()
            major, minor = map(int, version.split(".")[:2])
            if major < 22 or (major == 22 and minor < 12):
                parser.error(f"Node 22.12+ is required; selected Node reports {version}.")
            if not (ROOT / "node_modules/typescript/bin/tsc").is_file():
                parser.error("Frontend dependencies are missing. Run npm ci first.")
            run([args.node, "node_modules/typescript/bin/tsc", "--noEmit"])
            run([args.node, "node_modules/vite/bin/vite.js", "build", "--config", "frontend/vite.config.ts"])
            run([args.node, "frontend/prerender.mjs"])
            run([sys.executable, "-m", "pytest", *TEST_FILES, "-o", "addopts=", "-q", "--tb=short"])
        if args.mode in ("capture", "all"):
            output = args.output_dir.expanduser().resolve()
            output.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env["MOSO_LIST_CAPTURE_DIR"] = str(output)
            env["MOSO_LIST_CAPTURE_STAGE"] = args.stage
            env["MOSO_LIST_CAPTURE_SCENARIO"] = args.scenario
            run_id = uuid.uuid4().hex
            env["MOSO_LIST_CAPTURE_RUN"] = run_id
            env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(ROOT), env.get("PYTHONPATH"))))
            run([sys.executable, "-m", "pytest", CAPTURE_TEST, "-p", "scripts.listing_visual_capture",
                 "-o", "addopts=", "-q", "--tb=short"], env=env)
            metadata_path = output / (args.stage + "-metadata.json")
            if not metadata_path.is_file():
                parser.error("Capture did not produce metadata. Check browser/fixture availability.")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("run_id") != run_id or not metadata.get("images"):
                parser.error("Capture metadata is stale or empty. Visual acceptance remains open.")
            expected_before_errors = args.stage == "before" and args.scenario == "missing-times"
            if metadata.get("errors") and not expected_before_errors:
                parser.error(f"Capture recorded uncaught page errors; see {metadata_path}")
            print(f"Capture metadata: {metadata_path}", flush=True)
        return 0
    except FileNotFoundError as error:
        parser.error(str(error))
    except subprocess.CalledProcessError as error:
        return error.returncode
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
