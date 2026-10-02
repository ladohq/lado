"""Persistent state: sessions, agents, their message inbox and events, in one SQLite file.

Several processes use it at once (the CLI, one MCP server and hooks per agent), so every
call opens its own short-lived connection and SQLite does the locking.
"""

import datetime
import json
import os
import sqlite3
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

SCHEMA_VERSION = 11

# What happened to an agent, for `lado log`. Before version 6 events had no run column.
EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    agent TEXT NOT NULL,
    kind TEXT NOT NULL,  -- spawned | status | finished | flow_start | flow | ...
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))  -- UTC
)"""
EVENTS_RUN = "ALTER TABLE events ADD COLUMN run TEXT"  # the flow run the event is about
AGENTS_RUN = "ALTER TABLE agents ADD COLUMN run TEXT"  # the flow run a worker works for

# Flow runs (lado.runs). Their transitions are events with the run's name.
RUNS = """
CREATE TABLE IF NOT EXISTS runs (
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    name TEXT NOT NULL,  -- <flow>/<slug>
    flow TEXT NOT NULL,
    snapshot TEXT NOT NULL,  -- JSON: the flow as it was when the run started
    kit TEXT NOT NULL,  -- JSON: name, version and source of the flow's kit
    task TEXT NOT NULL,
    state TEXT NOT NULL,
    visits TEXT NOT NULL DEFAULT '{}',  -- JSON: state -> times entered
    status TEXT NOT NULL,  -- active | waiting | ended | cancelled
    reason TEXT NOT NULL DEFAULT '',  -- why it waits for the human, or was cancelled
    note TEXT NOT NULL DEFAULT '',  -- the previous step's note: one line
    note_body TEXT NOT NULL DEFAULT '',
    worktree TEXT NOT NULL,
    branch TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    PRIMARY KEY (session, name)
)"""

# Questions to the human from waiting runs (lado.runs). A run has at most one open gate.
GATES = """
CREATE TABLE IF NOT EXISTS gates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    run TEXT NOT NULL,
    state TEXT NOT NULL,  -- the gate state, or the state a loop limit kept the run out of
    kind TEXT NOT NULL,  -- approval | choice | loop
    question TEXT NOT NULL,
    options TEXT NOT NULL,  -- JSON list of the answers the human can give
    note TEXT NOT NULL DEFAULT '',  -- the note of the step that led here
    note_body TEXT NOT NULL DEFAULT '',
    answer TEXT,  -- an option, or how the gate was closed otherwise; NULL while open
    comment TEXT NOT NULL DEFAULT '',
    answered_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    answered_at TEXT
)"""
GATES_OPEN = (
    "CREATE UNIQUE INDEX IF NOT EXISTS gates_open ON gates (session, run) WHERE answer IS NULL"
)
# When `lado stop` stopped the session; NULL while it runs. A stopped session keeps its
# history and open runs until `lado start` resumes it or `lado forget` drops it.
SESSIONS_STOPPED = "ALTER TABLE sessions ADD COLUMN stopped_at TEXT"
# The language the human writes in, e.g. "ru": the run's notes are written in it. '' for
# none given.
RUNS_LANGUAGE = "ALTER TABLE runs ADD COLUMN language TEXT NOT NULL DEFAULT ''"
# How often a message was typed into its recipient's window (lado.runtime.sweep).
MESSAGES_ATTEMPTS = "ALTER TABLE messages ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"
MESSAGES_FAILED = "ALTER TABLE messages ADD COLUMN failed_at REAL"  # when sweep gave it up
# When the agent's latest hook ran (time.time()); 0 for none yet.
AGENTS_SEEN = "ALTER TABLE agents ADD COLUMN seen_at REAL NOT NULL DEFAULT 0"
# Every note a run's step reported, with the state it was reported from: a state's
# `needs` (lado.flows) gets the latest reports. Kept from version 11 on.
NOTES = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    run TEXT NOT NULL,
    state TEXT NOT NULL,  -- where the run was, or the gate a loop limit asked at
    kind TEXT NOT NULL,  -- report | override
    summary TEXT NOT NULL,  -- one line
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))  -- UTC
)"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    name TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    permission_mode TEXT,
    provider TEXT NOT NULL DEFAULT 'claude',  -- default for the session's agents
    kits TEXT NOT NULL DEFAULT '["default"]',  -- JSON list of kit names
    switched_off TEXT NOT NULL DEFAULT '[]',  -- JSON list of "agent:x", "skill:y", "mcp:z"
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS agents (
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT NOT NULL,  -- the agent's name in the session's kits
    cwd TEXT NOT NULL,
    branch TEXT,
    task TEXT,
    status TEXT NOT NULL,
    instance TEXT NOT NULL,  -- new on every launch; hooks of older launches are ignored
    provider TEXT NOT NULL DEFAULT 'claude',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (session, name)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',  -- one line; '' in messages from before version 5
    body TEXT NOT NULL DEFAULT '',  -- the full text, read with read_messages; '' for none
    state TEXT NOT NULL DEFAULT 'pending',  -- pending | sent | delivered | read | dropped | failed
    sent_at REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
SCHEMA += (
    ";\n".join(
        [
            EVENTS,
            EVENTS_RUN,
            AGENTS_RUN,
            RUNS,
            GATES,
            GATES_OPEN,
            SESSIONS_STOPPED,
            RUNS_LANGUAGE,
            MESSAGES_ATTEMPTS,
            MESSAGES_FAILED,
            AGENTS_SEEN,
            NOTES,
        ]
    )
    + ";\n"
)

SUMMARY_LIMIT = 200  # characters in a message summary

# Statements that upgrade a database from the version in the key to the next one.
MIGRATIONS = {
    1: [
        "ALTER TABLE sessions ADD COLUMN provider TEXT NOT NULL DEFAULT 'claude'",
        "ALTER TABLE agents ADD COLUMN provider TEXT NOT NULL DEFAULT 'claude'",
    ],
    2: [
        """ALTER TABLE sessions ADD COLUMN kits TEXT NOT NULL DEFAULT '["default"]'""",
        "ALTER TABLE sessions ADD COLUMN switched_off TEXT NOT NULL DEFAULT '[]'",
    ],
    3: [EVENTS],
    # Before version 5 a message was one text, typed in full: a delivered one was read.
    4: [
        "ALTER TABLE messages RENAME COLUMN text TO body",
        "ALTER TABLE messages ADD COLUMN summary TEXT NOT NULL DEFAULT ''",
        "UPDATE messages SET state = 'read' WHERE state = 'delivered'",
    ],
    5: [AGENTS_RUN, EVENTS_RUN, RUNS],
    6: [GATES, GATES_OPEN],
    7: [SESSIONS_STOPPED],
    8: [RUNS_LANGUAGE],
    9: [MESSAGES_ATTEMPTS, MESSAGES_FAILED, AGENTS_SEEN],
    10: [NOTES],
}

# Agent statuses. Hooks move an agent between them; see lado.hooks.
STARTING = "starting"
BUSY = "busy"
IDLE = "idle"
WAITING = "waiting"  # waiting for the human, e.g. a permission prompt
STOPPED = "stopped"

# Message states. A message typed into an agent's window is only "sent" until the agent's
# prompt-submit hook confirms it; a modal dialog in the TUI can swallow the text.
PENDING = "pending"
SENT = "sent"
DELIVERED = "delivered"
READ = "read"  # its recipient got the body with read_messages
DROPPED = "dropped"  # its recipient was finished or stopped before it got (or read) it
FAILED = "failed"  # typed again and again, never confirmed (lado.runtime.sweep)
# What an agent has not received yet: messages not delivered, and bodies not read. When the
# agent is finished or stopped, they are dropped: a new agent of the same name starts fresh.
UNRECEIVED = "(state IN (?, ?, ?) OR (state = ? AND body != ''))"
UNRECEIVED_ARGS = (PENDING, SENT, FAILED, DELIVERED)

# Event kinds.
SPAWNED = "spawned"  # detail: "role <role>, provider <provider>"
STATUS = "status"  # detail: the new status
FINISHED = "finished"  # a worker was ended; detail: "merged" or "discarded"
MCP_READY = "mcp_ready"  # the agent's CLI listed LADO's MCP tools; detail: the launch (instance)
# Flow run events (lado.runs); their run column names the run.
FLOW_START = "flow_start"
FLOW = "flow"  # a transition; detail: "<from> -<outcome>-> <to>"
FLOW_END = "flow_end"
FLOW_CANCEL = "flow_cancel"
FLOW_SET = "flow_set"  # the human forced the run into a state
GATE_OPEN = "gate_open"  # the run waits for the human; detail: "#<id> <kind> at <state>: ..."
GATE_ANSWER = "gate_answer"  # the gate closed; detail: "#<id> <answer>[: <comment>]"
# Session events, by LADO.
SESSION_STOP = "session_stop"  # detail: what was dropped
SESSION_RESUME = "session_resume"  # detail: what changed

LADO = "lado"  # the sender of LADO's own messages and the actor of its own events

# Run statuses.
ACTIVE = "active"
WAITING = "waiting"  # for the human: a gate or a loop limit
ENDED = "ended"
CANCELLED = "cancelled"
OPEN = (ACTIVE, WAITING)

# Note kinds. A report is a state's own: a work state's flow_advance, the answer at an
# approval or choice gate. An override is the human's past the flow (flow-set's reason, an
# answer at a loop limit): kept, but never taken for the state's report.
REPORT = "report"
OVERRIDE = "override"


@dataclass
class Agent:
    session: str
    name: str
    role: str
    cwd: str
    branch: str | None
    task: str | None
    status: str
    provider: str = "claude"
    instance: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    run: str | None = None  # the flow run it works for
    seen_at: float = 0  # when its latest hook ran (time.time()); 0 for none yet


@dataclass
class Session:
    name: str
    repo: str
    permission_mode: str | None
    provider: str = "claude"
    kits: list[str] = field(default_factory=lambda: ["default"])
    without: list[str] = field(default_factory=list)  # switched-off agents, skills, MCP
    stopped_at: str | None = None  # UTC; None while it runs


@dataclass
class Message:
    id: int
    sender: str
    summary: str
    body: str = ""
    recipient: str = ""
    state: str = ""
    created_at: str = ""  # UTC, "YYYY-MM-DD HH:MM:SS.SSS"; older rows have whole seconds
    attempts: int = 0  # how often it was typed into the recipient's window
    sent_at: float | None = None  # when it was last typed or handed over (time.time())

    @property
    def title(self) -> str:
        """The summary; for a message from before summaries, the first line of its body."""
        if self.summary:
            return self.summary
        first = self.body.strip().split("\n", 1)[0].rstrip()
        return first if len(first) <= SUMMARY_LIMIT else first[: SUMMARY_LIMIT - 1] + "…"


@dataclass
class Event:
    id: int
    agent: str
    kind: str
    detail: str
    created_at: str  # UTC, "YYYY-MM-DD HH:MM:SS.SSS"
    run: str | None = None


@dataclass
class Run:
    """A flow run: one task going through the states of a flow (lado.runs)."""

    session: str
    name: str  # <flow>/<slug>
    flow: str
    snapshot: dict  # the flow as it was at the start
    kit: dict  # name, version, source of the flow's kit
    task: str
    state: str
    worktree: str
    branch: str
    visits: dict[str, int] = field(default_factory=dict)
    status: str = ACTIVE
    reason: str = ""  # why it waits for the human, or was cancelled
    note: str = ""  # the previous step's note, one line
    note_body: str = ""
    language: str = ""  # the human's language, for the notes; "" for none given
    created_at: str = ""


@dataclass
class Gate:
    """A question to the human from a waiting run; open while `answer` is None."""

    session: str
    run: str
    state: str  # the gate state, or the state a loop limit kept the run out of
    kind: str  # approval | choice | loop
    question: str
    options: list[str]
    note: str = ""  # the note of the step that led here
    note_body: str = ""
    id: int = 0
    answer: str | None = None  # an option, or how it was closed otherwise
    comment: str = ""
    answered_by: str = ""
    created_at: str = ""
    answered_at: str | None = None


@dataclass(frozen=True)
class Note:
    """A note a run's step reported, kept with the state it was reported from."""

    state: str
    summary: str
    body: str
    created_at: str
    id: int = 0


