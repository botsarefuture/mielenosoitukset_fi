"""Migration release gate behavior without a real database."""

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from mielenosoitukset_fi.utils import migration_runner


ROOT = Path(__file__).resolve().parents[1]


class Ledger:
    def __init__(self, applied=()):
        self.rows = {key: {"id": key} for key in applied}
        self.indexes = []

    def find_one(self, query):
        return self.rows.get(query["id"])

    def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))

    def insert_one(self, row):
        self.rows[row["id"]] = row


@pytest.fixture
def migrations(monkeypatch):
    calls = []

    def migration(key, fail=False):
        def run(*, db):
            calls.append(key)
            if fail:
                raise RuntimeError("migration failed")
            return {"done": key}
        return {"id": key, "description": key, "run": run}

    entries = [migration("001_first"), migration("002_second", fail=True), migration("003_third")]
    monkeypatch.setattr(migration_runner, "MIGRATIONS", entries)
    return entries, calls


def test_check_is_read_only_and_reports_ordered_missing_ids(migrations):
    _, calls = migrations
    ledger = Ledger(applied={"002_second"})
    db = SimpleNamespace(schema_migrations=ledger)
    assert migration_runner.pending_migrations(db) == ["001_first", "003_third"]
    with pytest.raises(migration_runner.PendingMigrationsError) as error:
        migration_runner.assert_migrations_ready(db)
    assert error.value.pending_ids == ["001_first", "003_third"]
    assert not ledger.indexes and not calls and set(ledger.rows) == {"002_second"}


def test_all_pending_approvals_required_before_any_write(migrations):
    _, calls = migrations
    ledger = Ledger()
    with pytest.raises(migration_runner.PendingMigrationsError) as error:
        migration_runner.run_approved_migrations(SimpleNamespace(schema_migrations=ledger), ["001_first"])
    assert error.value.pending_ids == ["002_second", "003_third"]
    assert not calls and not ledger.rows and not ledger.indexes


def test_failure_is_unacknowledged_and_retry_skips_completed(migrations):
    entries, calls = migrations
    ledger = Ledger()
    db = SimpleNamespace(schema_migrations=ledger)
    approvals = [entry["id"] for entry in entries]
    with pytest.raises(RuntimeError, match="migration failed"):
        migration_runner.run_approved_migrations(db, approvals)
    assert calls == ["001_first", "002_second"]
    assert set(ledger.rows) == {"001_first"}
    entries[1]["run"] = lambda *, db: calls.append("002_second_retry") or {"done": True}
    assert migration_runner.run_approved_migrations(db, approvals) == ["002_second", "003_third"]
    assert calls == ["001_first", "002_second", "002_second_retry", "003_third"]
    assert set(ledger.rows) == set(approvals)


def _phase_module():
    spec = importlib.util.spec_from_file_location("run_migrations", ROOT / "deploy/run_migrations.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_history_detects_migration_added_then_removed(tmp_path):
    module = _phase_module()
    repo = tmp_path / "repo"
    source = repo / module.RUNNER_PATH
    source.parent.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    def commit(body):
        source.write_text(body)
        subprocess.run(["git", "add", module.RUNNER_PATH], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "-qm", "registry"], cwd=repo, check=True)
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

    baseline = commit("MIGRATIONS = []\n")
    commit("MIGRATIONS = [{'id': '001_transient', 'run': dangerous_call}]\n")
    commit("MIGRATIONS = []\n")
    assert module.historical_migration_ids(repo, baseline) == {"001_transient"}
    db = SimpleNamespace(schema_migrations=Ledger())
    with pytest.raises(module.MigrationHistoryError, match="001_transient"):
        module.assert_migration_history_ready(db, repo, baseline, set())
    db.schema_migrations.rows["001_transient"] = {"id": "001_transient"}
    module.assert_migration_history_ready(db, repo, baseline, set())


def test_history_keeps_migration_from_discarded_merge_parent(tmp_path):
    module = _phase_module()
    source = tmp_path / module.RUNNER_PATH
    source.parent.mkdir(parents=True)
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], text=True).strip()
    def commit():
        git('add', '.')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'registry')
        return git('rev-parse', 'HEAD')
    git('init', '-q', '-b', 'main')
    source.write_text('MIGRATIONS = []\n')
    baseline = commit()
    git('switch', '-qc', 'transient')
    source.write_text("MIGRATIONS = [{'id': '011_transient', 'run': must_not_execute}]\n")
    commit()
    git('switch', '-q', 'main')
    (tmp_path / 'other').write_text('main change')
    commit()
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
        'merge', '-q', '--no-ff', '-s', 'ours', 'transient', '-m', 'discard registry')
    assert '011_transient' in module.historical_migration_ids(tmp_path, baseline)
    with pytest.raises(module.MigrationHistoryError, match='011_transient'):
        module.assert_migration_history_ready(SimpleNamespace(schema_migrations=Ledger()), tmp_path, baseline, set())
