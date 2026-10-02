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


def test_a_killed_tmux_session_shows_as_tmux_gone(streams, session):
    stream = streams()
    stream.next()
    time.sleep(4)  # past the server's first computation of what is derived
    tmux.kill_session(session)
    gone = stream.until(session_change(session, "tmux_gone"), timeout=15)[-1]
    assert gone.id is None


def test_a_tmux_session_killed_while_no_stream_was_open_shows_on_reconnect(streams, session):
    stream = streams()
    position = stream.next().id
    stream.close()
    tmux.kill_session(session)
    again = streams(after=position)
    assert again.until(session_change(session, "tmux_gone"), timeout=5)[-1].id is None


def test_the_server_stops_with_a_stream_open(streams):
    stream = streams()
    stream.next()
    started = time.monotonic()
    stopped = lado_cli("server", "stop")
    assert stopped.returncode == 0, stopped.stderr
    assert stream.closed.wait(5)
    assert time.monotonic() - started < server_run.STOP_TIMEOUT / 2
