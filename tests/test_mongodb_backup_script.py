"""The nightly MongoDB backup script, run against stand-in Mongo tools."""

import gzip
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path("deploy/backup/mongodb-backup.sh").resolve()
SECRET = "s3cr3t-pass"

FAKE_TOOL = """#!/usr/bin/env bash
# Records its argv, then behaves like mongodump or mongorestore.
printf '%s\\n' "$@" >> "$ARGV_LOG"
for arg in "$@"; do
  case "$arg" in
    --config=*) cat "${arg#--config=}" >> "$CONFIG_LOG" ;;
    --archive=*) archive="${arg#--archive=}" ;;
  esac
done
if [[ "$(basename "$0")" == mongodump ]]; then
  if [[ -n "${EMPTY_DUMP:-}" ]]; then : > "$archive"
  elif [[ -n "${CORRUPT_DUMP:-}" ]]; then printf 'dump-bytes' | gzip | head -c 20 > "$archive"
  else printf 'dump-bytes' | gzip > "$archive"; fi
fi
exit "${FAKE_EXIT:-0}"
"""


def _run(tmp_path, uri=f"mongodb://app:{SECRET}@db.example:27017", **env):
    tools = tmp_path / "bin"
    tools.mkdir(exist_ok=True)
    for name in ("mongodump", "mongorestore"):
        tool = tools / name
        tool.write_text(FAKE_TOOL)
        tool.chmod(0o755)
    config = tmp_path / "config.yaml"
    config.write_text(f'MONGO_URI: "{uri}"\nMONGO_DBNAME: "mielenosoitukset"\n')
    backups = tmp_path / "backups"
    full_env = {
        **os.environ,
        "APP_CONFIG": str(config), "BACKUP_DIR": str(backups), "PYTHON": sys.executable,
        "MONGODUMP": str(tools / "mongodump"), "MONGORESTORE": str(tools / "mongorestore"),
        "ARGV_LOG": str(tmp_path / "argv.log"), "CONFIG_LOG": str(tmp_path / "config.log"),
        **env,
    }
    result = subprocess.run(["bash", str(SCRIPT)], env=full_env, capture_output=True, text=True)
    return result, backups


def test_backup_writes_a_verified_archive_without_exposing_the_password(tmp_path):
    result, backups = _run(tmp_path)

    assert result.returncode == 0, result.stderr
    archives = list(backups.glob("mielenosoitukset-*.archive.gz"))
    assert len(archives) == 1 and gzip.decompress(archives[0].read_bytes()) == b"dump-bytes"
    assert oct(backups.stat().st_mode & 0o777) == "0o700"
    argv = (tmp_path / "argv.log").read_text()
    assert SECRET not in argv and SECRET not in result.stdout + result.stderr
    assert "--dryRun" in argv and "--nsTo=restorecheck_mielenosoitukset.*" in argv
    # The URI names no auth database, so the tools authenticate where PyMongo does.
    assert argv.count("--authenticationDatabase=admin") == 2
    assert SECRET in (tmp_path / "config.log").read_text()


def test_failed_or_empty_dump_leaves_no_archive(tmp_path):
    result, backups = _run(tmp_path, EMPTY_DUMP="1")
    assert result.returncode != 0
    assert not list(backups.glob("*.archive.gz"))
    assert not list(backups.glob("*.partial"))

    result, backups = _run(tmp_path, FAKE_EXIT="1")
    assert result.returncode != 0
    assert not list(backups.glob("*.archive.gz"))


def test_retention_keeps_recent_archives_and_ignores_other_files(tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir(mode=0o700)
    old = backups / "mielenosoitukset-core-20260101T000000Z.archive.gz"
    recent = backups / "mielenosoitukset-core-20261105T000000Z.archive.gz"
    weekly = backups / "mielenosoitukset-full-20260101T000000Z.archive.gz"
    unrelated = backups / "notes.txt"
    for path, age_days in ((old, 30), (recent, 3), (unrelated, 60), (weekly, 30)):
        path.write_text("x")
        stamp = time.time() - age_days * 86400
        os.utime(path, (stamp, stamp))

    result, _ = _run(tmp_path, KEEP_DAYS="14")

    assert result.returncode == 0, result.stderr
    assert not old.exists()
    # Each mode only prunes its own archives; weekly full dumps keep their own retention.
    assert recent.exists() and unrelated.exists() and weekly.exists()
    assert len(list(backups.glob("mielenosoitukset-core-*.archive.gz"))) == 2


def test_rejects_bad_keep_days(tmp_path):
    result, _ = _run(tmp_path, KEEP_DAYS="0")
    assert result.returncode == 2


def test_truncated_archive_is_rejected_and_cleaned_up(tmp_path):
    result, backups = _run(tmp_path, CORRUPT_DUMP="1")

    assert result.returncode != 0
    assert "gzip integrity" in result.stderr
    assert not list(backups.glob("*.archive.gz")) and not list(backups.glob("*.partial"))
    # The parse check never ran on a corrupt archive.
    assert "--dryRun" not in (tmp_path / "argv.log").read_text()


def test_leftover_partials_from_killed_runs_are_removed(tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir(mode=0o700)
    stale = backups / "mielenosoitukset-20261101T000000Z.archive.gz.partial"
    stale.write_text("half a dump")

    result, _ = _run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert not stale.exists()


def test_auth_database_follows_the_uri_like_pymongo(tmp_path):
    result, _ = _run(tmp_path, uri=f"mongodb://app:{SECRET}@db.example:27017/appdb?authSource=users")
    assert result.returncode == 0, result.stderr
    assert "--authenticationDatabase=users" in (tmp_path / "argv.log").read_text()

    other = tmp_path / "second"
    other.mkdir()
    result, _ = _run(other, uri=f"mongodb://app:{SECRET}@db.example:27017/appdb")
    assert result.returncode == 0, result.stderr
    assert "--authenticationDatabase=appdb" in (other / "argv.log").read_text()


def test_core_mode_skips_audit_logs_and_full_mode_keeps_everything(tmp_path):
    result, backups = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    argv = (tmp_path / "argv.log").read_text()
    assert "--excludeCollection=super_audit_logs" in argv and "--excludeCollection=admin_logs" in argv
    assert len(list(backups.glob("mielenosoitukset-core-*.archive.gz"))) == 1

    other = tmp_path / "full"
    other.mkdir()
    result, backups = _run(other, BACKUP_MODE="full")
    assert result.returncode == 0, result.stderr
    assert "--excludeCollection" not in (other / "argv.log").read_text()
    assert len(list(backups.glob("mielenosoitukset-full-*.archive.gz"))) == 1


def test_rejects_unknown_mode_and_unsafe_collection_names(tmp_path):
    assert _run(tmp_path, BACKUP_MODE="partial")[0].returncode == 2
    assert _run(tmp_path, EXCLUDE_COLLECTIONS="logs;rm")[0].returncode == 2


def test_core_run_expires_archives_named_before_modes_existed(tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir(mode=0o700)
    legacy_old = backups / "mielenosoitukset-20260101T000000Z.archive.gz"
    legacy_recent = backups / "mielenosoitukset-20261105T000000Z.archive.gz"
    for path, age_days in ((legacy_old, 30), (legacy_recent, 3)):
        path.write_text("x")
        stamp = time.time() - age_days * 86400
        os.utime(path, (stamp, stamp))

    result, _ = _run(tmp_path, KEEP_DAYS="14")

    assert result.returncode == 0, result.stderr
    assert not legacy_old.exists()
    assert legacy_recent.exists()
