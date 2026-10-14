"""The usage table: each counted fact recorded as it happens, by triggers (lado.state)."""

import sqlite3
from pathlib import Path

import agent_helpers
import pytest

from lado import state
from lado.providers import base

SESSION = "secret-session"


def _rows(with_time: bool = False) -> list[tuple]:
    columns = "kind, key, provider, agrees" + (", created_at" if with_time else "")
    with state.connect() as db:
        return [tuple(r) for r in db.execute(f"SELECT {columns} FROM usage ORDER BY rowid")]


def _session(name: str = SESSION) -> None:
    state.add_session(state.Session(name, "/r", None, provider="claude"))


def _spawn(name: str, role: str, kit: str, provider: str, session: str = SESSION) -> None:
    """An agent added as lado.runtime._add_agent adds it."""
    state.add_agent(state.Agent(session, name, role, "/r", None, None, state.IDLE, provider))
    state.add_event(session, name, state.SPAWNED, state.spawned_detail(role, kit, provider))


def _run(name: str = "task/x", kit: str = "sdlc", session: str = SESSION) -> state.Run:
    return state.Run(
        session=session,
        name=name,
        flow=name.split("/")[0],
        snapshot="{}",
        kit={"name": kit, "version": "1.0.0", "source": "installed"},
        task="secret task",
        state="design",
        worktree="/w",
        branch="lado/s/x",
        visits={"design": 1},
    )


def _start_run(run: state.Run, gate: state.Gate | None = None) -> None:
    state.add_run(run, [(state.LEAD, state.FLOW_START, "")], opens=gate)


def _gate(run: state.Run, kind: str = "approval") -> state.Gate:
    return state.Gate(run.session, run.name, "design_ok", kind, "Ship?", ["approve", "reject"])


def _close(run: state.Run, answer: str, gate_id: int) -> None:
    after = state.Run(**{**run.__dict__, "status": state.ACTIVE, "state": "build"})
    assert state.update_run(run, after, [], closes=("human", answer, "secret comment", gate_id))


def test_a_workers_life_is_counted_without_its_names(lado_home):
    _session()
    _spawn(state.LEAD, "supervisor", "default", "claude")
    _spawn("w-secret", "developer", "sdlc", "kilo")
    state.add_event(
        SESSION, "w-secret", state.TURN_ERROR, base.error_line("overloaded", "try later")
    )
    state.agent_ended(SESSION, "w-secret", "its CLI exited")
    assert [r for r in _rows()] == [
        (state.USAGE_SESSION, None, None, None),
        (state.USAGE_AGENT, "supervisor@default", "claude", None),
        (state.USAGE_AGENT, "developer@sdlc", "kilo", None),
        (state.USAGE_TURN_ERROR, "overloaded", "kilo", None),
        (state.USAGE_AGENT_ENDED, None, "kilo", None),
    ]
    for row in _rows(with_time=True):
        for value in row:
            text = str(value)
            assert SESSION not in text and "w-secret" not in text and "try later" not in text


def test_each_row_has_the_time_of_its_fact(lado_home):
    _session()
    _spawn("w1", "developer", "sdlc", "claude")
    with state.connect() as db:
        added = db.execute("SELECT created_at FROM sessions").fetchone()[0]
        spawned = db.execute("SELECT created_at FROM events WHERE kind = 'spawned'").fetchone()[0]
    assert [r[-1] for r in _rows(with_time=True)] == [added, spawned]


def test_a_session_added_again_is_not_counted_again(lado_home):
    _session()
    assert not state.add_session(state.Session(SESSION, "/r", None, provider="claude"))
    assert _rows() == [(state.USAGE_SESSION, None, None, None)]


def test_a_resume_is_counted(lado_home):
    _session()
    state.stop_session(SESSION)
    assert state.resume_session(state.get_session(SESSION), "same settings")
    assert _rows()[-1] == (state.USAGE_RESUME, None, None, None)


