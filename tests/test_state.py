import dataclasses
import datetime
import re
import sqlite3

import agent_helpers
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
    with pytest.raises(RuntimeError, match="version 99") as refused:
        state.list_sessions()
    message = str(refused.value)
    assert "newer LADO" in message
    assert "upgrade LADO" in message
    assert "delete" not in message


def _database():
    """The bytes of lado.db with its WAL folded in, to tell whether anything was written."""
    path = state.home() / "lado.db"
    db = sqlite3.connect(path)  # not state.connect(): it would migrate
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.close()
    return path.read_bytes()


def test_no_pending_migration_without_a_database(lado_home):
    assert state.pending_migration() is None
    assert not (lado_home / "lado.db").exists()


def test_no_pending_migration_at_the_current_version(lado_home):
    state.add_session(state.Session("s", "/r", None))
    assert state.pending_migration() is None


def test_pending_migration_names_the_sessions_not_stopped(lado_home):
    for name in ("b", "a", "gone"):
        state.add_session(state.Session(name, "/r", None))
    state.stop_session("gone")
    agent_helpers.previous_schema()
    before = _database()
    assert state.pending_migration() == (state.SCHEMA_VERSION - 1, ["a", "b"])
    assert (lado_home / "lado.db").read_bytes() == before


def test_pending_migration_before_sessions_could_stop(lado_home):
    """Before version 8 a session had no stopped_at: each one may be running."""
    lado_home.mkdir()
    sqlite3.connect(lado_home / "lado.db").executescript(SCHEMA_V1)
    assert state.pending_migration() == (1, ["s"])


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


def test_version_6_database_gets_gates(lado_home):
    db = _schema_v4(lado_home)
    for version in (4, 5):
        for statement in state.MIGRATIONS[version]:
            db.execute(statement)
    db.execute("PRAGMA user_version = 6")
    db.commit()
    assert state.open_gates() == []
    assert state.get_gate(1) is None


def _gate(**changes):
    gate = state.Gate(
        session="s",
        run="feature/x",
        state="design_ok",
        kind="approval",
        question="Approve the design?",
        options=["approve", "reject"],
        note="design ready",
        note_body="see plan.md",
    )
    return dataclasses.replace(gate, **changes)


def _waiting(lado_home):
    """A run that waits at an open gate."""
    state.add_session(state.Session("s", "/r", None))
    state.add_run(_run(), [("supervisor", state.FLOW_START, "started")])
    before = state.get_run("s", "feature/x")
    after = dataclasses.replace(before, state="design_ok", status=state.WAITING)
    gate = _gate()
    assert state.update_run(before, after, [("supervisor", state.FLOW, "go")], opens=gate)
    return after, gate


def test_a_gate_opens_with_the_run_that_waits_at_it(lado_home):
    run, gate = _waiting(lado_home)
    assert gate.id
    stored = state.get_gate(gate.id)
    assert stored == dataclasses.replace(gate, created_at=stored.created_at)
    assert (stored.answer, stored.answered_at) == (None, None)
    assert state.open_gates() == [stored]
    assert state.open_gates("other") == []
    assert state.open_gate("s", "feature/x") == stored
    events = [(e.agent, e.kind, e.detail, e.run) for e in state.list_events("s")][1:]
    assert events == [
        ("supervisor", state.FLOW, "go", "feature/x"),
        (
            "lado",
            state.GATE_OPEN,
            f"#{gate.id} approval at design_ok: Approve the design?",
            "feature/x",
        ),
    ]


def test_a_run_has_one_open_gate(lado_home):
    run, _ = _waiting(lado_home)
    again = dataclasses.replace(run, visits={"design_ok": 2})
    with pytest.raises(sqlite3.IntegrityError):
        state.update_run(run, again, [], opens=_gate())
    assert state.get_run("s", "feature/x").visits == run.visits  # rolled back
    assert len(state.open_gates()) == 1


