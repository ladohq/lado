"""An agent's liveness for real: a fake agent that crashes, dies in a turn, ends a turn on an
error or exits with messages queued, and LADO ending agents itself with no false alarm."""

import json
import time

import agent_helpers
import fake_provider
import pytest

from lado import loop, runtime, state, tmux

pytestmark = pytest.mark.integration

SESSION = "live"


def found_gone() -> float:
    """Two passes of the session loop after an agent's first loop interval, and some slack:
    loop.INTERVAL is the integration tests' (conftest) only once a test runs."""
    return 5 * loop.INTERVAL + agent_helpers.TIMEOUT


def wait_for(check, what: str, timeout: float = agent_helpers.TIMEOUT):
    return agent_helpers.wait_for(check, what, SESSION, timeout)


def status(agent: str) -> str | None:
    found = state.get_agent(SESSION, agent)
    return found.status if found else None


def wait_status(agent: str, expected: str, timeout: float = agent_helpers.TIMEOUT) -> None:
    wait_for(lambda: status(agent) == expected, f"{agent} to be {expected}", timeout)


def release(agent: str, n: int) -> None:
    agent_helpers.release(SESSION, agent, n)


def inputs(agent: str) -> list:
    log = agent_helpers.fake_logs(SESSION, agent) / "inputs.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def hung_up(agent: str) -> bool:
    """Whether the agent ran its session-end hook as its window was killed."""
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return path.exists() and "hung_up" in json.loads(path.read_text())


def from_lado(to: str) -> list[str]:
    return [
        m.summary
        for m in state.list_messages(SESSION)
        if m.sender == state.LADO and m.recipient == to
    ]


def about_an_end() -> list[str]:
    """LADO's lines about an agent that stopped or a message not delivered."""
    lines = from_lado("supervisor") + from_lado(state.HUMAN)
    return [s for s in lines if " stopped (" in s or "not delivered" in s]


def message_to(agent: str) -> state.Message:
    """The first message to the agent after its task."""
    return [m for m in state.list_messages(SESSION) if m.recipient == agent][1]


@pytest.fixture
def session(repo, monkeypatch):
    # Like Claude Code, the fake agent runs its session-end hook when its window is killed.
    monkeypatch.setenv("FAKE_AGENT_HANGUP_HOOK", "1")
    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_status("supervisor", state.IDLE)
    return SESSION


