from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest
import yaml

from deploy import release_state, verify_release_target as target

SHA = 'a' * 40
REPO = 'mielenosoitukset-fi/mielenosoitukset_fi'


def run_record(**changes):
    return {**dict(id=12, run_attempt=2, head_sha=SHA, event='merge_group',
                   conclusion='success', head_repository={'full_name': REPO},
                   path='.github/workflows/tests.yml', head_branch='gh-readonly-queue/main/pr-12'), **changes}


def fetcher(runs, jobs=None, head=SHA):
    calls = []
    def fetch(repo, path):
        assert repo == REPO
        calls.append(path)
        if path == 'commits/main':
            return {'sha': head}
        if path.startswith('actions/workflows/'):
            return {'workflow_runs': runs}
        return {'jobs': jobs if jobs is not None else [{'name': 'python-tests', 'conclusion': 'success'}]}
    return fetch, calls


@pytest.mark.parametrize('count', [1, 4, 8, 40])
def test_burst_selects_only_latest_verified_revision(count):
    candidates = [f'{i:040x}' for i in range(1, count + 1)]
    latest = candidates[-1]
    for sha in candidates:
        fetch, calls = fetcher([run_record(head_sha=latest)], head=latest)
        eligible, message = target.verify(REPO, sha, fetch)
        assert eligible == (sha == latest)
        if sha != latest:
            assert calls == ['commits/main']
            assert 'Superseded' in message


@pytest.mark.parametrize('changes', [
    {'event': 'pull_request'}, {'conclusion': 'failure'}, {'head_sha': 'b' * 40},
    {'head_repository': {'full_name': 'other/repo'}},
    {'path': '.github/workflows/other.yml'}, {'event': 'push', 'head_branch': 'other'},
])
def test_untrusted_or_wrong_revision_evidence_is_rejected(changes):
    fetch, calls = fetcher([run_record(**changes)])
    with pytest.raises(RuntimeError, match='No successful'):
        target.verify(REPO, SHA, fetch)
    assert not any('/jobs?' in call for call in calls)


@pytest.mark.parametrize('conclusion', ['failure', 'skipped', 'cancelled'])
def test_failed_or_skipped_full_suite_does_not_admit(conclusion):
    fetch, _ = fetcher([run_record()], [{'name': 'python-tests', 'conclusion': conclusion}])
    with pytest.raises(RuntimeError):
        target.verify(REPO, SHA, fetch)


def test_successful_exact_attempt_is_reused():
    fetch, calls = fetcher([run_record()])
    assert target.verify(REPO, SHA, fetch)[0]
    assert 'actions/runs/12/attempts/2/jobs?per_page=100' in calls


def test_workflows_keep_protected_suites_and_native_pending_coalescing():
    tests = yaml.load(Path('.github/workflows/tests.yml').read_text(), Loader=yaml.BaseLoader)
    production = yaml.load(Path('.github/workflows/production-deploy.yml').read_text(), Loader=yaml.BaseLoader)
    assert set(tests['on']) == {'pull_request', 'merge_group'}
    assert 'python-tests' in tests['jobs']
    assert production['concurrency'] == {'group': 'production-deploy', 'cancel-in-progress': 'false', 'queue': 'single'}
    release = production['jobs']['release']
    assert 'admission.outputs.eligible' in release['outputs']['eligible']
    assert any(step.get('id') == 'admission' for step in release['steps'])


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def test_monotonic_revision_and_atomic_success_receipt(tmp_path):
    git(tmp_path, 'init', '-q')
    git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'first')
    first = git(tmp_path, 'rev-parse', 'HEAD')
    git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'second')
    second = git(tmp_path, 'rev-parse', 'HEAD')
    release_state.check_target(tmp_path, first, second)
    release_state.check_target(tmp_path, second, second)
    with pytest.raises(ValueError, match='newer'):
        release_state.check_target(tmp_path, second, first)
    fallback = tmp_path / 'worker-sha'
    fallback.write_text(first)
    receipt = tmp_path / 'state' / 'last-successful.json'
    assert release_state.baseline(receipt, fallback) == first
    release_state.record(receipt, first, second, True)
    assert release_state.baseline(receipt, fallback) == second
    before = receipt.read_bytes()
    with pytest.raises(ValueError):
        release_state.record(receipt, second, 'bad', True)
    assert receipt.read_bytes() == before
    assert list(receipt.parent.iterdir()) == [receipt]


def test_corrupt_success_receipt_does_not_fall_back_to_attempted_worker_sha(tmp_path):
    receipt, fallback = tmp_path / 'receipt', tmp_path / 'worker'
    receipt.write_text('{}')
    fallback.write_text(SHA)
    with pytest.raises(ValueError):
        release_state.baseline(receipt, fallback)
