"""The UI server's event stream (GET /api/events, lado.server.feed): a real uvicorn in this
process, so the stream is read over HTTP as the browser reads it; the writers are lado.state
and lado.runtime in the same process. Writers in other processes are in
tests/integration/test_server_process.py."""

import asyncio
import dataclasses
import json
import logging
import socket
import sqlite3
import threading
import time
from collections.abc import Callable

import pytest
import uvicorn
from agent_helpers import previous_schema, spoil_snapshot
from event_stream import EventStream

from lado import artifacts, kits, loop, runs, runtime, state
from lado.server import app as server_app
from lado.server import auth, feed, models
from lado.server.run import SHUTDOWN_GRACE


@dataclasses.dataclass
class Running:
    url: str
    stop: Callable[[], None]  # shuts the server down as SIGTERM does, and waits for its end


@pytest.fixture
def running(monkeypatch):
    """The server; quick polls, so a change shows within a test's patience."""
    monkeypatch.setattr(feed, "POLL", 0.05)
    monkeypatch.setattr(feed, "DERIVED_EVERY", 0.2)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(
        server_app.create_app(auth.token(), port),
        log_level="warning",
        timeout_graceful_shutdown=SHUTDOWN_GRACE,
    )
    server = server_app.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "the server did not start"
        time.sleep(0.01)

    def stop() -> None:
        server.should_exit = True
        thread.join(10)

    yield Running(f"http://127.0.0.1:{port}", stop)
    stop()
    sock.close()


@pytest.fixture
def server(running):
    """The server's base URL."""
    return running.url


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
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    stream = streams()
    first = stream.next()
    assert (first.event, first.id) == ("reset", last_change())


def test_a_change_after_the_start_comes_with_its_item_in_the_form_of_the_rest_api(
    streams, fake_tmux
):
    stream = streams()
    stream.next()  # reset
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    added = stream.until(is_change("sessions", "s"))[-1]
    assert added.id == last_change()
    assert added.data == {
        "kind": "sessions",
        "session": "s",
        "key": "",
        "op": "insert",
        "item": {
            "name": "s",
            "repo": "/r",
            "status": "tmux_gone",
            "agents": 0,
            "waiting": {"gates": 0, "questions": 0, "agents": 0},
            "kits": ["default"],
            "provider": "claude",
            "permission_mode": None,
            "without": [],
            "ran_seconds": 0,
            "running_since": None,
            "stopped_at": None,
        },
    }
    state.delete_session("s")
    deleted = stream.until(is_change("sessions", "s"))[-1]
    assert (deleted.data["op"], deleted.data["item"]) == ("delete", None)


def test_the_item_is_the_rows_current_state_whatever_the_op(streams, fake_tmux):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    position = last_change()
    state.delete_session("s")
    state.add_session(state.Session("s", "/new", None, provider="claude"))
    stream = streams(after=position)
    change = stream.next()
    # The delete and the insert are one change of the same row; the item is what is there.
    assert (change.data["op"], change.data["item"]["repo"]) == ("insert", "/new")
    assert change.id == last_change()


# The smallest flow a run can have: its item is built from the run's snapshot.
SNAPSHOT = {
    "name": "feature",
    "description": "d",
    "start": "design",
    "states": {
        "design": {"agent": "supervisor", "do": "Design it.", "outcomes": {"ready": "done"}},
        "done": {"end": True},
    },
}


def bare_run() -> state.Run:
    return state.Run(
        "s", "feature/x", "feature", json.dumps(SNAPSHOT), {}, "x", "design", "/w", "b"
    )


def test_a_runs_change_comes_with_its_item_in_the_form_of_the_rest_api(streams):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    stream = streams()
    stream.next()
    state.add_run(bare_run(), [("lado", state.FLOW_START, "at design")])
    added = stream.until(is_change("runs", "s"))[-1]
    item = added.data["item"]
    assert (added.data["key"], added.data["op"]) == ("feature/x", "insert")
    assert (item["name"], item["state"], item["acting"]) == (
        "feature/x",
        "design",
        "supervisor",  # the lead's step
    )
    assert [s["name"] for s in item["states"]] == ["design", "done"]
    state.delete_session("s")
    gone = stream.until(is_change("runs", "s"))[-1]
    assert (gone.data["op"], gone.data["item"]) == ("delete", None)


