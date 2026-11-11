"""The session loop as a process: started by `lado start`, one per session, ended with it."""

import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

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


SILENCE = 30  # the limit of a start of the fake agent (Provider.start_silence)
SILENCE_REASON = (
    "Waiting for an answer in its terminal: no sign from it 30 s after its start. "
    "Open its terminal."
)


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


def test_the_loop_runs_on_the_interval_of_the_environment_it_was_started_in(repo, session):
    interval = os.environ["LADO_LOOP_INTERVAL"]  # the integration tests' (conftest)
    assert loop.INTERVAL == loop.interval_from(interval) < 2
    start(repo, session)
    wait_for(lambda: f"{session}: loop started" in logged(session), "the loop", session)
    assert f"a pass every {loop.INTERVAL:g} s" in logged(session)


def test_the_loop_ends_when_its_tmux_session_is_gone(repo, session):
    start(repo, session)
    wait_for(lambda: loops(session), "the loop", session)
    tmux.kill_session(session)
    wait_for(lambda: not loops(session), "the loop to end", session)
    assert f"{session}: loop ended: its tmux session is gone" in logged(session)
    assert not loop.running(session)


def several_passes() -> None:
    """Wait as long as several passes of a loop that would still run take."""
    time.sleep(8 * loop.INTERVAL)  # the integration tests' interval, set per test (conftest)


def test_a_home_deleted_right_after_lado_stop_stays_deleted(repo, session, lado_home):
    start(repo, session)
    wait_for(lambda: loops(session), "the loop", session)
    assert lado_cli("stop", session).returncode == 0
    assert not loop.running(session) and not loops(session)
    shutil.rmtree(lado_home)
    several_passes()
    assert not lado_home.exists()


def test_stop_then_start_leaves_one_loop_the_new_one(repo, session):
    start(repo, session)
    wait_for(lambda: loops(session), "the loop", session)
    stopped = lado_cli("stop", session)
    assert stopped.returncode == 0, stopped.stderr
    start(repo, session)  # resumed at once
    wait_for(lambda: len(loops(session)) == 1, "one loop", session)
    first, ended, second = [
        line.split(f" {session}: ", 1)[1]
        for line in logged(session).splitlines()
        if f" {session}: loop " in line
    ]
    assert first.startswith("loop started") and second.startswith("loop started")
    assert ended in [f"loop ended: {reason}" for reason in (loop.STOPPED, loop.TMUX_GONE)]
    several_passes()
    assert loops(session) == [second.split("pid ")[1].split(",")[0]]  # the second one


def test_a_home_deleted_under_a_running_loop_is_not_made_again(repo, session, lado_home):
    start(repo, session)
    wait_for(lambda: loops(session), "the loop", session)
    shutil.rmtree(lado_home)
    wait_for(lambda: not loops(session), "the loop to end", session)
    several_passes()
    assert not lado_home.exists()


def test_the_loop_types_a_swallowed_message_again(repo, session):
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


def _launched_ago(session: str, name: str, seconds: float) -> None:
    """The agent's CLI was launched `seconds` ago, as the loop reads it (its window mark)."""
    with state.connect() as db:
        db.execute(
            "UPDATE agents SET window_at = strftime('%Y-%m-%d %H:%M:%f', 'now', ?)"
            " WHERE session = ? AND name = ?",
            (f"-{seconds} seconds", session, name),
        )


def test_the_loop_shows_an_agent_its_cli_holds_with_a_question_lado_does_not_know(
    repo, session, monkeypatch
):
    start(repo, session)
    monkeypatch.setenv("FAKE_AGENT_ASKS_UNKNOWN", "1")
    runtime.spawn_worker(session, "sleep 0", name="w1")
    wait_for(lambda: "Go on?" in tmux.capture(session, "w1"), "the question", session)
    assert state.get_agent(session, "w1").status == state.STARTING
    _launched_ago(session, "w1", SILENCE + 1)
    held = lambda: runtime.status_reason(session, "w1") == SILENCE_REASON  # noqa: E731
    wait_for(held, "the loop's reason", session)
    assert SILENCE_REASON in lado_cli("ls").stdout
    tmux.send_text(session, "w1", "yes")  # the human answers in its terminal
    wait_for(lambda: state.get_agent(session, "w1").status == state.IDLE, "w1 idle", session)
    assert runtime.status_reason(session, "w1") is None


def test_a_queue_waits_for_a_late_session_start_and_goes_in_once(
    repo, session, monkeypatch, tmp_path
):
    """A CLI slow to take input (OpenCode's or Kilo's TUI): no attempt runs out, however long
    it takes, and the agent is never busy before it has its message."""
    start(repo, session)
    ready = tmp_path / "ready"
    monkeypatch.setenv("FAKE_AGENT_START_HOLD", str(ready))
    runtime.spawn_worker(session, "sleep 0", name="w1")
    waited = sum(runtime.RETRY_DELAYS) + 2 * loop.INTERVAL
    deadline = time.monotonic() + waited
    while time.monotonic() < deadline:
        [task] = [m for m in state.list_messages(session) if m.recipient == "w1"]
        assert (task.state, task.attempts) == (state.PENDING, 0)
        assert state.get_agent(session, "w1").status == state.STARTING
        time.sleep(0.05)

    _launched_ago(session, "w1", SILENCE + 1)
    held = lambda: runtime.status_reason(session, "w1") == SILENCE_REASON  # noqa: E731
    wait_for(held, "the loop's reason", session)
    assert state.get_message(session, task.id).state == state.PENDING

    ready.touch()
    delivered = lambda: state.get_message(session, task.id).state in (state.DELIVERED, state.READ)  # noqa: E731
    wait_for(delivered, "the task delivered", session)
    assert state.get_message(session, task.id).attempts == 1
    assert runtime.status_reason(session, "w1") is None