# Who closes a run's open gate, the answer, a comment, and the id of the gate that must be
# the open one (an answer), or None to close whichever is open, if any (an override).
Close = tuple[str, str, str, int | None]


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
    if version in MIGRATIONS:
        version = _migrate(conn)
    if version != SCHEMA_VERSION:
        tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()
        if version > SCHEMA_VERSION:
            conn.close()
            raise RuntimeError(
                f"{home() / 'lado.db'} has schema version {version}, made by a newer LADO "
                f"(this one knows up to {SCHEMA_VERSION}); upgrade LADO, and restart a "
                "session that runs on this version with `lado stop` and `lado start`"
            )
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


def schema_version() -> int | None:
    """lado.db's schema version, None when there is no lado.db. Reads only: unlike
    connect(), it never migrates."""
    path = home() / "lado.db"
    if not path.exists():
        return None
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=10)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def pending_migration() -> tuple[int, list[str]] | None:
    """When connect() would migrate lado.db: its schema version and the sessions it does
    not mark stopped. Reads only: creates and changes nothing."""
    path = home() / "lado.db"
    if not path.exists():
        return None
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=10)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in MIGRATIONS:
            return None
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
        # Before version 8 a session could not be stopped.
        where = " WHERE stopped_at IS NULL" if "stopped_at" in columns else ""
        rows = conn.execute(f"SELECT name FROM sessions{where} ORDER BY name").fetchall()
    finally:
        conn.close()
    return version, [row[0] for row in rows]


