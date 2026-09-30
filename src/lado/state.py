"""Persistent state: sessions, agents and their message inbox, in one SQLite file.

Several processes use it at once (the CLI, one MCP server and hooks per agent), so every
call opens its own short-lived connection and SQLite does the locking.
"""

import os
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    name TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    permission_mode TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS agents (
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    cwd TEXT NOT NULL,
    branch TEXT,
    task TEXT,
    status TEXT NOT NULL,
    instance TEXT NOT NULL,  -- new on every launch; hooks of older launches are ignored
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (session, name)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    text TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',  -- pending | sent | delivered
    sent_at REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Agent statuses. Hooks move an agent between them; see lado.hooks.
STARTING = "starting"
BUSY = "busy"
IDLE = "idle"
WAITING = "waiting"  # waiting for the human, e.g. a permission prompt
STOPPED = "stopped"

# Message states. A message typed into an agent's window is only "sent" until the agent's
# UserPromptSubmit hook confirms it; a modal dialog in the TUI can swallow the text.
PENDING = "pending"
SENT = "sent"
DELIVERED = "delivered"


@dataclass
class Agent:
    session: str
    name: str
    role: str
    cwd: str
    branch: str | None
    task: str | None
    status: str
    instance: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class Session:
    name: str
    repo: str
    permission_mode: str | None


@dataclass
class Message:
    id: int
    sender: str
    text: str


def home() -> Path:
    path = Path(os.environ.get("LADO_HOME") or Path.home() / ".lado")
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(home() / "lado.db", timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()
        if version or tables[0]:
            conn.close()
            raise RuntimeError(
                f"{home() / 'lado.db'} has an incompatible schema (version {version}); "
                "stop all LADO sessions and delete it"
            )
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    try:
        yield conn
    finally:
        conn.close()


def add_session(session: Session) -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO sessions (name, repo, permission_mode) VALUES (?, ?, ?)",
            (session.name, session.repo, session.permission_mode),
        )


def get_session(name: str) -> Session | None:
    with connect() as db:
        row = db.execute("SELECT * FROM sessions WHERE name = ?", (name,)).fetchone()
    return Session(row["name"], row["repo"], row["permission_mode"]) if row else None


def delete_session(name: str) -> None:
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE name = ?", (name,))


def list_sessions() -> list[Session]:
    with connect() as db:
        rows = db.execute("SELECT * FROM sessions ORDER BY created_at, rowid").fetchall()
    return [Session(r["name"], r["repo"], r["permission_mode"]) for r in rows]


def add_agent(agent: Agent) -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO agents (session, name, role, cwd, branch, task, status, instance)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                agent.session,
                agent.name,
                agent.role,
                agent.cwd,
                agent.branch,
                agent.task,
                agent.status,
                agent.instance,
            ),
        )


def get_agent(session: str, name: str) -> Agent | None:
    with connect() as db:
        row = db.execute(
            "SELECT * FROM agents WHERE session = ? AND name = ?", (session, name)
        ).fetchone()
    return _agent(row) if row else None


def list_agents(session: str) -> list[Agent]:
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM agents WHERE session = ? ORDER BY created_at, rowid", (session,)
        ).fetchall()
    return [_agent(r) for r in rows]


def set_status(session: str, name: str, status: str) -> None:
    with connect() as db:
        db.execute(
            "UPDATE agents SET status = ? WHERE session = ? AND name = ?", (status, session, name)
        )


def queue_message(session: str, sender: str, recipient: str, text: str) -> int:
    with connect() as db:
        cur = db.execute(
            "INSERT INTO messages (session, sender, recipient, text) VALUES (?, ?, ?, ?)",
            (session, sender, recipient, text),
        )
        return cur.lastrowid or 0


def take_pending(session: str, recipient: str, mark: str) -> list[Message]:
    """Move all pending messages for `recipient` to `mark` and return them, oldest first.

    Runs in one write transaction, so two concurrent callers never get the same message.
    """
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute(
            "SELECT id, sender, text FROM messages"
            " WHERE session = ? AND recipient = ? AND state = ? ORDER BY id",
            (session, recipient, PENDING),
        ).fetchall()
        db.executemany(
            "UPDATE messages SET state = ?, sent_at = ? WHERE id = ?",
            [(mark, time.time(), r["id"]) for r in rows],
        )
        db.execute("COMMIT")
    return [Message(r["id"], r["sender"], r["text"]) for r in rows]


def confirm_sent(session: str, recipient: str, prompt: str) -> None:
    """Mark sent messages whose text is in the prompt the agent just received as delivered."""
    with connect() as db:
        rows = db.execute(
            "SELECT id, text FROM messages WHERE session = ? AND recipient = ? AND state = ?",
            (session, recipient, SENT),
        ).fetchall()
        confirmed = [(DELIVERED, r["id"]) for r in rows if r["text"].strip() in prompt]
        db.executemany("UPDATE messages SET state = ? WHERE id = ?", confirmed)


def requeue_unconfirmed(session: str, recipient: str, older_than: float) -> int:
    """Put sent messages that were never confirmed back in the queue. Returns how many."""
    with connect() as db:
        cur = db.execute(
            "UPDATE messages SET state = ? WHERE session = ? AND recipient = ? AND state = ?"
            " AND sent_at < ?",
            (PENDING, session, recipient, SENT, time.time() - older_than),
        )
        return cur.rowcount


def _agent(row: sqlite3.Row) -> Agent:
    return Agent(
        session=row["session"],
        name=row["name"],
        role=row["role"],
        cwd=row["cwd"],
        branch=row["branch"],
        task=row["task"],
        status=row["status"],
        instance=row["instance"],
    )
