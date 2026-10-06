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
from contextlib import contextmanager, suppress
from dataclasses import astuple, dataclass, field, replace
from pathlib import Path

SCHEMA_VERSION = 19

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
# A note is the record of the step that reported it, from version 15 on: who reported it,
# the outcome and the state the outcome leads to. When a loop limit kept the run out of
# `target`, the run waits before it at a loop gate, the run's next note. '' in notes from
# before, and the outcome of the human's flow-set.
NOTES_STEP = [
    "ALTER TABLE notes ADD COLUMN actor TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE notes ADD COLUMN outcome TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE notes ADD COLUMN target TEXT NOT NULL DEFAULT ''",
]
# The request a waiting agent waits for the human to answer (a provider's id for it, see
# lado.hooks), from version 16 on; NULL when it waits for none in particular or does not
# wait. Only an answer to that request ends the wait (`resume`).
AGENTS_WAITING_FOR = "ALTER TABLE agents ADD COLUMN waiting_for TEXT"
# Kit marketplaces (lado.marketplaces), from version 17 on: git repositories that list kits
# by name. They belong to no session. The official one is a row like the others, made with
# the table, but has no url (its address is lado.marketplaces.OFFICIAL_URL) and is never
# removed, only disabled.
MARKETPLACES = """
CREATE TABLE IF NOT EXISTS marketplaces (
    name TEXT PRIMARY KEY,
    url TEXT,  -- NULL for the official one
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT  -- UTC: when its clone was last brought up to date; NULL for never
)"""
OFFICIAL_MARKETPLACE = "official"
MARKETPLACES_OFFICIAL = (
    f"INSERT OR IGNORE INTO marketplaces (name) VALUES ('{OFFICIAL_MARKETPLACE}')"
)
# The kits the user installed (lado.kits, `lado kits add`), from version 18 on: a kit from
# git by its address, version tag and the tag's commit at install time (its clone's folder
# is gitcache.clone_dir(address, tag), not kept), or a folder read in place. They belong to
# no session.
KITS = """
CREATE TABLE IF NOT EXISTS kits (
    name TEXT PRIMARY KEY,  -- the name in its kit.yaml
    address TEXT,  -- a kit from git: its address, tag and commit; NULL for a folder
    tag TEXT,
    "commit" TEXT,
    folder TEXT,  -- a folder kit's absolute path; NULL for a kit from git
    marketplace TEXT,  -- the marketplace it was added from (-m), kept when that one goes
    installed_at TEXT NOT NULL DEFAULT (datetime('now')),  -- UTC
    updated_at TEXT,  -- UTC: its latest `lado kits update`; NULL for never
    CHECK ((address IS NULL) <> (folder IS NULL)),
    CHECK ((address IS NULL) = (tag IS NULL) AND (address IS NULL) = ("commit" IS NULL))
)"""
# The change journal, from version 12 on: one row for each insert, update and delete of the
# tables the UI shows, written by triggers in the writer's own transaction, so a change by
# any process (CLI, hooks, MCP server, session loop) is in it. The UI server reads it
# (lado.server.feed). `key` names the row in its session: an agent's or run's name, a
# message's, gate's or note's id, '' for the session itself.
CHANGES = """
CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,  -- the table: sessions | agents | messages | runs | gates | notes | ...
    session TEXT NOT NULL,
    key TEXT NOT NULL,
    op TEXT NOT NULL  -- insert | update | delete
)"""
CHANGES_KEPT = 100_000  # the journal keeps the latest changes; an older position gets reset
CHANGES_TRIM = f"""
CREATE TRIGGER IF NOT EXISTS changes_trim AFTER INSERT ON changes BEGIN
    DELETE FROM changes WHERE id <= NEW.id - {CHANGES_KEPT};
END"""
# Each table with the expression of its key.
JOURNALED = {
    "sessions": "''",
    "agents": "{row}.name",
    "messages": "{row}.id",
    "runs": "{row}.name",
    "gates": "{row}.id",
    "notes": "{row}.id",
    "events": "{row}.id",  # from version 14 on: run events only (RUN_EVENT)
    "marketplaces": "{row}.name",  # from version 17 on
    "kits": "{row}.name",  # from version 18 on
}
# The session of a change, where it is not the row's session column: a session is its own,
# a marketplace or an installed kit belongs to none ('').
JOURNAL_SESSION = {"sessions": "{row}.name", "marketplaces": "''", "kits": "''"}
ALL_OPS = ("insert", "update", "delete")
# The writes of a table that are recorded, where not all are: an event is never changed,
# and goes only with its session.
JOURNALED_OPS = {"events": ("insert",)}
# Every hook sets agents.seen_at, which the UI does not show: an update that changes it is
# not a change. Only `seen` writes seen_at, and nothing else with it; so the condition names
# no other column, and a column added later is recorded without a new trigger (a trigger
# stays in lado.db as it was made).
AGENTS_CHANGED = "OLD.seen_at IS NEW.seen_at"
# Only a flow run's events are shown as such (the feed's lines); an agent's status event
# would double the journal, as its agents row is recorded already. The condition, too,
# stays in lado.db as the trigger was made.
RUN_EVENT = "NEW.run IS NOT NULL"
# The condition of a trigger, where there is one.
JOURNAL_WHEN = {("agents", "update"): AGENTS_CHANGED, ("events", "insert"): RUN_EVENT}


def _journal_trigger(table: str, op: str) -> str:
    row = "OLD" if op == "delete" else "NEW"
    when = f" WHEN {JOURNAL_WHEN[table, op]}" if (table, op) in JOURNAL_WHEN else ""
    key = JOURNALED[table].format(row=row)
    session = JOURNAL_SESSION.get(table, "{row}.session").format(row=row)
    return (
        f"CREATE TRIGGER IF NOT EXISTS changes_{table}_{op} AFTER {op.upper()} ON {table}"
        f"{when} BEGIN INSERT INTO changes (kind, session, key, op)"
        f" VALUES ('{table}', {session}, CAST({key} AS TEXT), '{op}'); END"
    )


def _journal_triggers(table: str) -> list[str]:
    return [_journal_trigger(table, op) for op in JOURNALED_OPS.get(table, ALL_OPS)]