def _migrate(conn: sqlite3.Connection) -> int:
    """Apply MIGRATIONS in one transaction. Returns the new schema version."""
    conn.execute("BEGIN IMMEDIATE")
    # Read the version again inside the lock: another process may have just migrated.
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    while version in MIGRATIONS:
        for statement in MIGRATIONS[version]:
            conn.execute(statement)
        version += 1
    conn.execute(f"PRAGMA user_version = {version}")
    conn.execute("COMMIT")
    return version


def add_session(session: Session) -> bool:
    """False, with nothing changed, when a session of that name exists already."""
    with connect() as db:
        added = db.execute(
            "INSERT INTO sessions (name, repo, permission_mode, provider, kits, switched_off)"
            " VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (name) DO NOTHING",
            (
                session.name,
                session.repo,
                session.permission_mode,
                session.provider,
                json.dumps(session.kits),
                json.dumps(session.without),
            ),
        ).rowcount
    return added == 1


def get_session(name: str) -> Session | None:
    with connect() as db:
        row = db.execute("SELECT * FROM sessions WHERE name = ?", (name,)).fetchone()
    return _session(row) if row else None


def delete_session(name: str) -> None:
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE name = ?", (name,))


def stop_session(name: str) -> tuple[list[Agent], int]:
    """Mark the session stopped and forget its agents, so their names can be used again;
    their messages and events stay. Messages they never got, and bodies they never read,
    are dropped. Returns the agents
    and how many messages were dropped."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        rows, dropped = _stop_session(db, name, "")
        db.execute("COMMIT")
    return [_agent(r) for r in rows], dropped


def _stop_session(db: sqlite3.Connection, name: str, note: str) -> tuple[list, int]:
    rows = db.execute(
        "SELECT * FROM agents WHERE session = ? ORDER BY created_at, rowid", (name,)
    ).fetchall()
    for row in rows:
        if row["status"] != STOPPED:
            _add_event(db, name, row["name"], STATUS, STOPPED)
    db.execute("DELETE FROM agents WHERE session = ?", (name,))
    dropped = db.execute(
        f"UPDATE messages SET state = ? WHERE session = ? AND {UNRECEIVED}",
        (DROPPED, name, *UNRECEIVED_ARGS),
    ).rowcount
    db.execute(
        "UPDATE sessions SET stopped_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE name = ?",
        (name,),
    )
    detail = f"{dropped} message{'' if dropped == 1 else 's'} dropped{note}"
    _add_event(db, name, LADO, SESSION_STOP, detail)
    return rows, dropped


def resume_session(session: Session, detail: str) -> bool:
    """Mark the stopped session running again, with the settings of `session`; `detail`
    says what changed. False, with nothing changed, when the session is not stopped (another
    start took it first)."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        taken = db.execute(
            "UPDATE sessions SET stopped_at = NULL WHERE name = ? AND stopped_at IS NOT NULL",
            (session.name,),
        ).rowcount
        if not taken:
            db.execute("ROLLBACK")
            return False
        _set_settings(db, session)
        _add_event(db, session.name, LADO, SESSION_RESUME, detail)
        db.execute("COMMIT")
    return True


