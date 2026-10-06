"""The change journal (state.changes): SQLite triggers record every insert, update and delete
of the tables the UI shows, whoever writes them."""

import sqlite3

import agent_helpers
import pytest

from lado import state


def journal(after: int = 0) -> list[tuple]:
    with state.connect() as db:
        rows = db.execute(
            "SELECT kind, session, key, op FROM changes WHERE id > ? ORDER BY id", (after,)
        ).fetchall()
    return [tuple(row) for row in rows]


def last() -> int:
    with state.connect() as db:
        return db.execute("SELECT coalesce(max(id), 0) FROM changes").fetchone()[0]


def setup_session(db):
    db.execute("INSERT INTO sessions (name, repo) VALUES ('s', '/r')")


def setup_agent(db):
    setup_session(db)
    db.execute(
        "INSERT INTO agents (session, name, role, cwd, status, instance)"
        " VALUES ('s', 'w1', 'worker', '/r', 'idle', 'i')"
    )


def setup_run(db):
    setup_session(db)
    db.execute(
        "INSERT INTO runs (session, name, flow, snapshot, kit, task, state, status, worktree,"
        " branch) VALUES ('s', 'f/x', 'f', '{}', '{}', 't', 'a', 'active', '/w', 'b')"
    )


# Per table: what it needs first, its insert, an update, its delete, and the change's key.
TABLES = {
    "sessions": (
        lambda db: None,
        "INSERT INTO sessions (name, repo) VALUES ('s', '/r')",
        "UPDATE sessions SET repo = '/other'",
        "DELETE FROM sessions",
        "",
    ),
    "agents": (
        setup_session,
        "INSERT INTO agents (session, name, role, cwd, status, instance)"
        " VALUES ('s', 'w1', 'worker', '/r', 'idle', 'i')",
        "UPDATE agents SET status = 'busy'",
        "DELETE FROM agents",
        "w1",
    ),
    "messages": (
        setup_session,
        "INSERT INTO messages (id, session, sender, recipient) VALUES (7, 's', 'a', 'b')",
        "UPDATE messages SET state = 'sent'",
        "DELETE FROM messages",
        "7",
    ),
    "runs": (
        setup_session,
        "INSERT INTO runs (session, name, flow, snapshot, kit, task, state, status, worktree,"
        " branch) VALUES ('s', 'f/x', 'f', '{}', '{}', 't', 'a', 'active', '/w', 'b')",
        "UPDATE runs SET state = 'b'",
        "DELETE FROM runs",
        "f/x",
    ),
    "gates": (
        setup_run,
        "INSERT INTO gates (id, session, run, state, kind, question, options)"
        " VALUES (3, 's', 'f/x', 'g', 'approval', 'ok?', '[]')",
        "UPDATE gates SET answer = 'approved'",
        "DELETE FROM gates",
        "3",
    ),
    "notes": (
        setup_run,
        "INSERT INTO notes (id, session, run, state, kind, summary)"
        " VALUES (5, 's', 'f/x', 'a', 'report', 'done')",
        "UPDATE notes SET body = 'more'",
        "DELETE FROM notes",
        "5",
    ),
}


@pytest.mark.parametrize("table", TABLES)
def test_each_write_of_a_table_is_one_change(lado_home, table):
    setup, insert, update, delete, key = TABLES[table]
    with state.connect() as db:
        setup(db)
    for statement, op in ((insert, "insert"), (update, "update"), (delete, "delete")):
        before = last()
        with state.connect() as db:
            db.execute(statement)
        assert journal(before) == [(table, "s", key, op)], statement


def test_each_write_of_a_marketplace_is_one_change_of_no_session(lado_home):
    for statement, op in (
        ("INSERT INTO marketplaces (name, url) VALUES ('team', 'file:///m.git')", "insert"),
        ("UPDATE marketplaces SET enabled = 0 WHERE name = 'team'", "update"),
        ("DELETE FROM marketplaces WHERE name = 'team'", "delete"),
    ):
        before = last()
        with state.connect() as db:
            db.execute(statement)
        assert journal(before) == [("marketplaces", "", "team", op)], statement


def test_each_write_of_an_installed_kit_is_one_change_of_no_session(lado_home):
    for statement, op in (
        ("INSERT INTO kits (name, folder) VALUES ('team', '/dev/team')", "insert"),
        ("UPDATE kits SET updated_at = datetime('now') WHERE name = 'team'", "update"),
        ("DELETE FROM kits WHERE name = 'team'", "delete"),
    ):
        before = last()
        with state.connect() as db:
            db.execute(statement)
        assert journal(before) == [("kits", "", "team", op)], statement


def test_a_change_of_any_agent_column_but_seen_at_is_recorded(lado_home):
    with state.connect() as db:
        setup_agent(db)
        columns = [row["name"] for row in db.execute("PRAGMA table_info(agents)")]
    assert "seen_at" in columns
    for column in columns:
        if column in ("session", "name", "seen_at"):
            continue  # the key: a change of it is a delete and an insert for the UI
        before = last()
        with state.connect() as db:
            db.execute(f"UPDATE agents SET {column} = 'changed-' || coalesce({column}, '')")
        assert journal(before) == [("agents", "s", "w1", "update")], column


