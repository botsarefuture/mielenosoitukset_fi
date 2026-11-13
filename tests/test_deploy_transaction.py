"""Exercise the real production deploy script against an isolated Git origin."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy/production_deploy.sh"


def _git(directory, *args, env=None):
    return subprocess.check_output(["git", *args], cwd=directory, env=env, text=True).strip()


def _commit(directory, name, env):
    (directory / "version.txt").write_text(name)
    _git(directory, "add", ".", env=env)
    _git(directory, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "commit", "-qm", name, env=env)
    return _git(directory, "rev-parse", "HEAD", env=env)


@pytest.fixture
def deployment(tmp_path):
    bare = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    repo = tmp_path / "repo"
    pusher = tmp_path / "pusher"
    events = tmp_path / "events"
    state = tmp_path / "state"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True)
    (seed / "deploy").mkdir()
    shutil.copy2(ROOT / "deploy/release_state.py", seed / "deploy/release_state.py")
    (seed / ".gitignore").write_text(".deploy-build-sha\n")

    def python_stub(name, body):
        (seed / "deploy" / name).write_text(
            "import os,sys\nfrom pathlib import Path\n"
            "with Path(os.environ['EVENTS']).open('a') as event: event.write('" + name + "\\n')\n"
            + body + "\n"
        )

    python_stub("install_dependencies.py", "assert Path(os.environ['PRODUCTION_MIGRATIONS_MANAGED_FILE']).exists()")
    python_stub("run_migrations.py", "if os.getenv('FAIL_MIGRATION') == '1': sys.exit(1)")
    python_stub("verify_health_sha.py", "")
    package = seed / "mielenosoitukset_fi" / "scripts"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").write_text("")
    (package / "__init__.py").write_text("")
    (package / "provision_public_indexes.py").write_text(
        "import os\nfrom pathlib import Path\n"
        "with Path(os.environ['EVENTS']).open('a') as event: event.write('provision\\n')\n"
    )
    public = seed / "deploy/release_public.sh"
    public.write_text(
        "#!/usr/bin/env bash\nset -e\nprintf 'public\\n' >> \"$EVENTS\"\n"
        "if [[ ${ADVANCE_ORIGIN:-0} == 1 ]]; then\n"
        "  printf 'later\\n' > \"$PUSHER/version.txt\"\n"
        "  git -C \"$PUSHER\" add version.txt\n"
        "  git -C \"$PUSHER\" -c user.name=Test -c user.email=test@example.invalid commit -qm later\n"
        "  git -C \"$PUSHER\" push -q origin main\nfi\n"
        "[[ ${FAIL_PUBLIC:-0} != 1 ]]\n"
    )
    public.chmod(0o755)
    routing = seed / "deploy/release_routing.sh"
    routing.write_text("#!/usr/bin/env bash\nprintf 'routing\\n' >> \"$EVENTS\"\n")
    routing.chmod(0o755)
    (seed / "deploy/apache").mkdir()
    (seed / "deploy/apache/react-ssr-routing.conf").write_text("fixture routing\n")
    (bin_dir / "flock").write_text("#!/usr/bin/env bash\n[[ ${FAIL_FLOCK:-0} != 1 ]]\n")
    (bin_dir / "systemctl").write_text(
        "#!/usr/bin/env bash\nprintf 'systemctl %s\\n' \"$1\" >> \"$EVENTS\"\n")
    (bin_dir / "chown").write_text("#!/usr/bin/env bash\nprintf 'chown\\n' >> \"$EVENTS\"\n")
    for name in ("flock", "systemctl", "chown"):
        (bin_dir / name).chmod(0o755)

    env = dict(os.environ, GIT_CONFIG_GLOBAL=str(tmp_path / "gitconfig"),
               PATH=f"{bin_dir}:{os.environ['PATH']}", EVENTS=str(events), PUSHER=str(pusher),
               PRODUCTION_REPO_DIR=str(repo), PRODUCTION_LOCK_FILE=str(tmp_path / "lock"),
               PRODUCTION_DEPLOY_ENV=str(tmp_path / "missing-deploy-env"),
               PRODUCTION_STATE_DIR=str(state),
               PRODUCTION_MIGRATIONS_MANAGED_FILE=str(tmp_path / "managed"),
               PRODUCTION_DEPENDENCY_RECEIPT=str(tmp_path / "dependencies.json"),
               PRODUCTION_PYTHON=sys.executable)
    baseline = _commit(seed, "baseline", env)
    _git(seed, "remote", "add", "origin", str(bare), env=env)
    _git(seed, "push", "-q", "-u", "origin", "main", env=env)
    # The bare repository's default HEAD must point to main for clones.
    _git(bare, "symbolic-ref", "HEAD", "refs/heads/main", env=env)
    subprocess.run(["git", "clone", "-q", str(bare), str(repo)], env=env, check=True)
    (repo / ".deploy-build-sha").write_text(baseline + "\n")
    subprocess.run(["git", "clone", "-q", str(bare), str(pusher)], env=env, check=True)
    target = _commit(pusher, "target", env)
    _git(pusher, "push", "-q", "origin", "main", env=env)

    def run(sha=target, *, flags=(), **updates):
        call_env = dict(env, **{key: str(value) for key, value in updates.items()})
        return subprocess.run(["bash", str(DEPLOY), sha, *flags], env=call_env,
                              capture_output=True, text=True, timeout=30)

    def read_events():
        return events.read_text().splitlines() if events.exists() else []

    return SimpleDeployment(run, read_events, events, repo, pusher, state, tmp_path, env,
                            baseline, target)


class SimpleDeployment:
    def __init__(self, run, read_events, events, repo, pusher, state, root, env, baseline, target):
        self.run = run
        self.read_events = read_events
        self.events = events
        self.repo = repo
        self.pusher = pusher
        self.state = state
        self.root = root
        self.env = env
        self.baseline = baseline
        self.target = target

    @property
    def receipt(self):
        return self.state / "last-successful.json"

    def next_commit(self, name="next"):
        sha = _commit(self.pusher, name, self.env)
        _git(self.pusher, "push", "-q", "origin", "main", env=self.env)
        return sha


@pytest.mark.parametrize('routing', [True, False])
def test_one_routing_transaction_orders_public_and_records_receipt(deployment, routing):
    result = deployment.run(flags=("--routing",) if routing else ())
    assert result.returncode == 0, result.stderr
    events = deployment.read_events()
    assert events.count("systemctl reload") == 1
    assert events.index("provision") < events.index("systemctl reload")
    if routing:
        assert events.index("public") < events.index("routing")
    else:
        assert 'routing' not in events
    receipt = json.loads(deployment.receipt.read_text())
    assert receipt["commit"] == deployment.target and receipt["routing"] is routing


def test_new_main_during_public_stage_does_not_abort_original_transaction(deployment):
    result = deployment.run(flags=("--routing",), ADVANCE_ORIGIN=1)
    assert result.returncode == 0, result.stderr
    assert _git(deployment.pusher, "rev-parse", "HEAD", env=deployment.env) != deployment.target
    assert deployment.read_events().index("public") < deployment.read_events().index("routing")
    assert json.loads(deployment.receipt.read_text())["commit"] == deployment.target


def test_migration_failure_blocks_provision_reload_public_and_receipt(deployment):
    result = deployment.run(FAIL_MIGRATION=1)
    assert result.returncode != 0
    assert (deployment.root / "managed").exists()
    assert not deployment.receipt.exists()
    assert not any(event in deployment.read_events() for event in
                   ("provision", "systemctl reload", "public", "routing"))


def test_deployment_hold_blocks_effects(deployment):
    deployment.state.mkdir()
    (deployment.state / "hold").write_text("maintenance\n")
    result = deployment.run()
    assert result.returncode != 0
    assert deployment.read_events() == []
    assert not deployment.receipt.exists()


def test_failed_public_stage_preserves_last_successful_receipt(deployment):
    first = deployment.run(flags=("--routing",))
    assert first.returncode == 0, first.stderr
    old_receipt = deployment.receipt.read_bytes()
    newer = deployment.next_commit()
    failed = deployment.run(newer, FAIL_PUBLIC=1)
    assert failed.returncode != 0
    assert deployment.receipt.read_bytes() == old_receipt


def test_repeat_verified_sha_has_no_reload_or_dependency_effects(deployment):
    first = deployment.run(flags=("--routing",))
    assert first.returncode == 0, first.stderr
    deployment.events.write_text("")
    second = deployment.run()
    assert second.returncode == 0, second.stderr
    assert "Already verified" in second.stdout
    assert deployment.read_events().count("verify_health_sha.py") == 3
    assert not any(event in deployment.read_events() for event in
                   ("install_dependencies.py", "provision", "systemctl reload", "public"))


def test_stale_requested_target_fails_before_effects(deployment):
    result = deployment.run(deployment.baseline)
    assert result.returncode != 0
    assert "stale deployment" in result.stderr
    assert deployment.read_events() == []
    assert not deployment.receipt.exists()
