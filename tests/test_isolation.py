import os
import re
import subprocess
import sys

from lado import state, tmux


def test_tests_ignore_the_lado_and_tmux_of_the_agent_running_them(lado_home):
    # An agent's shell has these set; `make check` must run there as is.
    for var in ("LADO_AGENT", "LADO_SESSION", "TMUX"):
        assert var not in os.environ
    assert state.home() == lado_home
    assert re.fullmatch(r"lado-test-[0-9a-f]{8}", tmux.socket())


def test_lado_processes_of_a_test_send_no_statistics():
    # LADO_TELEMETRY=0 of tests/conftest.py reaches the LADO processes a test starts.
    result = subprocess.run(
        [sys.executable, "-m", "lado.cli", "telemetry", "status"],
        capture_output=True,
        text=True,
        check=True,    )
    assert "statistics: off: LADO_TELEMETRY=0 is set" in result.stdout
