"""An agent's liveness for real: a fake agent that crashes, dies in a turn, ends a turn on an
error or exits with messages queued, and LADO ending agents itself with no false alarm."""

import json

import agent_helpers
import pytest

from lado import loop, runtime, state

pytestmark = pytest.mark.integration

SESSION = "live"
# Two passes of the session loop after an agent's first loop interval, and some slack.
FOUND_GONE = 5 * loop.INTERVAL + agent_helpers.TIMEOUT


def wait_for(check, what: str, timeout: float = agent_helpers.TIMEOUT):
    return agent_helpers.wait_for(check, what, SESSION, timeout)


def status(agent: str) -> str | None:
    found = state.get_agent(SESSION, agent)
    return found.status if found else None


def wait_status(agent: str, expected: str, timeout: float = agent_helpers.TIMEOUT) -> None:
    wait_for(lambda: status(agent) == expected, f"{agent} to be {expected}", timeout)


def inputs(agent: str) -> list:
    log = state.home() / "agents" / SESSION / agent / "inputs.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def hung_up(agent: str) -> bool:
    """Whether the agent ran its session-end hook as its window was killed."""
    path = state.home() / "agents" / SESSION / agent / "seen.json"
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
    return next(m for m in state.list_messages(SESSION) if m.recipient == agent)


@pytest.fixture
def session(repo, monkeypatch):
    # Like Claude Code, the fake agent runs its session-end hook when its window is killed.
    monkeypatch.setenv("FAKE_AGENT_HANGUP_HOOK", "1")
    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_status("supervisor", state.IDLE)
    return SESSION


def test_an_agent_that_crashes_before_its_first_hook_is_found_stopped(session):
    runtime.spawn_worker(SESSION, "crash at start", name="w1")
    runtime.send_message(SESSION, "supervisor", "w1", "are you there?")
    wait_status("w1", state.STOPPED, FOUND_GONE)
    assert runtime.status_reason(SESSION, "w1") == runtime.WINDOW_GONE
    assert message_to("w1").state == state.DROPPED
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
    runtime.spawn_worker(SESSION, "sleep 1\ndie", name="w1")
    wait_status("w1", state.BUSY)
    runtime.send_message(SESSION, "supervisor", "w1", "next")
    wait_status("w1", state.STOPPED, FOUND_GONE)
    assert runtime.status_reason(SESSION, "w1") == runtime.WINDOW_GONE
    assert message_to("w1").state == state.DROPPED


def test_a_turn_that_ends_on_an_error_hands_over_the_queue(session):
    runtime.spawn_worker(SESSION, "sleep 1\nfail rate_limit", name="w1")
    wait_status("w1", state.BUSY)
    runtime.send_message(SESSION, "supervisor", "w1", "go on")
    wait_for(lambda: message_to("w1").state == state.DELIVERED, "w1 to get its queue")
    assert "[from supervisor] go on" in inputs("w1")
    wait_status("w1", state.IDLE)
    assert "turn of w1 ended on an error: rate_limit; it is idle" in from_lado("supervisor")
    errors = [e.detail for e in state.list_events(SESSION) if e.kind == state.TURN_ERROR]
    assert errors == ["rate_limit"]


def test_an_agent_that_exits_with_messages_queued_drops_them_and_tells_the_sender(session):
    runtime.spawn_worker(SESSION, "sleep 1\nexit", name="w1")
    wait_status("w1", state.BUSY)
    runtime.send_message(SESSION, "supervisor", "w1", "one more")
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


def test_finishing_a_worker_tells_no_one_it_stopped(session):
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_status("w1", state.IDLE)
    runtime.finish_worker(SESSION, "w1")
    wait_for(lambda: hung_up("w1"), "w1's hook")
    assert about_an_end() == []


def test_stopping_a_session_tells_no_one_and_counts_what_it_dropped(session):
    runtime.spawn_worker(SESSION, "sleep 30", name="w1")
    wait_status("w1", state.BUSY)
    runtime.send_message(SESSION, "supervisor", "w1", "queued")
    stopped = runtime.stop_session(SESSION)
    for agent in ("supervisor", "w1"):
        wait_for(lambda agent=agent: hung_up(agent), f"{agent}'s hook")
    assert about_an_end() == []
    dropped = [m for m in state.list_messages(SESSION) if m.state == state.DROPPED]
    assert stopped.dropped == len(dropped) == 1