def test_runs_are_counted_by_flow_and_kit(lado_home):
    _session()
    first, second = _run("task/a"), _run("hotfix/b")
    _start_run(first)
    _start_run(second)
    ended = state.Run(**{**first.__dict__, "status": state.ENDED, "state": "done"})
    assert state.update_run(first, ended, [(state.LEAD, state.FLOW_END, "")])
    cancelled = state.Run(**{**second.__dict__, "status": state.CANCELLED})
    assert state.update_run(second, cancelled, [(state.LEAD, state.FLOW_CANCEL, "why")])
    assert _rows()[1:] == [
        (state.USAGE_RUN_START, "task@sdlc", None, None),
        (state.USAGE_RUN_START, "hotfix@sdlc", None, None),
        (state.USAGE_RUN_END, "task@sdlc", None, None),
        (state.USAGE_RUN_CANCEL, "hotfix@sdlc", None, None),
    ]


def test_one_role_and_flow_name_in_two_kits_are_counted_apart(lado_home):
    for session, kit in (("one", "sdlc"), ("two", "acme")):
        _session(session)
        _spawn("w1", "developer", kit, "claude", session)
        _start_run(_run("task/x", kit, session))
    keys = [key for kind, key, _, _ in _rows() if kind != state.USAGE_SESSION]
    assert keys == ["developer@sdlc", "task@sdlc", "developer@acme", "task@acme"]


def test_gates_are_counted_with_their_answer_and_the_leads_advice(lado_home):
    _session()
    agreed, other, unadvised = _run("task/a"), _run("task/b"), _run("task/c")
    for run in (agreed, other, unadvised):
        _start_run(dataclass_waiting(run), _gate(run))
    gates = {g.run: g.id for g in state.open_gates(SESSION)}
    assert state.recommend(state.GATE, gates["task/a"], "fine", "approve", False)
    assert state.recommend(state.GATE, gates["task/b"], "fine", "approve", False)
    _close(dataclass_waiting(agreed), "approve", gates["task/a"])
    _close(dataclass_waiting(other), "reject", gates["task/b"])
    _close(dataclass_waiting(unadvised), "approve", gates["task/c"])
    rows = [r for r in _rows() if r[0] in (state.USAGE_GATE_OPEN, state.USAGE_GATE_CLOSE)]
    assert rows == [
        (state.USAGE_GATE_OPEN, "approval", None, None),
        (state.USAGE_GATE_OPEN, "approval", None, None),
        (state.USAGE_GATE_OPEN, "approval", None, None),
        (state.USAGE_GATE_CLOSE, "approve", None, 1),
        (state.USAGE_GATE_CLOSE, "reject", None, 0),
        (state.USAGE_GATE_CLOSE, "approve", None, None),
    ]
    for row in _rows(with_time=True):
        assert "secret" not in str(row)


@pytest.mark.parametrize("closed", ["cancelled", "overridden"])
def test_a_gate_closed_by_no_answer_of_the_human_is_no_agreement(lado_home, closed):
    """A run cancelled or set past its gate: the gate closes, but no human chose against
    the lead's advice."""
    _session()
    run = _run()
    _start_run(dataclass_waiting(run), _gate(run))
    [gate] = state.open_gates(SESSION)
    assert state.recommend(state.GATE, gate.id, "fine", "approve", False)
    _close(dataclass_waiting(run), closed, gate.id)
    assert _rows()[-1] == (state.USAGE_GATE_CLOSE, closed, None, None)


def dataclass_waiting(run: state.Run) -> state.Run:
    return state.Run(**{**run.__dict__, "status": state.WAITING})


def test_questions_and_failed_and_dropped_messages_are_counted(lado_home):
    _session()
    _spawn("w1", "developer", "sdlc", "claude")
    state.add_question(SESSION, "w1", "secret question?", "", None, True)
    failed = state.queue_message(SESSION, state.LEAD, "w1", "secret summary")
    state.queue_message(SESSION, state.LEAD, "w1", "another")
    state.sweep(SESSION, "w1", 1_800_000_000.0, lambda agent, sent: state.Plan(fail=[failed]))
    assert state.drop_undelivered(SESSION, "w1") == 2  # the failed one too
    rows = _rows(with_time=True)[2:]
    assert [r[:4] for r in rows] == [
        (state.USAGE_QUESTION, None, None, None),
        (state.USAGE_MESSAGE_FAILED, None, None, None),
        (state.USAGE_MESSAGE_DROPPED, None, None, None),
        (state.USAGE_MESSAGE_DROPPED, None, None, None),
    ]
    assert rows[1][4] == "2027-01-15 08:00:00.000"  # failed_at, in UTC
    for row in rows:
        assert "secret" not in str(row)