def fail_resume(old: Session, message_ids: list[int], restored: str) -> None:
    """Stop a session whose resume failed, in one go: drop the messages its supervisor never
    got (`message_ids`) and put back the settings of `old`; `restored` says which."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.executemany(
            "UPDATE messages SET state = ? WHERE session = ? AND id = ?",
            [(DROPPED, old.name, i) for i in message_ids],
        )
        _stop_session(db, old.name, f"; settings put back: {restored}" if restored else "")
        _set_settings(db, old)
        db.execute("COMMIT")


def _set_settings(db: sqlite3.Connection, session: Session) -> None:
    db.execute(
        "UPDATE sessions SET permission_mode = ?, provider = ?, kits = ?, switched_off = ?"
        " WHERE name = ?",
        (
            session.permission_mode,
            session.provider,
            json.dumps(session.kits),
            json.dumps(session.without),
            session.name,
        ),
    )


def list_sessions() -> list[Session]:
    with connect() as db:
        rows = db.execute("SELECT * FROM sessions ORDER BY created_at, rowid").fetchall()
    return [_session(r) for r in rows]


def add_agent(agent: Agent) -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO agents"
            " (session, name, role, cwd, branch, task, status, provider, instance, run)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                agent.session,
                agent.name,
                agent.role,
                agent.cwd,
                agent.branch,
                agent.task,
                agent.status,
                agent.provider,
                agent.instance,
                agent.run,
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


def delete_agent(session: str, name: str) -> None:
    """Forget the agent; its messages and events stay in the log."""
    with connect() as db:
        db.execute("DELETE FROM agents WHERE session = ? AND name = ?", (session, name))


def set_status(session: str, name: str, status: str) -> None:
    """Set the agent's status and, if it changed, record a "status" event."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _set_status(db, session, name, status)
        db.execute("COMMIT")


