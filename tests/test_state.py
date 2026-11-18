import contextlib
import dataclasses
import json
import re
import sqlite3
import time
from pathlib import Path

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
    assert state.migrate().after == state.SCHEMA_VERSION
    assert state.get_session("s").provider == "claude"
    agent = state.get_agent("s", "supervisor")
    assert (agent.provider, agent.instance, agent.status) == ("claude", "abc", "idle")
    with state.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == state.SCHEMA_VERSION


def test_a_commit_does_not_wait_for_the_disk(lado_home):
    """WAL with synchronous NORMAL (1): a commit holds the write lock without an fsync."""
    with state.connect() as db:
        assert db.execute("PRAGMA synchronous").fetchone()[0] == 1
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_the_migration_does_not_wait_for_the_disk_either(lado_home, monkeypatch):
    lado_home.mkdir()
    sqlite3.connect(lado_home / "lado.db").executescript(SCHEMA_V1)
    opened, settings = state._open, []

    def spied():
        db = opened()
        settings.append(
            (
                db.execute("PRAGMA synchronous").fetchone()[0],
                db.execute("PRAGMA journal_mode").fetchone()[0],
            )
        )
        return db

    monkeypatch.setattr(state, "_open", spied)
    assert state.migrate().after == state.SCHEMA_VERSION
    assert settings and set(settings) == {(1, "wal")}


def test_the_official_marketplace_is_in_a_new_database_and_after_the_migration(lado_home):
    official = state.Marketplace("official", None, True, None)
    assert state.list_marketplaces() == [official]
    agent_helpers.schema_before(17)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    names = {row[0] for row in db.execute("SELECT name FROM sqlite_master")}
    db.close()
    assert not any("marketplaces" in name for name in names)
    state.migrate()
    assert state.list_marketplaces() == [official]
    with state.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == state.SCHEMA_VERSION


def test_the_kits_table_is_made_by_the_migration(lado_home):
    state.add_kit(state.InstalledKit("team", folder="/dev/team"))
    agent_helpers.schema_before(18)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    names = {row[0] for row in db.execute("SELECT name FROM sqlite_master")}
    version = db.execute("PRAGMA user_version").fetchone()[0]
    db.close()
    assert version == 17 and not any("kits" in name for name in names)
    state.migrate()
    assert state.list_kits() == []
    with state.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == state.SCHEMA_VERSION
        columns = [row["name"] for row in db.execute("PRAGMA table_info(kits)")]
    assert columns == [
        "name",
        "address",
        "tag",
        "commit",
        "folder",
        "marketplace",
        "installed_at",
        "updated_at",
    ]


def test_installed_kits_are_added_replaced_and_removed(lado_home):
    git = state.InstalledKit(
        "team", address="file:///team.git", tag="v1.0.0", commit="abc", marketplace="ours"
    )
    assert state.add_kit(git)
    assert not state.add_kit(state.InstalledKit("team", folder="/dev/team"))
    assert state.add_kit(state.InstalledKit("local", folder="/dev/local"))
    team = state.get_kit("team")
    assert dataclasses.replace(team, installed_at=None) == git
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", team.installed_at)
    assert team.updated_at is None
    assert [k.name for k in state.list_kits()] == ["local", "team"]
    # An update moves the version and keeps where it came from and when it was installed.
    assert state.replace_kit("team", "file:///team.git", "v1.1.0", "def") is True
    updated = state.get_kit("team")
    assert (updated.tag, updated.commit, updated.marketplace) == ("v1.1.0", "def", "ours")
    assert updated.installed_at == team.installed_at and updated.updated_at is not None
    assert state.delete_kit("team")
    assert not state.delete_kit("team")
    assert state.get_kit("team") is None
    # Nothing to move: the kit is gone.
    assert state.replace_kit("team", "file:///team.git", "v1.2.0", "123") is False
    assert state.get_kit("team") is None


def test_an_incomplete_kit_row_is_an_error_not_a_name_taken(lado_home):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        state.add_kit(state.InstalledKit("team", address="file:///team.git", tag="v1.0.0"))


def test_marketplaces_are_added_changed_and_removed(lado_home):
    assert state.add_marketplace("team", "file:///m.git")
    assert not state.add_marketplace("team", "file:///other.git")
    state.update_marketplace("team", enabled=False)
    state.update_marketplace("team", updated_at="2026-10-05 10:00:00")
    assert state.get_marketplace("team") == state.Marketplace(
        "team", "file:///m.git", False, "2026-10-05 10:00:00"
    )
    assert [m.name for m in state.list_marketplaces()] == ["official", "team"]
    assert state.delete_marketplace("team")
    assert not state.delete_marketplace("team")
    assert state.get_marketplace("team") is None


@pytest.mark.parametrize(
    ("setup", "kind"),
    [
        ("PRAGMA user_version = 99", state.NEWER),
        ("CREATE TABLE sessions (name TEXT)", state.INCOMPATIBLE),
        (f"PRAGMA user_version = {min(state.MIGRATIONS)}", state.OLDER),
    ],
)
def test_the_refusal_of_a_schema_is_read_without_a_change(lado_home, setup, kind):
    lado_home.mkdir()
    sqlite3.connect(lado_home / "lado.db").execute(setup)
    before = (lado_home / "lado.db").read_bytes()
    found, text = state.read_schema_refusal()
    assert (lado_home / "lado.db").read_bytes() == before
    with pytest.raises(state.SchemaError) as refused:
        state.list_sessions()
    assert (found, text) == (kind, str(refused.value))  # connect()'s words


def test_no_refusal_of_this_schema_or_no_database(lado_home):
    assert state.read_schema_refusal() is None
    assert not lado_home.exists()  # read only: LADO_HOME not made
    state.list_sessions()
    assert state.read_schema_refusal() is None


def test_the_migration_gives_messages_their_channel(lado_home):
    _session_with(_agent(status=state.IDLE))
    old = state.queue_message("s", "supervisor", "w1", "before")
    agent_helpers.schema_before(19)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    columns = [row[1] for row in db.execute("PRAGMA table_info(messages)")]
    db.close()
    assert "channel" not in columns
    assert state.migrate().after == state.SCHEMA_VERSION
    assert state.get_message("s", old).channel is None
    state.take_pending("s", "w1", state.SENT, channel=state.HOOK_OUTPUT)
    assert state.get_message("s", old).channel == state.HOOK_OUTPUT


def test_the_migration_gives_messages_their_print_mark(lado_home):
    _session_with(_agent(status=state.BUSY))
    old = state.queue_message("s", "supervisor", "w1", "before")
    agent_helpers.schema_before(24)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    columns = [row[1] for row in db.execute("PRAGMA table_info(messages)")]
    db.close()
    assert "printed_at" not in columns
    assert state.migrate().after == state.SCHEMA_VERSION
    assert state.get_message("s", old).printed_at is None


def test_the_migration_gives_agents_their_resumes(lado_home):
    _session_with(_agent(status=state.BUSY))
    agent_helpers.schema_before(20)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    columns = [row[1] for row in db.execute("PRAGMA table_info(agents)")]
    db.close()
    assert "resume_at" not in columns and "resumes" not in columns
    assert state.migrate().after == state.SCHEMA_VERSION
    agent = state.get_agent("s", "w1")
    assert (agent.resume_at, agent.resumes) == (None, 0)
    assert state.schedule_resume("s", "w1", 100.0, (30.0,)) == 1
    agent = state.get_agent("s", "w1")
    assert (agent.resume_at, agent.resumes) == (130.0, 1)


ARTIFACT_OBJECTS = (
    "SELECT type, name, sql FROM sqlite_master WHERE name LIKE '%artifact%'"
    " OR name LIKE '%attachments%' ORDER BY name"
)


def test_the_migration_makes_the_artifact_tables_as_a_new_database_has_them(lado_home):
    _session_with(_agent(status=state.BUSY))
    with state.connect() as db:
        fresh = [tuple(row) for row in db.execute(ARTIFACT_OBJECTS)]
    assert {name for _, name, _ in fresh} == {
        "artifacts",
        "artifact_records",
        "attachments",
        *(f"changes_{t}_{op}" for t in ("artifacts", "artifact_records") for op in state.ALL_OPS),
    } | {name for _, name, _ in fresh if name.startswith("sqlite_autoindex")}
    agent_helpers.schema_before(21)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert db.execute(ARTIFACT_OBJECTS).fetchall() == []
    db.close()
    assert state.migrate().after == state.SCHEMA_VERSION
    with state.connect() as db:
        assert [tuple(row) for row in db.execute(ARTIFACT_OBJECTS)] == fresh


GATES_TABLE = "SELECT sql FROM sqlite_master WHERE name = 'gates'"


def test_the_migration_gives_gates_the_note_before_them_as_a_new_database_has_it(lado_home):
    _session_with(_agent(status=state.BUSY))
    with state.connect() as db:
        fresh = db.execute(GATES_TABLE).fetchone()[0]
        db.execute(
            "INSERT INTO gates (session, run, state, kind, question, options)"
            " VALUES ('s', 'f/x', 'ok', 'approval', 'Ship?', '[]')"
        )
    assert "note_id" in fresh
    agent_helpers.schema_before(22)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert "note_id" not in db.execute(GATES_TABLE).fetchone()[0]
    db.close()
    assert state.migrate().after == state.SCHEMA_VERSION
    with state.connect() as db:
        assert db.execute(GATES_TABLE).fetchone()[0] == fresh
    [old] = state.session_gates("s")
    assert old.note_id is None


PROJECTS_TABLE = "SELECT sql FROM sqlite_master WHERE name = 'projects'"


