"""The UI server's event stream as the UI gets it: a real `lado server` process, and changes
written by other processes (the CLI, the fake agent's hooks, the session loop) or by tmux."""

import os
import subprocess
import sys
import time
import uuid

import agent_helpers
import httpx
import pytest
from event_stream import EventStream

from lado import runtime, state, tmux
from lado.server import auth
from lado.server import run as server_run

pytestmark = pytest.mark.integration


def lado_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lado.cli", *args],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
        timeout=30,
    )


@pytest.fixture
def server():
    process = subprocess.Popen(
        [sys.executable, "-m", "lado.cli", "server", "--port", "0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ,
    )
    try:
        yield server_run.wait_ready()["url"]
    finally:
        lado_cli("server", "stop")
        process.wait(timeout=10)


@pytest.fixture
def streams(server):
    opened: list[EventStream] = []

    def open_stream(**kwargs) -> EventStream:
        stream = EventStream(f"{server}/api/events", auth.token(), **kwargs)
        assert stream.status == 200
        opened.append(stream)
        return stream

    yield open_stream
    for stream in opened:
        stream.close()


@pytest.fixture
def session(repo):
    name = f"ev-{uuid.uuid4().hex[:8]}"
    runtime.start_session(str(repo), name, None, "fake")
    agent_helpers.wait_for(
        lambda: state.get_agent(name, "supervisor").status == state.IDLE, "idle", name
    )
    agent_helpers.wait_for(
        lambda: runtime.session_status(state.get_session(name)) == runtime.SessionStatus.RUNNING,
        "its loop",
        name,
    )
    yield name
    if not state.get_session(name).stopped_at:
        runtime.stop_session(name)


def session_change(session: str, status: str | None = None):
    def wanted(event) -> bool:
        if event.event != "change" or event.data["kind"] != "sessions":
            return False
        item = event.data["item"]
        return event.data["session"] == session and (status is None or item["status"] == status)

    return wanted


def derived_change(session: str, status: str):
    """A change of the session's status the hub derived (no id: no journal row has it)."""
    of_session = session_change(session, status)
    return lambda event: of_session(event) and event.id is None


def test_a_change_by_another_process_reaches_the_stream(streams, session):
    stream = streams()
    reset = stream.next()
    assert reset.event == "reset"
    assert lado_cli("stop", session).returncode == 0
    events = stream.until(session_change(session, "stopped"), timeout=15)
    assert events[-1].id > reset.id
    agents = [e for e in events if e.event == "change" and e.data["kind"] == "agents"]
    assert ("supervisor", "delete") in [(e.data["key"], e.data["op"]) for e in agents]


def test_an_agents_hook_reaches_the_stream(streams, session):
    stream = streams()
    stream.next()
    runtime.send_message(session, "human", "supervisor", "hello")  # the fake agent goes busy
    stream.until(
        lambda e: (
            e.event == "change" and (e.data["kind"], e.data["key"]) == ("agents", "supervisor")
        ),
        timeout=15,
    )


def test_a_reconnect_from_its_position_gets_what_it_missed(streams, session):
    stream = streams()
    position = stream.next().id
    stream.close()
    assert lado_cli("stop", session).returncode == 0
    again = streams(after=position)
    replayed = again.until(session_change(session, "stopped"), timeout=15)
    assert all(e.event == "change" for e in replayed)


def test_a_write_between_the_streams_start_and_the_load_is_not_lost(server, streams, session):
    """The UI loads its data on reset; whatever is written after the reset's position comes
    in the stream, also when the load already has it."""
    stream = streams()
    reset = stream.next()
    assert lado_cli("stop", session).returncode == 0
    headers = {"Authorization": f"Bearer {auth.token()}"}
    loaded = httpx.get(f"{server}/api/sessions", headers=headers).json()
    assert [s["status"] for s in loaded if s["name"] == session] == ["stopped"]
    assert stream.until(session_change(session, "stopped"), timeout=15)[-1].id > reset.id


def past_the_first_derivation(stream: EventStream, session: str) -> None:
    """Wait until the server has computed what is derived once for this stream: its hub does
    that at the end of its first pass (feed.Hub._pass). A change written after one that came
    in the stream comes in a later pass, so the first one is over by then."""
    for n in (1, 2):
        runtime.send_message(session, "human", "supervisor", f"probe {n}")
        stream.until(
            lambda e, n=n: (
                e.event == "change"
                and e.data["kind"] == "messages"
                and (e.data["item"] or {}).get("summary") == f"probe {n}"
            ),
            timeout=15,
        )


def test_a_killed_tmux_session_shows_as_tmux_gone(streams, session):
    stream = streams()
    stream.next()
    past_the_first_derivation(stream, session)
    tmux.kill_session(session)
    # The supervisor's end (agent_ended) may bring the session's item already gone through
    # the journal first, an id with it: what the hub promises is its derived change.
    stream.until(derived_change(session, "tmux_gone"), timeout=15)


def test_a_tmux_session_killed_while_no_stream_was_open_shows_on_reconnect(streams, session):
    stream = streams()
    position = stream.next().id
    stream.close()
    tmux.kill_session(session)
    again = streams(after=position)
    again.until(derived_change(session, "tmux_gone"), timeout=5)


def test_the_server_stops_with_a_stream_open(streams):
    """The shutdown ends the stream (the response's end, not a cut), so the stop does not
    wait out the server's grace for open requests."""
    stream = streams()
    stream.next()
    started = time.monotonic()
    assert server_run.stop() is not None
    took = time.monotonic() - started
    assert stream.closed.wait(5)
    assert stream.error is None
    assert took < server_run.SHUTDOWN_GRACE * 0.8
