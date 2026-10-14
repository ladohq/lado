"""`lado stats` of a real session: the counted facts written by LADO's processes (hooks,
the CLI), and the counts kept across `lado forget`."""

import subprocess

import agent_helpers
import fake_provider
import pytest

from lado import runtime, state

pytestmark = pytest.mark.integration

SESSION = "usage"


def _lado(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        fake_provider.lado_command(*args),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )


def _stats() -> list[str]:
    done = _lado("stats", "--all")
    assert done.returncode == 0, done.stderr
    return done.stdout.splitlines()


def test_stats_counts_a_session_and_keeps_it_after_forget(repo):
    runtime.start_session(str(repo), SESSION, None, "fake")
    agent_helpers.wait_for(
        lambda: state.get_agent(SESSION, "supervisor").status == state.IDLE, "idle", SESSION
    )
    runtime.spawn_worker(SESSION, "fail rate_limit", name="w1")  # its hook writes the error
    agent_helpers.wait_for(
        lambda: any(e.kind == state.TURN_ERROR for e in state.list_events(SESSION)),
        "w1's turn error",
        SESSION,
    )
    done = _lado("stop", SESSION)
    assert done.returncode == 0, done.stderr
    before = _stats()
    expected = [
        "  started                       1",
        "  started                       2  fake 2",
        "  by role                          supervisor@default 1, worker@default 1",
        "  turns ended on an error       1  fake 1 (rate_limit 1)",
    ]
    for line in expected:
        assert line in before, before
    done = _lado("forget", SESSION)
    assert done.returncode == 0, done.stderr
    assert state.get_session(SESSION) is None
    assert _stats() == before