def test_the_migration_makes_the_projects_table_as_a_new_database_has_it(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    with state.connect() as db:
        fresh = db.execute(PROJECTS_TABLE).fetchone()[0]
    agent_helpers.schema_before(32)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert db.execute(PROJECTS_TABLE).fetchone() is None
    db.close()
    migrated = state.migrate()
    assert (migrated.before, migrated.after) == (31, state.SCHEMA_VERSION)
    assert migrated.backup == lado_home / "backups" / "lado.db.schema-31"
    with state.connect() as db:
        assert db.execute(PROJECTS_TABLE).fetchone()[0] == fresh
    assert state.list_projects() == []


def test_projects_kept_in_lado_db(lado_home):
    with state.creating_project("shop", "Shop"):
        pass
    with state.creating_project("acme", None):
        pass
    with pytest.raises(sqlite3.IntegrityError):
        with state.creating_project("shop", "Again"):
            pass
    assert [p.id for p in state.list_projects()] == ["acme", "shop"]
    shop = state.get_project("shop")
    assert (shop.id, shop.title) == ("shop", "Shop")
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", shop.created_at)  # UTC
    assert state.get_project("nope") is None
    assert state.set_project_title("shop", "Shop EU") is True
    assert state.get_project("shop").title == "Shop EU"
    assert state.set_project_title("shop", None) is True
    assert state.get_project("shop").title is None
    assert state.set_project_title("nope", "x") is False
    assert state.delete_project("acme") is True
    assert state.delete_project("acme") is False
    assert [p.id for p in state.list_projects()] == ["shop"]


SESSIONS_TABLE = "SELECT sql FROM sqlite_master WHERE name = 'sessions'"


def test_the_migration_gives_sessions_no_project_as_a_new_database_has_it(lado_home):
    state.add_session(state.Session("site", "/ws/projects/shop/site", None, provider="claude"))
    with state.connect() as db:
        fresh = db.execute(SESSIONS_TABLE).fetchone()[0]
    agent_helpers.schema_before(33)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert "project" not in db.execute(SESSIONS_TABLE).fetchone()[0]
    db.close()
    migrated = state.migrate()
    assert (migrated.before, migrated.after) == (32, state.SCHEMA_VERSION)
    assert migrated.backup == lado_home / "backups" / "lado.db.schema-32"
    with state.connect() as db:
        assert db.execute(SESSIONS_TABLE).fetchone()[0] == fresh
    assert state.get_session("site").project is None  # never taken from the path


def test_a_project_with_sessions_keeps_its_record(lado_home):
    with state.creating_project("shop", None):
        pass
    state.add_session(state.Session("a", "/r/a", None, provider="claude", project="shop"))
    with pytest.raises(sqlite3.IntegrityError):
        state.delete_project("shop")
    state.delete_session("a")
    assert state.delete_project("shop") is True


def test_the_migration_marks_the_windows_of_the_agents_there_as_opened(lado_home):
    """They were started by an older LADO and run: the window check treats them as before."""
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(state.Agent("s", "w1", "worker", "/r", None, None, "idle", "claude"))
    agent_helpers.schema_before(35)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    columns = _agent_columns(db)
    db.close()
    assert "window_at" not in columns
    migrated = state.migrate()
    assert (migrated.before, migrated.after) == (34, state.SCHEMA_VERSION)
    agent = state.get_agent("s", "w1")
    assert agent.window_at == agent.created_at != ""


def test_an_agent_has_no_window_mark_until_its_window_opened(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(state.Agent("s", "w1", "worker", "/r", None, None, "starting", "claude"))
    assert state.get_agent("s", "w1").window_at is None
    state.window_opened("s", "w1")
    assert state.get_agent("s", "w1").window_at
    state.window_opened("s", "gone")  # a spawn that failed forgot it: no error


def _model(agent: state.Agent) -> tuple:
    return (
        agent.model,
        agent.model_source,
        agent.model_detail,
        agent.effort,
        agent.effort_source,
        agent.effort_detail,
    )


CLI_DEFAULT_MODEL = (None, "cli", None, None, "cli", None)


def _last_change() -> int:
    with state.connect() as db:
        return db.execute("SELECT coalesce(max(id), 0) FROM changes").fetchone()[0]


def test_the_migration_gives_the_agents_there_the_clis_default(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(state.Agent("s", "w1", "worker", "/r", None, None, "idle", "claude"))
    agent_helpers.schema_before(36)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    columns = _agent_columns(db)
    db.close()
    assert "model" not in columns
    migrated = state.migrate()
    assert (migrated.before, migrated.after) == (35, state.SCHEMA_VERSION)
    assert _model(state.get_agent("s", "w1")) == CLI_DEFAULT_MODEL


@pytest.mark.parametrize(
    ("source", "detail", "words"),
    [
        ("cli", None, "CLI default"),
        ("cli-config", None, "your Codex config"),
        ("cli-config", "profile work", "your Codex config, profile work"),
        ("session", None, "chosen for the session"),
        ("default", None, "default in Settings"),
        ("supervisor", None, "chosen by the supervisor"),
        ("cli-changed", None, "changed in the agent CLI"),
        ("server", None, "server"),  # a newer LADO's token: shown as it is
        ("server", "x", "server, x"),
    ],
)
def test_source_words(source, detail, words):
    assert state.source_words(source, detail, "Codex") == words
    assert state.source_words(source, detail, "Codex CLI") == words  # the CLI's own name


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        "null",
        "{}",
        '{"light": {"cli": "codex", "model": "a"}}',  # no row an agent takes
        '{"normal": "codex"}',
        '{"normal": {"cli": "codex"}}',
        '{"normal": {"model": "a"}}',
        '{"normal": {"cli": 1, "model": "a"}}',
        '{"normal": {"cli": "codex", "model": null}}',
        '{"normal": {"cli": "codex", "model": "a", "model_id": 7}}',
        '{"normal": {"cli": "codex", "model": "a"}, "heavy": 1}',
    ],
)
def test_a_table_that_cannot_be_read_is_unreadable(text):
    assert state.PowerTable.from_json(text) == state.PowerTable.unreadable()
    assert not state.PowerTable.from_json(text).readable


def test_the_migration_gives_sessions_no_power(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="codex"))
    agent_helpers.schema_before(37)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    columns = _session_columns(db)
    db.close()
    assert "power" not in columns
    migrated = state.migrate()
    assert (migrated.before, migrated.after) == (36, state.SCHEMA_VERSION)
    assert state.get_session("s").power is None


def _unread_session() -> None:
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(state.Agent("s", "w1", "worker", "/r", None, None, "idle", "claude"))


def _unread(mark: str, body: str = "the text", attachments=()) -> int:
    """A message to w1 with something to read (or not), in state `mark`."""
    return state.queue_message(
        "s", "supervisor", "w1", "a note", body, mark=mark, attachments=attachments
    )


def test_check_unread_marks_a_delivered_text_reminded_once(lado_home):
    _unread_session()
    first = _unread(state.DELIVERED)
    second = _unread(state.DELIVERED, body="", attachments=[("a1", "r1")])
    assert [m.id for m in state.check_unread("s", "w1")] == [first, second]
    assert state.check_unread("s", "w1") == []  # each one once
    assert state.get_message("s", first).state == state.DELIVERED  # still unread


@pytest.mark.parametrize("mark", [state.PENDING, state.SENT, state.READ, state.DROPPED])
def test_check_unread_leaves_a_text_not_delivered_or_already_read(lado_home, mark):
    _unread_session()
    _unread(mark)
    assert state.check_unread("s", "w1") == []


def test_check_unread_reminds_a_sent_text_once_it_is_delivered(lado_home):
    _unread_session()
    sent = _unread(state.SENT)
    assert state.check_unread("s", "w1") == []
    with state.connect() as db:
        db.execute("UPDATE messages SET state = ? WHERE id = ?", (state.DELIVERED, sent))
    assert [m.id for m in state.check_unread("s", "w1")] == [sent]


def test_check_unread_leaves_a_line_with_nothing_to_read(lado_home):
    _unread_session()
    _unread(state.DELIVERED, body="")
    assert state.check_unread("s", "w1") == []


def test_check_unread_looks_at_the_agents_own_messages_only(lado_home):
    _unread_session()
    state.add_agent(state.Agent("s", "w2", "worker", "/r", None, None, "idle", "claude"))
    state.queue_message("s", "supervisor", "w2", "a note", "the text", mark=state.DELIVERED)
    assert state.check_unread("s", "w1") == []


def test_the_migration_marks_the_messages_there_reminded(lado_home):
    """Left unread under an older LADO: not reminded after the update."""
    _unread_session()
    _unread(state.DELIVERED)
    agent_helpers.schema_before(40)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    columns = _message_columns(db)
    db.close()
    assert "read_reminded" not in columns
    migrated = state.migrate()
    assert (migrated.before, migrated.after) == (39, state.SCHEMA_VERSION)
    assert state.check_unread("s", "w1") == []
    later = _unread(state.DELIVERED)
    assert [m.id for m in state.check_unread("s", "w1")] == [later]


def _codex_agent_with_a_config_model():
    state.add_session(state.Session("s", "/r", None, provider="codex"))
    state.add_agent(state.Agent("s", "w1", "worker", "/r", None, None, "starting", "codex"))
    state.set_model(
        "s",
        "w1",
        state.Choice("gpt-5.6-sol", state.CLI_CONFIG, "profile work"),
        state.Choice("high", state.CLI_CONFIG, "profile work"),
    )


def test_a_different_model_is_the_clis(lado_home):
    _codex_agent_with_a_config_model()
    before = _last_change()
    state.report_model("s", "w1", "gpt-5.5", None)
    assert _model(state.get_agent("s", "w1")) == (
        "gpt-5.5",
        "cli-changed",
        None,
        "high",
        "cli-config",
        "profile work",
    )
    assert _last_change() == before + 1


