#!/usr/bin/env python3
"""Check migration readiness, or apply expressly approved pending migrations.

Run from the deployed checkout with its CONFIG_YAML_PATH configuration. The
deployment caller must hold the existing host flock throughout this phase.
This command does not create a Flask application or start background jobs.
"""

import argparse
import ast
from contextlib import redirect_stderr, redirect_stdout
import logging
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = "mielenosoitukset_fi/utils/migration_runner.py"


class MigrationHistoryError(RuntimeError):
    pass


def migration_ids_from_source(source):
    """Read a literal registry with AST; never import historical application code."""
    tree = ast.parse(source)
    registries = [
        node.value for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "MIGRATIONS" for target in node.targets)
    ]
    if len(registries) != 1 or not isinstance(registries[0], ast.List):
        raise MigrationHistoryError("Migration history has an unsupported registry; verify it manually.")
    ids = set()
    for entry in registries[0].elts:
        if not isinstance(entry, ast.Dict):
            raise MigrationHistoryError("Migration history has an unsupported registry; verify it manually.")
        values = [
            value for key, value in zip(entry.keys, entry.values)
            if isinstance(key, ast.Constant) and key.value == "id"
        ]
        if (len(values) != 1 or not isinstance(values[0], ast.Constant)
                or not isinstance(values[0].value, str)
                or not re.fullmatch(r"[0-9]{3}_[a-z0-9_]+", values[0].value)
                or values[0].value in ids):
            raise MigrationHistoryError("Migration history has an unsupported registry; verify it manually.")
        ids.add(values[0].value)
    return ids


def historical_migration_ids(repo, baseline):
    """Include IDs added and removed between a proven serving baseline and HEAD."""
    if not re.fullmatch(r"[0-9a-fA-F]{40}", baseline):
        raise MigrationHistoryError("Migration baseline must be a full commit SHA.")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, "HEAD"], cwd=repo,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if ancestor.returncode:
        raise MigrationHistoryError("Migration baseline is not an ancestor of this checkout.")
    revisions = subprocess.check_output(
        ["git", "log", "--full-history", "--format=%H", f"{baseline}..HEAD", "--", RUNNER_PATH],
        cwd=repo, text=True, stderr=subprocess.DEVNULL,
    ).splitlines()
    ids = set()
    for revision in [baseline, *revisions]:
        source = subprocess.check_output(
            ["git", "show", f"{revision}:{RUNNER_PATH}"], cwd=repo,
            text=True, stderr=subprocess.DEVNULL,
        )
        ids.update(migration_ids_from_source(source))
    return ids


def assert_migration_history_ready(db, repo, baseline, registered_ids):
    historical = historical_migration_ids(repo, baseline)
    removed_pending = [
        migration_id for migration_id in sorted(historical - set(registered_ids))
        if not db.schema_migrations.find_one({"id": migration_id})
    ]
    if removed_pending:
        raise MigrationHistoryError(
            "Unapplied migrations were removed from the registry: "
            + ", ".join(removed_pending)
            + ". An approved bridge or manual procedure is required."
        )


def _run_phase(args):
    sys.path.insert(0, str(ROOT))
    from config import Config
    from mielenosoitukset_fi.utils.migration_runner import (
        MIGRATIONS,
        MigrationApprovalError,
        PendingMigrationsError,
        pending_migrations,
        run_approved_migrations,
    )
    from mielenosoitukset_fi.database_manager import DatabaseManager

    # DatabaseManager has legacy defaults; a deployment must name its database.
    if not all(
        isinstance(Config.config.get(key), str) and Config.config[key].strip()
        for key in ("MONGO_URI", "MONGO_DBNAME")
    ):
        return 1, "Migration phase requires configured MONGO_URI and MONGO_DBNAME."

    manager = DatabaseManager.get_instance()
    try:
        db = manager.get_db()
        if args.baseline:
            try:
                assert_migration_history_ready(db, ROOT, args.baseline, {item["id"] for item in MIGRATIONS})
            except MigrationHistoryError as error:
                return 1, str(error)
        if not args.apply:
            pending = pending_migrations(db)
            if pending:
                return 1, "Pending migrations: " + ", ".join(pending)
            return 0, "Migrations ready; no database changes made."
        try:
            completed = run_approved_migrations(db, args.approve)
        except (MigrationApprovalError, PendingMigrationsError) as error:
            return 1, str(error)
        if completed:
            return 0, "Applied migrations: " + ", ".join(completed)
        return 0, "Migrations ready; nothing to apply."
    finally:
        manager.close_connection()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="read-only readiness check (default)")
    mode.add_argument("--apply", action="store_true", help="apply approved pending migrations")
    parser.add_argument(
        "--approve", action="append", default=[], metavar="ID",
        help="approve one registered migration ID; repeat for every pending ID",
    )
    parser.add_argument(
        "--baseline", metavar="SHA",
        help="also verify removed migrations since this last proven serving commit",
    )
    args = parser.parse_args(argv)
    if args.approve and not args.apply:
        parser.error("--approve requires --apply")
    if args.apply and not args.approve:
        parser.error("--apply requires at least one --approve ID")

    # Legacy configuration/DB logs and migration exceptions can contain URIs or
    # user identities. Only the controlled status messages below leave this CLI.
    previous_disable = logging.root.manager.disable
    logging.disable(sys.maxsize)
    try:
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            try:
                code, message = _run_phase(args)
            except Exception:
                code = 1
                message = "Migration phase failed; database and user details suppressed."
    finally:
        logging.disable(previous_disable)
    print(message, file=sys.stdout if code == 0 else sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