def _set_status(db: sqlite3.Connection, session: str, name: str, status: str) -> None:
    cur = db.execute(
        "UPDATE agents SET status = ? WHERE session = ? AND name = ? AND status != ?",
        (status, session, name, status),
    )
    if cur.rowcount:
        _add_event(db, session, name, STATUS, status)


def seen(session: str, name: str) -> None:
    """Record that a hook of the agent ran now. Its failed messages that no hook ran after
    (a dialog swallowed them) go back to the queue, with their attempts from 0."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE messages SET state = ?, attempts = 0 WHERE session = ? AND recipient = ?"
            " AND state = ? AND sent_at > (SELECT seen_at FROM agents"
            " WHERE session = ? AND name = ?)",
            (PENDING, session, name, FAILED, session, name),
        )
        db.execute(
            "UPDATE agents SET seen_at = ? WHERE session = ? AND name = ?",
            (time.time(), session, name),
        )
        db.execute("COMMIT")


def add_event(
    session: str, agent: str, kind: str, detail: str = "", run: str | None = None
) -> None:
    with connect() as db:
        _add_event(db, session, agent, kind, detail, run)


def _add_event(
    db: sqlite3.Connection,
    session: str,
    agent: str,
    kind: str,
    detail: str,
    run: str | None = None,
) -> None:
    db.execute(
        "INSERT INTO events (session, agent, kind, detail, run) VALUES (?, ?, ?, ?, ?)",
        (session, agent, kind, detail, run),
    )


def has_event(session: str, agent: str, kind: str, detail: str) -> bool:
    with connect() as db:
        row = db.execute(
            "SELECT 1 FROM events WHERE session = ? AND agent = ? AND kind = ? AND detail = ?",
            (session, agent, kind, detail),
        ).fetchone()
    return row is not None


def list_events(session: str, after: int = 0) -> list[Event]:
    """The session's events with an id above `after`, oldest first."""
    with connect() as db:
        rows = db.execute(
            "SELECT id, agent, kind, detail, created_at, run FROM events"
            " WHERE session = ? AND id > ? ORDER BY id",
            (session, after),
        ).fetchall()
    return [Event(*r) for r in rows]


def add_run(run: Run, events: list[tuple[str, str, str]], opens: Gate | None = None) -> None:
    """Store a new run, its events (actor, kind, detail) and the gate it waits at, if
    any, in one transaction."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT INTO runs (session, name, flow, snapshot, kit, task, state, visits, status,"
            " reason, note, note_body, worktree, branch, language) VALUES"
            " (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run.session,
                run.name,
                run.flow,
                json.dumps(run.snapshot),
                json.dumps(run.kit),
                run.task,
                run.state,
                json.dumps(run.visits),
                run.status,
                run.reason,
                run.note,
                run.note_body,
                run.worktree,
                run.branch,
                run.language,
            ),
        )
        for actor, kind, detail in events:
            _add_event(db, run.session, actor, kind, detail, run.name)
        if opens:
            _open_gate(db, opens)
        db.execute("COMMIT")


def get_run(session: str, name: str) -> Run | None:
    with connect() as db:
        row = db.execute(
            "SELECT * FROM runs WHERE session = ? AND name = ?", (session, name)
        ).fetchone()
    return _run(row) if row else None


def list_runs(session: str, open_only: bool = False) -> list[Run]:
    """The session's runs, oldest first; with `open_only` only active and waiting ones."""
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM runs WHERE session = ? ORDER BY created_at, rowid", (session,)
        ).fetchall()
    runs = [_run(r) for r in rows]
    return [r for r in runs if r.status in OPEN] if open_only else runs