def test_a_column_added_to_agents_later_is_recorded_without_a_new_trigger(lado_home):
    """The trigger is kept in lado.db as it was made: it must not list the columns."""
    with state.connect() as db:
        setup_agent(db)
        db.execute("ALTER TABLE agents ADD COLUMN later TEXT")
    before = last()
    with state.connect() as db:
        db.execute("UPDATE agents SET later = 'x'")
    assert journal(before) == [("agents", "s", "w1", "update")]


def test_a_hook_that_only_marks_the_agent_seen_is_not_a_change(lado_home):
    with state.connect() as db:
        setup_agent(db)
    before = last()
    state.seen("s", "w1")
    assert journal(before) == []
    assert state.get_agent("s", "w1").seen_at > 0


def test_a_hook_after_a_failure_is_a_change_of_the_agent(lado_home):
    """Why the agent waits (failed messages after its latest hook) changes with seen_at
    alone when a message it saw stays failed: the UI hears of it as a change of the agent."""
    with state.connect() as db:
        setup_agent(db)
        db.execute(
            "INSERT INTO messages (session, sender, recipient, summary, state, sent_at,"
            " failed_at) VALUES ('s', 'w2', 'w1', 'report', ?, 1, 2)",
            (state.FAILED,),
        )
        db.execute("UPDATE agents SET seen_at = 1.5")  # a hook after the paste, before it failed
    state.set_status("s", "w1", state.WAITING)
    before = last()
    state.seen("s", "w1")  # its hooks ran after the paste: it stays failed, unconfirmed
    assert journal(before) == [("agents", "s", "w1", "update")]
    before = last()
    state.seen("s", "w1")  # the failure is older than its latest hook now
    assert journal(before) == []


def test_deleting_a_session_records_what_went_with_it(lado_home):
    with state.connect() as db:
        setup_agent(db)
    before = last()
    state.delete_session("s")
    assert journal(before) == [("agents", "s", "w1", "delete"), ("sessions", "s", "", "delete")]


def test_the_journal_keeps_the_latest_changes_only(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    first = last()
    with state.connect() as db:  # the journal's numbers jump past CHANGES_KEPT
        db.execute(
            "INSERT INTO changes (id, kind, session, key, op) VALUES (?, 'x', 's', '', 'insert')",
            (first + state.CHANGES_KEPT,),
        )
        ids = [row[0] for row in db.execute("SELECT id FROM changes")]
    assert ids == [first + state.CHANGES_KEPT]


def test_version_11_has_no_journal_and_migrates_to_one(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    agent_helpers.schema_before(13)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert state.MIGRATIONS[11] == state.JOURNAL
    for (name,) in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'changes_%'"
    ).fetchall():
        db.execute(f"DROP TRIGGER {name}")
    db.execute("DROP TABLE changes")
    db.execute("PRAGMA user_version = 11")
    db.commit()
    names = {row[0] for row in db.execute("SELECT name FROM sqlite_master")}
    db.close()
    assert "changes" not in names and not any(n.startswith("changes_") for n in names)
    state.migrate()
    state.add_session(state.Session("t", "/r", None, provider="claude"))
    assert journal() == [("sessions", "t", "", "insert")]


def test_a_run_event_is_a_change_and_an_agent_event_is_none(lado_home):
    """A status event would double the journal: the agent's own row tells it already."""
    with state.connect() as db:
        setup_agent(db)
    before = last()
    state.add_event("s", "w1", state.STATUS, "busy")
    state.add_event("s", "lado", state.FLOW, "a -done-> b", run="f/x")
    with state.connect() as db:
        event_id = db.execute("SELECT max(id) FROM events").fetchone()[0]
        db.execute("UPDATE events SET detail = 'changed'")
        db.execute("DELETE FROM events")
    assert journal(before) == [("events", "s", str(event_id), "insert")]


def test_the_step_that_made_the_journal_keeps_its_six_tables():
    """A table journaled later comes with a step of its own, never into step 11."""
    tables = {s.split(" ON ")[1].split()[0] for s in state.MIGRATIONS[11] if "TRIGGER" in s}
    assert tables == {"changes", "sessions", "agents", "messages", "runs", "gates", "notes"}
    assert not any("events" in s for s in state.MIGRATIONS[11])


def test_version_13_journals_no_events_and_migrates_to_journal_run_events(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    agent_helpers.schema_before(14)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    names = {row[0] for row in db.execute("SELECT name FROM sqlite_master")}
    db.close()
    assert not any(n.startswith("changes_events") for n in names)
    state.migrate()
    state.add_event("s", "lado", state.FLOW_START, "", run="f/x")
    assert journal()[-1][:2] == ("events", "s")
