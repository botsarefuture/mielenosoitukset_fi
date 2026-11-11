"""The nightly MongoDB backup script, run against stand-in Mongo tools."""

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
  [[ -n "${EMPTY_DUMP:-}" ]] && : > "$archive" || printf 'dump-bytes' > "$archive"
fi
exit "${FAKE_EXIT:-0}"
"""


def _run(tmp_path, **env):
    tools = tmp_path / "bin"
    tools.mkdir(exist_ok=True)
    for name in ("mongodump", "mongorestore"):
        tool = tools / name
        tool.write_text(FAKE_TOOL)
        tool.chmod(0o755)
    config = tmp_path / "config.yaml"
    config.write_text(f'MONGO_URI: "mongodb://app:{SECRET}@db.example:27017"\nMONGO_DBNAME: "mielenosoitukset"\n')
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
    assert len(archives) == 1 and archives[0].read_text() == "dump-bytes"
    assert oct(backups.stat().st_mode & 0o777) == "0o700"
    argv = (tmp_path / "argv.log").read_text()
    assert SECRET not in argv and SECRET not in result.stdout + result.stderr
    assert "--dryRun" in argv and "--nsTo=restorecheck_mielenosoitukset.*" in argv
    assert SECRET in (tmp_path / "config.log").read_text()


def test_failed_or_empty_dump_leaves_no_archive(tmp_path):
    result, backups = _run(tmp_path, EMPTY_DUMP="1")
    assert result.returncode != 0
    assert not list(backups.glob("*.archive.gz"))

    result, backups = _run(tmp_path, FAKE_EXIT="1")
    assert result.returncode != 0
    assert not list(backups.glob("*.archive.gz"))


def test_retention_keeps_recent_archives_and_ignores_other_files(tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir(mode=0o700)
    old = backups / "mielenosoitukset-20260101T000000Z.archive.gz"
    recent = backups / "mielenosoitukset-20261105T000000Z.archive.gz"
    unrelated = backups / "notes.txt"
    for path, age_days in ((old, 30), (recent, 3), (unrelated, 60)):
        path.write_text("x")
        stamp = time.time() - age_days * 86400
        os.utime(path, (stamp, stamp))

    result, _ = _run(tmp_path, KEEP_DAYS="14")

    assert result.returncode == 0, result.stderr
    assert not old.exists()
    assert recent.exists() and unrelated.exists()
    assert len(list(backups.glob("mielenosoitukset-*.archive.gz"))) == 2


def test_rejects_bad_keep_days(tmp_path):
    result, _ = _run(tmp_path, KEEP_DAYS="0")
    assert result.returncode == 2