# The journal as version 12 made it: its tables are fixed here, so that migration step
# stays as it was when a table is journaled later; and the run events version 14 added.
JOURNALED_V12 = ("sessions", "agents", "messages", "runs", "gates", "notes")
JOURNAL = [
    CHANGES,
    CHANGES_TRIM,
    *(trigger for t in JOURNALED_V12 for trigger in _journal_triggers(t)),
]
EVENTS_JOURNAL = _journal_triggers("events")
MARKETPLACES_TABLE = [MARKETPLACES, MARKETPLACES_OFFICIAL, *_journal_triggers("marketplaces")]
KITS_TABLE = [KITS, *_journal_triggers("kits")]
# How a message was handed over to its recipient, from version 19 on: typed into its window
# or carried on in its turn-end hook's output (TYPED, HOOK_OUTPUT; lado.runtime.hand_over).
# NULL while it is pending, and for one handed over another way (a first input, the human's
# UI). Each channel has its own confirmation and its own sweep rule (lado.runtime._plan).
MESSAGES_CHANNEL = "ALTER TABLE messages ADD COLUMN channel TEXT"

# The human in messages, from version 13 on: an agent's question to the human (ask_human)
# and its outcome, the answer to it, and whether an agent replied to the human's message.
MESSAGES_HUMAN = [
    "ALTER TABLE messages ADD COLUMN kind TEXT NOT NULL DEFAULT 'message'",  # | question
    # A question's: JSON list of the choices, or NULL for none; whether the human may answer
    # in their own words; open | answered | dismissed | closed; the id of the answer.
    "ALTER TABLE messages ADD COLUMN choices TEXT",
    "ALTER TABLE messages ADD COLUMN free_answer INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE messages ADD COLUMN question_state TEXT",
    "ALTER TABLE messages ADD COLUMN answered_by INTEGER",
    # An answer's or dismissal's: the question's id, and the choice taken, if one was.
    "ALTER TABLE messages ADD COLUMN reply_to INTEGER",
    "ALTER TABLE messages ADD COLUMN choice TEXT",
    # The human's message to an agent: NULL until the turn it started ends, then replied
    # or missing (the agent wrote nothing to the human: it replied only in its terminal).
    "ALTER TABLE messages ADD COLUMN reply_state TEXT",
]

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
            *JOURNAL,
            *MESSAGES_HUMAN,
            *EVENTS_JOURNAL,
            *NOTES_STEP,
            AGENTS_WAITING_FOR,
            *MARKETPLACES_TABLE,
            *KITS_TABLE,
            MESSAGES_CHANNEL,
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
    11: JOURNAL,
    12: MESSAGES_HUMAN,
    13: EVENTS_JOURNAL,
    14: NOTES_STEP,
    15: [AGENTS_WAITING_FOR],
    16: MARKETPLACES_TABLE,
    17: KITS_TABLE,
    18: [MESSAGES_CHANNEL],
}

# Agent statuses. Hooks move an agent between them; see lado.hooks.
STARTING = "starting"
BUSY = "busy"
IDLE = "idle"
WAITING = "waiting"  # waiting for the human, e.g. a permission prompt
STOPPED = "stopped"

LADO = "lado"  # the sender of LADO's own messages and the actor of its own events
HUMAN = "human"  # the human as a participant of messages: no agent, no window
RESERVED = frozenset({LADO, HUMAN})  # senders of messages that no agent may be named

# Message states. A message typed into an agent's window is only "sent" until the agent's
# prompt-submit hook confirms it; a modal dialog in the TUI can swallow the text.
PENDING = "pending"
SENT = "sent"
DELIVERED = "delivered"
READ = "read"  # its recipient got the body with read_messages
DROPPED = "dropped"  # its recipient was finished or stopped before it got (or read) it
FAILED = "failed"  # typed again and again, never confirmed (lado.runtime.sweep)
# The channels a sent message went by (messages.channel).
TYPED = "typed"  # typed into the window; confirmed by its line in a prompt-submit hook
# Carried on in the turn-end hook's output; confirmed by its line in a prompt-submit hook,
# or by the next turn's end that says the turn went on from that output (lado.hooks).
HOOK_OUTPUT = "hook_output"
# What an agent has not received yet: messages not delivered, and bodies not read. When the
# agent is finished or stopped, they are dropped: a new agent of the same name starts fresh.
# The human is no agent: their messages stay as they are.
UNRECEIVED = "(state IN (?, ?, ?) OR (state = ? AND body != '')) AND recipient != ?"
UNRECEIVED_ARGS = (PENDING, SENT, FAILED, DELIVERED, HUMAN)

# Event kinds.
SPAWNED = "spawned"  # detail: "role <role>, provider <provider>"
STATUS = "status"  # detail: the new status
FINISHED = "finished"  # a worker was ended; detail: "merged" or "discarded"
MCP_READY = "mcp_ready"  # the agent's CLI listed LADO's MCP tools; detail: the launch (instance)
TURN_ERROR = "turn_error"  # its turn ended on an error (lado.hooks); detail: the error
# Its process ended by itself, not by LADO (agent_ended): its "stopped" status event follows;
# detail: why, e.g. "its CLI exited". The one source of why a stopped agent stopped.
ENDED = "ended"
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
# Its runtime was found gone at a stop or resume: created_at is the last sign of life
# (last_alive), not when it was found; the session_stop follows.
SESSION_GONE = "session_gone"
# The events that start and end the spans a session ran (runtime.session_time).
SPAN_EVENTS = (SESSION_RESUME, SESSION_STOP, SESSION_GONE)

# Message kinds.
MESSAGE = "message"
QUESTION = "question"  # an agent's question to the human (ask_human)
# Question states: waiting for the human; answered or dismissed by them; closed when the
# agent that asked was forgotten (finished, or its session stopped).
OPEN_QUESTION = "open"
ANSWERED = "answered"
DISMISSED = "dismissed"
CLOSED = "closed"
# Reply states of the human's message to an agent, set when the turn it started ends.
REPLIED = "replied"
MISSING = "missing"  # the agent wrote nothing to the human: it replied only in its terminal

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
    provider: str
    instance: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    run: str | None = None  # the flow run it works for
    seen_at: float = 0  # when its latest hook ran (time.time()); 0 for none yet
    waiting_for: str | None = None  # the request it waits for, while waiting (`wait`)
    created_at: str = ""  # UTC, "YYYY-MM-DD HH:MM:SS", when it was added; set by the database


@dataclass
class Session:
    name: str
    repo: str
    permission_mode: str | None
    provider: str
    kits: list[str] = field(default_factory=lambda: ["default"])
    without: list[str] = field(default_factory=list)  # switched-off agents, skills, MCP
    stopped_at: str | None = None  # UTC; None while it runs
    created_at: str = ""  # UTC, "YYYY-MM-DD HH:MM:SS", when it was added; set by the database


@dataclass(frozen=True)
class Marketplace:
    name: str
    url: str | None  # None for the official one
    enabled: bool
    updated_at: str | None  # UTC; None while its clone was never brought up to date