def update_run(
    before: Run,
    after: Run,
    events: list[tuple[str, str, str]],
    opens: Gate | None = None,
    closes: Close | None = None,
    noted: tuple[str, str] | None = None,
) -> bool:
    """Write `after` and the events (actor, kind, detail) in one transaction, but only if
    the run still has the state, status and visits of `before`: entering a state counts a
    visit, so even a self-loop changes what the next writer compares. Returns whether it
    was written. In the same transaction `closes` closes the run's open gate (nothing is
    written if it names a gate that is not open), the gate `opens` is stored (its id
    set), and `after`'s note is kept as `noted` says, if given: (state, REPORT or
    OVERRIDE)."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        cur = db.execute(
            "UPDATE runs SET state = ?, visits = ?, status = ?, reason = ?, note = ?,"
            " note_body = ? WHERE session = ? AND name = ? AND state = ? AND status = ?"
            " AND visits = ?",
            (
                after.state,
                json.dumps(after.visits),
                after.status,
                after.reason,
                after.note,
                after.note_body,
                before.session,
                before.name,
                before.state,
                before.status,
                json.dumps(before.visits),
            ),
        )
        if cur.rowcount and closes and not _close_gate(db, before.session, before.name, *closes):
            db.execute("ROLLBACK")
            return False
        if cur.rowcount:
            for actor, kind, detail in events:
                _add_event(db, before.session, actor, kind, detail, before.name)
            if opens:
                _open_gate(db, opens)
            if noted is not None:
                db.execute(
                    "INSERT INTO notes (session, run, state, kind, summary, body)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (before.session, before.name, *noted, after.note, after.note_body),
                )
        db.execute("COMMIT")
    return bool(cur.rowcount)


def latest_notes(session: str, run: str) -> dict[str, Note]:
    """The latest report kept from each state of the run; the human's overrides are not
    a state's report."""
    with connect() as db:
        rows = db.execute(
            "SELECT state, summary, body, created_at, id FROM notes WHERE id IN"
            " (SELECT MAX(id) FROM notes WHERE session = ? AND run = ? AND kind = ?"
            " GROUP BY state)",
            (session, run, REPORT),
        ).fetchall()
    return {r["state"]: Note(*r) for r in rows}


def last_note(session: str, run: str) -> Note | None:
    """The run's latest note of any kind: the one its current step got as the previous
    step's note, since each note a step gets is kept when the run moves on."""
    with connect() as db:
        row = db.execute(
            "SELECT state, summary, body, created_at, id FROM notes"
            " WHERE session = ? AND run = ? ORDER BY id DESC LIMIT 1",
            (session, run),
        ).fetchone()
    return Note(*row) if row else None


def _open_gate(db: sqlite3.Connection, gate: Gate) -> None:
    cur = db.execute(
        "INSERT INTO gates (session, run, state, kind, question, options, note, note_body)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            gate.session,
            gate.run,
            gate.state,
            gate.kind,
            gate.question,
            json.dumps(gate.options),
            gate.note,
            gate.note_body,
        ),
    )
    gate.id = cur.lastrowid or 0
    detail = f"#{gate.id} {gate.kind} at {gate.state}: {gate.question}"
    _add_event(db, gate.session, LADO, GATE_OPEN, detail, gate.run)


def _close_gate(
    db: sqlite3.Connection,
    session: str,
    run: str,
    actor: str,
    answer: str,
    comment: str,
    gate_id: int | None,
) -> bool:
    """Close the run's open gate. Returns False if `gate_id` is given and is not it."""
    row = db.execute(
        "SELECT id FROM gates WHERE session = ? AND run = ? AND answer IS NULL", (session, run)
    ).fetchone()
    if row is None or (gate_id is not None and row["id"] != gate_id):
        return gate_id is None
    db.execute(
        "UPDATE gates SET answer = ?, comment = ?, answered_by = ?,"
        " answered_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
        (answer, comment, actor, row["id"]),
    )
    detail = f"#{row['id']} {answer}" + (f": {comment}" if comment else "")
    _add_event(db, session, actor, GATE_ANSWER, detail, run)
    return True


def get_gate(gate_id: int) -> Gate | None:
    with connect() as db:
        row = db.execute("SELECT * FROM gates WHERE id = ?", (gate_id,)).fetchone()
    return _gate(row) if row else None


def open_gates(session: str | None = None) -> list[Gate]:
    """The open gates of `session` (default: of all sessions), oldest first."""
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM gates WHERE answer IS NULL AND (? IS NULL OR session = ?) ORDER BY id",
            (session, session),
        ).fetchall()
    return [_gate(r) for r in rows]


def open_gate(session: str, run: str) -> Gate | None:
    """The run's open gate, if it has one."""
    return next((g for g in open_gates(session) if g.run == run), None)


def run_since(session: str) -> dict[str, datetime.datetime]:
    """When each run got into its current state: its latest event (UTC)."""
    with connect() as db:
        rows = db.execute(
            "SELECT run, created_at FROM events WHERE id IN"
            " (SELECT MAX(id) FROM events WHERE session = ? AND run IS NOT NULL GROUP BY run)",
            (session,),
        ).fetchall()
    return {r["run"]: _utc(r["created_at"]) for r in rows}