def test_a_message_whose_state_does_not_change_is_not_counted_again(lado_home):
    _session()
    _spawn("w1", "developer", "sdlc", "claude")
    state.queue_message(SESSION, state.LEAD, "w1", "hi")
    state.drop_undelivered(SESSION, "w1")
    with state.connect() as db:
        db.execute("UPDATE messages SET state = state")
    assert [r[0] for r in _rows()].count(state.USAGE_MESSAGE_DROPPED) == 1


def test_a_rolled_back_write_records_nothing(lado_home):
    _session()
    state.add_agent(state.Agent(SESSION, "w1", "developer", "/r", None, None, state.IDLE, "claude"))
    with state.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT INTO events (session, agent, kind, detail) VALUES (?, 'w1', ?, ?)",
            (SESSION, state.SPAWNED, state.spawned_detail("developer", "sdlc", "claude")),
        )
        db.execute("ROLLBACK")
    assert _rows() == [(state.USAGE_SESSION, None, None, None)]


def test_forget_keeps_the_counts(lado_home):
    _session()
    _spawn(state.LEAD, "supervisor", "default", "claude")
    _spawn("w1", "developer", "sdlc", "codex")
    run = _run()
    _start_run(dataclass_waiting(run), _gate(run))
    state.stop_session(SESSION)
    state.resume_session(state.get_session(SESSION), "same settings")
    state.stop_session(SESSION)
    before = _rows(with_time=True)
    state.delete_session(SESSION)
    assert state.get_session(SESSION) is None
    assert _rows(with_time=True) == before


@pytest.mark.parametrize(
    ("detail", "key", "provider"),
    [
        (state.spawned_detail("developer", "sdlc", "claude"), "developer@sdlc", "claude"),
        (state.spawned_detail("code-reviewer", "my-kit", "kilo"), "code-reviewer@my-kit", "kilo"),
        ("role developer, provider claude", "developer@?", "claude"),  # before 0.38.0
        ("role developer", "developer@?", None),
    ],
)
def test_the_trigger_reads_the_spawned_detail_as_python_does(lado_home, detail, key, provider):
    _session()
    state.add_event(SESSION, "w1", state.SPAWNED, detail)
    assert _rows()[-1] == (state.USAGE_AGENT, key, provider, None)
    assert state.spawned_provider(detail) == provider


@pytest.mark.parametrize(
    ("kind", "details"),
    [("overloaded", "try later: soon"), ("rate_limit", ""), ("APIError", "line one\nline two")],
)
def test_the_trigger_reads_an_errors_kind_as_error_line_writes_it(lado_home, kind, details):
    _session()
    _spawn("w1", "developer", "sdlc", "opencode")
    state.add_event(SESSION, "w1", state.TURN_ERROR, base.error_line(kind, details))
    assert _rows()[-1] == (state.USAGE_TURN_ERROR, kind, "opencode", None)


def test_only_the_triggers_write_usage():
    src = Path(state.__file__).parent
    writers = [p.name for p in src.rglob("*.py") if "INTO usage" in p.read_text()]
    assert writers == ["state.py"]
    text = Path(state.__file__).read_text()
    assert text.count("INSERT INTO usage") == 1  # _usage_insert, of the triggers and backfill