@dataclass(frozen=True)
class InstalledKit:
    """A kit the user installed: from git (address, tag, commit) or a folder."""

    name: str
    address: str | None = None
    tag: str | None = None  # the version tag vX.Y.Z
    commit: str | None = None  # the commit of the tag when it was installed
    folder: str | None = None
    marketplace: str | None = None  # the marketplace it was added from, if any
    installed_at: str | None = None  # UTC; set by add_kit
    updated_at: str | None = None  # UTC; None while never updated


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
    kind: str = "message"  # MESSAGE | QUESTION
    # A question's (ask_human): its choices (None for none), whether the human may answer in
    # their own words, its QUESTION_STATES and the id of its answer.
    choices: list[str] | None = None
    free_answer: bool = False
    question_state: str | None = None
    answered_by: int | None = None
    reply_to: int | None = None  # an answer's or dismissal's: the question's id
    choice: str | None = None  # an answer's: the choice taken, if one was
    reply_state: str | None = None  # the human's message to an agent: REPLIED | MISSING
    channel: str | None = None  # how it was handed over: TYPED | HOOK_OUTPUT; None for none

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
    # The flow as it was at the start, JSON as stored: read by runs.flow_of, so a run whose
    # snapshot cannot be read still reads.
    snapshot: str
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
    run: str = ""
    kind: str = REPORT
    actor: str = ""  # who reported it; '' before version 15
    outcome: str = ""  # '' before version 15 and for the human's flow-set
    target: str = ""  # where the outcome leads (NOTES_STEP); '' before version 15


@dataclass(frozen=True)
class Noted:
    """How update_run keeps the new note: the state it was reported from, its kind (REPORT
    or OVERRIDE), and the step: who reported it, the outcome and where it leads."""

    state: str
    kind: str
    actor: str = ""
    outcome: str = ""
    target: str = ""


NOTE_COLUMNS = "state, summary, body, created_at, id, run, kind, actor, outcome, target"


# Who closes a run's open gate, the answer, a comment, and the id of the gate that must be
# the open one (an answer), or None to close whichever is open, if any (an override).
Close = tuple[str, str, str, int | None]


def home() -> Path:
    path = Path(os.environ.get("LADO_HOME") or Path.home() / ".lado")
    path.mkdir(parents=True, exist_ok=True)
    return path


class SchemaError(RuntimeError):
    """lado.db has another schema than this LADO's: older (migrate() upgrades it), newer or
    incompatible. connect() raises it and changes nothing."""