def test_the_gate_closes_with_the_runs_next_write(lado_home):
    run, gate = _waiting(lado_home)
    after = dataclasses.replace(run, state="design", status=state.ACTIVE)
    stale = dataclasses.replace(run, state="other")
    answer = ("human", "approve", "fine", gate.id)
    assert not state.update_run(stale, after, [], closes=answer)
    assert state.get_gate(gate.id).answer is None
    # An answer to a gate that is not the open one writes nothing.
    assert not state.update_run(run, after, [], closes=("human", "approve", "", gate.id + 1))
    assert state.get_run("s", "feature/x").state == "design_ok"
    assert state.update_run(run, after, [("human", state.FLOW, "on")], closes=answer)
    closed = state.get_gate(gate.id)
    assert (closed.answer, closed.comment, closed.answered_by) == ("approve", "fine", "human")
    assert closed.answered_at
    assert state.open_gates() == []
    assert state.open_gate("s", "feature/x") is None
    events = [(e.agent, e.kind, e.detail) for e in state.list_events("s")][-2:]
    assert events == [
        ("human", state.GATE_ANSWER, f"#{gate.id} approve: fine"),
        ("human", state.FLOW, "on"),
    ]
    # Answering it again writes nothing; an override closes whatever is open, if anything.
    again = dataclasses.replace(after, state="design_ok", status=state.WAITING)
    assert not state.update_run(after, again, [], closes=answer)
    assert state.update_run(after, again, [], closes=("human", "overridden", "x", None))


def test_a_new_run_can_start_at_a_gate_and_gates_go_with_their_session(lado_home):
    state.add_session(state.Session("s", "/r", None))
    gate = _gate()
    state.add_run(_run(status=state.WAITING), [("supervisor", state.FLOW_START, "x")], gate)
    assert state.open_gates() == [state.get_gate(gate.id)]
    state.delete_session("s")
    assert state.get_gate(gate.id) is None


def test_version_7_database_gets_stopped_sessions(lado_home):
    db = _schema_v4(lado_home)
    for version in (4, 5, 6):
        for statement in state.MIGRATIONS[version]:
            db.execute(statement)
    db.execute("PRAGMA user_version = 7")
    db.commit()
    assert state.get_session("s").stopped_at is None


def test_version_8_database_gets_the_language_of_runs(lado_home):
    db = _schema_v4(lado_home)
    for version in (4, 5, 6, 7):
        for statement in state.MIGRATIONS[version]:
            db.execute(statement)
    db.execute(
        "INSERT INTO runs (session, name, flow, snapshot, kit, task, state, status, worktree,"
        " branch) VALUES ('s', 'feature/x', 'feature', '{}', '{}', 'x', 'design', 'active',"
        " '/w', 'b')"
    )
    db.execute("PRAGMA user_version = 8")
    db.commit()
    assert state.get_run("s", "feature/x").language == ""


def test_version_9_database_gets_message_attempts_and_when_agents_were_seen(lado_home):
    db = _schema_v4(lado_home)
    for version in (4, 5, 6, 7, 8):
        for statement in state.MIGRATIONS[version]:
            db.execute(statement)
    db.execute(
        "INSERT INTO messages (session, sender, recipient, summary, body, state, sent_at)"
        " VALUES ('s', 'w1', 'supervisor', 'hi', '', 'sent', 5.0)"
    )
    db.execute("PRAGMA user_version = 9")
    db.commit()
    [message] = state.list_messages("s")
    assert (message.state, message.attempts, message.sent_at) == (state.SENT, 0, 5.0)
    assert state.get_agent("s", "supervisor").seen_at == 0
    assert state.failed_counts("s") == {}  # reads messages.failed_at


def test_a_run_keeps_the_language_of_the_human(lado_home):
    state.add_session(state.Session("s", "/r", None))
    state.add_run(_run(language="ru"), [("supervisor", state.FLOW_START, "started")])
    assert state.get_run("s", "feature/x").language == "ru"


def test_version_10_database_keeps_the_notes_of_runs(lado_home):
    db = _schema_v4(lado_home)
    for version in range(4, 10):
        for statement in state.MIGRATIONS[version]:
            db.execute(statement)
    db.execute(
        "INSERT INTO runs (session, name, flow, snapshot, kit, task, state, status, worktree,"
        " branch, note) VALUES ('s', 'feature/x', 'feature', '{}', '{}', 'x', 'implement',"
        " 'active', '/w', 'b', 'designed')"
    )
    db.execute("PRAGMA user_version = 10")
    db.commit()
    # A run from before keeps its previous note; no earlier note was kept.
    assert state.get_run("s", "feature/x").note == "designed"
    assert state.latest_notes("s", "feature/x") == {}


def _moved(run, to, note, body="", kind=state.REPORT):
    """Move `run` to state `to` with the note reported from where it was."""
    after = dataclasses.replace(run, state=to, note=note, note_body=body)
    assert state.update_run(run, after, [], noted=(run.state, kind))
    return after