def test_a_notes_change_comes_with_its_item_in_the_form_of_the_rest_api(streams):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    run = bare_run()
    state.add_run(run, [])
    stream = streams()
    stream.next()
    after = dataclasses.replace(run, state="done", status=state.ENDED, note="designed")
    step = state.Noted("design", state.REPORT, "supervisor", "ready", "done")
    assert state.update_run(run, after, [], noted=step)
    [note] = state.run_notes("s")
    added = stream.until(is_change("notes", "s"))[-1]
    assert (added.data["key"], added.data["op"]) == (str(note.id), "insert")
    item = added.data["item"]
    del item["created_at"]
    assert item == {
        "id": note.id,
        "run": "feature/x",
        "state": "design",
        "kind": "report",
        "actor": "supervisor",
        "outcome": "ready",
        "target": "done",
        "summary": "designed",
        "body": "",
        "attachments": [],
    }


def test_a_new_artifact_and_its_new_record_come_as_its_item(streams):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(state.Agent("s", "supervisor", "x", "/r", None, None, "idle", "claude"))
    stream = streams()
    stream.next()
    first = artifacts.write("s", "supervisor", "plan", content="v1", title="Plan")
    added = stream.until(is_change("artifacts", "s"))[-1]
    assert added.data["key"] == first.artifact.id
    found = artifacts.of_artifact("s", first.artifact.id)
    assert added.data["item"] == models.artifact_info(*found).model_dump(mode="json")
    latest = artifacts.write("s", "supervisor", "plan", content="v2", summary="two")
    item = stream.until(
        lambda e: (
            is_change("artifacts", "s")(e) and e.data["item"]["latest"]["id"] == latest.record.id
        )
    )[-1].data["item"]
    assert (item["id"], item["latest"]["summary"]) == (first.artifact.id, "two")


def test_a_run_event_comes_with_its_item_in_the_form_of_the_rest_api(streams):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    stream = streams()
    stream.next()
    run = bare_run()
    state.add_run(run, [("lado", state.FLOW_START, "at design")])
    [event] = state.run_events("s")
    added = stream.until(is_change("events", "s"))[-1]
    assert (added.data["key"], added.data["op"]) == (str(event.id), "insert")
    item = added.data["item"]
    del item["created_at"]
    assert item == {
        "id": event.id,
        "run": "feature/x",
        "kind": "flow_start",
        "actor": "lado",
        "detail": "at design",
        "transition": None,
    }


def test_a_marketplaces_change_comes_with_its_item_in_the_form_of_the_rest_api(streams):
    """A marketplace's change has no session; its item is its row and its clone's
    (none yet), never the network."""
    stream = streams()
    stream.next()
    state.add_marketplace("team", "file:///m.git")
    added = stream.until(is_change("marketplaces", ""))[-1]
    item = models.marketplace_info(state.get_marketplace("team")).model_dump(mode="json")
    assert added.data == {
        "kind": "marketplaces",
        "session": "",
        "key": "team",
        "op": "insert",
        "item": item,
    }
    assert item["problem"] == "not fetched yet: update it"
    state.delete_marketplace("team")
    gone = stream.until(is_change("marketplaces", ""))[-1]
    assert (gone.data["op"], gone.data["item"]) == ("delete", None)


def test_an_installed_kits_change_comes_with_its_item_in_the_form_of_the_rest_api(
    streams, tmp_path
):
    """Only the kit's own row and files: no sessions that use it, no marketplace's state."""
    folder = tmp_path / "team"
    (folder / "agents").mkdir(parents=True)
    (folder / "kit.yaml").write_text("name: team\nversion: 1.0.0\ndescription: d\n")
    stream = streams()
    stream.next()
    state.add_kit(state.InstalledKit("team", folder=str(folder), marketplace="gone"))
    added = stream.until(is_change("kits", ""))[-1]
    item = models.installed_kit_info(kits.installed_kit("team")).model_dump(mode="json")
    assert added.data == {
        "kind": "kits",
        "session": "",
        "key": "team",
        "op": "insert",
        "item": item,
    }
    assert (item["kind"], item["version"], item["marketplace"]) == ("folder", "1.0.0", "gone")
    assert not {"users", "marketplace_removed", "installed_from"} & set(item)
    state.delete_kit("team")
    gone = stream.until(is_change("kits", ""))[-1]
    assert (gone.data["op"], gone.data["item"]) == ("delete", None)