def test_an_effort_reported_as_the_clis_default_clears_the_name(lado_home):
    """The OpenCode family names its model with each prompt, and no variant then means the
    model's default one: the effort goes back to the CLI's default."""
    state.add_session(state.Session("s", "/r", None, provider="opencode"))
    state.add_agent(state.Agent("s", "w1", "worker", "/r", None, None, "idle", "opencode"))
    state.report_model("s", "w1", "anthropic/claude-sonnet-5-5", "high")
    before = _last_change()
    state.report_model("s", "w1", "anthropic/claude-sonnet-5-5", "")
    assert _model(state.get_agent("s", "w1"))[3:] == (None, "cli", None)
    assert _last_change() == before + 1
    state.report_model("s", "w1", "anthropic/claude-sonnet-5-5", "")  # the default again
    assert _last_change() == before + 1
    # A chosen effort the CLI says it does not run is the CLI's default.
    state.set_model("s", "w1", None, state.Choice("high", state.CLI_CONFIG, "profile work"))
    state.report_model("s", "w1", "", "")
    assert _model(state.get_agent("s", "w1"))[3:] == (None, "cli", None)


PROJECT_VARIABLES_TABLE = "SELECT sql FROM sqlite_master WHERE name = 'project_variables'"


def test_the_migration_makes_the_project_variables_table_as_a_new_database_has_it(lado_home):
    with state.creating_project("shop", "Shop"):
        pass
    state.add_session(state.Session("site", "/r", None, provider="claude", project="shop"))
    with state.connect() as db:
        fresh = db.execute(PROJECT_VARIABLES_TABLE).fetchone()[0]
    agent_helpers.schema_before(34)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert db.execute(PROJECT_VARIABLES_TABLE).fetchone() is None
    db.close()
    migrated = state.migrate()
    assert (migrated.before, migrated.after) == (33, state.SCHEMA_VERSION)
    assert migrated.backup == lado_home / "backups" / "lado.db.schema-33"
    with state.connect() as db:
        assert db.execute(PROJECT_VARIABLES_TABLE).fetchone()[0] == fresh
    assert state.get_project("shop").title == "Shop"
    assert state.get_session("site").project == "shop"
    assert state.project_variables("shop") == {}


def test_the_migration_gives_agents_their_read_only_flag(lado_home):
    _session_with(_agent(status=state.BUSY))
    agent_helpers.schema_before(25)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert "read_only" not in [row[1] for row in db.execute("PRAGMA table_info(agents)")]
    db.close()
    assert state.migrate().after == state.SCHEMA_VERSION
    assert state.get_agent("s", "w1").read_only is False
    state.add_agent(
        state.Agent(
            "s", "w2", "reviewer", "/w", None, None, state.STARTING, "claude", read_only=True
        )
    )
    assert state.get_agent("s", "w2").read_only is True


def test_setting_a_title_is_journaled_as_a_session_update(lado_home):
    state.add_session(state.Session("s", "/r", None, "claude"))
    with state.connect() as db:
        after = db.execute("SELECT max(id) FROM changes").fetchone()[0]
    state.set_title("s", "Review")
    with state.connect() as db:
        rows = db.execute("SELECT kind, session, op FROM changes WHERE id > ?", (after,)).fetchall()
    assert [tuple(row) for row in rows] == [("sessions", "s", "update")]


def test_a_new_project_title_is_journaled_as_an_update_of_its_sessions_alone(lado_home):
    with state.creating_project("shop", "Shop"):
        pass
    state.add_session(state.Session("a", "/a", None, "claude", project="shop"))
    state.add_session(state.Session("b", "/b", None, "claude"))
    with state.connect() as db:
        after = db.execute("SELECT max(id) FROM changes").fetchone()[0]
    assert state.set_project_title("nope", "x") is False
    assert state.set_project_title("shop", "Shop EU") is True
    with state.connect() as db:
        rows = db.execute("SELECT kind, session, op FROM changes WHERE id > ?", (after,)).fetchall()
    assert [tuple(row) for row in rows] == [("sessions", "a", "update")]


def test_schema_28_gives_sessions_a_title(lado_home):
    state.add_session(state.Session("s", "/r", None, "claude"))
    with state.connect() as db:
        fresh = db.execute("SELECT sql FROM sqlite_master WHERE name = 'sessions'").fetchone()[0]
    agent_helpers.schema_before(28)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert "title" not in _columns(db, "sessions")
    db.close()
    assert state.migrate().after == state.SCHEMA_VERSION
    with state.connect() as db:
        assert (
            db.execute("SELECT sql FROM sqlite_master WHERE name = 'sessions'").fetchone()[0]
            == fresh
        )
    assert state.get_session("s").title is None
    assert state.set_title("s", "Review")


def test_schema_30_gives_each_gate_closed_before_the_event_of_its_closing(lado_home):
    state.add_session(state.Session("s", "/r", None, "claude"))
    with state.connect() as db:
        fresh = db.execute(GATES_TABLE).fetchone()[0]
        for run, answer in [("a", "reject"), ("a", "overridden"), ("b", "cancelled")]:
            db.execute(
                "INSERT INTO gates (session, run, state, kind, question, options, answer)"
                " VALUES ('s', ?, 'ok', 'approval', 'Ship?', '[]', ?)",
                (run, answer),
            )
        db.execute(  # gate 4: open
            "INSERT INTO gates (session, run, state, kind, question, options)"
            " VALUES ('s', 'b', 'ok', 'approval', 'Ship?', '[]')"
        )
        db.execute(  # gate 5: closed, its events gone
            "INSERT INTO gates (session, run, state, kind, question, options, answer)"
            " VALUES ('s', 'c', 'ok', 'approval', 'Ship?', '[]', 'approve')"
        )

    def event(run, kind, detail):
        with state.connect() as db:
            return db.execute(
                "INSERT INTO events (session, agent, kind, detail, run)"
                " VALUES ('s', 'human', ?, ?, ?)",
                (kind, detail, run),
            ).lastrowid

    event("a", state.GATE_OPEN, "#1 approval at ok: Ship?")
    event("a", state.GATE_ANSWER, "#1 reject: too big")
    event("b", state.FLOW, "build -done-> ok")  # another run's, written in between
    rejected = event("a", state.FLOW, "ok -rejected-> build")
    event("a", state.GATE_ANSWER, "#2 overridden: hold")
    forced = event("a", state.FLOW_SET, "ok -> build: hold")
    event("b", state.GATE_ANSWER, "#3 cancelled: dropped")
    cancelled = event("b", state.FLOW_CANCEL, "dropped")
    event("b", state.GATE_OPEN, "#4 approval at ok: Ship?")
    agent_helpers.schema_before(30)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert "closed_event" not in _columns(db, "gates")
    db.close()
    assert state.migrate().after == state.SCHEMA_VERSION
    with state.connect() as db:
        assert db.execute(GATES_TABLE).fetchone()[0] == fresh
    assert [g.closed_event for g in state.session_gates("s")] == [
        rejected,
        forced,
        cancelled,
        None,
        None,
    ]


def test_schema_31_gives_gates_the_answer_note_and_old_gates_none(lado_home):
    state.add_session(state.Session("s", "/r", None, "claude"))
    with state.connect() as db:
        fresh = db.execute(GATES_TABLE).fetchone()[0]
        db.execute(
            "INSERT INTO gates (session, run, state, kind, question, options, answer)"
            " VALUES ('s', 'a', 'ok', 'approval', 'Ship?', '[]', 'reject')"
        )
    agent_helpers.schema_before(31)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert "answer_note" not in _columns(db, "gates")
    db.close()
    assert state.migrate().after == state.SCHEMA_VERSION
    with state.connect() as db:
        assert db.execute(GATES_TABLE).fetchone()[0] == fresh
    [old] = state.session_gates("s")
    assert (old.answer, old.answer_note) == ("reject", None)


def _kinds(name: str) -> list[str]:
    return [e.kind for e in state.list_events(name)]


def test_the_containers_stop_marks_every_running_session_in_one_go(lado_home):
    for name in ("a", "b", "c"):
        state.add_session(state.Session(name, "/r", None, "claude"))
    state.add_agent(state.Agent("a", "supervisor", "supervisor", "/r", None, None, "idle", "x"))
    state.stop_session("c")  # the human's
    assert state.stop_for_container() == ["a", "b"]
    by = {s.name: s for s in state.list_sessions()}
    assert by["a"].stopped_at and by["a"].resume_at_start
    assert by["b"].stopped_at and by["b"].resume_at_start
    assert by["c"].stopped_at and not by["c"].resume_at_start
    assert state.list_agents("a") == []
    [stop] = [e for e in state.list_events("a") if e.kind == state.SESSION_STOP]
    assert stop.detail == "0 messages dropped; the container stopped"
    assert state.stop_for_container() == []


def test_giving_up_stops_a_session_not_stopped(lado_home):
    state.add_session(state.Session("s", "/r", None, "claude"))
    state.give_up_resume("s")
    sess = state.get_session("s")
    assert sess.stopped_at and not sess.resume_at_start
    assert _kinds("s")[-2:] == [state.SESSION_GONE, state.SESSION_STOP]


def test_schema_29_gives_sessions_the_resume_mark(lado_home):
    state.add_session(state.Session("s", "/r", None, "claude"))
    with state.connect() as db:
        fresh = db.execute("SELECT sql FROM sqlite_master WHERE name = 'sessions'").fetchone()[0]
    agent_helpers.schema_before(29)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert "resume_at_start" not in _columns(db, "sessions")
    assert db.execute("PRAGMA user_version").fetchone()[0] == 28
    db.close()
    assert state.migrate().after == state.SCHEMA_VERSION
    with state.connect() as db:
        assert (
            db.execute("SELECT sql FROM sqlite_master WHERE name = 'sessions'").fetchone()[0]
            == fresh
        )
    assert not state.get_session("s").resume_at_start


RECOMMENDATION_COLUMNS = {
    "recommendation_state",
    "recommendation",
    "recommended_choice",
    "recommendation_disagrees",
    "recommended_at",
    "recommendation_request",
}