def test_every_note_is_kept_with_the_state_it_was_reported_from(lado_home):
    state.add_session(state.Session("s", "/r", None))
    run = _run()
    state.add_run(run, [("supervisor", state.FLOW_START, "started")])
    run = _moved(run, "implement", "first design", "plan A")
    run = _moved(run, "design", "back to design")
    run = _moved(run, "implement", "second design", "plan B")
    # A write that moves nothing keeps no note.
    stale = dataclasses.replace(run, state="other")
    lost = dataclasses.replace(run, note="lost")
    assert not state.update_run(stale, lost, [], noted=("other", state.REPORT))
    notes = state.latest_notes("s", "feature/x")
    assert set(notes) == {"design", "implement"}
    design = notes["design"]
    assert (design.state, design.summary, design.body) == ("design", "second design", "plan B")
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}", design.created_at)
    assert notes["implement"].summary == "back to design"
    # The notes go with their session.
    state.delete_session("s")
    assert state.latest_notes("s", "feature/x") == {}


def test_notes_belong_to_their_run(lado_home):
    state.add_session(state.Session("s", "/r", None))
    for name in ("feature/x", "feature/y"):
        state.add_run(_run(name), [("supervisor", state.FLOW_START, "started")])
    _moved(_run("feature/x"), "implement", "x designed")
    assert state.latest_notes("s", "feature/y") == {}


def test_the_humans_override_is_kept_but_never_taken_for_a_states_report(lado_home):
    state.add_session(state.Session("s", "/r", None))
    run = _run()
    state.add_run(run, [("supervisor", state.FLOW_START, "started")])
    run = _moved(run, "implement", "the design")
    run = _moved(run, "design", "back to design")
    _moved(run, "implement", "set by the human: old design is fine", kind=state.OVERRIDE)
    assert state.latest_notes("s", "feature/x")["design"].summary == "the design"
    with state.connect() as db:
        kept = db.execute("SELECT state, kind, summary FROM notes ORDER BY id").fetchall()
    assert [tuple(row) for row in kept][-1] == (
        "design",
        state.OVERRIDE,
        "set by the human: old design is fine",
    )


def test_stopping_a_session_keeps_its_history_and_drops_what_was_not_delivered(lado_home):
    state.add_session(state.Session("s", "/r", None))
    state.add_agent(_agent("supervisor", state.IDLE))
    state.add_agent(_agent("w1", state.BUSY))
    state.add_run(_run(), [("supervisor", state.FLOW_START, "started")])
    state.queue_message("s", "w1", "supervisor", "read", "its body")
    state.take_pending("s", "supervisor", state.DELIVERED)
    state.read_messages("s", "supervisor")
    # A body delivered but never read must not reach a new agent of the same name.
    for recipient, mark, body in (
        ("w1", state.DELIVERED, ""),
        ("w1", state.DELIVERED, "unread"),
        ("supervisor", state.SENT, ""),
        ("w1", None, ""),
    ):
        state.queue_message("s", "lado", recipient, "hi", body)
        if mark:
            state.take_pending("s", recipient, mark)
    agents, dropped = state.stop_session("s")
    assert [a.name for a in agents] == ["supervisor", "w1"]
    assert dropped == 3
    assert state.get_session("s").stopped_at
    assert state.list_agents("s") == []
    assert [m.state for m in state.list_messages("s")] == [
        state.READ,
        state.DELIVERED,
        state.DROPPED,
        state.DROPPED,
        state.DROPPED,
    ]
    assert state.get_run("s", "feature/x").status == state.ACTIVE
    events = [(e.agent, e.kind, e.detail) for e in state.list_events("s")][1:]
    assert events == [
        ("supervisor", state.STATUS, state.STOPPED),
        ("w1", state.STATUS, state.STOPPED),
        ("lado", state.SESSION_STOP, "3 messages dropped"),
    ]


def test_a_resumed_session_gets_its_new_settings(lado_home):
    state.add_session(state.Session("s", "/r", None))
    state.stop_session("s")
    state.resume_session(state.Session("s", "/r", "plan", "kilo", ["team"], ["skill:x"]), "kits")
    sess = state.get_session("s")
    assert sess == state.Session("s", "/r", "plan", "kilo", ["team"], ["skill:x"])
    last = state.list_events("s")[-1]
    assert (last.agent, last.kind, last.detail) == ("lado", state.SESSION_RESUME, "kits")


def test_version_12_messages_become_plain_messages_in_version_13(lado_home):
    state.add_session(state.Session("s", "/r", None))
    state.queue_message("s", "w1", "supervisor", "hi", "body")
    agent_helpers.schema_before(13)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it would migrate
    columns = {row[1] for row in db.execute("PRAGMA table_info(messages)")}
    db.close()
    assert "kind" not in columns and "reply_state" not in columns
    [message] = state.list_messages("s")  # migrates
    assert (message.kind, message.choices, message.question_state) == (state.MESSAGE, None, None)
    assert (message.reply_to, message.choice, message.reply_state) == (None, None, None)