def _history() -> None:
    """Two sessions, five spawned agents, three answered gates, a failed and a dropped
    message, written as LADO writes them."""
    _session("one")
    _spawn(state.LEAD, "supervisor", "default", "claude", "one")
    _spawn("w1", "developer", "sdlc", "kilo", "one")
    _spawn("w2", "reviewer", "sdlc", "codex", "one")
    state.add_event("one", "w1", state.TURN_ERROR, base.error_line("overloaded", "later"))
    state.agent_ended("one", "w2", "its CLI exited")
    state.add_question("one", "w1", "why?", "", ["a", "b"], False)
    state.queue_message("one", state.LEAD, "w1", "two")
    state.drop_pending("one", state.LEAD, "w1", "two")
    runs = [_run("task/a", session="one"), _run("task/b", session="one")]
    for run in runs:
        _start_run(dataclass_waiting(run), _gate(run))
    gates = {g.run: g.id for g in state.open_gates("one")}
    state.recommend(state.GATE, gates["task/a"], "yes", "approve", False)
    _close(dataclass_waiting(runs[0]), "approve", gates["task/a"])
    _close(dataclass_waiting(runs[1]), "reject", gates["task/b"])
    built = state.Run(**{**runs[0].__dict__, "status": state.ACTIVE, "state": "build"})
    ended = state.Run(**{**built.__dict__, "status": state.ENDED, "state": "done"})
    state.update_run(built, ended, [(state.LEAD, state.FLOW_END, "")])
    state.stop_session("one")  # forgets the agents: the provider still comes from `spawned`
    state.resume_session(state.get_session("one"), "same settings")
    _session("two")
    _spawn(state.LEAD, "supervisor", "default", "claude", "two")
    _spawn("w1", "developer", "acme", "claude", "two")
    # Failed in a session not stopped since: a stop drops it, and the row keeps only that.
    failed = state.queue_message("two", state.LEAD, "w1", "one")
    state.sweep("two", "w1", 1_800_000_000.0, lambda agent, sent: state.Plan(fail=[failed]))
    run = _run("hotfix/c", "acme", "two")
    _start_run(dataclass_waiting(run), _gate(run, "choice"))
    _close(dataclass_waiting(run), "approve", state.open_gates("two")[0].id)
    cancelled = state.Run(**{**run.__dict__, "status": state.CANCELLED, "state": "build"})
    state.update_run(
        state.Run(**{**run.__dict__, "status": state.ACTIVE, "state": "build"}),
        cancelled,
        [(state.LEAD, state.FLOW_CANCEL, "")],
    )


def _comparable(rows: list[tuple]) -> list[tuple]:
    """Rows to compare: a dropped message's time is that of its drop live, of its message
    in the backfill, which keeps no time of the drop."""
    return sorted((r[:4] if r[0] == state.USAGE_MESSAGE_DROPPED else r for r in rows), key=repr)


def test_the_migration_fills_usage_as_the_triggers_did(lado_home):
    _history()
    live = _rows(with_time=True)
    counts = {kind: [r[0] for r in live].count(kind) for kind in state.USAGE_KINDS}
    assert (counts["session"], counts["agent"], counts["gate_close"]) == (2, 5, 3)
    assert all(counts[kind] for kind in state.USAGE_KINDS), counts
    agent_helpers.previous_schema()
    db = sqlite3.connect(lado_home / "lado.db")  # not state.connect(): it refuses an older schema
    names = {row[0] for row in db.execute("SELECT name FROM sqlite_master")}
    db.close()
    assert not any("usage" in name for name in names)
    assert state.migrate() == state.SCHEMA_VERSION
    assert _comparable(_rows(with_time=True)) == _comparable(live)


def test_the_migration_counts_no_agreement_for_a_gate_closed_by_no_answer(lado_home):
    _session()
    for name, closed in (("task/a", "cancelled"), ("task/b", "overridden"), ("task/c", "approve")):
        run = _run(name)
        _start_run(dataclass_waiting(run), _gate(run))
        gate = state.open_gate(SESSION, name)
        assert state.recommend(state.GATE, gate.id, "fine", "approve", False)
        _close(dataclass_waiting(run), closed, gate.id)
    live = [r for r in _rows() if r[0] == state.USAGE_GATE_CLOSE]
    assert [r[3] for r in live] == [None, None, 1]
    agent_helpers.previous_schema()
    state.migrate()
    assert [r for r in _rows() if r[0] == state.USAGE_GATE_CLOSE] == live


