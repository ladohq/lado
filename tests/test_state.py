import dataclasses
import datetime
import re
import sqlite3

import pytest

from lado import state

# The schema of LADO 0.0.2, before agents had a provider.
SCHEMA_V1 = """
CREATE TABLE sessions (
    name TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    permission_mode TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE agents (
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    cwd TEXT NOT NULL,
    branch TEXT,
    task TEXT,
    status TEXT NOT NULL,
    instance TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (session, name)
);
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    text TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    sent_at REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO sessions (name, repo) VALUES ('s', '/repo');
INSERT INTO agents (session, name, role, cwd, status, instance)
    VALUES ('s', 'supervisor', 'supervisor', '/repo', 'idle', 'abc');
PRAGMA user_version = 1;
"""


def test_version_1_database_is_migrated(lado_home):
    lado_home.mkdir()
    sqlite3.connect(lado_home / "lado.db").executescript(SCHEMA_V1)
    assert state.get_session("s").provider == "claude"
    agent = state.get_agent("s", "supervisor")
    assert (agent.provider, agent.instance, agent.status) == ("claude", "abc", "idle")
    with state.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == state.SCHEMA_VERSION


def test_incompatible_database_is_reported(lado_home):
    lado_home.mkdir()
    sqlite3.connect(lado_home / "lado.db").execute("CREATE TABLE sessions (name TEXT)")
    with pytest.raises(RuntimeError, match="incompatible schema"):
        state.list_sessions()


def test_newer_database_is_reported(lado_home):
    lado_home.mkdir()
    sqlite3.connect(lado_home / "lado.db").execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="version 99"):
        state.list_sessions()


def test_version_2_database_gets_kits(lado_home):
    lado_home.mkdir()
    db = sqlite3.connect(lado_home / "lado.db")
    db.executescript(SCHEMA_V1)
    for statement in state.MIGRATIONS[1]:
        db.execute(statement)
    db.execute("PRAGMA user_version = 2")
    db.commit()
    sess = state.get_session("s")
    assert (sess.kits, sess.without) == (["default"], [])


def test_session_kits_round_trip(lado_home):
    state.add_session(state.Session("s", "/r", None, "kilo", ["a", "b"], ["skill:x"]))
    sess = state.get_session("s")
    assert (sess.kits, sess.without) == (["a", "b"], ["skill:x"])


def _schema_v3(lado_home):
    lado_home.mkdir()
    db = sqlite3.connect(lado_home / "lado.db")
    db.executescript(SCHEMA_V1)
    for version in (1, 2):
        for statement in state.MIGRATIONS[version]:
            db.execute(statement)
    db.execute("PRAGMA user_version = 3")
    db.commit()


def test_version_3_database_gets_events(lado_home):
    _schema_v3(lado_home)
    state.add_event("s", "supervisor", "finished", "done")
    [event] = state.list_events("s")
    assert (event.agent, event.kind, event.detail) == ("supervisor", "finished", "done")


def _agent(name="w1", status=state.STARTING):
    return state.Agent("s", name, "worker", "/r", None, None, status)


def test_status_change_is_an_event_once(lado_home):
    state.add_session(state.Session("s", "/r", None))
    state.add_agent(_agent())
    state.set_status("s", "w1", state.BUSY)
    state.set_status("s", "w1", state.BUSY)
    state.set_status("s", "w1", state.IDLE)
    assert [(e.agent, e.kind, e.detail) for e in state.list_events("s")] == [
        ("w1", "status", "busy"),
        ("w1", "status", "idle"),
    ]
    assert state.get_agent("s", "w1").status == state.IDLE


def _event_at(agent, kind, created_at, detail=""):
    with state.connect() as db:
        db.execute(
            "INSERT INTO events (session, agent, kind, detail, created_at) VALUES (?, ?, ?, ?, ?)",
            ("s", agent, kind, detail, created_at),
        )


def test_status_since_is_the_latest_status_event_or_the_spawn(lado_home):
    state.add_session(state.Session("s", "/r", None))
    _event_at("w1", state.SPAWNED, "2026-10-01 10:00:00.000")
    _event_at("w1", state.STATUS, "2026-10-01 10:00:05.250", state.BUSY)
    _event_at("w1", state.STATUS, "2026-10-01 10:07:00.000", state.IDLE)
    _event_at("w1", state.FINISHED, "2026-10-01 11:00:00.000", "merged")
    _event_at("w2", state.SPAWNED, "2026-10-01 10:30:00.000")
    utc = datetime.timezone.utc
    assert state.status_since("s") == {
        "w1": datetime.datetime(2026, 10, 1, 10, 7, tzinfo=utc),
        "w2": datetime.datetime(2026, 10, 1, 10, 30, tzinfo=utc),
    }


def test_status_since_of_a_reused_name_starts_at_its_new_spawn(lado_home):
    state.add_session(state.Session("s", "/r", None))
    _event_at("w1", state.SPAWNED, "2026-10-01 10:00:00.000")
    _event_at("w1", state.STATUS, "2026-10-01 10:05:00.000", state.IDLE)
    _event_at("w1", state.SPAWNED, "2026-10-01 12:00:00.000")
    assert state.status_since("s")["w1"].hour == 12


def test_events_have_sub_second_times_and_go_with_the_session(lado_home):
    state.add_session(state.Session("s", "/r", None))
    state.add_event("s", "w1", "finished", "")
    [event] = state.list_events("s")
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}", event.created_at)
    state.delete_session("s")
    assert state.list_events("s") == []


def _schema_v4(lado_home):
    _schema_v3(lado_home)
    db = sqlite3.connect(lado_home / "lado.db")
    for statement in state.MIGRATIONS[3]:
        db.execute(statement)
    db.execute("PRAGMA user_version = 4")
    db.commit()
    return db


