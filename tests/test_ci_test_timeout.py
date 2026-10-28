"""CI must fail with diagnostics when fixture setup, a test, or teardown hangs."""
import subprocess
import sys

import pytest


@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
def test_ci_timeout_bounds_the_entire_test_lifecycle(tmp_path, phase):
    test = tmp_path / "test_stalled_fixture.py"
    test.write_text(
        "import pytest, threading\n"
        "def stall(): threading.Event().wait()\n"
        "@pytest.fixture\n"
        "def resource():\n"
        f"    if {phase!r} == 'setup': stall()\n"
        "    yield\n"
        f"    if {phase!r} == 'teardown': stall()\n"
        "def test_stall(resource):\n"
        f"    if {phase!r} == 'call': stall()\n"
    )
    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\n")
    result = subprocess.run(
        [sys.executable, "-u", "-m", "pytest", "-c", str(config),
         "--noconftest", "--timeout=1", "--timeout-method=thread", "-v", str(test)],
        cwd=tmp_path, capture_output=True, text=True, timeout=15,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "timeout" in output.lower()
    assert "test_stall" in output
    assert "stall" in output  # The actual blocked stack must be printed.
