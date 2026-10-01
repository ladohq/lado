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
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 7

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
    state TEXT NOT NULL DEFAULT 'pending',  -- pending | sent | delivered | read | dropped
    sent_at REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
SCHEMA += ";\n".join([EVENTS, EVENTS_RUN, AGENTS_RUN, RUNS, GATES, GATES_OPEN]) + ";\n"

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
DROPPED = "dropped"  # its recipient was finished before it got the message

# Event kinds.
SPAWNED = "spawned"  # detail: "role <role>, provider <provider>"
STATUS = "status"  # detail: the new status
FINISHED = "finished"  # a worker was ended; detail: "merged" or "discarded"
# Flow run events (lado.runs); their run column names the run.
FLOW_START = "flow_start"
FLOW = "flow"  # a transition; detail: "<from> -<outcome>-> <to>"
FLOW_END = "flow_end"
FLOW_CANCEL = "flow_cancel"
FLOW_SET = "flow_set"  # the human forced the run into a state
GATE_OPEN = "gate_open"  # the run waits for the human; detail: "#<id> <kind> at <state>: ..."
GATE_ANSWER = "gate_answer"  # the gate closed; detail: "#<id> <answer>[: <comment>]"

LADO = "lado"  # the sender of LADO's own messages and the actor of its own events

# Run statuses.
ACTIVE = "active"
WAITING = "waiting"  # for the human: a gate or a loop limit
ENDED = "ended"
CANCELLED = "cancelled"
OPEN = (ACTIVE, WAITING)


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


@dataclass
class Session:
    name: str
    repo: str
    permission_mode: str | None
    provider: str = "claude"
    kits: list[str] = field(default_factory=lambda: ["default"])
    without: list[str] = field(default_factory=list)  # switched-off agents, skills, MCP


@dataclass
class Message:
    id: int
    sender: str
    summary: str
    body: str = ""
    recipient: str = ""
    state: str = ""
    created_at: str = ""  # UTC, "YYYY-MM-DD HH:MM:SS.SSS"; older rows have whole seconds

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


Close = tuple[str, str, str]  # who closes a run's open gate, the answer and a comment


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


def add_session(session: Session) -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO sessions (name, repo, permission_mode, provider, kits, switched_off)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                session.name,
                session.repo,
                session.permission_mode,
                session.provider,
                json.dumps(session.kits),
                json.dumps(session.without),
            ),
        )


def get_session(name: str) -> Session | None:
    with connect() as db:
        row = db.execute("SELECT * FROM sessions WHERE name = ?", (name,)).fetchone()
    return _session(row) if row else None


def delete_session(name: str) -> None:
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE name = ?", (name,))


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
        cur = db.execute(
            "UPDATE agents SET status = ? WHERE session = ? AND name = ? AND status != ?",
            (status, session, name, status),
        )
        if cur.rowcount:
            _add_event(db, session, name, STATUS, status)
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
            " reason, note, note_body, worktree, branch) VALUES"
            " (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
) -> bool:
    """Write `after` and the events (actor, kind, detail) in one transaction, but only if
    the run still has the state, status and visits of `before`: entering a state counts a
    visit, so even a self-loop changes what the next writer compares. Returns whether it
    was written. In the same transaction `closes` closes the run's open gate, and the
    gate `opens` is stored (its id set)."""
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
        if cur.rowcount:
            if closes:
                _close_gate(db, before.session, before.name, *closes)
            for actor, kind, detail in events:
                _add_event(db, before.session, actor, kind, detail, before.name)
            if opens:
                _open_gate(db, opens)
        db.execute("COMMIT")
    return bool(cur.rowcount)


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
    db: sqlite3.Connection, session: str, run: str, actor: str, answer: str, comment: str
) -> None:
    row = db.execute(
        "SELECT id FROM gates WHERE session = ? AND run = ? AND answer IS NULL", (session, run)
    ).fetchone()
    if row is None:
        return
    db.execute(
        "UPDATE gates SET answer = ?, comment = ?, answered_by = ?,"
        " answered_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
        (answer, comment, actor, row["id"]),
    )
    detail = f"#{row['id']} {answer}" + (f": {comment}" if comment else "")
    _add_event(db, session, actor, GATE_ANSWER, detail, run)


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


MESSAGE_COLUMNS = "id, sender, summary, body, recipient, state, created_at"


def queue_message(session: str, sender: str, recipient: str, summary: str, body: str = "") -> int:
    with connect() as db:
        cur = db.execute(
            "INSERT INTO messages (session, sender, recipient, summary, body, created_at)"
            " VALUES (?, ?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
            (session, sender, recipient, summary, body),
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


def take_pending(session: str, recipient: str, mark: str) -> list[Message]:
    """Move all pending messages for `recipient` to `mark` and return them, oldest first.

    Runs in one write transaction, so two concurrent callers never get the same message.
    """
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute(
            f"SELECT {MESSAGE_COLUMNS} FROM messages"
            " WHERE session = ? AND recipient = ? AND state = ? ORDER BY id",
            (session, recipient, PENDING),
        ).fetchall()
        db.executemany(
            "UPDATE messages SET state = ?, sent_at = ? WHERE id = ?",
            [(mark, time.time(), r["id"]) for r in rows],
        )
        db.execute("COMMIT")
    return [Message(*r[:5], mark, r["created_at"]) for r in rows]


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
    """Mark the recipient's pending and unconfirmed messages dropped. Returns how many."""
    with connect() as db:
        cur = db.execute(
            "UPDATE messages SET state = ? WHERE session = ? AND recipient = ? AND state IN (?, ?)",
            (DROPPED, session, recipient, PENDING, SENT),
        )
        return cur.rowcount


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
        provider=row["provider"],
        instance=row["instance"],
        run=row["run"],
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
    )
