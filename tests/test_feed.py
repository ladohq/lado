"""The UI server's event stream (GET /api/events, lado.server.feed): a real uvicorn in this
process, so the stream is read over HTTP as the browser reads it; the writers are lado.state
and lado.runtime in the same process. Writers in other processes are in
tests/integration/test_server_process.py."""

import socket
import sqlite3
import threading
import time

import pytest
import uvicorn
from agent_helpers import previous_schema
from event_stream import EventStream

from lado import loop, runtime, state
from lado.server import app as server_app
from lado.server import auth, feed


@pytest.fixture
def server(monkeypatch):
    """The server's base URL; quick polls, so a change shows within a test's patience."""
    monkeypatch.setattr(feed, "POLL", 0.05)
    monkeypatch.setattr(feed, "DERIVED_EVERY", 0.2)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(
        server_app.create_app(auth.token(), port),
        log_level="warning",
        timeout_graceful_shutdown=1,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "the server did not start"
        time.sleep(0.01)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(10)
    sock.close()


@pytest.fixture
def streams(server):
    opened: list[EventStream] = []

    def open_stream(**kwargs) -> EventStream:
        stream = EventStream(f"{server}/api/events", auth.token(), **kwargs)
        opened.append(stream)
        return stream

    yield open_stream
    for stream in opened:
        stream.close()


def last_change() -> int:
    with state.connect() as db:
        return db.execute("SELECT coalesce(max(id), 0) FROM changes").fetchone()[0]


def is_change(kind: str, session: str):
    return lambda e: e.event == "change" and (e.data["kind"], e.data["session"]) == (kind, session)


def test_a_stream_without_a_position_starts_with_reset_at_the_latest_change(streams):
    state.add_session(state.Session("s", "/r", None))
    stream = streams()
    first = stream.next()
    assert (first.event, first.id) == ("reset", last_change())


def test_a_change_after_the_start_comes_with_its_item_in_the_form_of_the_rest_api(
    streams, fake_tmux
):
    stream = streams()
    stream.next()  # reset
    state.add_session(state.Session("s", "/r", None))
    added = stream.until(is_change("sessions", "s"))[-1]
    assert added.id == last_change()
    assert added.data == {
        "kind": "sessions",
        "session": "s",
        "key": "",
        "op": "insert",
        "item": {"name": "s", "repo": "/r", "status": "tmux_gone", "agents": 0},
    }
    state.delete_session("s")
    deleted = stream.until(is_change("sessions", "s"))[-1]
    assert (deleted.data["op"], deleted.data["item"]) == ("delete", None)


def test_the_item_is_the_rows_current_state_whatever_the_op(streams, fake_tmux):
    state.add_session(state.Session("s", "/r", None))
    position = last_change()
    state.delete_session("s")
    state.add_session(state.Session("s", "/new", None))
    stream = streams(after=position)
    change = stream.next()
    # The delete and the insert are one change of the same row; the item is what is there.
    assert (change.data["op"], change.data["item"]["repo"]) == ("insert", "/new")
    assert change.id == last_change()


def test_kinds_without_a_model_yet_come_with_a_null_item(streams):
    state.add_session(state.Session("s", "/r", None))
    stream = streams()
    stream.next()
    state.queue_message("s", "a", "b", "hello")
    message = stream.until(is_change("messages", "s"))[-1]
    assert message.data["item"] is None and message.data["op"] == "insert"


def test_a_change_of_an_agent_also_updates_its_session(streams, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    stream = streams()
    stream.next()
    runtime.stop_session("s")
    events = stream.quiet(1)
    agents = [e for e in events if e.event == "change" and e.data["kind"] == "agents"]
    sessions = [e for e in events if e.event == "change" and e.data["kind"] == "sessions"]
    assert agents and agents[-1].data["op"] == "delete"
    assert sessions[-1].data["item"]["agents"] == 0
    assert sessions[-1].data["item"]["status"] == "stopped"


def test_a_position_replays_what_came_after_it_once_per_row(streams):
    state.add_session(state.Session("s", "/r", None))
    position = last_change()
    state.add_session(state.Session("t", "/r", None))
    with state.connect() as db:
        for repo in ("/a", "/b", "/c"):
            db.execute("UPDATE sessions SET repo = ? WHERE name = 's'", (repo,))
    stream = streams(after=position)
    replayed = [stream.next(), stream.next()]
    assert [(e.data["session"], e.id) for e in replayed] == [
        ("t", position + 1),
        ("s", last_change()),
    ]
    assert replayed[1].data["item"]["repo"] == "/c"


def test_last_event_id_counts_before_after(streams):
    state.add_session(state.Session("s", "/r", None))
    middle = last_change()
    state.add_session(state.Session("t", "/r", None))
    stream = streams(after=0, last_id=middle)
    assert stream.next().data["session"] == "t"


@pytest.mark.parametrize("gone", ["trimmed", "ahead"])
def test_a_position_the_journal_no_longer_has_starts_with_reset(streams, gone):
    state.add_session(state.Session("s", "/r", None))
    old = last_change()
    if gone == "trimmed":
        with state.connect() as db:
            db.execute(
                "INSERT INTO changes (id, kind, session, key, op)"
                " VALUES (?, 'sessions', 's', '', 'update')",
                (old + state.CHANGES_KEPT + 1,),
            )
        position = old - 1
    else:
        position = old + 5
    first = streams(after=position).next()
    assert (first.event, first.id) == ("reset", last_change())


def test_the_stream_needs_the_token(server):
    assert EventStream(f"{server}/api/events", "nope").status == 401


@pytest.mark.parametrize("which", ["older", "newer"])
def test_another_schema_answers_503(streams, which):
    state.list_sessions()
    if which == "older":
        previous_schema()
    else:
        with state.connect() as db:
            db.execute(f"PRAGMA user_version = {state.SCHEMA_VERSION + 1}")
    assert streams().status == 503


def test_another_schema_ends_an_open_stream(streams):
    state.add_session(state.Session("s", "/r", None))
    stream = streams()
    stream.next()
    with state.connect() as db:
        db.execute(f"PRAGMA user_version = {state.SCHEMA_VERSION + 1}")
    assert stream.closed.wait(5)


def test_without_a_database_the_stream_waits_for_one_and_creates_none(streams, fake_tmux):
    stream = streams()
    first = stream.next()
    assert (first.event, first.id) == ("reset", 0)
    time.sleep(0.3)
    assert not (state.home() / "lado.db").exists()
    state.add_session(state.Session("s", "/r", None))
    assert stream.until(is_change("sessions", "s"))[-1].id == last_change()


def test_a_session_whose_tmux_is_gone_comes_without_an_id(streams, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    held = loop.take_lock("s")
    try:
        stream = streams()
        stream.next()
        stream.quiet(0.5)  # the server has seen it running
        fake_tmux.append(("kill_session", "s"))
        gone = stream.until(is_change("sessions", "s"))[-1]
    finally:
        held.close()
    assert gone.id is None
    assert gone.data["item"]["status"] == "tmux_gone"


def test_a_resumed_stream_gets_the_derived_fields_as_they_are_now(streams, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    state.add_session(state.Session("stopped", "/r", None))
    state.stop_session("stopped")
    position = last_change()
    fake_tmux.append(("kill_session", "s"))  # while no stream was open
    stream = streams(after=position)
    snapshot = stream.next()
    assert (snapshot.event, snapshot.id) == ("change", None)
    assert snapshot.data["item"] == {
        "name": "s",
        "repo": str(repo),
        "status": "tmux_gone",
        "agents": 1,
    }
    assert stream.quiet(0.3) == []  # a stopped session has nothing derived


def test_a_quiet_stream_gets_keep_alive_comments(streams, monkeypatch):
    monkeypatch.setattr(feed, "KEEPALIVE", 0.1)
    stream = streams()
    assert stream.next().event == "reset"
    assert stream.next(comments=True).event == "comment"


def broken_journal(monkeypatch):
    def fail(self, *args):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(feed.Journal, "after", fail)
    monkeypatch.setattr(feed.Journal, "last", fail)


def test_a_journal_that_cannot_be_read_ends_the_streams_and_new_ones_get_503(
    streams, monkeypatch, caplog
):
    state.add_session(state.Session("s", "/r", None))
    stream = streams()
    stream.next()
    broken_journal(monkeypatch)
    assert stream.closed.wait(5)  # the browser comes again and learns why
    for _ in range(5):  # the browser tries again and again
        refused = streams()
        assert refused.status == 503
        assert "disk I/O error" in refused.detail
    tracebacks = [
        r for r in caplog.records if r.name == "lado.server" and "Traceback" in r.getMessage()
    ]
    assert len(tracebacks) == 1  # the same error is not written again and again


def test_a_pass_that_keeps_failing_ends_each_new_stream_too(streams, monkeypatch):
    """The journal reads, but each pass fails later (here: building an item): every stream
    ends after FAILED_PASSES, not only the first one."""

    def fail(session, key):
        raise RuntimeError("no item")

    monkeypatch.setitem(feed.ITEMS, "sessions", fail)
    for round in range(2):
        stream = streams()
        assert stream.status == 200, round
        stream.next()
        state.add_session(state.Session(f"s{round}", "/r", None))
        assert stream.closed.wait(5), round


def test_the_journal_is_read_only(streams):
    """The server never writes lado.db: not even to trim the journal."""
    state.add_session(state.Session("s", "/r", None))
    path = state.home() / "lado.db"
    db = sqlite3.connect(path)
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.close()
    before = path.stat().st_mtime_ns, path.read_bytes()
    stream = streams(after=0)
    stream.quiet(0.3)
    assert (path.stat().st_mtime_ns, path.read_bytes()) == before