def _open() -> sqlite3.Connection:
    conn = sqlite3.connect(home() / "lado.db", timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """lado.db, made when there is none. It never migrates: another schema version is a
    SchemaError, so no process opening it upgrades the database under a running session
    (only migrate() does, which the CLI calls when no session runs)."""
    conn = _open()
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()
        if version in MIGRATIONS:
            conn.close()
            raise SchemaError(
                f"{home() / 'lado.db'} has schema version {version} and this LADO knows "
                f"{SCHEMA_VERSION}: LADO was upgraded under a running session. Run "
                "`lado stop --all`, then `lado start`; with no session running, any `lado` "
                "command upgrades the database"
            )
        if version > SCHEMA_VERSION:
            conn.close()
            raise SchemaError(
                f"{home() / 'lado.db'} has schema version {version}, made by a newer LADO "
                f"(this one knows up to {SCHEMA_VERSION}); upgrade LADO, and restart a "
                "session that runs on this version with `lado stop` and `lado start`"
            )
        if version or tables[0]:
            conn.close()
            raise SchemaError(
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
    connect(), it never makes the database or refuses a schema."""
    path = home() / "lado.db"
    if not path.exists():
        return None
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=10)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def pending_migration() -> tuple[int, list[str]] | None:
    """When migrate() would upgrade lado.db: its schema version and the sessions it does
    not mark stopped. Reads only: changes nothing in the database (a WAL database opened
    read-only may leave lado.db-wal and lado.db-shm behind)."""
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


def migrate() -> int | None:
    """Upgrade an older lado.db to SCHEMA_VERSION in one transaction: the only place that
    applies MIGRATIONS. The new version, or None when there was nothing to migrate (no
    lado.db, or not an older schema). Its caller makes sure no session runs
    (lado.runtime)."""
    if not (home() / "lado.db").exists():
        return None
    conn = _open()
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Read the version inside the lock: another process may have just migrated.
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in MIGRATIONS:
            conn.execute("ROLLBACK")
            return None
        while version in MIGRATIONS:
            for statement in MIGRATIONS[version]:
                conn.execute(statement)
            version += 1
        conn.execute(f"PRAGMA user_version = {version}")
        conn.execute("COMMIT")
        return version
    finally:
        conn.close()


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


def stop_session(name: str, gone: bool = False) -> tuple[list[Agent], int]:
    """Mark the session stopped and forget its agents, so their names can be used again;
    their messages and events stay. Messages they never got, and bodies they never read,
    are dropped. `gone`: its runtime was found gone, so a session not stopped yet gets a
    `session_gone` at its last sign of life first. Returns the agents
    and how many messages were dropped."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if gone:
            _session_gone(db, name)
        rows, dropped = _stop_session(db, name, "")
        db.execute("COMMIT")
    return [_agent(r) for r in rows], dropped


def unreceived(name: str) -> int:
    """How many of the session's messages a stop would drop now."""
    with connect() as db:
        return db.execute(
            f"SELECT count(*) FROM messages WHERE session = ? AND {UNRECEIVED}",
            (name, *UNRECEIVED_ARGS),
        ).fetchone()[0]


def _session_gone(db: sqlite3.Connection, name: str) -> None:
    """Record, for a session not stopped, that it ended at its last sign of life; before
    _stop_session, which forgets the agents whose hooks tell it."""
    if db.execute(
        "SELECT 1 FROM sessions WHERE name = ? AND stopped_at IS NULL", (name,)
    ).fetchone():
        db.execute(
            "INSERT INTO events (session, agent, kind, created_at) VALUES (?, ?, ?, ?)",
            (name, LADO, SESSION_GONE, _last_alive(db, name)),
        )


def last_alive(name: str) -> str:
    """The session's last sign of life, in events' form ("YYYY-MM-DD HH:MM:SS.SSS", UTC)."""
    with connect() as db:
        return _last_alive(db, name)


def _last_alive(db: sqlite3.Connection, name: str) -> str:
    """When the latest hook of its agents ran; with none, its latest event."""
    seen = db.execute("SELECT max(seen_at) FROM agents WHERE session = ?", (name,)).fetchone()[0]
    if seen:
        at = datetime.datetime.fromtimestamp(seen, datetime.timezone.utc)
        return at.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    latest = "SELECT max(created_at) FROM events WHERE session = ?"
    return db.execute(latest, (name,)).fetchone()[0] or ""


def span_events(name: str) -> list[Event]:
    """The session's events that start or end a span it ran (SPAN_EVENTS), oldest first."""
    marks = ", ".join("?" * len(SPAN_EVENTS))
    with connect() as db:
        rows = db.execute(
            "SELECT id, agent, kind, detail, created_at, run FROM events"
            f" WHERE session = ? AND kind IN ({marks}) ORDER BY id",
            (name, *SPAN_EVENTS),
        ).fetchall()
    return [Event(*r) for r in rows]


def _stop_session(db: sqlite3.Connection, name: str, note: str) -> tuple[list, int]:
    rows = db.execute(
        "SELECT * FROM agents WHERE session = ? ORDER BY created_at, rowid", (name,)
    ).fetchall()
    for row in rows:
        if row["status"] != STOPPED:
            _add_event(db, name, row["name"], STATUS, STOPPED)
    db.execute("DELETE FROM agents WHERE session = ?", (name,))
    _close_questions(db, name)
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


def sessions_by_start() -> list[Session]:
    """The sessions, the latest started (or resumed) first: by their supervisor's latest
    `spawned` event, which each start and resume writes."""
    with connect() as db:
        rows = db.execute(
            "SELECT s.*, (SELECT max(e.id) FROM events e WHERE e.session = s.name"
            " AND e.agent = 'supervisor' AND e.kind = ?) AS started"
            " FROM sessions s ORDER BY coalesce(started, 0) DESC, s.rowid DESC",
            (SPAWNED,),
        ).fetchall()
    return [_session(r) for r in rows]


def last_session(repo: str) -> Session | None:
    """The session of the folder `repo` started (or resumed) latest, if any."""
    return next((s for s in sessions_by_start() if s.repo == repo), None)


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
    """Forget the agent and close its open questions to the human, in one transaction; its
    messages and events stay in the log."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM agents WHERE session = ? AND name = ?", (session, name))
        _close_questions(db, session, name)
        db.execute("COMMIT")


def _close_questions(db: sqlite3.Connection, session: str, sender: str | None = None) -> None:
    """Close the open questions of `sender` (default: of every agent of the session): no
    agent is left to get their answer."""
    db.execute(
        "UPDATE messages SET question_state = ? WHERE session = ? AND kind = ?"
        " AND question_state = ? AND (? IS NULL OR sender = ?)",
        (CLOSED, session, QUESTION, OPEN_QUESTION, sender, sender),
    )


def agent_ended(session: str, name: str, reason: str) -> list["Message"] | None:
    """The agent's process ended by itself: in one transaction, mark it stopped with an
    ENDED event for `reason`, drop the messages it never got (pending, or typed and not
    confirmed) and close its open questions. None, and nothing changed, when there is no
    such agent or it is stopped already (LADO ending it forgets or stops it before it kills
    its window, lado.runtime). Else the messages dropped, oldest first."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute(
            "SELECT 1 FROM agents WHERE session = ? AND name = ? AND status != ?",
            (session, name, STOPPED),
        ).fetchone():
            db.execute("COMMIT")
            return None
        _add_event(db, session, name, ENDED, reason)
        _set_status(db, session, name, STOPPED)
        where = "session = ? AND recipient = ? AND state IN (?, ?)"
        args = (session, name, PENDING, SENT)
        rows = db.execute(
            f"SELECT {MESSAGE_COLUMNS} FROM messages WHERE {where} ORDER BY id", args
        ).fetchall()
        db.execute(f"UPDATE messages SET state = ? WHERE {where}", (DROPPED, *args))
        _close_questions(db, session, name)
        db.execute("COMMIT")
    return [_message(r, state=DROPPED) for r in rows]


def set_status(session: str, name: str, status: str) -> None:
    """Set the agent's status and, if it changed, record a "status" event."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _set_status(db, session, name, status)
        db.execute("COMMIT")


def _set_status(db: sqlite3.Connection, session: str, name: str, status: str) -> None:
    # An agent that waits for nothing in particular has no key; one that stops waiting none.
    cur = db.execute(
        "UPDATE agents SET status = ?, waiting_for = NULL"
        " WHERE session = ? AND name = ? AND status != ?",
        (status, session, name, status),
    )
    if cur.rowcount:
        _add_event(db, session, name, STATUS, status)


def wait(session: str, name: str, key: str = "") -> None:
    """The agent waits for the human to answer request `key` (a provider's id for it; one
    open request at a time, so a new one replaces the key). Without a key it waits for
    nothing in particular, and a key it already waits for stays: only its answer, or a
    change of status, ends that wait."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _set_status(db, session, name, WAITING)
        if key:
            db.execute(
                "UPDATE agents SET waiting_for = ? WHERE session = ? AND name = ?",
                (key, session, name),
            )
        db.execute("COMMIT")


def resume(session: str, name: str, key: str) -> None:
    """The human answered request `key`: an agent waiting for it, or for no request in
    particular, works again. Any other agent stays as it is, so a late answer cannot undo
    an idle, starting or stopped agent, nor an answer to another request end its wait."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        cur = db.execute(
            "UPDATE agents SET status = ?, waiting_for = NULL WHERE session = ? AND name = ?"
            " AND status = ? AND (waiting_for IS NULL OR waiting_for = ?)",
            (BUSY, session, name, WAITING, key),
        )
        if cur.rowcount:
            _add_event(db, session, name, STATUS, BUSY)
        db.execute("COMMIT")


def seen(session: str, name: str) -> None:
    """Record that a hook of the agent ran now. The only writer of seen_at, which it sets
    alone: an update of it is no change for the UI (AGENTS_CHANGED). Its failed messages
    that no hook ran after (a dialog swallowed them) go back to the queue, with their
    attempts from 0. When it has messages that failed after its previous hook, why it waits
    (runtime.status_reason, from failed_counts) changes with seen_at: that is recorded as a
    change of the agent, which the UI then shows again."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE agents SET status = status WHERE session = ? AND name = ? AND EXISTS"
            " (SELECT 1 FROM messages m WHERE m.session = agents.session"
            " AND m.recipient = agents.name AND m.state = ? AND m.failed_at > agents.seen_at)",
            (session, name, FAILED),
        )
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