SILENT = "no report from its TUI"


def test_the_loop_counts_a_start_by_its_provider_s_limit(repo, session, monkeypatch, tmp_path):
    """Past the 30 s of any CLI, a TUI whose report may still come is left alone. The loop is
    plain LADO, which knows no fake provider, so the agent's record names Kilo CLI."""
    start(repo, session)
    monkeypatch.setenv("FAKE_AGENT_START_HOLD", str(tmp_path / "ready"))
    runtime.spawn_worker(session, "sleep 0", name="w1")
    with state.connect() as db:
        db.execute(
            "UPDATE agents SET provider = 'kilo' WHERE session = ? AND name = 'w1'", (session,)
        )
    _launched_ago(session, "w1", SILENCE + 1)
    time.sleep(4 * loop.INTERVAL)
    assert state.get_agent(session, "w1").status == state.STARTING

    _launched_ago(session, "w1", 46)
    reason = SILENCE_REASON.replace("30 s", "45 s")
    wait_for(lambda: runtime.status_reason(session, "w1") == reason, "the reason", session)


def test_a_silent_tui_s_agent_is_ready_its_lead_is_told_and_its_task_is_typed_in(
    repo, session, monkeypatch, tmp_path
):
    """The server plugin is alive and the TUI said nothing: LADO types in as it did."""
    start(repo, session)
    ready = tmp_path / "ready"
    monkeypatch.setenv("FAKE_AGENT_START_HOLD", str(ready))
    monkeypatch.setenv("FAKE_AGENT_START_NOTE", SILENT)
    runtime.spawn_worker(session, "sleep 0", name="w1")
    [task] = [m for m in state.list_messages(session) if m.recipient == "w1"]
    typed = lambda: state.get_message(session, task.id).attempts >= 1  # noqa: E731
    wait_for(typed, "the task typed in", session)
    told = [m.summary for m in state.list_messages(session) if m.recipient == "supervisor"]
    assert f"w1: {SILENT}" in told


def _silent_worker(monkeypatch, tmp_path, session: str) -> tuple[state.Message, Path]:
    ready = tmp_path / "ready"
    monkeypatch.setenv("FAKE_AGENT_START_HOLD", str(ready))
    monkeypatch.setenv("FAKE_AGENT_START_NOTE", SILENT)
    runtime.spawn_worker(session, "sleep 0", name="w1")
    [task] = [m for m in state.list_messages(session) if m.recipient == "w1"]
    return task, ready


def _inputs(session: str) -> list[str]:
    log = agent_helpers.fake_logs(session, "w1") / "inputs.jsonl"
    return log.read_text().splitlines() if log.exists() else []


@pytest.mark.parametrize("attempts", [1, 4], ids=["first paste", "last paste"])
def test_a_tui_that_opens_while_a_paste_is_unconfirmed_gets_it(
    repo, session, monkeypatch, tmp_path, attempts
):
    """Busy, with the paste lost: the report ran no turn, so nothing but LADO ends that."""
    monkeypatch.setenv("LADO_RETRY_DELAYS", "1,1,4")
    monkeypatch.setattr(runtime, "RETRY_DELAYS", (1.0, 1.0, 4.0))
    start(repo, session)
    task, ready = _silent_worker(monkeypatch, tmp_path, session)
    typed = lambda: state.get_message(session, task.id).attempts >= attempts  # noqa: E731
    wait_for(typed, f"attempt {attempts}", session)

    ready.touch()
    delivered = lambda: state.get_message(session, task.id).state in (state.DELIVERED, state.READ)  # noqa: E731
    wait_for(delivered, "the task delivered", session)


def test_a_paste_the_cli_held_is_not_typed_again_when_it_opens(
    repo, session, monkeypatch, tmp_path
):
    monkeypatch.setenv("FAKE_AGENT_START_KEEPS", "1")
    start(repo, session)
    task, ready = _silent_worker(monkeypatch, tmp_path, session)
    typed = lambda: state.get_message(session, task.id).attempts >= 1  # noqa: E731
    wait_for(typed, "the task typed in", session)

    ready.touch()
    delivered = lambda: state.get_message(session, task.id).state in (state.DELIVERED, state.READ)  # noqa: E731
    wait_for(delivered, "the task delivered", session)
    time.sleep(runtime.RETRY_DELAYS[0] + 2 * loop.INTERVAL)
    assert len([line for line in _inputs(session) if "your task" in line]) == 1


def test_what_a_silent_tui_lost_goes_in_when_it_opens_after_all(
    repo, session, monkeypatch, tmp_path
):
    """Every attempt went into a window with no input field, and the message failed: the TUI's
    late report brings it back (state.seen), and it arrives."""
    start(repo, session)
    ready = tmp_path / "ready"
    monkeypatch.setenv("FAKE_AGENT_START_HOLD", str(ready))
    monkeypatch.setenv("FAKE_AGENT_START_NOTE", SILENT)
    runtime.spawn_worker(session, "sleep 0", name="w1")
    [task] = [m for m in state.list_messages(session) if m.recipient == "w1"]
    failed = lambda: state.get_message(session, task.id).state == state.FAILED  # noqa: E731
    wait_for(failed, "the task failed", session)

    ready.touch()
    delivered = lambda: state.get_message(session, task.id).state in (state.DELIVERED, state.READ)  # noqa: E731
    wait_for(delivered, "the task delivered", session)
