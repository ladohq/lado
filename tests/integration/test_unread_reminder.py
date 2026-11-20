"""An agent that ends its turn with a message's text unread gets one reminder from LADO
(LAD-234): the fake agent's hooks, its MCP server, tmux and lado.db as processes. The fake
agent reads a body only when told to (`read`), as a weak model that answers the line alone."""

import json

import agent_helpers
import pytest

from lado import hooks, runtime, state

pytestmark = pytest.mark.integration

SESSION = "unread"
REMINDER = hooks.UNREAD_REMINDER.partition("{")[0]


def wait_for(check, what: str):
    return agent_helpers.wait_for(check, what, SESSION)


def inputs(agent: str = "w1") -> list:
    log = agent_helpers.fake_logs(SESSION, agent) / "inputs.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def reminders(agent: str = "w1") -> list[state.Message]:
    return [
        m
        for m in state.list_messages(SESSION)
        if (m.sender, m.recipient) == (state.LADO, agent) and m.summary.startswith(REMINDER)
    ]


def idle(agent: str = "w1") -> bool:
    return state.get_agent(SESSION, agent).status == state.IDLE


@pytest.fixture
def worker(repo):
    """w1 of a fake session, idle after its task."""
    runtime.start_session(str(repo), SESSION, None, "fake")
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_for(lambda: idle() and inputs(), "w1 idle after its task")
    yield "w1"
    runtime.stop_session(SESSION)


def got(summary: str, body: str = "Reply with the single word ACK") -> state.Message:
    """The supervisor's message to w1, once w1 got it and its turn is over."""
    runtime.send_message(SESSION, "supervisor", "w1", summary, body)
    # By its sender and summary: w1's reminder of it may follow it before this line runs.
    message = next(
        m
        for m in reversed(state.list_messages(SESSION))
        if m.sender == "supervisor" and m.summary == summary
    )
    line = runtime.format_message(message)
    wait_for(lambda: any(line in text for text in inputs() if isinstance(text, str)), "the line")
    return message


def test_a_text_left_unread_gets_one_reminder_and_is_read_after_it(worker):
    note = got("next read")  # reads only at its next input, the reminder
    [reminder] = wait_for(reminders, "the reminder")
    assert reminder.summary == (
        f"you have not read message #{note.id} from supervisor: call read_messages to get"
        " its text; if it asks nothing of you, do nothing."
    )
    wait_for(lambda: f"[from lado] {reminder.summary}" in inputs(), "the reminder typed in")
    wait_for(
        lambda: state.get_message(SESSION, note.id).state == state.READ, "the text read after it"
    )
    wait_for(idle, "w1 idle after the reminder's turn")
    assert len(reminders()) == 1


def test_a_reminder_ignored_gets_no_second_one(worker):
    note = got("sleep 0")
    wait_for(reminders, "the reminder")
    wait_for(lambda: len(inputs()) >= 3 and idle(), "the reminder's turn over")
    got("sleep 0", body="")  # one more turn
    wait_for(idle, "w1 idle")
    assert len(reminders()) == 1
    assert state.get_message(SESSION, note.id).state == state.DELIVERED


def test_a_text_read_in_the_turn_gets_no_reminder(worker):
    note = got("read")
    wait_for(lambda: state.get_message(SESSION, note.id).state == state.READ, "the text read")
    wait_for(idle, "w1 idle")
    assert reminders() == []


def test_a_turn_that_ended_on_an_error_reminds_of_nothing(worker):
    got("fail APIError: it broke")
    wait_for(
        lambda: [e for e in state.list_events(SESSION) if e.kind == state.TURN_ERROR],
        "the failed turn",
    )
    assert reminders() == []