def end_reasons(session: str) -> dict[str, str]:
    """Per agent name, why its process ended last (its latest ENDED event's detail). Only an
    agent that ended by itself is stopped and still listed (agent_ended), so for such an
    agent this is why it stopped."""
    with connect() as db:
        rows = db.execute(
            "SELECT agent, detail FROM events WHERE id IN (SELECT MAX(id) FROM events"
            " WHERE session = ? AND kind = ? GROUP BY agent)",
            (session, ENDED),
        ).fetchall()
    return {r["agent"]: r["detail"] for r in rows}


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


def run_events(session: str) -> list[Event]:
    """The session's flow run events, oldest first."""
    with connect() as db:
        rows = db.execute(
            "SELECT id, agent, kind, detail, created_at, run FROM events"
            " WHERE session = ? AND run IS NOT NULL ORDER BY id",
            (session,),
        ).fetchall()
    return [Event(*r) for r in rows]


def last_run_event(session: str, run: str) -> Event | None:
    """The run's latest event: since when it is where it is, or when it ended."""
    with connect() as db:
        row = db.execute(
            "SELECT id, agent, kind, detail, created_at, run FROM events"
            " WHERE session = ? AND run = ? ORDER BY id DESC LIMIT 1",
            (session, run),
        ).fetchone()
    return Event(*row) if row else None


def get_note(session: str, note_id: int) -> Note | None:
    with connect() as db:
        row = db.execute(
            f"SELECT {NOTE_COLUMNS} FROM notes WHERE session = ? AND id = ?",
            (session, note_id),
        ).fetchone()
    return Note(*row) if row else None


def get_event(session: str, event_id: int) -> Event | None:
    with connect() as db:
        row = db.execute(
            "SELECT id, agent, kind, detail, created_at, run FROM events"
            " WHERE session = ? AND id = ?",
            (session, event_id),
        ).fetchone()
    return Event(*row) if row else None


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
                run.snapshot,
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
    noted: Noted | None = None,
) -> bool:
    """Write `after` and the events (actor, kind, detail) in one transaction, but only if
    the run still has the state, status and visits of `before`: entering a state counts a
    visit, so even a self-loop changes what the next writer compares. Returns whether it
    was written. In the same transaction `closes` closes the run's open gate (nothing is
    written if it names a gate that is not open), the gate `opens` is stored (its id
    set), and `after`'s note is kept as `noted` says, if given."""
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
                    "INSERT INTO notes (session, run, state, kind, actor, outcome, target,"
                    " summary, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        before.session,
                        before.name,
                        *astuple(noted),
                        after.note,
                        after.note_body,
                    ),
                )
        db.execute("COMMIT")
    return bool(cur.rowcount)


def latest_notes(session: str, run: str) -> dict[str, Note]:
    """The latest report kept from each state of the run; the human's overrides are not
    a state's report."""
    with connect() as db:
        rows = db.execute(
            f"SELECT {NOTE_COLUMNS} FROM notes WHERE id IN"
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
            f"SELECT {NOTE_COLUMNS} FROM notes WHERE session = ? AND run = ?"
            " ORDER BY id DESC LIMIT 1",
            (session, run),
        ).fetchone()
    return Note(*row) if row else None


def run_notes(session: str, run: str | None = None) -> list[Note]:
    """Every note of the session's runs (or of `run`), oldest first: the steps they took."""
    with connect() as db:
        rows = db.execute(
            f"SELECT {NOTE_COLUMNS} FROM notes WHERE session = ? AND (? IS NULL OR run = ?)"
            " ORDER BY id",
            (session, run, run),
        ).fetchall()
    return [Note(*r) for r in rows]


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


def session_gates(session: str) -> list[Gate]:
    """All gates of `session`, open and closed, oldest first."""
    with connect() as db:
        rows = db.execute("SELECT * FROM gates WHERE session = ? ORDER BY id", (session,))
        return [_gate(r) for r in rows.fetchall()]


@dataclass
class Waits:
    """One thing that waits for the human: an open gate, an open question to the human or
    an agent in `waiting`; exactly one of them is set."""

    session: str
    since: str  # UTC, as lado.db keeps it: when it opened, or the agent got `waiting`
    gate: Gate | None = None
    question: Message | None = None
    agent: Agent | None = None


NOT_STOPPED = "SELECT name FROM sessions WHERE stopped_at IS NULL AND (? IS NULL OR name = ?)"


def waiting_items(session: str | None = None) -> list[Waits]:
    """What waits for the human in `session` (default: in every session), oldest first:
    only in a session not stopped, since nothing in a stopped one can be answered."""
    with connect() as db:
        gates = db.execute(
            f"SELECT * FROM gates WHERE answer IS NULL AND session IN ({NOT_STOPPED})",
            (session, session),
        ).fetchall()
        questions = db.execute(
            f"SELECT {MESSAGE_COLUMNS}, session FROM messages WHERE kind = ?"
            f" AND question_state = ? AND session IN ({NOT_STOPPED})",
            (QUESTION, OPEN_QUESTION, session, session),
        ).fetchall()
        # An agent waits since it got `waiting` (STATUS_EVENTS, as status_since says); one
        # with no such event, written without LADO's runtime, since it was added.
        agents = db.execute(
            "SELECT a.*, COALESCE(e.created_at, a.created_at) AS since FROM agents a"
            f" LEFT JOIN ({STATUS_EVENTS}) e ON e.session = a.session AND e.agent = a.name"
            f" WHERE a.status = ? AND a.session IN ({NOT_STOPPED})",
            (*status_events_args(session), WAITING, session, session),
        ).fetchall()
    items = [Waits(r["session"], r["created_at"], gate=_gate(r)) for r in gates]
    items += [Waits(r["session"], r["created_at"], question=_message(r)) for r in questions]
    items += [Waits(r["session"], r["since"], agent=_agent(r)) for r in agents]
    return sorted(items, key=lambda waits: waits.since)


def waiting_for_human(session: str) -> tuple[int, int, int]:
    """What in the session waits for the human (waiting_items), counted: its open gates, its
    open questions to the human and its agents in `waiting`."""
    items = waiting_items(session)
    return (
        sum(w.gate is not None for w in items),
        sum(w.question is not None for w in items),
        sum(w.agent is not None for w in items),
    )


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


# When each agent of `session` (NULL: of every session; `agent` NULL: every agent) got its
# current status: its latest "status" or "spawned" event. The one rule for status_since,
# agent_times and waiting_items; its arguments: status_events_args(session, agent).
STATUS_EVENTS = (
    "SELECT session, agent, created_at FROM events WHERE id IN (SELECT MAX(id) FROM events"
    " WHERE kind IN (?, ?) AND (? IS NULL OR session = ?) AND (? IS NULL OR agent = ?)"
    " GROUP BY session, agent)"
)