def test_a_gates_change_comes_with_its_item_in_the_form_of_the_rest_api(streams, repo, fake_tmux):
    kit = repo / ".lado" / "kits" / "team"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(
        "name: ship\ndescription: d\nstart: plan\nstates:\n"
        "  plan: {agent: supervisor, do: Plan it., produces: [plan], outcomes: {ready: build}}\n"
        "  build: {agent: supervisor, do: Build it., outcomes: {done: check}}\n"
        "  check: {gate: approval, ask: 'Ship it?', reads: [plan], outcomes:"
        " {approved: end, rejected: plan}}\n"
        "  end: {end: true}\n"
    )
    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider="claude")
    stream = streams()
    stream.next()
    runs.start("s", "ship", "Add x", name="x")
    artifacts.write("s", "supervisor", "ship/x/plan", content="step 1")
    runs.advance("s", "supervisor", "ship/x", "ready", "planned")
    runs.advance("s", "supervisor", "ship/x", "done", "the plan", "step 1")
    opened = stream.until(is_change("gates", "s"))[-1]
    item = opened.data["item"]
    assert (opened.data["key"], item["id"], item["note"], item["answer"]) == (
        "1",
        1,
        "the plan",
        None,
    )
    assert item["reads"] == ["ship/x/plan"]
    runs.answer("s", "1", "reject", "replan")
    closed = stream.until(lambda e: is_change("gates", "s")(e) and e.data["item"]["answer"])[-1]
    # A closed gate is still there: its item is replaced, never null.
    item = closed.data["item"]
    assert (closed.data["op"], item["answer"], item["comment"], item["reads"]) == (
        "update",
        "reject",
        "replan",
        None,
    )


def waiting_of(session: str):
    return lambda e: is_change("sessions", session)(e) and e.data["item"]["waiting"]