def test_version_4_messages_keep_their_text_as_body(lado_home):
    db = _schema_v4(lado_home)
    db.execute(
        "INSERT INTO messages (session, sender, recipient, text, state)"
        " VALUES ('s', 'w1', 'supervisor', 'done\nall tests pass', 'delivered'),"
        " ('s', 'w1', 'supervisor', 'later', 'pending')"
    )
    db.commit()
    old, queued = state.list_messages("s")
    assert (old.summary, old.body, old.state) == ("", "done\nall tests pass", state.READ)
    assert (queued.summary, queued.body, queued.state) == ("", "later", state.PENDING)
    # Delivered before 0.7, the full text was typed: nothing left to read.
    assert state.read_messages("s", "supervisor") == []


def test_old_message_gets_a_summary_from_its_first_line():
    assert state.Message(1, "w1", "", "done\nmore").title == "done"
    assert state.Message(1, "w1", "", "done \t\nmore").title == "done"
    long = state.Message(1, "w1", "", "x" * 300)
    assert long.title == "x" * 199 + "…"
    assert state.Message(1, "w1", "now", "details").title == "now"


def test_read_messages_returns_unread_bodies_once(lado_home):
    state.add_session(state.Session("s", "/r", None))
    one = state.queue_message("s", "w1", "supervisor", "done", "the report")
    state.queue_message("s", "w1", "supervisor", "no body")
    later = state.queue_message("s", "w2", "supervisor", "blocked", "why")
    state.queue_message("s", "w1", "w2", "not mine", "body")
    state.take_pending("s", "supervisor", state.DELIVERED)
    state.queue_message("s", "w1", "supervisor", "still pending", "body")
    read = state.read_messages("s", "supervisor")
    assert [(m.id, m.sender, m.summary, m.body) for m in read] == [
        (one, "w1", "done", "the report"),
        (later, "w2", "blocked", "why"),
    ]
    assert read[0].created_at
    assert state.read_messages("s", "supervisor") == []
    states = {m.summary: m.state for m in state.list_messages("s")}
    assert states == {
        "done": state.READ,
        "no body": state.DELIVERED,
        "blocked": state.READ,
        "not mine": state.PENDING,
        "still pending": state.PENDING,
    }


def test_version_5_database_gets_runs(lado_home):
    db = _schema_v4(lado_home)
    for statement in state.MIGRATIONS[4]:
        db.execute(statement)
    db.execute("PRAGMA user_version = 5")
    db.commit()
    assert state.get_agent("s", "supervisor").run is None
    assert state.list_runs("s") == []
    state.add_event("s", "supervisor", "finished", "done")
    assert state.list_events("s")[-1].run is None


def _run(name="feature/x", **changes):
    run = state.Run(
        session="s",
        name=name,
        flow="feature",
        snapshot={"name": "feature"},
        kit={"name": "k", "version": "1.0.0", "source": "project: /k"},
        task="add x",
        state="design",
        worktree="/r/.lado/worktrees/s/feature-x",
        branch="lado/s/feature-x",
    )
    return dataclasses.replace(run, **changes)


def test_a_run_is_stored_with_its_start_event(lado_home):
    state.add_session(state.Session("s", "/r", None))
    state.add_run(_run(), [("supervisor", state.FLOW_START, "feature/x: started")])
    run = state.get_run("s", "feature/x")
    assert run == _run(created_at=run.created_at)
    assert (run.status, run.visits, run.reason) == (state.ACTIVE, {}, "")
    [event] = state.list_events("s")
    assert (event.agent, event.kind, event.run) == ("supervisor", state.FLOW_START, "feature/x")
    assert state.run_since("s")["feature/x"] == datetime.datetime.fromisoformat(
        event.created_at
    ).replace(tzinfo=datetime.timezone.utc)


def test_a_run_changes_only_from_the_state_it_was_read_in(lado_home):
    state.add_session(state.Session("s", "/r", None))
    state.add_run(_run(), [("supervisor", state.FLOW_START, "started")])
    before = state.get_run("s", "feature/x")
    after = dataclasses.replace(before, state="build", visits={"build": 1})
    assert state.update_run(before, after, [("w1", state.FLOW, "design -ready-> build")])
    assert state.get_run("s", "feature/x").visits == {"build": 1}
    # Someone else moved it on meanwhile: nothing is written.
    stale = dataclasses.replace(before, state="review")
    assert not state.update_run(before, stale, [("w2", state.FLOW, "lost")])
    assert state.get_run("s", "feature/x").state == "build"
    assert [e.detail for e in state.list_events("s")] == ["started", "design -ready-> build"]


def test_two_self_loops_from_the_same_read_write_once(lado_home):
    state.add_session(state.Session("s", "/r", None))
    state.add_run(_run(visits={"design": 1}), [("supervisor", state.FLOW_START, "started")])
    before = state.get_run("s", "feature/x")
    again = dataclasses.replace(before, visits={"design": 2})
    assert state.update_run(before, again, [("supervisor", state.FLOW, "design -again-> design")])
    assert not state.update_run(before, again, [("w1", state.FLOW, "design -again-> design")])
    assert len(state.list_events("s")) == 2


def test_runs_go_with_their_session(lado_home):
    state.add_session(state.Session("s", "/r", None))
    state.add_run(_run(), [("supervisor", state.FLOW_START, "started")])
    state.add_run(
        _run("feature/y", status=state.ENDED), [("supervisor", state.FLOW_START, "started")]
    )
    assert [r.name for r in state.list_runs("s")] == ["feature/x", "feature/y"]
    assert [r.name for r in state.list_runs("s", open_only=True)] == ["feature/x"]
    state.delete_session("s")
    assert state.list_runs("s") == []