def status_events_args(session: str | None, agent: str | None = None) -> tuple:
    return (STATUS, SPAWNED, session, session, agent, agent)


def status_since(session: str) -> dict[str, datetime.datetime]:
    """When each agent got its current status: its latest "status" or "spawned" event (UTC)."""
    with connect() as db:
        rows = db.execute(STATUS_EVENTS, status_events_args(session)).fetchall()
    return {r["agent"]: _utc(r["created_at"]) for r in rows}


def agent_times(
    session: str, agent: str
) -> tuple[datetime.datetime | None, datetime.datetime | None]:
    """When the agent of that name was last spawned and when it got its current status, as
    status_since says (UTC); None for what has no event."""
    with connect() as db:
        spawned = db.execute(
            "SELECT MAX(created_at) FROM events WHERE session = ? AND agent = ? AND kind = ?",
            (session, agent, SPAWNED),
        ).fetchone()[0]
        since = db.execute(STATUS_EVENTS, status_events_args(session, agent)).fetchone()
    return (
        _utc(spawned) if spawned else None,
        _utc(since["created_at"]) if since else None,
    )


MESSAGE_COLUMNS = (
    "id, sender, summary, body, recipient, state, created_at, attempts, sent_at, kind, choices,"
    " free_answer, question_state, answered_by, reply_to, choice, reply_state, channel"
)


def _message(row: sqlite3.Row, **changed) -> Message:
    """A row of MESSAGE_COLUMNS as a Message, with the `changed` fields."""
    choices = row["choices"]
    message = Message(
        *row[:9],
        kind=row["kind"],
        choices=None if choices is None else json.loads(choices),
        free_answer=bool(row["free_answer"]),
        question_state=row["question_state"],
        answered_by=row["answered_by"],
        reply_to=row["reply_to"],
        choice=row["choice"],
        reply_state=row["reply_state"],
        channel=row["channel"],
    )
    return replace(message, **changed) if changed else message


class NotRunning(Exception):
    """The recipient of a message is not a running agent: no agent of that name, or a
    stopped one."""

    def __init__(self, name: str):
        super().__init__(f'no running agent "{name}"')
        self.name = name


def _check_running(db: sqlite3.Connection, session: str, name: str) -> None:
    """Raise NotRunning unless `name` is a running agent. Called in the transaction that
    queues a message for it: an agent finished in between (deleted, its undelivered
    messages dropped) must not leave one for a later agent of the same name."""
    row = db.execute(
        "SELECT 1 FROM agents WHERE session = ? AND name = ? AND status != ?",
        (session, name, STOPPED),
    ).fetchone()
    if row is None:
        raise NotRunning(name)


def queue_message(
    session: str,
    sender: str,
    recipient: str,
    summary: str,
    body: str = "",
    mark: str = PENDING,
    before_start: bool = False,
) -> int:
    """Store a message in state `mark`: pending, or delivered when its line goes to the
    recipient another way (its first input, or the human's UI): then it is handed over
    now (sent_at). Returns its id.

    A pending message to an agent needs it running (NotRunning), but with `before_start`:
    the supervisor of a session being started, not stored yet, takes it as its first
    input."""
    sent_at = None if mark == PENDING else time.time()
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if mark == PENDING and recipient != HUMAN and not before_start:
            _check_running(db, session, recipient)
        cur = db.execute(
            "INSERT INTO messages (session, sender, recipient, summary, body, state, sent_at,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
            (session, sender, recipient, summary, body, mark, sent_at),
        )
        db.execute("COMMIT")
        return cur.lastrowid or 0


def queue_with_copy(
    session: str,
    sender: str,
    recipient: str,
    summary: str,
    body: str,
    copy_to: str,
    copy_summary: Callable[[int], str],
) -> int:
    """Queue a message and, in the same transaction, a copy from LADO to `copy_to` whose
    summary is `copy_summary(id of the message)`, without a body. Returns the message's id;
    NotRunning, with nothing queued, when the recipient does not run. When `copy_to` does
    not run, there is no copy: it would never be delivered."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _check_running(db, session, recipient)
        insert = (
            "INSERT INTO messages (session, sender, recipient, summary, body, created_at)"
            " VALUES (?, ?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))"
        )
        message = db.execute(insert, (session, sender, recipient, summary, body)).lastrowid
        with suppress(NotRunning):
            _check_running(db, session, copy_to)
            db.execute(insert, (session, LADO, copy_to, copy_summary(message), ""))
        db.execute("COMMIT")
    return message


def add_question(
    session: str,
    sender: str,
    question: str,
    details: str,
    choices: list[str] | None,
    free_answer: bool,
) -> int:
    """Store an agent's open question to the human, delivered: the UI shows it. Returns its
    id."""
    with connect() as db:
        cur = db.execute(
            "INSERT INTO messages (session, sender, recipient, summary, body, state, kind,"
            " choices, free_answer, question_state, sent_at, created_at) VALUES"
            " (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
            (
                session,
                sender,
                HUMAN,
                question,
                details,
                DELIVERED,
                QUESTION,
                None if choices is None else json.dumps(choices),
                int(free_answer),
                OPEN_QUESTION,
                time.time(),
            ),
        )
        return cur.lastrowid or 0


def reply_to_question(
    session: str, question: int, summary: str, body: str, choice: str | None, outcome: str
) -> int | None:
    """Queue the human's answer or dismissal of an open question to the agent that asked,
    and set the question's outcome (ANSWERED or DISMISSED), in one transaction. Returns the
    reply's id; None, with nothing changed, when the question is not open; NotRunning, with
    nothing changed, when the agent that asked does not run."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT sender, question_state FROM messages WHERE session = ? AND id = ? AND kind = ?",
            (session, question, QUESTION),
        ).fetchone()
        if row is not None:
            # First, as the asker's question is closed when it is finished.
            _check_running(db, session, row["sender"])
        if row is None or row["question_state"] != OPEN_QUESTION:
            db.execute("ROLLBACK")
            return None
        reply = db.execute(
            "INSERT INTO messages (session, sender, recipient, summary, body, reply_to, choice,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
            (session, HUMAN, row["sender"], summary, body, question, choice),
        ).lastrowid
        db.execute(
            "UPDATE messages SET question_state = ?, answered_by = ? WHERE id = ?",
            (outcome, reply, question),
        )
        db.execute("COMMIT")
    return reply