def test_a_gate_and_a_question_change_what_waits_in_their_session(streams, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    stream = streams()
    stream.next()
    run = bare_run()
    # A loop limit: its item reads no artifacts.
    gate = state.Gate("s", "feature/x", "design", "loop", "Again?", ["continue", "cancel"])
    state.add_run(run, [], gate)
    stream.until(lambda e: waiting_of("s")(e) and e.data["item"]["waiting"]["gates"] == 1)
    runtime.ask_human("s", "supervisor", "Ship?", None, ["yes"])
    stream.until(lambda e: waiting_of("s")(e) and e.data["item"]["waiting"]["questions"] == 1)


def test_a_messages_change_comes_with_its_item_in_the_form_of_the_rest_api(
    streams, repo, fake_tmux
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    stream = streams()
    stream.next()
    runtime.ask_human("s", "supervisor", "Ship?", None, ["yes"])
    [question] = state.list_messages("s")
    asked = stream.until(is_change("messages", "s"))[-1]
    assert asked.data["key"] == str(question.id)
    item = asked.data["item"]
    assert (item["from"], item["kind"], item["question_state"]) == (
        "supervisor",
        "question",
        "open",
    )
    runtime.answer_question("s", question.id, "yes")
    answered = stream.until(
        lambda e: (
            is_change("messages", "s")(e)
            and e.data["key"] == str(question.id)
            and e.data["item"]["question_state"] == "answered"
        )
    )[-1]
    assert answered.data["item"]["answered_by"] == question.id + 1


def test_a_change_of_an_agent_also_updates_its_session(streams, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    stream = streams()
    stream.next()
    runtime.stop_session("s")
    events = stream.quiet(1)
    agents = [e for e in events if e.event == "change" and e.data["kind"] == "agents"]
    sessions = [e for e in events if e.event == "change" and e.data["kind"] == "sessions"]
    assert agents and agents[-1].data["op"] == "delete"
    assert sessions[-1].data["item"]["agents"] == 0
    assert sessions[-1].data["item"]["status"] == "stopped"


def test_an_agents_change_comes_with_its_item_in_the_form_of_the_rest_api(streams, repo, fake_tmux):
    stream = streams()
    stream.next()
    runtime.start_session(str(repo), "s", None, provider="claude")
    state.set_status("s", "supervisor", state.IDLE)
    added = stream.until(
        lambda e: is_change("agents", "s")(e) and e.data["item"]["status"] == "idle"
    )
    assert added[-1].data["key"] == "supervisor"
    item = added[-1].data["item"]
    since, spawned = item.pop("since"), item.pop("spawned_at")
    assert item == {
        "name": "supervisor",
        "role": "supervisor",
        "provider": "claude",
        "status": "idle",
        "run": None,
        "task": None,
        "status_reason": None,
        "branch": None,
        "worktree": None,
    }
    assert (
        spawned
        < since
        == state.status_since("s")["supervisor"].strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    )


def test_a_position_replays_what_came_after_it_once_per_row(streams):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    position = last_change()
    state.add_session(state.Session("t", "/r", None, provider="claude"))
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
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    middle = last_change()
    state.add_session(state.Session("t", "/r", None, provider="claude"))
    stream = streams(after=0, last_id=middle)
    assert stream.next().data["session"] == "t"


@pytest.mark.parametrize("gone", ["trimmed", "ahead"])
def test_a_position_the_journal_no_longer_has_starts_with_reset(streams, gone):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
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
    state.add_session(state.Session("s", "/r", None, provider="claude"))
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
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    assert stream.until(is_change("sessions", "s"))[-1].id == last_change()


def test_a_session_whose_tmux_is_gone_comes_without_an_id(streams, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
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
    runtime.start_session(str(repo), "s", None, provider="claude")
    state.add_session(state.Session("stopped", "/r", None, provider="claude"))
    state.stop_session("stopped")
    position = last_change()
    fake_tmux.append(("kill_session", "s"))  # while no stream was open
    stream = streams(after=position)
    snapshot = stream.next()
    assert (snapshot.event, snapshot.id) == ("change", None)
    # From its creation, in whole seconds, to its latest event: the run time it was found
    # gone with.
    assert snapshot.data["item"].pop("ran_seconds") <= 1
    assert snapshot.data["item"] == {
        "name": "s",
        "repo": str(repo),
        "status": "tmux_gone",
        "agents": 1,
        "waiting": {"gates": 0, "questions": 0, "agents": 0},
        "kits": ["default"],
        "provider": "claude",
        "permission_mode": None,
        "without": [],
        "running_since": None,
        "stopped_at": None,
    }
    assert stream.quiet(0.3) == []  # a stopped session has nothing derived


def test_a_quiet_stream_gets_keep_alive_comments(streams, monkeypatch):
    monkeypatch.setattr(feed, "KEEPALIVE", 0.1)
    stream = streams()
    assert stream.next().event == "reset"
    assert stream.next(comments=True).event == "comment"


def test_the_servers_shutdown_ends_the_open_streams_at_once(running, streams):
    """uvicorn waits for open responses up to its grace, then cuts them: a stream ends when
    the shutdown starts, so a stop with a tab open is as fast as one without."""
    opened = [streams(), streams()]
    for stream in opened:
        assert stream.next().event == "reset"
    started = time.monotonic()
    running.stop()
    took = time.monotonic() - started
    for stream in opened:
        assert stream.closed.wait(1)
        assert stream.error is None  # the response's end, not a cut connection
    assert took < SHUTDOWN_GRACE / 2


def test_a_stream_that_starts_after_the_shutdown_began_ends_at_once():
    hub = feed.Hub(feed.Journal())

    async def read() -> list[str]:
        hub.close()
        return [text async for text in feed.stream(hub, None)]

    assert asyncio.run(asyncio.wait_for(read(), 2)) == [feed.encode("reset", {}, 0)]


def broken_journal(monkeypatch):
    def fail(self, *args):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(feed.Journal, "after", fail)
    monkeypatch.setattr(feed.Journal, "last", fail)


def test_a_journal_that_cannot_be_read_ends_the_streams_and_new_ones_get_503(
    streams, monkeypatch, caplog
):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
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
        state.add_session(state.Session(f"s{round}", "/r", None, provider="claude"))
        assert stream.closed.wait(5), round


def test_the_journal_is_read_only(streams):
    """The server never writes lado.db: not even to trim the journal."""
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    path = state.home() / "lado.db"
    db = sqlite3.connect(path)
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.close()
    before = path.stat().st_mtime_ns, path.read_bytes()
    stream = streams(after=0)
    stream.quiet(0.3)
    assert (path.stat().st_mtime_ns, path.read_bytes()) == before


def run_item(stream, acting: str):
    """The stream's events up to the change of run ship/x whose acting is `acting`."""
    return stream.until(
        lambda e: (
            is_change("runs", "s")(e)
            and e.data["key"] == "ship/x"
            and e.data["item"]["acting"] == acting
        )
    )


def test_any_change_of_the_sessions_agents_updates_who_acts_in_its_open_runs(
    streams, repo, fake_tmux
):
    kit = repo / ".lado" / "kits" / "team"
    (kit / "flows").mkdir(parents=True)
    (kit / "agents").mkdir()
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\n")
    (kit / "agents" / "developer.md").write_text(
        "---\nname: developer\ndescription: d\n---\nYou build.\n"
    )
    (kit / "flows" / "ship.yaml").write_text(
        "name: ship\ndescription: d\nstart: build\nstates:\n"
        "  build: {agent: developer, do: Build it., outcomes: {done: end}}\n"
        "  end: {end: true}\n"
    )
    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider="claude")
    runs.start("s", "ship", "Add x", name="x")
    state.add_run(dataclasses.replace(bare_run(), session="s", name="feature/closed"), [])
    runs.cancel("s", "feature/closed", "not needed")
    stream = streams()
    stream.next()
    runs.spawn_worker("s", "ship/x")
    run_item(stream, "developer")
    [worker] = [a for a in state.list_agents("s") if a.run == "ship/x"]
    runtime.close_worker("s", worker, "test")
    seen = run_item(stream, "developer (not spawned)")
    # Only open runs are updated; a closed one's acting cannot change.
    assert not any(is_change("runs", "s")(e) and e.data["key"] == "feature/closed" for e in seen)


def test_a_run_whose_flow_cannot_be_read_does_not_stop_the_feed(
    streams, repo, fake_tmux, monkeypatch, caplog
):
    monkeypatch.setattr(models, "_logged", set())  # what other tests logged is not counted
    caplog.set_level(logging.WARNING, logger="lado.server")
    kit = repo / ".lado" / "kits" / "team"
    (kit / "flows").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\n")
    (kit / "flows" / "ship.yaml").write_text(
        "name: ship\ndescription: d\nstart: plan\nstates:\n"
        "  plan: {agent: supervisor, do: Plan it., outcomes: {ready: check}}\n"
        "  check: {gate: approval, ask: 'Ship it?', outcomes: {approved: end, rejected: plan}}\n"
        "  end: {end: true}\n"
    )
    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider="claude")
    runs.start("s", "ship", "Add x", name="x")
    runs.start("s", "ship", "Add y", name="y")  # open and active: its acting needs the flow
    runs.advance("s", "supervisor", "ship/x", "ready", "the plan")
    spoil_snapshot("s", "ship/x")
    spoil_snapshot("s", "ship/y")
    stream = streams()
    stream.next()
    # Each change of an agent builds the open runs' items again, in a pass of its own.
    for status in ["busy", "idle"] * feed.FAILED_PASSES:
        state.set_status("s", "supervisor", status)
        seen = stream.until(lambda e: is_change("runs", "s")(e) and e.data["key"] == "ship/y")
        seen += stream.quiet(0.2)  # ship/x of the same batch, if it came after
        items = {e.data["key"]: e.data["item"] for e in seen if is_change("runs", "s")(e)}
        x, y = items["ship/x"], items["ship/y"]
        assert (y["states"], y["acting"], y["status"]) == ([], "", "active")
        assert y["problem"].startswith('run "ship/y": its flow snapshot is not JSON')
        assert (x["states"], x["acting"], x["status"]) == ([], "human", "waiting")
        assert x["problem"].startswith('run "ship/x"')
    with state.connect() as db:  # a change of the gate itself
        db.execute("UPDATE gates SET comment = 'later' WHERE run = 'ship/x'")
    [*_, gate] = stream.until(is_change("gates", "s"))
    assert (gate.data["item"]["reads"], gate.data["item"]["question"]) == (None, "Ship it?")
    assert gate.data["item"]["problem"].startswith('run "ship/x"')
    assert not stream.closed.is_set()
    logged = [r.getMessage() for r in caplog.records if r.name == "lado.server"]
    assert len([m for m in logged if 'run "ship/x"' in m]) == 1, logged
    assert len([m for m in logged if 'run "ship/y"' in m]) == 1, logged