def test_an_agent_that_crashes_before_its_first_hook_is_found_stopped(session, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_CRASH_AT_START", "1")  # w1 only: the supervisor runs
    runtime.spawn_worker(SESSION, "task", name="w1")
    runtime.send_message(SESSION, "supervisor", "w1", "are you there?")
    wait_status("w1", state.STOPPED, found_gone())
    assert runtime.status_reason(SESSION, "w1") == runtime.WINDOW_GONE
    assert [m.state for m in state.list_messages(SESSION) if m.recipient == "w1"] == [
        state.DROPPED,  # its task
        state.DROPPED,
    ]
    hint = f"w1 stopped ({runtime.WINDOW_GONE}): end it with"
    wait_for(
        lambda: any(s.startswith(hint) for s in from_lado("supervisor")), "the supervisor's hint"
    )
    lines = from_lado("supervisor")
    assert any(s.startswith("message #") and "w1 stopped (its window closed" in s for s in lines)
    with pytest.raises(runtime.LadoError, match='no running agent "w1"'):
        runtime.send_message(SESSION, "supervisor", "w1", "still there?")
    # The way out: finish it, though its window is gone.
    runtime.finish_worker(SESSION, "w1", discard=True)
    assert status("w1") is None


def test_an_agent_that_dies_in_a_turn_is_found_stopped(session):
    runtime.spawn_worker(SESSION, "pause\ndie", name="w1")
    wait_status("w1", state.BUSY)
    runtime.send_message(SESSION, "supervisor", "w1", "next")
    release("w1", 1)
    wait_status("w1", state.STOPPED, found_gone())
    assert runtime.status_reason(SESSION, "w1") == runtime.WINDOW_GONE
    assert message_to("w1").state == state.DROPPED


def test_a_turn_that_ends_on_an_error_hands_over_the_queue(session):
    runtime.spawn_worker(SESSION, "pause\nfail rate_limit", name="w1")
    wait_status("w1", state.BUSY)
    runtime.send_message(SESSION, "supervisor", "w1", "go on")
    release("w1", 1)
    wait_for(lambda: message_to("w1").state == state.DELIVERED, "w1 to get its queue")
    assert "[from supervisor] go on" in inputs("w1")
    wait_status("w1", state.IDLE)
    assert "turn of w1 ended on an error: rate_limit; it is idle" in from_lado("supervisor")
    errors = [e.detail for e in state.list_events(SESSION) if e.kind == state.TURN_ERROR]
    assert errors == ["rate_limit"]


def test_a_turn_that_ends_on_a_transient_error_is_resumed_until_the_resumes_are_spent(
    repo, monkeypatch
):
    """No hook comes after the turn's end: the session loop types in each resume. The lead
    hears of the error only after the last one."""
    monkeypatch.setenv("LADO_RESUME_DELAYS", "0.5,0.5")  # for the hooks and the loop
    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_status("supervisor", state.IDLE)
    runtime.spawn_worker(SESSION, "failing overloaded", name="w1")
    spent = "turn of w1 ended on an error after 2 resumes: overloaded; it is idle"
    wait_for(lambda: spent in from_lado("supervisor"), "the supervisor to be told")
    resumes = [
        f"[from lado] your turn ended on a temporary API error (overloaded); "
        f"continue where you left off (resume {n} of 2)"
        for n in (1, 2)
    ]
    lines = [i for i in inputs("w1") if str(i).startswith("[from lado]")]
    assert lines[0].startswith("[from lado] your task (#")
    assert lines[1:] == resumes
    assert [m.state for m in state.list_messages(SESSION) if m.recipient == "w1"] == [
        state.READ,  # its task
        state.DELIVERED,
        state.DELIVERED,
    ]
    assert from_lado("supervisor") == [spent]
    errors = [e.detail for e in state.list_events(SESSION) if e.kind == state.TURN_ERROR]
    assert errors == ["overloaded"] * 3


def test_an_agent_that_exits_with_messages_queued_drops_them_and_tells_the_sender(session):
    runtime.spawn_worker(SESSION, "pause\nexit", name="w1")
    wait_status("w1", state.BUSY)
    runtime.send_message(SESSION, "supervisor", "w1", "one more")
    release("w1", 1)
    wait_status("w1", state.STOPPED)
    assert runtime.status_reason(SESSION, "w1") == "its CLI exited"
    message = message_to("w1")
    assert message.state == state.DROPPED
    wait_for(
        lambda: any(
            s.startswith(f"message #{message.id} to w1 not delivered: w1 stopped")
            for s in from_lado("supervisor")
        ),
        "the supervisor to be told",
    )


def test_an_agent_whose_cli_asks_first_waits_until_the_human_answers(session, monkeypatch):
    """Like Claude Code's "trust this folder?": a question before any hook."""
    monkeypatch.setenv("FAKE_AGENT_ASKS_FIRST", "1")
    warnings = []
    runtime.spawn_worker(SESSION, "sleep 0", name="w1", warnings=warnings)
    assert warnings == [fake_provider.ASKS_FIRST]
    assert status("w1") == state.WAITING
    assert runtime.status_reason(SESSION, "w1") == fake_provider.ASKS_FIRST
    runtime.send_message(SESSION, "supervisor", "w1", "hello")
    time.sleep(2 * loop.INTERVAL)  # the loop sweeps: nothing is typed into the question
    assert (status("w1"), message_to("w1").state) == (state.WAITING, state.PENDING)
    tmux.send_text(SESSION, "w1", "yes")  # the human answers
    # Typed in with its task.
    wait_for(lambda: any("[from supervisor] hello" in i for i in inputs("w1")), "its message")
    wait_for(lambda: message_to("w1").state == state.DELIVERED, "w1 to confirm its message")
    assert runtime.status_reason(SESSION, "w1") is None


def test_an_agent_whose_cli_asks_first_and_ends_on_no_is_found_stopped(session, monkeypatch):
    monkeypatch.setenv("FAKE_AGENT_ASKS_FIRST", "1")
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    tmux.run("send-keys", "-t", f"{SESSION}:w1", "Enter")  # "no": the CLI exits, no hook
    wait_status("w1", state.STOPPED, found_gone())
    assert runtime.status_reason(SESSION, "w1") == runtime.WINDOW_GONE


def test_the_human_writes_to_a_worker_while_the_supervisor_is_stopped(session):
    """No copy is queued for a supervisor that would never get it; the worker gets the text."""
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_status("w1", state.IDLE)
    runtime.send_message(SESSION, "human", "supervisor", "exit")
    wait_status("supervisor", state.STOPPED)
    runtime.write_as_human(SESSION, "sleep 0", to="w1")
    wait_for(lambda: message_to("w1").state == state.DELIVERED, "w1 to get it")
    assert "[from human] sleep 0" in inputs("w1")
    assert from_lado("supervisor") == []


def test_finishing_a_worker_tells_no_one_it_stopped(session):
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_status("w1", state.IDLE)
    runtime.finish_worker(SESSION, "w1")
    wait_for(lambda: hung_up("w1"), "w1's hook")
    assert about_an_end() == []


def test_stopping_a_session_tells_no_one_and_counts_what_it_dropped(session):
    runtime.spawn_worker(SESSION, "pause", name="w1")  # never released: busy till the stop
    wait_for(lambda: agent_helpers.paused(SESSION, "w1", 1), "w1 to read its task")
    runtime.send_message(SESSION, "supervisor", "w1", "queued")
    stopped = runtime.stop_session(SESSION)
    for agent in ("supervisor", "w1"):
        wait_for(lambda agent=agent: hung_up(agent), f"{agent}'s hook")
    assert about_an_end() == []
    dropped = [m for m in state.list_messages(SESSION) if m.state == state.DROPPED]
    assert stopped.dropped == len(dropped) == 1