def check_replies(session: str, agent: str) -> None:
    """At the end of the agent's turn: each message from the human it got and that is not
    checked yet is REPLIED when the agent wrote to the human after it got it (a message or
    a question), else MISSING: it replied only in its terminal. Each one is checked once.
    Answers and dismissals of the agent's questions need no reply.

    "After it got it" compares when each was handed over (sent_at), not ids: the human's
    message gets its id when queued, and the agent may write to the human before it is
    handed over. A message to the human is handed over when stored."""
    with connect() as db:
        db.execute(
            "UPDATE messages SET reply_state = CASE WHEN EXISTS (SELECT 1 FROM messages r"
            " WHERE r.session = messages.session AND r.sender = messages.recipient"
            " AND r.recipient = ? AND r.sent_at > messages.sent_at) THEN ? ELSE ? END"
            " WHERE session = ? AND sender = ? AND recipient = ? AND state IN (?, ?)"
            " AND reply_state IS NULL AND reply_to IS NULL",
            (HUMAN, REPLIED, MISSING, session, HUMAN, agent, DELIVERED, READ),
        )


def get_message(session: str, message_id: int) -> Message | None:
    with connect() as db:
        row = db.execute(
            f"SELECT {MESSAGE_COLUMNS} FROM messages WHERE session = ? AND id = ?",
            (session, message_id),
        ).fetchone()
    return _message(row) if row else None


def list_messages(session: str, after: int = 0) -> list[Message]:
    """The session's messages with an id above `after`, oldest first."""
    with connect() as db:
        rows = db.execute(
            f"SELECT {MESSAGE_COLUMNS} FROM messages WHERE session = ? AND id > ? ORDER BY id",
            (session, after),
        ).fetchall()
    return [_message(r) for r in rows]


@dataclass(frozen=True)
class MessageFilter:
    """Which of a session's messages a page of them takes (the UI's chat and Agents tab):
    from or to `with_` and `agent`, ids between the cursors `after` and `before`, and
    `created_at` from `since` to `until`, both in lado.db's form; `until` is exclusive."""

    with_: str | None = None
    agent: str | None = None
    before: int | None = None
    after: int | None = None
    since: str | None = None
    until: str | None = None

    def where(self, cursors: bool = True) -> tuple[str, list]:
        """The SQL condition and its parameters; without the cursors when not `cursors`."""
        terms, params = ["session = ?"], []
        for name in (self.with_, self.agent):
            if name is not None:
                terms.append("(sender = ? OR recipient = ?)")
                params += [name, name]
        if self.since is not None:
            terms.append("created_at >= ?")
            params.append(self.since)
        if self.until is not None:
            terms.append("created_at < ?")
            params.append(self.until)
        if cursors and self.before is not None:
            terms.append("id < ?")
            params.append(self.before)
        if cursors and self.after is not None:
            terms.append("id > ?")
            params.append(self.after)
        return " AND ".join(terms), params


def message_page(
    session: str, where: MessageFilter, limit: int | None = None
) -> tuple[list[Message], bool]:
    """The latest `limit` messages that match (all without a limit), oldest first, and
    whether messages of the same kind and times come before the first of them (the cursors
    aside: a range up to a page still says what lies before it)."""
    condition, params = where.where()
    with connect() as db:
        if limit is None:
            rows = db.execute(
                f"SELECT {MESSAGE_COLUMNS} FROM messages WHERE {condition} ORDER BY id",
                [session, *params],
            ).fetchall()
        else:
            rows = db.execute(
                f"SELECT {MESSAGE_COLUMNS} FROM messages WHERE {condition}"
                " ORDER BY id DESC LIMIT ?",
                [session, *params, limit],
            ).fetchall()[::-1]
        if rows:
            first = rows[0]["id"]
        elif where.before is not None:
            first = where.before
        else:
            first = 0 if where.after is None else where.after + 1
        kind, kind_params = where.where(cursors=False)
        earlier = db.execute(
            f"SELECT EXISTS (SELECT 1 FROM messages WHERE {kind} AND id < ?)",
            [session, *kind_params, first],
        ).fetchone()[0]
    return [_message(r) for r in rows], bool(earlier)


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
    return [_message(r, state=READ) for r in rows]


def take_pending(
    session: str,
    recipient: str,
    mark: str,
    status: str | None = None,
    idle_only: bool = False,
    channel: str | None = None,
) -> list[Message]:
    """Move all pending messages for `recipient` to `mark`, by `channel`, and return them,
    oldest first; when there are any and `status` is given, set the recipient's status too.
    `idle_only`: take none unless the recipient is idle and no message handed over to it is
    unconfirmed. Every hand-over to an agent takes them so (lado.runtime.hand_over): an
    agent never has more than one batch of sent messages at a time.

    Runs in one write transaction, so two concurrent callers never get the same message,
    and no one sees the messages moved without the status that goes with them.
    """
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if (
            idle_only
            and not db.execute(
                "SELECT 1 FROM agents WHERE session = ? AND name = ? AND status = ?"
                " AND NOT EXISTS (SELECT 1 FROM messages WHERE session = agents.session"
                " AND recipient = agents.name AND state = ?)",
                (session, recipient, IDLE, SENT),
            ).fetchone()
        ):
            db.execute("ROLLBACK")
            return []
        rows = db.execute(
            f"SELECT {MESSAGE_COLUMNS} FROM messages"
            " WHERE session = ? AND recipient = ? AND state = ? ORDER BY id",
            (session, recipient, PENDING),
        ).fetchall()
        # Sent, it is an attempt (lado.runtime.sweep); handed over another way, it is
        # delivered and needs none.
        attempt = 1 if mark == SENT else 0
        db.executemany(
            "UPDATE messages SET state = ?, sent_at = ?, attempts = attempts + ?, channel = ?"
            " WHERE id = ?",
            [(mark, time.time(), attempt, channel, r["id"]) for r in rows],
        )
        if rows and status:
            _set_status(db, session, recipient, status)
        db.execute("COMMIT")
    return [_message(r, state=mark, channel=channel) for r in rows]


@dataclass
class Plan:
    """What to do with an agent's unconfirmed messages (lado.runtime.sweep decides)."""

    # Type its sent and pending messages (again), as one text: by the TYPED channel.
    retype: bool = False
    requeue: list[int] = field(default_factory=list)  # back to pending
    fail: list[int] = field(default_factory=list)
    wait: bool = False  # set the agent waiting


@dataclass
class Swept:
    typed: list[Message]  # marked typed again: type them into the window, as one text
    failed: list[Message]