def _columns(db, table: str) -> set[str]:
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def test_schema_26_adds_the_recommendation_columns(lado_home):
    _session_with(_agent(status=state.BUSY))
    with state.connect() as db:
        fresh = {
            t: db.execute(f"SELECT sql FROM sqlite_master WHERE name = '{t}'").fetchone()[0]
            for t in ("gates", "messages")
        }
        assert RECOMMENDATION_COLUMNS <= _columns(db, "gates")
        assert RECOMMENDATION_COLUMNS <= _columns(db, "messages")
    agent_helpers.schema_before(26)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert not RECOMMENDATION_COLUMNS & _columns(db, "gates")
    assert not RECOMMENDATION_COLUMNS & _columns(db, "messages")
    db.execute(
        "INSERT INTO gates (session, run, state, kind, question, options)"
        " VALUES ('s', 'f/x', 'ok', 'approval', 'Ship?', '[]')"
    )
    db.execute("INSERT INTO messages (session, sender, recipient) VALUES ('s', 'w1', 'human')")
    db.commit()
    db.close()
    assert state.migrate().after == state.SCHEMA_VERSION
    with state.connect() as db:
        for table, sql in fresh.items():
            assert (
                db.execute(f"SELECT sql FROM sqlite_master WHERE name = '{table}'").fetchone()[0]
                == sql
            )
    [gate] = state.session_gates("s")
    assert (gate.recommendation_state, gate.recommendation, gate.recommendation_disagrees) == (
        None,
        "",
        False,
    )
    [message] = state.list_messages("s")
    assert (message.recommendation_state, message.recommended_choice) == (None, None)


def test_a_gate_and_a_question_read_back_their_recommendation_fields(lado_home):
    _session_with(_agent(status=state.BUSY))
    question = state.add_question("s", "w1", "Ship?", "", ["yes", "no"], False)
    with state.connect() as db:
        db.execute(
            "INSERT INTO gates (session, run, state, kind, question, options,"
            " recommendation_state, recommendation, recommended_choice,"
            " recommendation_disagrees, recommended_at, recommendation_request)"
            " VALUES ('s', 'f/x', 'ok', 'approval', 'Ship?', '[]', 'given', 'Reject',"
            " 'reject', 1, '2026-10-12 10:00:00.000', 9)"
        )
        db.execute(
            "UPDATE messages SET recommendation_state = 'asked', recommendation_request = 4"
            " WHERE id = ?",
            (question,),
        )
    [gate] = state.session_gates("s")
    assert (
        gate.recommendation_state,
        gate.recommendation,
        gate.recommended_choice,
        gate.recommendation_disagrees,
        gate.recommended_at,
        gate.recommendation_request,
    ) == (state.REC_GIVEN, "Reject", "reject", True, "2026-10-12 10:00:00.000", 9)
    asked = state.get_message("s", question)
    assert (asked.recommendation_state, asked.recommendation_request) == (state.REC_ASKED, 4)
    assert asked.recommendation == "" and asked.recommendation_disagrees is False


# A flow of LADO 0.26: `needs` names states.
WITH_NEEDS = {
    "name": "ship",
    "description": "d",
    "start": "build",
    "states": {
        "build": {"agent": "worker", "do": "Build.", "outcomes": {"done": "ok"}},
        "ok": {
            "gate": "approval",
            "ask": "Ship?",
            "needs": ["build"],
            "outcomes": {"approved": "end", "rejected": "build"},
        },
        "end": {"end": True},
    },
}


def test_the_migration_drops_needs_from_the_snapshots_of_closed_runs_only(lado_home):
    from lado import runs

    _session_with()
    agent_helpers.schema_before(23)
    assert state.MIGRATIONS[22] == [state.closed_runs_without_needs]
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    old = json.dumps(WITH_NEEDS, indent=1)
    snapshots = {
        "ended": old,
        "cancelled": old,
        "active": old,
        "waiting": old,
        "broken": "{not json",
        "states": json.dumps({**WITH_NEEDS, "states": ["build"]}),
    }
    for name, snapshot in snapshots.items():
        status = name if name in state.OPEN + (state.ENDED, state.CANCELLED) else state.ENDED
        db.execute(
            "INSERT INTO runs (session, name, flow, snapshot, kit, task, state, status,"
            " worktree, branch) VALUES ('s', ?, 'ship', ?, '{}', 't', 'ok', ?, '/w', 'b')",
            (f"ship/{name}", snapshot, status),
        )
    db.commit()
    db.close()
    assert state.migrate().after == state.SCHEMA_VERSION
    for name in ("ended", "cancelled"):
        run = state.get_run("s", f"ship/{name}")
        assert "needs" not in json.loads(run.snapshot)["states"]["ok"]
        assert runs.flow_of(run).states["ok"].reads == ()
    for name in ("active", "waiting", "broken", "states"):
        assert state.get_run("s", f"ship/{name}").snapshot == snapshots[name]
    with pytest.raises(runs.SnapshotError, match="needs was replaced by reads"):
        runs.flow_of(state.get_run("s", "ship/waiting"))


def test_a_due_resume_is_queued_on_a_database_from_before_0_7(lado_home):
    """Its messages.body is the old text column, renamed: NOT NULL without a DEFAULT."""
    lado_home.mkdir()
    sqlite3.connect(lado_home / "lado.db").executescript(SCHEMA_V1)
    state.migrate()
    state.add_agent(_agent(status=state.BUSY))
    state.add_event("s", "w1", state.TURN_ERROR, "server_error")
    state.schedule_resume("s", "w1", 100.0, (30.0,))
    state.set_status("s", "w1", state.IDLE)
    message = state.take_resume("s", "w1", 130.0, lambda n, error: f"resume {n}: {error}")
    queued = state.get_message("s", message)
    assert (queued.sender, queued.summary, queued.body, queued.state) == (
        "lado",
        "resume 1: server_error",
        "",
        "pending",
    )
    assert state.get_agent("s", "w1").resume_at is None


def test_every_insert_into_messages_names_its_body():
    """A database made before LADO 0.7.0 (schema below 5) has messages.body without the
    DEFAULT '' of a new one (SQLite cannot add one to an existing column): an insert that
    leaves body out fails there with NOT NULL constraint failed."""
    source = Path(state.__file__).read_text(encoding="utf-8")
    joined = re.sub(r'"\s*\n\s*"', "", source)  # the literals the code writes over lines
    inserts = re.findall(r"INSERT INTO messages \(([^)]*)\)", joined)
    assert inserts
    without = [c for c in inserts if "body" not in [n.strip() for n in c.split(",")]]
    assert without == []


