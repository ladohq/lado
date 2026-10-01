import time

import pytest

from lado import log, state
from lado.cli import main


@pytest.fixture(autouse=True)
def utc(monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def _at(table: str, row_id: int, created_at: str) -> None:
    with state.connect() as db:
        db.execute(f"UPDATE {table} SET created_at = ? WHERE id = ?", (created_at, row_id))


@pytest.fixture
def session(lado_home):
    """Session "s": w1 spawned, the supervisor sends it a task, w1 gets busy, reports back."""
    state.add_session(state.Session("s", "/r", None))
    state.add_event("s", "w1", state.SPAWNED, "role developer, provider claude")
    _at("events", 1, "2026-10-01 10:00:00.100")
    state.queue_message("s", "supervisor", "w1", "fix it\nplease")
    _at("messages", 1, "2026-10-01 10:00:00.200")
    state.add_event("s", "w1", state.STATUS, "busy")
    _at("events", 2, "2026-10-01 10:00:00.300")
    state.queue_message("s", "w1", "supervisor", "done")
    _at("messages", 2, "2026-10-01 10:00:05.000")
    state.add_event("s", "supervisor", state.STATUS, "idle")
    _at("events", 3, "2026-10-01 10:00:01.000")
    return "s"


FEED = """\
10:00:00 w1: spawned (role developer, provider claude)
10:00:00 supervisor → w1 [pending]
    fix it
    please
10:00:00 w1: busy
10:00:01 supervisor: idle
10:00:05 w1 → supervisor [pending]
    done
"""


def test_log_prints_events_and_messages_in_time_order(session, capsys):
    assert main(["log", session]) == 0
    assert capsys.readouterr().out == FEED


def test_log_agent_keeps_its_messages_and_events(session, capsys):
    assert main(["log", session, "--agent", "supervisor"]) == 0
    assert capsys.readouterr().out == (
        "10:00:00 supervisor → w1 [pending]\n"
        "    fix it\n"
        "    please\n"
        "10:00:01 supervisor: idle\n"
        "10:00:05 w1 → supervisor [pending]\n"
        "    done\n"
    )


def test_log_n_shows_the_last_entries(session, capsys):
    assert main(["log", session, "-n", "2"]) == 0
    assert capsys.readouterr().out == (
        "10:00:01 supervisor: idle\n10:00:05 w1 → supervisor [pending]\n    done\n"
    )


def test_log_unknown_session_lists_sessions(session, capsys):
    assert main(["log", "nope"]) == 1
    assert capsys.readouterr().err == 'lado: unknown session "nope"; sessions: s\n'


def test_follow_prints_new_entries_until_interrupted(session, capsys):
    polls = []

    def sleep(seconds):
        polls.append(seconds)
        if len(polls) == 1:
            state.add_event("s", "w1", state.FINISHED, "")
            _at("events", 4, "2026-10-01 10:00:09.000")
        else:
            raise KeyboardInterrupt

    log.show("s", follow=True, sleep=sleep)
    assert capsys.readouterr().out == FEED + "10:00:09 w1: finished\n"
    assert polls == [1.0, 1.0]


def test_follow_ends_when_the_session_is_stopped(session, capsys):
    log.show("s", follow=True, sleep=lambda _: state.delete_session("s"))
    assert capsys.readouterr().out.endswith('Session "s" stopped.\n')


def test_messages_have_sub_second_times(lado_home):
    state.add_session(state.Session("s", "/r", None))
    state.queue_message("s", "a", "b", "hi")
    [message] = state.list_messages("s")
    assert len(message.created_at) == len("2026-10-01 10:00:00.000")
