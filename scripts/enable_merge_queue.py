#!/usr/bin/env python3
"""Enable the GitHub merge queue on the transferred repository.

Run only after the repository is owned by the mielenosoitukset-fi organization
and the merge_group workflow is on main. GitHub offers merge queues for public
repositories owned by an organization, so the rule cannot be applied before the
transfer.

The script adds the merge_queue rule to the existing "Protection" branch ruleset
and sends every other rule, condition and bypass actor back unchanged. It never
enqueues or merges pull requests and never triggers a deployment. Re-running it
with matching settings reports them without writing.

Usage:
    python scripts/enable_merge_queue.py --dry-run   # print the plan, change nothing
    python scripts/enable_merge_queue.py --confirm   # apply the reviewed plan
    # Rollback: pass both flags to --dry-run, then --confirm:
    # --max-entries-to-build 3 --max-entries-to-merge 3
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys

TARGET = "mielenosoitukset-fi/mielenosoitukset_fi"
BRANCH = "main"
WORKFLOW_PATH = ".github/workflows/tests.yml"
REQUIRED_CHECK = "python-tests"

# Defaults for a backlog of about 40 pull requests: bounded batches, no wait,
# every entry must pass its own required checks, and merge commits to match the
# history this repository already has.
QUEUE_PARAMETERS = {
    "check_response_timeout_minutes": 60,
    "grouping_strategy": "ALLGREEN",
    "max_entries_to_build": 8,
    "max_entries_to_merge": 8,
    "merge_method": "MERGE",
    "min_entries_to_merge": 1,
    "min_entries_to_merge_wait_minutes": 0,
}

MANUAL_STEPS = """\
If the API refuses, inspect the error and retry this script; do not hand-edit the ruleset.
Prerequisites: a public organization repository, `python-tests` on merge_group,
and an exact branch pattern."""


class ScriptError(RuntimeError):
    pass


def gh(*arguments: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["gh", "api", *arguments], capture_output=True, text=True, input=input_text
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise ScriptError(detail[-1] if detail else "gh api failed")
    return result.stdout


def get_json(path: str) -> dict:
    return json.loads(gh(path))


def check_repository() -> dict:
    try:
        repository = get_json(f"repos/{TARGET}")
    except ScriptError as error:
        raise ScriptError(
            f"{TARGET} is not reachable ({error}). Finish the transfer first."
        ) from None
    owner = repository["owner"]["login"]
    if owner != TARGET.split("/")[0]:
        raise ScriptError(
            f"repository is still owned by {owner}; the transfer has not completed"
        )
    if repository["private"]:
        raise ScriptError(
            "merge queue needs a public repository owned by an organization"
        )
    if repository["default_branch"] != BRANCH:
        raise ScriptError(f"default branch is not {BRANCH}")
    permissions = get_json(f"repos/{TARGET}/actions/permissions")
    if not permissions.get("enabled"):
        raise ScriptError("GitHub Actions is disabled for this repository")
    return repository


def check_workflow() -> None:
    contents = get_json(f"repos/{TARGET}/contents/{WORKFLOW_PATH}?ref={BRANCH}")
    text = base64.b64decode(contents["content"]).decode("utf-8")
    if "merge_group:" not in text:
        raise ScriptError(
            f"{WORKFLOW_PATH} on {BRANCH} does not trigger on merge_group; "
            "the queue would wait forever for its required check"
        )


def check_recent_checks() -> str:
    payload = get_json(f"repos/{TARGET}/commits/{BRANCH}/check-runs?per_page=100")
    names = {run["name"] for run in payload.get("check_runs", [])}
    if REQUIRED_CHECK in names:
        return f"{REQUIRED_CHECK} has reported on {BRANCH}"
    return (
        f"warning: {REQUIRED_CHECK} has not reported on the latest {BRANCH} commit yet; "
        "confirm it runs before relying on the queue"
    )


def ruleset_candidates() -> list[dict]:
    summaries = json.loads(gh(f"repos/{TARGET}/rulesets"))
    details = []
    for summary in summaries:
        if summary.get("target") != "branch":
            continue
        details.append(json.loads(gh(f"repos/{TARGET}/rulesets/{summary['id']}")))
    return details


def rule_types(ruleset: dict) -> list[str]:
    return [rule["type"] for rule in ruleset.get("rules", [])]


def requires_target_check(ruleset: dict) -> bool:
    for rule in ruleset.get("rules", []):
        if rule["type"] != "required_status_checks":
            continue
        contexts = {
            check["context"] for check in rule["parameters"]["required_status_checks"]
        }
        if REQUIRED_CHECK in contexts:
            return True
    return False


def targets_branch(ruleset: dict) -> bool:
    include = ruleset.get("conditions", {}).get("ref_name", {}).get("include", [])
    return any(item in ("~DEFAULT_BRANCH", f"refs/heads/{BRANCH}") for item in include)


def queue_rule(parameters: dict | None = None) -> dict:
    return {
        "type": "merge_queue",
        "parameters": dict(QUEUE_PARAMETERS if parameters is None else parameters),
    }


def payload_for(ruleset: dict, parameters: dict | None = None) -> dict:
    existing = []
    for rule in ruleset.get("rules", []):
        if rule["type"] == "merge_queue":
            existing.append(queue_rule(parameters))
            continue
        entry = {"type": rule["type"]}
        if rule.get("parameters") is not None:
            entry["parameters"] = rule["parameters"]
        existing.append(entry)
    bypass = [
        {
            "actor_id": actor.get("actor_id"),
            "actor_type": actor.get("actor_type"),
            "bypass_mode": actor.get("bypass_mode"),
        }
        for actor in ruleset.get("bypass_actors", [])
    ]
    if "merge_queue" not in rule_types(ruleset):
        existing.append(queue_rule(parameters))
    return {
        "name": ruleset["name"],
        "target": ruleset["target"],
        "enforcement": ruleset["enforcement"],
        "bypass_actors": bypass,
        "conditions": ruleset["conditions"],
        "rules": existing,
    }


def apply(ruleset: dict, payload: dict) -> None:
    gh(
        f"repos/{TARGET}/rulesets/{ruleset['id']}",
        "-X",
        "PUT",
        "--input",
        "-",
        input_text=json.dumps(payload),
    )


def verify(ruleset_id: int, expected: dict) -> dict:
    updated = get_json(f"repos/{TARGET}/rulesets/{ruleset_id}")
    actual = payload_for(updated, next(
        (rule["parameters"] for rule in updated["rules"] if rule["type"] == "merge_queue"),
        {},
    ))
    if actual != expected:
        raise ScriptError("ruleset differs from the planned payload; inspect and restore it")
    return next(rule["parameters"] for rule in updated["rules"] if rule["type"] == "merge_queue")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print the plan only")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="apply the change; required because it edits branch protections",
    )
    for name in ("build", "merge"):
        parser.add_argument(
            f"--max-entries-to-{name}", type=int, choices=range(1, 101),
            default=QUEUE_PARAMETERS[f"max_entries_to_{name}"], metavar="1..100",
            help=f"maximum entries to {name} (default: 8; rollback: 3)",
        )
    arguments = parser.parse_args(argv)
    parameters = dict(QUEUE_PARAMETERS)
    parameters["max_entries_to_build"] = arguments.max_entries_to_build
    parameters["max_entries_to_merge"] = arguments.max_entries_to_merge
    if not arguments.dry_run and not arguments.confirm:
        print(
            "refusing to run without --dry-run or --confirm; "
            "this script changes branch protections",
            file=sys.stderr,
        )
        return 2

    try:
        check_repository()
        check_workflow()
        print(f"repo: {TARGET} is a public organization repository on {BRANCH}")
        print(check_recent_checks())

        candidates = [
            ruleset
            for ruleset in ruleset_candidates()
            if ruleset.get("enforcement") == "active"
            and targets_branch(ruleset)
            and requires_target_check(ruleset)
        ]
        if not candidates:
            raise ScriptError(
                f"no active {BRANCH} ruleset requires {REQUIRED_CHECK}; "
                "not creating a second protection rule"
            )
        ruleset = candidates[0]
        for item in candidates:
            include = item["conditions"]["ref_name"]["include"]
            if any("*" in entry for entry in include):
                raise ScriptError(
                    "the ruleset uses a wildcard branch pattern; merge queue "
                    "needs an exact branch"
                )

        before = rule_types(ruleset)
        if "merge_queue" in before:
            current = next(
                rule["parameters"]
                for rule in ruleset["rules"]
                if rule["type"] == "merge_queue"
            )
            print("current queue parameters:")
            print(json.dumps(current, indent=2, sort_keys=True))
            if current == parameters:
                print(f"merge queue already matches on ruleset {ruleset['id']}; nothing changed")
                return 0

        payload = payload_for(ruleset, parameters)
        print(f"ruleset {ruleset['id']} ({ruleset['name']}) planned queue:")
        print(json.dumps(queue_rule(parameters), indent=2, sort_keys=True))
        print(f"rules kept: {', '.join(before)}")
        if arguments.dry_run:
            print("dry run: nothing changed")
            return 0

        apply(ruleset, payload)
        parameters = verify(ruleset["id"], payload)
        print("merge queue configured and full ruleset verified")
        print(json.dumps(parameters, indent=2, sort_keys=True))
        current_types = rule_types(get_json("repos/{}/rulesets/{}".format(TARGET, ruleset["id"])))
        print(f"rules now: {', '.join(current_types)}")
        return 0
    except ScriptError as error:
        print(f"error: {error}", file=sys.stderr)
        print(MANUAL_STEPS, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