def test_migrate_upgrades_an_older_schema_once(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    agent_helpers.previous_schema()
    assert state.migrate().after == state.SCHEMA_VERSION
    assert state.get_session("s").name == "s"
    assert state.migrate() is None  # nothing left to migrate
    assert state.pending_migration() is None


def test_migrate_makes_no_database(lado_home):
    assert state.migrate() is None
    assert not (lado_home / "lado.db").exists()


def _agent_columns(db: sqlite3.Connection) -> list[str]:
    return [row[1] for row in db.execute("PRAGMA table_info(agents)")]


def _session_columns(db: sqlite3.Connection) -> list[str]:
    return [row[1] for row in db.execute("PRAGMA table_info(sessions)")]


def _message_columns(db: sqlite3.Connection) -> list[str]:
    return [row[1] for row in db.execute("PRAGMA table_info(messages)")]


def _tables(db: sqlite3.Connection) -> list[str]:
    return [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]


def _schema(path: Path) -> int:
    with contextlib.closing(sqlite3.connect(path)) as db:
        return db.execute("PRAGMA user_version").fetchone()[0]


def test_migrate_backs_up_the_older_schema_first(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    agent_helpers.previous_schema()
    old = state.SCHEMA_VERSION - 1
    backups = lado_home / "backups"
    backups.mkdir()
    (backups / f"lado.db.schema-{old - 1}").write_text("an earlier migration's")
    (backups / "lado.db.0.38.0").write_text("lado update's")
    migrated = state.migrate()
    backup = backups / f"lado.db.schema-{old}"
    assert migrated == state.Migrated(old, state.SCHEMA_VERSION, backup)
    assert sorted(p.name for p in backups.iterdir()) == ["lado.db.0.38.0", backup.name]
    assert _schema(backup) == old
    with contextlib.closing(sqlite3.connect(backup)) as db:
        assert db.execute("SELECT name FROM sessions").fetchall() == [("s",)]
        tables = _tables(db)
    assert "github_takeover" not in tables  # the content before the migration
    assert _schema(lado_home / "lado.db") == state.SCHEMA_VERSION


def test_a_failing_step_leaves_the_schema_and_keeps_the_backup(lado_home, monkeypatch):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    old = state.SCHEMA_VERSION - 1
    agent_helpers.previous_schema()
    # The last step, then a statement that fails: the step's change must not stay either.
    monkeypatch.setitem(
        state.MIGRATIONS, old, [*state.MIGRATIONS[old], "SELECT no_such_function()"]
    )
    with pytest.raises(state.MigrationFailed) as e:
        state.migrate()
    backup = lado_home / "backups" / f"lado.db.schema-{old}"
    assert (e.value.before, e.value.after, e.value.backup) == (old, state.SCHEMA_VERSION, backup)
    assert isinstance(e.value.__cause__, sqlite3.OperationalError)
    assert "no such function" in e.value.reason
    assert _schema(lado_home / "lado.db") == old
    assert _schema(backup) == old
    with contextlib.closing(sqlite3.connect(lado_home / "lado.db")) as db:
        assert "github_takeover" not in _tables(db)  # rolled back


def test_version_2_database_gets_kits(lado_home):
    lado_home.mkdir()
    db = sqlite3.connect(lado_home / "lado.db")
    db.executescript(SCHEMA_V1)
    for statement in state.MIGRATIONS[1]:
        db.execute(statement)
    db.execute("PRAGMA user_version = 2")
    db.commit()
    state.migrate()
    sess = state.get_session("s")
    assert (sess.kits, sess.without) == (["default"], [])


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
    state.migrate()
    state.add_event("s", "supervisor", "finished", "done")
    [event] = state.list_events("s")
    assert (event.agent, event.kind, event.detail) == ("supervisor", "finished", "done")


def _agent(name="w1", status=state.STARTING):
    return state.Agent("s", name, "worker", "/r", None, None, status, provider="claude")


def _status_events():
    return [e.detail for e in state.list_events("s") if e.kind == state.STATUS]


def _waiting_agent(key=""):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(_agent(status=state.BUSY))
    state.wait("s", "w1", key)


def test_any_resume_ends_a_wait_without_a_key(lado_home):
    _waiting_agent()
    state.resume("s", "w1", "x")
    assert state.get_agent("s", "w1").status == state.BUSY
    assert _status_events() == ["waiting", "busy"]


def test_an_answer_returns_an_agent_that_waited_from_background_to_background(lado_home):
    """E.g. a background subagent's permission dialog after the main turn ended."""
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(_agent(status=state.BUSY))
    state.set_status("s", "w1", state.BACKGROUND)
    state.wait("s", "w1", "k1")
    state.resume("s", "w1", "k1")
    agent = state.get_agent("s", "w1")
    assert (agent.status, agent.waiting_for) == (state.BACKGROUND, None)
    assert _status_events() == ["background", "waiting", "background"]
    # From background, then busy before the wait: back to busy.
    state.set_status("s", "w1", state.BUSY)
    state.wait("s", "w1", "k2")
    state.resume("s", "w1", "k2")
    assert state.get_agent("s", "w1").status == state.BUSY


def _turn_end_take():
    """A turn-end hook's hand-over: idle, and the queue by the hook's output."""
    return state.take_pending(
        "s", "w1", state.SENT, state.BUSY, True, state.HOOK_OUTPUT, become=state.IDLE
    )


def test_take_pending_becomes_idle_and_takes_in_one_commit(lado_home):
    _session_with(_agent(status=state.BUSY))
    state.queue_message("s", "supervisor", "w1", "hi", "")
    commits = []
    opened = state._open

    def counted():
        db = opened()
        db.set_trace_callback(lambda sql: sql == "COMMIT" and commits.append(sql))
        return db

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(state, "_open", counted)
        taken = _turn_end_take()
    assert [m.channel for m in taken] == [state.HOOK_OUTPUT]
    assert commits == ["COMMIT"]
    assert state.get_agent("s", "w1").status == state.BUSY
    assert _status_events() == ["idle", "busy"]


def test_take_pending_becomes_idle_with_nothing_to_take(lado_home):
    _session_with(_agent(status=state.BUSY))
    assert _turn_end_take() == []
    assert state.get_agent("s", "w1").status == state.IDLE
    assert _status_events() == ["idle"]


def test_take_pending_keeps_the_status_when_a_batch_is_unconfirmed(lado_home):
    _session_with(_agent(status=state.IDLE))
    state.queue_message("s", "supervisor", "w1", "first", "")
    state.take_pending("s", "w1", state.SENT, state.BUSY, True, state.HOOK_OUTPUT)
    later = state.queue_message("s", "supervisor", "w1", "second", "")
    assert _turn_end_take() == []
    assert state.get_agent("s", "w1").status == state.IDLE  # committed, not rolled back
    assert state.get_message("s", later).state == state.PENDING


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
    state.migrate()
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


def test_a_queue_taken_by_a_tool_result_is_delivered_once_and_out_of_the_sweep(lado_home):
    _session_with(_agent(status=state.BUSY))
    first = state.queue_message("s", "supervisor", "w1", "first", "the details")
    second = state.queue_message("s", "w2", "w1", "second")
    before = time.time()
    taken = state.take_pending("s", "w1", state.DELIVERED, channel=state.TOOL_RESULT)
    assert [(m.id, m.state, m.channel) for m in taken] == [
        (first, state.DELIVERED, state.TOOL_RESULT),
        (second, state.DELIVERED, state.TOOL_RESULT),
    ]
    stored = {m.id: m for m in state.list_messages("s")}
    assert all(stored[i].sent_at >= before for i in (first, second))
    assert {stored[i].channel for i in (first, second)} == {state.TOOL_RESULT}
    assert state.take_pending("s", "w1", state.SENT, channel=state.TYPED) == []
    seen = []

    def plan(agent, sent):
        seen.extend(sent)
        return state.Plan(retype=True)

    assert state.sweep("s", "w1", time.time(), plan).typed == []
    assert seen == []
    assert [m.id for m in state.read_messages("s", "w1")] == [first]


def test_a_message_from_a_sender_waits_until_its_recipient_received_it(lado_home):
    _session_with(_agent("supervisor", status=state.BUSY), _agent())
    assert state.waiting_from("s", "supervisor", "w1") is None
    report = state.queue_message("s", "w1", "supervisor", "report", "the details")
    state.queue_message("s", "w2", "supervisor", "other's", "body")
    assert state.waiting_from("s", "supervisor", "w1").id == report  # pending
    assert state.waiting_from("s", "w1", "supervisor") is None  # the other way round
    state.take_pending("s", "supervisor", state.DELIVERED, channel=state.TOOL_RESULT)
    assert state.waiting_from("s", "supervisor", "w1").id == report  # delivered, not read
    state.read_messages("s", "supervisor")
    assert state.waiting_from("s", "supervisor", "w1") is None
    line = state.queue_message("s", "w1", "supervisor", "a line only")
    assert state.waiting_from("s", "supervisor", "w1").id == line
    state.take_pending("s", "supervisor", state.DELIVERED, channel=state.TOOL_RESULT)
    assert state.waiting_from("s", "supervisor", "w1") is None  # its line was received


def test_version_5_database_gets_runs(lado_home):
    db = _schema_v4(lado_home)
    for statement in state.MIGRATIONS[4]:
        db.execute(statement)
    db.execute("PRAGMA user_version = 5")
    db.commit()
    state.migrate()
    assert state.get_agent("s", "supervisor").run is None
    assert state.list_runs("s") == []
    state.add_event("s", "supervisor", "finished", "done")
    assert state.list_events("s")[-1].run is None


def _run(name="feature/x", **changes):
    run = state.Run(
        session="s",
        name=name,
        flow="feature",
        snapshot='{"name": "feature"}',
        kit={"name": "k", "version": "1.0.0", "source": "project: /k"},
        task="add x",
        state="design",
        worktree="/r/.lado/worktrees/s/feature-x",
        branch="lado/s/feature-x",
    )
    return dataclasses.replace(run, **changes)


def test_version_6_database_gets_gates(lado_home):
    db = _schema_v4(lado_home)
    for version in (4, 5):
        for statement in state.MIGRATIONS[version]:
            db.execute(statement)
    db.execute("PRAGMA user_version = 6")
    db.commit()
    state.migrate()
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
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_run(_run(), [("supervisor", state.FLOW_START, "started")])
    before = state.get_run("s", "feature/x")
    after = dataclasses.replace(before, state="design_ok", status=state.WAITING)
    gate = _gate()
    assert state.update_run(before, after, [("supervisor", state.FLOW, "go")], opens=gate)
    return after, gate


def test_a_gate_and_its_event_share_one_time(lado_home, monkeypatch):
    """The chat shows an event before a gate only at the same time: a millisecond that
    turns between the two rows put the gate above the move that opened it."""
    add_event = state._add_event

    def late(db, session, agent, kind, *args, **kwargs):
        if kind == state.GATE_OPEN:
            time.sleep(0.005)  # the millisecond turns between the gate and its event
        return add_event(db, session, agent, kind, *args, **kwargs)

    monkeypatch.setattr(state, "_add_event", late)
    _, gate = _waiting(lado_home)
    [opened] = [e for e in state.list_events("s") if e.kind == state.GATE_OPEN]
    assert opened.created_at == state.get_gate(gate.id).created_at


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


def test_version_7_database_gets_stopped_sessions(lado_home):
    db = _schema_v4(lado_home)
    for version in (4, 5, 6):
        for statement in state.MIGRATIONS[version]:
            db.execute(statement)
    db.execute("PRAGMA user_version = 7")
    db.commit()
    state.migrate()
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
    state.migrate()
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
    state.migrate()
    [message] = state.list_messages("s")
    assert (message.state, message.attempts, message.sent_at) == (state.SENT, 0, 5.0)
    assert state.get_agent("s", "supervisor").seen_at == 0
    assert state.failed_counts("s") == {}  # reads messages.failed_at


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
    state.migrate()
    # A run from before keeps its previous note; no earlier note was kept.
    assert state.get_run("s", "feature/x").note == "designed"
    assert state.run_notes("s", "feature/x") == []


def test_stopping_a_session_keeps_its_history_and_drops_what_was_not_delivered(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
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
    agents, dropped, _ = state.stop_session("s")
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


def test_version_12_messages_become_plain_messages_in_version_13(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(_agent("supervisor"))
    state.queue_message("s", "w1", "supervisor", "hi", "body")
    agent_helpers.schema_before(13)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    columns = {row[1] for row in db.execute("PRAGMA table_info(messages)")}
    db.close()
    assert "kind" not in columns and "reply_state" not in columns
    state.migrate()
    [message] = state.list_messages("s")
    assert (message.kind, message.choices, message.question_state) == (state.MESSAGE, None, None)
    assert (message.reply_to, message.choice, message.reply_state) == (None, None, None)


def test_version_14_notes_get_an_empty_actor_outcome_and_target(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    run = _run()
    state.add_run(run, [("supervisor", state.FLOW_START, "started")])
    agent_helpers.schema_before(15)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    db.execute(
        "INSERT INTO notes (session, run, state, kind, summary) VALUES"
        " ('s', 'feature/x', 'design', 'report', 'old design')"
    )
    db.commit()
    db.close()
    state.migrate()
    [note] = state.run_notes("s")
    assert (note.run, note.state, note.kind, note.summary) == (
        "feature/x",
        "design",
        state.REPORT,
        "old design",
    )
    assert (note.actor, note.outcome, note.target) == ("", "", "")


def test_version_15_agents_wait_for_no_key(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(_agent(status=state.WAITING))
    agent_helpers.schema_before(16)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    columns = {row[1] for row in db.execute("PRAGMA table_info(agents)")}
    db.close()
    assert "waiting_for" not in columns
    state.migrate()
    agent = state.get_agent("s", "w1")
    assert (agent.status, agent.waiting_for) == (state.WAITING, None)
    state.resume("s", "w1", "k1")  # a wait from before has no key: any answer ends it
    assert state.get_agent("s", "w1").status == state.BUSY


def _session_with(*agents):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    for agent in agents:
        state.add_agent(agent)


@pytest.mark.parametrize("supervisor", [None, state.STOPPED, state.IDLE], ids=str)
def test_the_copy_is_queued_only_for_a_running_agent_and_the_message_anyway(lado_home, supervisor):
    _session_with(_agent(status=state.IDLE))
    if supervisor:
        state.add_agent(_agent("supervisor", status=supervisor))
    message = state.queue_with_copy("s", "human", "w1", "hi", "", "supervisor", str)
    queued = [(m.recipient, m.summary) for m in state.list_messages("s")]
    copy = [("supervisor", str(message))] if supervisor == state.IDLE else []
    assert queued == [("w1", "hi"), *copy]


def _yes(question):
    return state.Reply(question, f"Answer to #{question}: yes", "", "yes", state.ANSWERED)


@pytest.mark.parametrize(
    "stop",
    [
        lambda: state.stop_session("s"),
        lambda: state.stop_session("s", gone=True),
        state.stop_for_container,
        lambda: state.give_up_resume("s"),
        lambda: state.fail_resume(state.get_session("s"), ""),
    ],
    ids=["stop_session", "gone", "stop_for_container", "give_up_resume", "fail_resume"],
)
def test_every_stop_marks_the_open_questions_stopped(lado_home, stop):
    _session_with(_agent(status=state.IDLE))
    question = state.add_question("s", "w1", "Merge?", "", ["yes"], True)
    stop()
    assert state.get_message("s", question).question_state == state.QUESTION_STOPPED


@pytest.mark.parametrize(
    "end",
    [
        lambda: state.delete_agent("s", "w1"),
        lambda: state.agent_ended("s", "w1", "its CLI exited"),
    ],
    ids=["delete_agent", "agent_ended"],
)
def test_an_agents_end_in_a_running_session_keeps_closed(lado_home, end):
    _session_with(_agent(status=state.IDLE))
    question = state.add_question("s", "w1", "Merge?", "", ["yes"], True)
    end()
    assert state.get_message("s", question).question_state == state.CLOSED


def test_a_stop_counts_the_open_questions_it_closes(lado_home):
    _session_with(_agent(status=state.IDLE))
    state.add_question("s", "w1", "Merge?", "", None, True)
    state.add_question("s", "w1", "Port?", "", None, True)
    state.reply_to_questions("s", [_yes(state.add_question("s", "w1", "Done?", "", None, True))])
    assert state.open_questions("s") == 2
    assert state.stop_session("s")[2] == 2
    assert state.open_questions("s") == 0


def _stopped_question():
    _session_with(_agent(status=state.IDLE))
    question = state.add_question("s", "w1", "Merge?", "", None, True)
    state.stop_session("s")
    return question


def test_a_stopped_question_is_untold_until_a_notice_names_it(lado_home):
    question = _stopped_question()
    [untold] = state.untold_questions("s")
    assert untold.id == question
    notice = state.tell_questions("s", [question], "closed", "#1", [("a", "r")])
    assert state.untold_questions("s") == []
    assert state.get_message("s", question).answered_by == notice
    sent = state.get_message("s", notice)
    assert (sent.sender, sent.recipient, sent.state) == ("lado", "supervisor", state.PENDING)
    assert (sent.summary, sent.body) == ("closed", "#1")
    assert state.message_attachments(notice) == [("a", "r")]


def test_a_question_whose_notice_a_stop_dropped_is_untold_again(lado_home):
    question = _stopped_question()
    state.tell_questions("s", [question], "closed", "#1")
    state.stop_session("s")
    assert [m.id for m in state.untold_questions("s")] == [question]


def test_a_question_whose_notice_was_read_stays_told(lado_home):
    question = _stopped_question()
    notice = state.tell_questions("s", [question], "closed", "#1")
    with state.connect() as db:
        db.execute("UPDATE messages SET state = ? WHERE id = ?", (state.READ, notice))
    state.stop_session("s")
    assert state.untold_questions("s") == []


def test_only_the_sessions_stopped_questions_are_untold(lado_home):
    _session_with(_agent(status=state.IDLE))
    closed = state.add_question("s", "w1", "Agent left?", "", None, True)
    state.delete_agent("s", "w1")
    state.add_agent(_agent(status=state.IDLE))
    answered = state.add_question("s", "w1", "Answered?", "", None, True)
    state.reply_to_questions("s", [_yes(answered)])
    state.add_session(state.Session("other", "/r", None, provider="claude"))
    state.add_question("other", "w1", "Elsewhere?", "", None, True)
    state.stop_session("other")
    state.stop_session("s")
    assert state.get_message("s", closed).question_state == state.CLOSED
    assert state.untold_questions("s") == []


# The lead's recommendation (RECOMMENDATION).


def _lead_session(lead_status=state.IDLE):
    """Session s with its lead and a worker w1."""
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(_agent("supervisor", status=lead_status))
    state.add_agent(_agent("w1", status=state.BUSY))


def _gate_on(run_name: str) -> state.Gate:
    """An open gate of a new run `run_name`."""
    state.add_run(_run(run_name), [("supervisor", state.FLOW_START, "started")])
    before = state.get_run("s", run_name)
    after = dataclasses.replace(before, state="design_ok", status=state.WAITING)
    gate = _gate(run=run_name)
    assert state.update_run(before, after, [], opens=gate)
    return gate


def _answer(gate: state.Gate) -> None:
    run = state.get_run("s", gate.run)
    after = dataclasses.replace(run, state="design", status=state.ACTIVE)
    assert state.update_run(run, after, [], closes=("human", "approve", "", gate.id))


def _set_message_state(message_id: int, value: str) -> None:
    with state.connect() as db:
        db.execute("UPDATE messages SET state = ? WHERE id = ?", (value, message_id))


def test_ask_recommendation_queues_the_request_and_marks_asked(lado_home):
    _lead_session()
    gate = _gate_on("feature/x")
    request = state.ask_recommendation(
        "s", "gate", gate.id, "recommend on gate", "the body", attachments=[("a1", "r1")]
    )
    message = state.get_message("s", request)
    assert (message.sender, message.recipient, message.state, message.body) == (
        "lado",
        "supervisor",
        state.PENDING,
        "the body",
    )
    assert state.message_attachments(request) == [("a1", "r1")]
    stored = state.get_gate(gate.id)
    assert (stored.recommendation_state, stored.recommendation_request) == (
        state.REC_ASKED,
        request,
    )
    question = state.add_question("s", "w1", "Ship?", "", ["yes", "no"], False)
    asked = state.ask_recommendation("s", "question", question, "recommend on question", "b")
    assert state.get_message("s", question).recommendation_request == asked


def test_ask_recommendation_needs_the_lead_running(lado_home):
    _lead_session(lead_status=state.STOPPED)
    gate = _gate_on("feature/x")
    with pytest.raises(state.NotRunning):
        state.ask_recommendation("s", "gate", gate.id, "recommend", "body")
    assert state.get_gate(gate.id).recommendation_state is None
    assert [m for m in state.list_messages("s") if m.recipient == "supervisor"] == []
    # A request before the lead's start is queued all the same.
    assert state.ask_recommendation("s", "gate", gate.id, "recommend", "body", before_start=True)


def test_a_notice_marks_asked_without_a_request(lado_home):
    _lead_session()
    gate = _gate_on("feature/x")
    assert state.ask_recommendation("s", "gate", gate.id, None, "") is None
    stored = state.get_gate(gate.id)
    assert (stored.recommendation_state, stored.recommendation_request) == (state.REC_ASKED, None)
    assert [m for m in state.list_messages("s") if m.recipient == "supervisor"] == []


def test_recommend_stores_and_replaces(lado_home):
    _lead_session()
    gate = _gate_on("feature/x")
    assert state.recommend("gate", gate.id, "Reject: no test", "reject", True)
    first = state.get_gate(gate.id)
    assert (
        first.recommendation_state,
        first.recommendation,
        first.recommended_choice,
        first.recommendation_disagrees,
    ) == (state.REC_GIVEN, "Reject: no test", "reject", True)
    assert first.recommended_at
    assert state.recommend("gate", gate.id, "Approve", None, False)
    second = state.get_gate(gate.id)
    assert (
        second.recommendation,
        second.recommended_choice,
        second.recommendation_disagrees,
    ) == ("Approve", None, False)
    question = state.add_question("s", "w1", "Ship?", "", ["yes", "later"], False)
    assert state.recommend("question", question, "Later", "later", False)
    stored = state.get_message("s", question)
    assert (stored.recommendation_state, stored.recommended_choice) == (state.REC_GIVEN, "later")


def test_recommend_on_a_closed_gate_or_question_changes_nothing(lado_home):
    _lead_session()
    gate = _gate_on("feature/x")
    _answer(gate)
    assert not state.recommend("gate", gate.id, "Approve", "approve", False)
    assert state.get_gate(gate.id).recommendation_state is None
    question = state.add_question("s", "w1", "Ship?", "", ["yes"], False)
    state.reply_to_questions("s", [_yes(question)])
    assert not state.recommend("question", question, "Yes", "yes", False)
    assert state.get_message("s", question).recommendation_state is None


def test_answering_a_gate_drops_its_pending_request(lado_home):
    _lead_session()
    gate = _gate_on("feature/x")
    request = state.ask_recommendation("s", "gate", gate.id, "recommend", "body")
    _answer(gate)
    assert state.get_message("s", request).state == state.DROPPED


def test_an_override_drops_the_pending_request(lado_home):
    _lead_session()
    gate = _gate_on("feature/x")
    request = state.ask_recommendation("s", "gate", gate.id, "recommend", "body")
    run = state.get_run("s", "feature/x")
    after = dataclasses.replace(run, state="design", status=state.ACTIVE)
    assert state.update_run(run, after, [], closes=("human", "overridden", "x", None))
    assert state.get_message("s", request).state == state.DROPPED


def test_a_handed_over_request_is_not_dropped(lado_home):
    _lead_session()
    gate = _gate_on("feature/x")
    request = state.ask_recommendation("s", "gate", gate.id, "recommend", "body")
    _set_message_state(request, state.SENT)
    _answer(gate)
    assert state.get_message("s", request).state == state.SENT


def test_dismissing_a_question_drops_its_request(lado_home):
    _lead_session()
    question = state.add_question("s", "w1", "Ship?", "", ["yes"], True)
    request = state.ask_recommendation("s", "question", question, "recommend", "body")
    dismissal = state.Reply(question, f"Dismissed #{question}", "", None, state.DISMISSED)
    state.reply_to_questions("s", [dismissal])
    assert state.get_message("s", request).state == state.DROPPED


def test_answering_two_questions_drops_both_requests(lado_home):
    _lead_session()
    first = state.add_question("s", "w1", "Ship?", "", ["yes"], True)
    second = state.add_question("s", "w1", "Port?", "", None, True)
    requests = [
        state.ask_recommendation("s", "question", q, "recommend", "body") for q in (first, second)
    ]
    own = state.Reply(second, f"Answer to #{second}: 8123", "", None, state.ANSWERED)
    state.reply_to_questions("s", [_yes(first), own])
    assert [state.get_message("s", r).state for r in requests] == [state.DROPPED] * 2


def test_a_forgotten_agents_question_drops_its_request(lado_home):
    _lead_session()
    question = state.add_question("s", "w1", "Ship?", "", ["yes"], True)
    request = state.ask_recommendation("s", "question", question, "recommend", "body")
    state.delete_agent("s", "w1")
    assert state.get_message("s", request).state == state.DROPPED
    other = state.add_question("s", "supervisor", "Go?", "", None, True)
    unrelated = state.queue_message("s", "lado", "supervisor", "hello")
    state.delete_agent("s", "w2")  # no such agent: nothing of the others changes
    assert state.get_message("s", other).question_state == state.OPEN_QUESTION
    assert state.get_message("s", unrelated).state == state.PENDING


def test_missed_marks_only_requests_the_lead_got(lado_home):
    _lead_session()
    got = _gate_on("feature/a")
    pending = _gate_on("feature/b")
    noticed = _gate_on("feature/c")
    given = _gate_on("feature/d")
    closed = _gate_on("feature/e")
    read = state.add_question("s", "w1", "Ship?", "", ["yes"], True)
    _set_message_state(state.ask_recommendation("s", "gate", got.id, "r", "b"), state.DELIVERED)
    state.ask_recommendation("s", "gate", pending.id, "r", "b")
    state.ask_recommendation("s", "gate", noticed.id, None, "")
    state.ask_recommendation("s", "gate", given.id, "r", "b")
    state.recommend("gate", given.id, "Approve", "approve", False)
    _set_message_state(state.ask_recommendation("s", "gate", closed.id, "r", "b"), state.READ)
    _answer(closed)
    _set_message_state(state.ask_recommendation("s", "question", read, "r", "b"), state.READ)
    state.recommendations_missed("s")
    states = {g.run: g.recommendation_state for g in state.session_gates("s")}
    assert states == {
        "feature/a": state.REC_MISSING,
        "feature/b": state.REC_ASKED,
        "feature/c": state.REC_MISSING,
        "feature/d": state.REC_GIVEN,
        "feature/e": state.REC_ASKED,
    }
    assert state.get_message("s", read).recommendation_state == state.REC_MISSING
    # A recommendation given after that replaces "missing".
    assert state.recommend("gate", got.id, "Approve", None, False)
    assert state.get_gate(got.id).recommendation_state == state.REC_GIVEN


@pytest.mark.parametrize("end", ["lead_ended", "stop"])
def test_the_leads_end_and_a_stop_mark_asked_missing(lado_home, end):
    _lead_session()
    gate = _gate_on("feature/x")
    state.ask_recommendation("s", "gate", gate.id, "r", "b")
    question = state.add_question("s", "w1", "Ship?", "", ["yes"], True)
    state.ask_recommendation("s", "question", question, "r", "b")
    if end == "lead_ended":
        state.agent_ended("s", "supervisor", "its CLI exited")
    else:
        state.stop_session("s")
    assert state.get_gate(gate.id).recommendation_state == state.REC_MISSING
    assert state.get_message("s", question).recommendation_state == state.REC_MISSING


def test_a_workers_end_leaves_the_gates_asked(lado_home):
    _lead_session()
    gate = _gate_on("feature/x")
    state.ask_recommendation("s", "gate", gate.id, "r", "b")
    state.agent_ended("s", "w1", "its CLI exited")
    assert state.get_gate(gate.id).recommendation_state == state.REC_ASKED


MODEL_TABLES = (
    "SELECT name, sql FROM sqlite_master WHERE name IN ('model_servers', 'models', 'cli_defaults')"
)
CHAT = "chat completions"


def _server(id="s1", name="LM Studio дома", address="http://localhost:1234"):
    return state.add_model_server(id, name, address, "LM Studio", (CHAT,))


def test_the_migration_adds_empty_model_tables_as_a_new_database_has_them(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="codex"))
    state.add_agent(state.Agent("s", "w1", "worker", "/r", None, None, "starting", "claude"))
    with state.connect() as db:
        fresh = sorted(tuple(row) for row in db.execute(MODEL_TABLES))
    assert len(fresh) == 3
    agent_helpers.schema_before(38)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    assert db.execute(MODEL_TABLES).fetchall() == []
    db.close()
    migrated = state.migrate()
    assert (migrated.before, migrated.after) == (37, state.SCHEMA_VERSION)
    with state.connect() as db:
        assert sorted(tuple(row) for row in db.execute(MODEL_TABLES)) == fresh
    assert (state.model_servers(), state.models(), state.cli_defaults()) == ([], [], [])
    assert state.get_session("s").provider == "codex"
    assert state.get_agent("s", "w1").status == "starting"


def test_a_model_server_kept_and_found_ignoring_case(lado_home):
    saved = _server()
    assert (saved.id, saved.name, saved.address, saved.kind, saved.apis) == (
        "s1",
        "LM Studio дома",
        "http://localhost:1234",
        "LM Studio",
        (CHAT,),
    )
    assert state.model_server("lm studio ДОМА") == saved
    assert state.model_server("nope") is None
    with pytest.raises(state.NameTaken) as taken:
        _server("s2", "lm studio ДОМА")
    assert taken.value.name == "LM Studio дома"
    assert [s.id for s in state.model_servers()] == ["s1"]


def test_a_model_kept_and_found_ignoring_case(lado_home):
    _server()
    saved = state.add_model("Быстрая", "claude", "haiku", "s1")
    assert (saved.name, saved.cli, saved.model, saved.server) == (
        "Быстрая",
        "claude",
        "haiku",
        "s1",
    )
    assert saved.id
    assert state.model("быстрая") == saved
    with pytest.raises(state.NameTaken) as taken:
        state.add_model("БЫСТРАЯ", "claude", "sonnet", "s1")
    assert taken.value.name == "Быстрая"
    assert state.model("Быстрая").model == "haiku"


def test_a_model_refers_to_a_saved_server_only(lado_home):
    with pytest.raises(sqlite3.IntegrityError):
        state.add_model("Q", "opencode", "qwen3-8b", "nowhere")
    assert state.models() == []


def test_a_server_a_model_refers_to_is_not_removed(lado_home):
    _server()
    state.add_model("Локальная Qwen", "opencode", "qwen3-8b", "s1")
    assert [m.name for m in state.models_on("s1")] == ["Локальная Qwen"]
    with pytest.raises(sqlite3.IntegrityError):
        state.remove_model_server("s1")
    assert state.model_server("LM Studio дома") is not None
    assert state.remove_model("локальная qwen") == state.ModelsRemoved(["Локальная Qwen"], [])
    assert state.remove_model("локальная qwen") is None
    assert state.models_on("s1") == []
    assert state.remove_model_server("s1") is True
    assert state.remove_model_server("s1") is False
    assert state.model_servers() == []


def test_a_server_removed_with_its_models(lado_home):
    _server()
    _server("s2", "other")
    state.add_model("sp", "kilo", "qwen3-8b", "s1")
    state.add_model("Coder", "opencode", "qwen3-8b", "s1")
    state.add_model("kept", "opencode", "qwen3-8b", "s2")
    assert state.remove_model_server_with_models("s1").names == ["Coder", "sp"]
    assert [s.id for s in state.model_servers()] == ["s2"]
    assert [m.name for m in state.models()] == ["kept"]
    assert state.remove_model_server_with_models("s1") is None


def _schema_38_with_models(lado_home):
    """lado.db at schema 38 holding a model on a server and one without."""
    _server()
    agent_helpers.schema_before(39)
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    db.execute(
        "INSERT INTO models (folded, name, cli, model, server, created_at)"
        " VALUES ('локальная qwen', 'Локальная Qwen', 'opencode', 'qwen3-8b', 's1',"
        " '2026-10-01 10:00:00')"
    )
    db.execute(
        "INSERT INTO models (folded, name, cli, model, server)"
        " VALUES ('быстрая', 'Быстрая', 'claude', 'haiku', NULL)"
    )
    db.commit()
    db.close()


def test_the_migration_keeps_a_model_on_a_server_and_drops_one_without(lado_home):
    _schema_38_with_models(lado_home)
    migrated = state.migrate()
    assert (migrated.before, migrated.after) == (38, state.SCHEMA_VERSION)
    (kept,) = state.models()
    assert (kept.name, kept.cli, kept.model, kept.server, kept.created_at) == (
        "Локальная Qwen",
        "opencode",
        "qwen3-8b",
        "s1",
        "2026-10-01 10:00:00",
    )
    assert re.fullmatch("[0-9a-f]{12}", kept.id)
    assert state.cli_defaults() == []
    with state.connect() as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert "models_38" not in _tables(db)


def test_a_failed_migration_to_ids_leaves_the_rows_of_schema_38(lado_home, monkeypatch):
    _schema_38_with_models(lado_home)
    broken = [*state.MIGRATIONS[38], "SELECT * FROM no_such_table"]
    monkeypatch.setitem(state.MIGRATIONS, 38, broken)
    with pytest.raises(state.MigrationFailed):
        state.migrate()
    db = sqlite3.connect(lado_home / "lado.db")
    assert db.execute("SELECT name FROM models ORDER BY folded").fetchall() == [
        ("Быстрая",),
        ("Локальная Qwen",),
    ]
    assert _schema(lado_home / "lado.db") == 38
    db.close()


def test_a_stray_delete_of_a_default_s_model_is_refused_by_the_foreign_key(lado_home):
    _server()
    saved = state.add_model("Q", "opencode", "qwen3-8b", "s1")
    state.set_cli_default(state.ModelRef("opencode", saved.id, None))
    with state.connect() as db, pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM models WHERE id = ?", (saved.id,))


# Git servers (schema 41).


def test_a_git_server_kept_by_its_host(lado_home):
    saved = state.save_git_server(
        "a1", "https://gitlab.corp.ru", "gitlab.corp.ru", "gitlab", "ivan"
    )
    assert (saved.id, saved.address, saved.host, saved.kind, saved.login) == (
        "a1",
        "https://gitlab.corp.ru",
        "gitlab.corp.ru",
        "gitlab",
        "ivan",
    )
    assert state.git_server_by_host("gitlab.corp.ru") == saved
    assert state.git_server_by_host("git.lan") is None


def test_a_git_server_saved_again_keeps_its_id(lado_home):
    state.save_git_server("a1", "https://gitlab.corp.ru", "gitlab.corp.ru", "gitlab", "ivan")
    again = state.save_git_server(
        "b2", "https://gitlab.corp.ru/x", "gitlab.corp.ru", "github", None
    )
    assert (again.id, again.address, again.kind, again.login) == (
        "a1",
        "https://gitlab.corp.ru/x",
        "github",
        None,
    )
    assert [s.id for s in state.git_servers()] == ["a1"]


def test_git_servers_by_host_and_removed(lado_home):
    state.save_git_server("b", "https://z.lan", "z.lan", "gitlab", None)
    state.save_git_server("a", "https://a.lan:8443", "a.lan:8443", "github", "me")
    assert [s.host for s in state.git_servers()] == ["a.lan:8443", "z.lan"]
    assert state.remove_git_server("a") is True
    assert state.remove_git_server("a") is False
    assert [s.host for s in state.git_servers()] == ["z.lan"]


def test_schema_40_gets_git_servers_and_keeps_the_rest(lado_home):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    _server()
    agent_helpers.schema_before(41)
    with contextlib.closing(sqlite3.connect(lado_home / "lado.db")) as db:
        assert "git_servers" not in _tables(db)
    assert state.migrate().after == state.SCHEMA_VERSION
    assert state.git_servers() == []
    assert state.get_session("s").name == "s"
    assert [s.id for s in state.model_servers()] == ["s1"]


def test_a_git_server_has_no_author_until_set(lado_home):
    saved = state.save_git_server("a1", "https://gitlab.corp.ru", "gitlab.corp.ru", "gitlab", "i")
    assert (saved.author_name, saved.author_email) == (None, None)
    author = state.set_git_server_author("a1", "Ivan Petrov", "ivan@corp.ru")
    assert (author.author_name, author.author_email) == ("Ivan Petrov", "ivan@corp.ru")
    assert state.git_servers() == [author]
    cleared = state.set_git_server_author("a1", None, None)
    assert (cleared.author_name, cleared.author_email) == (None, None)
    assert state.set_git_server_author("nope", "A", "a@b") is None


def test_a_git_server_saved_again_keeps_its_author(lado_home):
    state.save_git_server("a1", "https://gitlab.corp.ru", "gitlab.corp.ru", "gitlab", "ivan")
    state.set_git_server_author("a1", "Ivan Petrov", "ivan@corp.ru")
    again = state.save_git_server("b2", "https://gitlab.corp.ru", "gitlab.corp.ru", "gitlab", "x")
    assert (again.id, again.login) == ("a1", "x")
    assert (again.author_name, again.author_email) == ("Ivan Petrov", "ivan@corp.ru")


def test_schema_41_gets_author_columns_and_keeps_the_servers(lado_home):
    state.save_git_server("a1", "https://gitlab.corp.ru", "gitlab.corp.ru", "gitlab", "ivan")
    agent_helpers.schema_before(42)
    with contextlib.closing(sqlite3.connect(lado_home / "lado.db")) as db:
        assert "author_name" not in _columns(db, "git_servers")
    migrated = state.migrate()
    assert (migrated.before, migrated.after) == (41, state.SCHEMA_VERSION)
    [server] = state.git_servers()
    assert (server.id, server.address, server.kind, server.login) == (
        "a1",
        "https://gitlab.corp.ru",
        "gitlab",
        "ivan",
    )
    assert (server.author_name, server.author_email) == (None, None)
    with contextlib.closing(sqlite3.connect(migrated.backup)) as db:
        assert _columns(db, "git_servers") == {"id", "address", "host", "kind", "login", "added_at"}
        assert db.execute("SELECT id FROM git_servers").fetchall() == [("a1",)]


def test_the_schema_41_backup_put_back_has_no_author(lado_home):
    state.save_git_server("a1", "https://gitlab.corp.ru", "gitlab.corp.ru", "gitlab", "ivan")
    agent_helpers.schema_before(42)
    backup = state.migrate().backup
    state.set_git_server_author("a1", "Ivan Petrov", "ivan@corp.ru")
    (lado_home / "lado.db-wal").unlink(missing_ok=True)
    (lado_home / "lado.db-shm").unlink(missing_ok=True)
    (lado_home / "lado.db").write_bytes(backup.read_bytes())  # the way back: the copy
    assert _schema(lado_home / "lado.db") == 41
    state.migrate()
    [server] = state.git_servers()
    assert (server.id, server.author_name, server.author_email) == ("a1", None, None)


# The GitHub login's takeover (schema 43).


def test_no_takeover_until_recorded(lado_home):
    assert state.github_takeover() is None
    state.record_github_takeover("saved", "GH_TOKEN of your shell")
    found = state.github_takeover()
    assert (found.outcome, found.source, found.why) == ("saved", "GH_TOKEN of your shell", None)
    assert len(found.ran_at) == 19  # UTC, YYYY-MM-DD HH:MM:SS


def test_a_takeover_is_one_row_the_last_written_wins(lado_home):
    state.record_github_takeover("pending", "the GitHub CLI's login", "keychain locked")
    assert state.github_takeover().why == "keychain locked"
    state.record_github_takeover("none", None)
    assert (state.github_takeover().outcome, state.github_takeover().source) == ("none", None)
    with state.connect() as db:
        assert db.execute("SELECT count(*) FROM github_takeover").fetchone()[0] == 1


def test_upgrade_from_42_keeps_servers_and_has_no_takeover(lado_home):
    state.save_git_server("a1", "https://gitlab.corp.ru", "gitlab.corp.ru", "gitlab", "ivan")
    agent_helpers.schema_before(43)
    with contextlib.closing(sqlite3.connect(lado_home / "lado.db")) as db:
        assert "github_takeover" not in _tables(db)
    migrated = state.migrate()
    assert (migrated.before, migrated.after) == (42, 43)
    assert migrated.backup.name == "lado.db.schema-42"
    assert [s.id for s in state.git_servers()] == ["a1"]
    assert state.github_takeover() is None


def test_the_schema_42_backup_put_back_has_no_github_entry(lado_home):
    agent_helpers.schema_before(43)
    backup = state.migrate().backup
    state.save_git_server("g1", "https://github.com", "github.com", "github", "octo")
    state.record_github_takeover("saved", "GH_TOKEN of your shell")
    (lado_home / "lado.db-wal").unlink(missing_ok=True)
    (lado_home / "lado.db-shm").unlink(missing_ok=True)
    (lado_home / "lado.db").write_bytes(backup.read_bytes())
    assert _schema(lado_home / "lado.db") == 42
    with contextlib.closing(sqlite3.connect(lado_home / "lado.db")) as db:
        assert db.execute("SELECT host FROM git_servers").fetchall() == []
        assert "github_takeover" not in _tables(db)


def test_previous_schema_drops_43(lado_home):
    state.record_github_takeover("none", None)
    agent_helpers.previous_schema()
    assert _schema(lado_home / "lado.db") == 42
    with contextlib.closing(sqlite3.connect(lado_home / "lado.db")) as db:
        assert "github_takeover" not in _tables(db)