def sweep(
    session: str, name: str, now: float, decide: Callable[[Agent, list[Message]], Plan]
) -> Swept:
    """Carry out `decide(agent, its sent messages)` in one write transaction, so two
    sweeps never type the same message twice."""
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT * FROM agents WHERE session = ? AND name = ?", (session, name)
        ).fetchone()
        if row is None:
            db.execute("ROLLBACK")
            return Swept([], [])
        agent = _agent(row)
        query = (
            f"SELECT {MESSAGE_COLUMNS} FROM messages WHERE session = ? AND recipient = ?"
            " AND state IN ({}) ORDER BY id"
        )
        sent = [_message(r) for r in db.execute(query.format("?"), (session, name, SENT))]
        plan = decide(agent, sent)
        failed = [m for m in sent if m.id in plan.fail]
        db.executemany(
            "UPDATE messages SET state = ?, failed_at = ? WHERE id = ?",
            [(FAILED, now, i) for i in plan.fail] + [(PENDING, None, i) for i in plan.requeue],
        )
        if plan.wait:
            _set_status(db, session, name, WAITING)
        typed = []
        if plan.retype:
            rows = db.execute(query.format("?, ?"), (session, name, SENT, PENDING)).fetchall()
            db.executemany(
                "UPDATE messages SET state = ?, sent_at = ?, attempts = attempts + 1,"
                " channel = ? WHERE id = ?",
                [(SENT, now, TYPED, r["id"]) for r in rows],
            )
            typed = [_message(r, state=SENT, channel=TYPED) for r in rows]
        db.execute("COMMIT")
    return Swept(typed, [replace(m, state=FAILED) for m in failed])


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
        confirmed = [(DELIVERED, r["id"]) for r in rows if typed(_message(r)) in prompt]
        db.executemany("UPDATE messages SET state = ? WHERE id = ?", confirmed)


def confirm_channel(session: str, recipient: str, channel: str) -> None:
    """Mark the recipient's sent messages that went by `channel` delivered: its CLI says it
    took them, without their lines (lado.hooks: a turn that went on from the hook's
    output)."""
    with connect() as db:
        db.execute(
            "UPDATE messages SET state = ? WHERE session = ? AND recipient = ? AND state = ?"
            " AND channel = ?",
            (DELIVERED, session, recipient, SENT, channel),
        )


def output_not_taken(session: str, recipient: str, since: float = 0) -> None:
    """The recipient's sent messages that went in a turn-end hook's output (since `since`)
    did not reach its CLI: the turn ended without going on from them, or the hook failed
    before it printed them. They go by the TYPED channel from now on, so only their lines
    confirm them, never a later turn that went on from another Stop hook's output."""
    with connect() as db:
        db.execute(
            "UPDATE messages SET channel = ? WHERE session = ? AND recipient = ? AND state = ?"
            " AND channel = ? AND sent_at >= ?",
            (TYPED, session, recipient, SENT, HOOK_OUTPUT, since),
        )


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
        waiting_for=row["waiting_for"],
        created_at=row["created_at"],
    )


def _run(row: sqlite3.Row) -> Run:
    return Run(
        session=row["session"],
        name=row["name"],
        flow=row["flow"],
        snapshot=row["snapshot"],
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


def list_marketplaces() -> list[Marketplace]:
    with connect() as db:
        rows = db.execute("SELECT * FROM marketplaces ORDER BY name").fetchall()
    return [_marketplace(row) for row in rows]


def get_marketplace(name: str) -> Marketplace | None:
    with connect() as db:
        row = db.execute("SELECT * FROM marketplaces WHERE name = ?", (name,)).fetchone()
    return _marketplace(row) if row else None


def add_marketplace(name: str, url: str) -> bool:
    """False, with nothing changed, when a marketplace of that name exists already."""
    with connect() as db:
        added = db.execute(
            "INSERT OR IGNORE INTO marketplaces (name, url) VALUES (?, ?)", (name, url)
        ).rowcount
    return added == 1


def update_marketplace(
    name: str, *, enabled: bool | None = None, updated_at: str | None = None
) -> None:
    """Set what is given of a marketplace: whether it is enabled, when it was updated."""
    with connect() as db:
        if enabled is not None:
            db.execute("UPDATE marketplaces SET enabled = ? WHERE name = ?", (enabled, name))
        if updated_at is not None:
            db.execute("UPDATE marketplaces SET updated_at = ? WHERE name = ?", (updated_at, name))


def delete_marketplace(name: str) -> bool:
    """False when there is no marketplace of that name."""
    with connect() as db:
        return db.execute("DELETE FROM marketplaces WHERE name = ?", (name,)).rowcount == 1


def list_kits() -> list[InstalledKit]:
    with connect() as db:
        rows = db.execute("SELECT * FROM kits ORDER BY name").fetchall()
    return [InstalledKit(**dict(row)) for row in rows]


def get_kit(name: str) -> InstalledKit | None:
    with connect() as db:
        row = db.execute("SELECT * FROM kits WHERE name = ?", (name,)).fetchone()
    return InstalledKit(**dict(row)) if row else None


def add_kit(kit: InstalledKit) -> bool:
    """False, with nothing changed, when a kit of that name is installed already. An
    incomplete row is an IntegrityError (not OR IGNORE: that would pass over CHECK too)."""
    with connect() as db:
        added = db.execute(
            'INSERT INTO kits (name, address, tag, "commit", folder, marketplace) '
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (name) DO NOTHING",
            (kit.name, kit.address, kit.tag, kit.commit, kit.folder, kit.marketplace),
        ).rowcount
    return added == 1


def replace_kit(name: str, address: str, tag: str, commit: str) -> bool:
    """Move kit `name`, installed from git, to another version; where it came from and
    when it was installed stay. False when no kit of that name is installed."""
    with connect() as db:
        changed = db.execute(
            'UPDATE kits SET address = ?, tag = ?, "commit" = ?, '
            "updated_at = datetime('now') WHERE name = ?",
            (address, tag, commit, name),
        ).rowcount
    return changed == 1


def delete_kit(name: str) -> bool:
    """False when no kit of that name is installed."""
    with connect() as db:
        return db.execute("DELETE FROM kits WHERE name = ?", (name,)).rowcount == 1


def _marketplace(row: sqlite3.Row) -> Marketplace:
    return Marketplace(row["name"], row["url"], bool(row["enabled"]), row["updated_at"])


def _session(row: sqlite3.Row) -> Session:
    return Session(
        row["name"],
        row["repo"],
        row["permission_mode"],
        row["provider"],
        json.loads(row["kits"]),
        json.loads(row["switched_off"]),
        row["stopped_at"],
        row["created_at"],
    )
