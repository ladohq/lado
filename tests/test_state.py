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
