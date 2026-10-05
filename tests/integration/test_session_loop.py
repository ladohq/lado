"""The session loop as a process: started by `lado start`, one per session, ended with it."""

import os
import subprocess
import sys
import uuid

import agent_helpers
import pytest

from lado import loop, runtime, state, tmux

pytestmark = pytest.mark.integration


@pytest.fixture
def session():
    # A name of its own: the loop processes of tests running in parallel are told apart by it.
    return f"loop-{uuid.uuid4().hex[:8]}"


def loops(session: str) -> list[str]:
    """The pids of the session's loop processes."""
    found = subprocess.run(
        ["pgrep", "-f", f"lado.cli loop {session}$"], capture_output=True, text=True
    )
    return found.stdout.split()


def lado_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lado.cli", *args],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
        timeout=10,
    )


def wait_for(check, what: str, session: str):
    return agent_helpers.wait_for(check, what, session)


def start(repo, session: str) -> None:
    runtime.start_session(str(repo), session, None, "fake")
    wait_for(lambda: state.get_agent(session, "supervisor").status == state.IDLE, "idle", session)


def logged(session: str) -> str:
    path = state.home() / "loop.log"
    return path.read_text() if path.exists() else ""


def test_a_session_has_one_loop_after_start_and_after_resume(repo, session):
    start(repo, session)
    wait_for(lambda: len(loops(session)) == 1, "one loop", session)
    assert lado_cli("loop", session).returncode == 0  # a second one exits at once
    assert len(loops(session)) == 1
    assert lado_cli("stop", session).returncode == 0
    wait_for(lambda: not loops(session), "the loop to end", session)
    agent_helpers.check_loop_ended_by_stop(session)
    start(repo, session)  # resumed
    wait_for(lambda: len(loops(session)) == 1, "one loop after the resume", session)
    assert loop.running(session)


def test_the_loop_ends_when_its_tmux_session_is_gone(repo, session):
    start(repo, session)
    wait_for(lambda: loops(session), "the loop", session)
    tmux.kill_session(session)
    wait_for(lambda: not loops(session), "the loop to end", session)
    assert f"{session}: loop ended: its tmux session is gone" in logged(session)
    assert not loop.running(session)


def test_the_loop_types_a_swallowed_message_again(repo, session, monkeypatch):
    monkeypatch.setenv("LADO_RETRY_DELAYS", "0.5,0.5,0.5")  # for the loop it starts
    start(repo, session)
    tmux.send_text(session, "supervisor", "dialog")  # opened by the human, say
    assert runtime.send_message(session, "w1", "supervisor", "report") == "sent"
    wait_for(lambda: "swallowed" in tmux.capture(session, "supervisor"), "the dialog", session)
    # No send and no hook from here on: only the loop types it again.
    delivered = [state.DELIVERED]
    wait_for(
        lambda: [m.state for m in state.list_messages(session)] == delivered, "delivery", session
    )
    [message] = state.list_messages(session)
    assert message.attempts == 2


def test_the_loop_types_in_a_message_every_hook_missed(repo, session):
    start(repo, session)
    # Queued for the idle supervisor without a send: no sender and no hook hands it over.
    state.queue_message(session, "w1", "supervisor", "report")
    wait_for(
        lambda: [m.state for m in state.list_messages(session)] == [state.DELIVERED],
        "delivery",
        session,
    )
