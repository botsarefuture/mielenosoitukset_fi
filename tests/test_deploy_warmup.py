"""Deploys must not fail, or briefly close the site, while a restarted service warms up."""

import re
import subprocess
from pathlib import Path

ROUTING = Path("deploy/release_routing.sh").read_text(encoding="utf-8")
PUBLIC_DEPLOY = Path("deploy/public-app/deploy.sh").read_text(encoding="utf-8")


def _run_retry(script):
    retry = re.search(r"^retry\(\) \{.*?^\}", ROUTING, re.S | re.M).group(0)
    return subprocess.run(
        ["bash", "-c", "set -euo pipefail\nsleep() { :; }\n" + retry + "\n" + script],
        capture_output=True, text=True, timeout=10,
    )


def test_retry_succeeds_once_a_probe_recovers_and_fails_after_the_last_attempt():
    recovered = _run_retry('n=0; probe() { n=$((n + 1)); [[ $n -ge 3 ]]; }; retry 3 2 probe; echo "tries=$n"')
    assert recovered.returncode == 0 and "tries=3" in recovered.stdout
    failed = _run_retry('n=0; probe() { n=$((n + 1)); return 1; }; retry 3 2 probe || echo "failed after $n"')
    assert "failed after 3" in failed.stdout
    stopped = _run_retry('n=0; probe() { n=$((n + 1)); return 1; }; retry 3 2 probe; echo unreachable')
    assert stopped.returncode != 0 and "unreachable" not in stopped.stdout, "set -e must still stop the rollout"


def test_routing_retries_every_probe_and_still_rolls_back_on_failure():
    assert 'retry 3 2 probe_origin "$path"' in ROUTING
    assert 'retry 3 2 probe_public "$path"' in ROUTING
    assert "if [[ $status -ne 0 ]]; then restore; fi" in ROUTING


def test_public_host_deploy_waits_for_a_rendered_page_not_only_health():
    health = PUBLIC_DEPLOY.index("http://127.0.0.1:8090/health")
    warm = PUBLIC_DEPLOY.index("http://127.0.0.1:8090/ ")
    enable = PUBLIC_DEPLOY.index('systemctl enable "$service"')
    assert health < warm < enable
    assert "grep -q -- /app-assets/" in PUBLIC_DEPLOY
    assert "Public app did not render the home page after restart" in PUBLIC_DEPLOY