def test_the_migration_keys_an_older_spawned_event_with_no_kit(lado_home):
    _session()
    agent_helpers.previous_schema()
    db = sqlite3.connect(lado_home / "lado.db")
    db.execute(
        "INSERT INTO events (session, agent, kind, detail) VALUES (?, 'w1', 'spawned', ?)",
        (SESSION, "role developer, provider claude"),
    )
    db.commit()
    db.close()
    state.migrate()
    assert _rows() == [
        (state.USAGE_SESSION, None, None, None),
        (state.USAGE_AGENT, "developer@?", "claude", None),
    ]


USAGE_OBJECTS = "SELECT type, name, sql FROM sqlite_master WHERE name LIKE '%usage%' ORDER BY name"


def test_the_migration_makes_usage_as_a_new_database_has_it(lado_home):
    _session()
    with state.connect() as db:
        fresh = [tuple(row) for row in db.execute(USAGE_OBJECTS)]
    assert {name for _, name, _ in fresh} == {"usage", "usage_time"} | {
        name for _, name, _ in fresh if name.startswith("usage_from_")
    }
    assert len(fresh) == 2 + len(state.USAGE_TRIGGERS)
    agent_helpers.previous_schema()
    state.migrate()
    with state.connect() as db:
        assert [tuple(row) for row in db.execute(USAGE_OBJECTS)] == fresh


# Reading it.


def _write(*rows: tuple) -> None:
    """Rows of usage as its triggers write them: (kind, key, provider, agrees, created_at)."""
    with state.connect() as db:
        db.executemany(
            "INSERT INTO usage (kind, key, provider, agrees, created_at) VALUES (?, ?, ?, ?, ?)",
            rows,
        )


OLD, NEW = "2026-09-01 10:00:00.500", "2026-10-13 08:00:00.250"


def test_usage_summary_counts_a_period_by_key_provider_and_agreement(lado_home):
    _write(
        ("session", None, None, None, OLD),
        ("session", None, None, None, NEW),
        ("agent", "developer@sdlc", "claude", None, NEW),
        ("agent", "developer@sdlc", "codex", None, NEW),
        ("agent", "supervisor@default", "claude", None, NEW),
        ("agent", "developer@?", "claude", None, OLD),
        ("turn_error", "overloaded", "claude", None, NEW),
        ("turn_error", "overloaded", "claude", None, NEW),
        ("turn_error", "APIError", "kilo", None, NEW),
        ("gate_close", "approve", None, 1, NEW),
        ("gate_close", "approve", None, 0, NEW),
        ("gate_close", "reject", None, None, NEW),
    )
    usage = state.usage_summary("2026-10-01 00:00:00")
    assert usage.keys["session"] == {None: 1}
    assert usage.keys["agent"] == {"developer@sdlc": 2, "supervisor@default": 1}
    assert usage.providers["agent"] == {"claude": 2, "codex": 1}
    assert usage.provider_keys["turn_error"] == {
        ("claude", "overloaded"): 2,
        ("kilo", "APIError"): 1,
    }
    assert usage.keys["gate_close"] == {"approve": 2, "reject": 1}
    assert usage.agrees["gate_close"] == {1: 1, 0: 1}
    assert usage.count("agent") == 3 and usage.count("question") == 0
    assert state.usage_summary("0000-01-01 00:00:00").count("agent") == 4


def test_usage_start_is_the_earliest_row_to_the_second(lado_home):
    assert state.usage_start() is None
    _write(("session", None, None, None, NEW), ("question", None, None, None, OLD))
    assert state.usage_start() == "2026-09-01 10:00:00"


def test_usage_counts_keeps_the_reports_shape(lado_home):
    _write(
        ("session", None, None, None, NEW),
        ("resume", None, None, None, NEW),
        ("agent", "developer@sdlc", "claude", None, NEW),
        ("agent", "developer@?", None, None, NEW),  # no provider: counted by none
        ("agent", "worker@default", "codex", None, OLD),
        ("run_start", "task@sdlc", None, None, NEW),
        ("gate_open", "approval", None, None, NEW),
        ("turn_error", "overloaded", "claude", None, NEW),
    )
    assert state.usage_counts("2026-10-01 00:00:00") == {
        "sessions": 2,
        "agents": {"claude": 1},
        "runs": 1,
        "gates": 1,
        "turn_errors": 1,
    }