def _utc(created_at: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(created_at).replace(tzinfo=datetime.timezone.utc)


def status_since(session: str) -> dict[str, datetime.datetime]:
    """When each agent got its current status: its latest "status" or "spawned" event (UTC)."""
    with connect() as db:
        rows = db.execute(
            "SELECT agent, created_at FROM events WHERE id IN"
            " (SELECT MAX(id) FROM events WHERE session = ? AND kind IN (?, ?) GROUP BY agent)",
            (session, STATUS, SPAWNED),
        ).fetchall()
    return {r["agent"]: _utc(r["created_at"]) for r in rows}


MESSAGE_COLUMNS = "id, sender, summary, body, recipient, state, created_at, attempts, sent_at"


def queue_message(
    session: str, sender: str, recipient: str, summary: str, body: str = "", mark: str = PENDING
) -> int:
    """Store a message in state `mark`: pending, or delivered when its line goes to the
    recipient another way (its first input). Returns its id."""
    with connect() as db:
        cur = db.execute(
            "INSERT INTO messages (session, sender, recipient, summary, body, state, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
            (session, sender, recipient, summary, body, mark),
        )
        return cur.lastrowid or 0


def list_messages(session: str, after: int = 0) -> list[Message]:
    """The session's messages with an id above `after`, oldest first."""
    with connect() as db:
        rows = db.execute(
            f"SELECT {MESSAGE_COLUMNS} FROM messages WHERE session = ? AND id > ? ORDER BY id",
            (session, after),
        ).fetchall()
    return [Message(*r) for r in rows]


def read_messages(session: str, recipient: str) -> list[Message]:
    """Mark the recipient's delivered messages that have a body read and return them, oldest
    first. Each one is returned once."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute(
            f"SELECT {MESSAGE_COLUMNS} FROM messages"
            " WHERE session = ? AND recipient = ? AND state = ? AND body != '' ORDER BY id",
            (session, recipient, DELIVERED),
        ).fetchall()
        db.executemany(
            "UPDATE messages SET state = ? WHERE id = ?", [(READ, r["id"]) for r in rows]
        )
        db.execute("COMMIT")
    return [Message(*r[:5], READ, r["created_at"]) for r in rows]


def take_pending(
    session: str, recipient: str, mark: str, status: str | None = None
) -> list[Message]:
    """Move all pending messages for `recipient` to `mark` and return them, oldest first;
    when there are any and `status` is given, set the recipient's status too.

    Runs in one write transaction, so two concurrent callers never get the same message,
    and no one sees the messages moved without the status that goes with them.
    """
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute(
            f"SELECT {MESSAGE_COLUMNS} FROM messages"
            " WHERE session = ? AND recipient = ? AND state = ? ORDER BY id",
            (session, recipient, PENDING),
        ).fetchall()
        # Typed into the window, it is an attempt (lado.runtime.sweep); handed over another
        # way, it is delivered and needs none.
        attempt = 1 if mark == SENT else 0
        db.executemany(
            "UPDATE messages SET state = ?, sent_at = ?, attempts = attempts + ? WHERE id = ?",
            [(mark, time.time(), attempt, r["id"]) for r in rows],
        )
        if rows and status:
            _set_status(db, session, recipient, status)
        db.execute("COMMIT")
    return [Message(*r[:5], mark, r["created_at"]) for r in rows]


@dataclass
class Plan:
    """What to do with an agent's unconfirmed messages (lado.runtime.sweep decides)."""

    retype: bool = False  # type its sent and pending messages again, as one text
    requeue: list[int] = field(default_factory=list)  # back to pending
    fail: list[int] = field(default_factory=list)


@dataclass
class Swept:
    typed: list[Message]  # marked typed again: type them into the window, as one text
    failed: list[Message]
    requeued: int


def sweep(
    session: str, name: str, now: float, decide: Callable[[Agent, list[Message]], Plan]
) -> Swept:
    """Carry out `decide(agent, its sent messages)` in one write transaction, so two
    sweeps never type the same message twice. A failure puts a busy or idle agent in
    waiting: it took or confirmed nothing for so long that typing more would not help."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT * FROM agents WHERE session = ? AND name = ?", (session, name)
        ).fetchone()
        if row is None:
            db.execute("ROLLBACK")
            return Swept([], [], 0)
        agent = _agent(row)
        query = (
            f"SELECT {MESSAGE_COLUMNS} FROM messages WHERE session = ? AND recipient = ?"
            " AND state IN ({}) ORDER BY id"
        )
        sent = [Message(*r) for r in db.execute(query.format("?"), (session, name, SENT))]
        plan = decide(agent, sent)
        failed = [m for m in sent if m.id in plan.fail]
        db.executemany(
            "UPDATE messages SET state = ?, failed_at = ? WHERE id = ?",
            [(FAILED, now, i) for i in plan.fail] + [(PENDING, None, i) for i in plan.requeue],
        )
        if failed and agent.status in (BUSY, IDLE):
            db.execute(
                "UPDATE agents SET status = ? WHERE session = ? AND name = ?",
                (WAITING, session, name),
            )
            _add_event(db, session, name, STATUS, WAITING)
        typed = []
        if plan.retype:
            rows = db.execute(query.format("?, ?"), (session, name, SENT, PENDING)).fetchall()
            db.executemany(
                "UPDATE messages SET state = ?, sent_at = ?, attempts = attempts + 1 WHERE id = ?",
                [(SENT, now, r["id"]) for r in rows],
            )
            typed = [Message(*r[:5], SENT, r["created_at"]) for r in rows]
        db.execute("COMMIT")
    return Swept(typed, [replace(m, state=FAILED) for m in failed], len(plan.requeue))


def confirm_sent(
    session: str, recipient: str, prompt: str, typed: Callable[[Message], str]
) -> None:
    """Mark sent messages as delivered whose typed line, `typed(message)`, is in the prompt
    the agent just received."""
    with connect() as db:
        rows = db.execute(
            f"SELECT {MESSAGE_COLUMNS} FROM messages"
            " WHERE session = ? AND recipient = ? AND state = ?",
            (session, recipient, SENT),
        ).fetchall()
        confirmed = [(DELIVERED, r["id"]) for r in rows if typed(Message(*r)) in prompt]
        db.executemany("UPDATE messages SET state = ? WHERE id = ?", confirmed)


def drop_undelivered(session: str, recipient: str) -> int:
    """Mark the recipient's pending and unconfirmed messages, and the bodies it never read,
    dropped. Returns how many."""
    with connect() as db:
        cur = db.execute(
            f"UPDATE messages SET state = ? WHERE session = ? AND recipient = ? AND {UNRECEIVED}",
            (DROPPED, session, recipient, *UNRECEIVED_ARGS),
        )
        return cur.rowcount


def drop_pending(session: str, sender: str, recipient: str, summary: str) -> int:
    """Mark the pending messages with this sender, recipient and summary dropped: what they
    ask for is done already. Returns how many."""
    with connect() as db:
        cur = db.execute(
            "UPDATE messages SET state = ? WHERE session = ? AND sender = ? AND recipient = ?"
            " AND summary = ? AND state = ?",
            (DROPPED, session, sender, recipient, summary, PENDING),
        )
        return cur.rowcount


def failed_counts(session: str) -> dict[str, tuple[int, int]]:
    """Per agent, its messages that failed after its latest hook: how many no hook ran after
    at all (swallowed) and how many it ran hooks after without confirming them."""
    with connect() as db:
        rows = db.execute(
            "SELECT m.recipient, SUM(m.sent_at > a.seen_at), SUM(m.sent_at <= a.seen_at)"
            " FROM messages m JOIN agents a ON a.session = m.session AND a.name = m.recipient"
            " WHERE m.session = ? AND m.state = ? AND m.failed_at > a.seen_at"
            " GROUP BY m.recipient",
            (session, FAILED),
        ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def has_sent(session: str, recipient: str) -> bool:
    """Whether a message typed into the recipient's window is still unconfirmed."""
    with connect() as db:
        row = db.execute(
            "SELECT 1 FROM messages WHERE session = ? AND recipient = ? AND state = ?",
            (session, recipient, SENT),
        ).fetchone()
    return row is not None


def _agent(row: sqlite3.Row) -> Agent:
    return Agent(
        session=row["session"],
        name=row["name"],
        role=row["role"],
        cwd=row["cwd"],
        branch=row["branch"],
        task=row["task"],
        status=row["status"],
        provider=row["provider"],
        instance=row["instance"],
        run=row["run"],
        seen_at=row["seen_at"],
    )


def _run(row: sqlite3.Row) -> Run:
    return Run(
        session=row["session"],
        name=row["name"],
        flow=row["flow"],
        snapshot=json.loads(row["snapshot"]),
        kit=json.loads(row["kit"]),
        task=row["task"],
        state=row["state"],
        worktree=row["worktree"],
        branch=row["branch"],
        visits=json.loads(row["visits"]),
        status=row["status"],
        reason=row["reason"],
        note=row["note"],
        note_body=row["note_body"],
        language=row["language"],
        created_at=row["created_at"],
    )


def _gate(row: sqlite3.Row) -> Gate:
    return Gate(
        session=row["session"],
        run=row["run"],
        state=row["state"],
        kind=row["kind"],
        question=row["question"],
        options=json.loads(row["options"]),
        note=row["note"],
        note_body=row["note_body"],
        id=row["id"],
        answer=row["answer"],
        comment=row["comment"],
        answered_by=row["answered_by"],
        created_at=row["created_at"],
        answered_at=row["answered_at"],
    )


def _session(row: sqlite3.Row) -> Session:
    return Session(
        row["name"],
        row["repo"],
        row["permission_mode"],
        row["provider"],
        json.loads(row["kits"]),
        json.loads(row["switched_off"]),
        row["stopped_at"],
    )
