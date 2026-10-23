"""Each LADO process journals its unexpected exceptions (lado.telemetry.record), and its
logs stay bounded."""

import asyncio
import json
import os
import sqlite3

import agent_helpers
import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError

from lado import cli, hooks, loop, mcp_server, runtime, state, telemetry
from lado.server import app as server_app
from lado.server import auth
from lado.server import run as server_run


def _journal(home):
    path = home / "errors.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


# The CLI.


def test_unexpected_cli_error_is_journaled_and_reraised(monkeypatch, lado_home):
    monkeypatch.setattr(cli, "cmd_ls", lambda args: {}["no such key"])
    with pytest.raises(KeyError):
        cli.main(["ls"])
    [line] = _journal(lado_home)
    assert line["where"] == "cli:ls"
    assert line["type"] == "KeyError"


def test_cli_subcommand_names_where(monkeypatch, lado_home):
    def fail(args):
        raise TypeError("x")

    monkeypatch.setattr(cli, "cmd_kits_remove", fail)
    with pytest.raises(TypeError):
        cli.main(["kits", "remove", "some-kit"])
    [line] = _journal(lado_home)
    assert line["where"] == "cli:kits remove"


def test_unexpected_doctor_error_is_journaled_and_reraised(monkeypatch, lado_home):
    from lado import doctor

    def fail():
        raise TypeError("x")

    monkeypatch.setattr(doctor, "main", fail)
    with pytest.raises(TypeError):
        cli.main(["doctor"])
    [line] = _journal(lado_home)
    assert line["where"] == "cli:doctor"


def test_cli_refusal_is_not_journaled(monkeypatch, lado_home):
    def refuse(args):
        raise runtime.LadoError("no")

    monkeypatch.setattr(cli, "cmd_ls", refuse)
    assert cli.main(["ls"]) == 1
    assert _journal(lado_home) == []


def test_keyboard_interrupt_is_not_journaled(monkeypatch, lado_home):
    def interrupt(args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "cmd_ls", interrupt)
    with pytest.raises(KeyboardInterrupt):
        cli.main(["ls"])
    assert _journal(lado_home) == []


# Hooks.


def test_failing_hook_is_journaled(repo, fake_tmux, lado_home, monkeypatch):
    runtime.start_session(str(repo), "s", None, provider="claude")
    instance = state.get_agent("s", "supervisor").instance

    def fail(*args):
        raise KeyError("w1")

    monkeypatch.setattr(hooks, "handle", fail)
    monkeypatch.setattr("sys.stdin.read", lambda: "{}")
    assert hooks.main("Stop", "s", "supervisor", instance) == 0
    [line] = _journal(lado_home)
    assert line["where"] == "hook:turn_end"
    assert line["type"] == "KeyError"
    assert (line["session"], line["agent"]) == ("s", "supervisor")
    assert "KeyError" in (lado_home / "hooks.log").read_text()


def test_a_hook_that_fails_before_its_event_names_the_native_one(
    repo, fake_tmux, lado_home, monkeypatch
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    instance = state.get_agent("s", "supervisor").instance
    monkeypatch.setattr("sys.stdin.read", lambda: "not json")
    assert hooks.main("Stop", "s", "supervisor", instance) == 0
    [line] = _journal(lado_home)
    assert line["where"] == "hook:Stop"


def test_failing_hook_queues_with_its_provider(repo, fake_tmux, telemetry_on, monkeypatch):
    runtime.start_session(str(repo), "s", None, provider="claude")
    instance = state.get_agent("s", "supervisor").instance
    monkeypatch.setattr(hooks, "handle", lambda *a: {}["x"])
    monkeypatch.setattr("sys.stdin.read", lambda: "{}")
    assert hooks.main("Stop", "s", "supervisor", instance) == 0
    [event] = telemetry.queued()
    assert (event["where"], event["provider"]) == ("hook:turn_end", "claude")
    assert "supervisor" not in json.dumps(event) and '"s"' not in json.dumps(event)


def test_schema_error_in_hook_is_not_journaled(repo, fake_tmux, lado_home, monkeypatch):
    runtime.start_session(str(repo), "s", None, provider="claude")
    instance = state.get_agent("s", "supervisor").instance
    agent_helpers.previous_schema()
    monkeypatch.setattr("sys.stdin.read", lambda: "{}")
    assert hooks.main("Stop", "s", "supervisor", instance) == 0
    assert "schema version" in (lado_home / "hooks.log").read_text()
    assert _journal(lado_home) == []


def test_hooks_log_is_bounded(lado_home, monkeypatch):
    monkeypatch.setattr(telemetry, "JOURNAL_MAX", 10)
    hooks._log("a line that passes ten bytes")
    hooks._log("next")
    assert (lado_home / "hooks.log").read_text() == "next\n"
    assert (lado_home / "hooks.log.1").exists()


# lado mcp.


def test_mcp_unexpected_error_is_journaled(repo, fake_tmux, lado_home, monkeypatch):
    runtime.start_session(str(repo), "s", None, provider="claude")

    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(runtime, "send_message", fail)
    server = mcp_server.build("s", "supervisor")
    with pytest.raises(ToolError, match="Error executing tool send_message"):
        asyncio.run(server.call_tool("send_message", {"to": "human", "summary": "hi"}))
    [line] = _journal(lado_home)
    assert line["where"] == "mcp:send_message"
    assert line["type"] == "RuntimeError"
    assert (line["session"], line["agent"]) == ("s", "supervisor")


def test_mcp_refusal_is_not_journaled(repo, fake_tmux, lado_home):
    runtime.start_session(str(repo), "s", None, provider="claude")
    server = mcp_server.build("s", "supervisor")
    with pytest.raises(ToolError, match='no running agent "nobody"'):
        asyncio.run(server.call_tool("send_message", {"to": "nobody", "summary": "hi"}))
    assert _journal(lado_home) == []


def test_mcp_schema_error_is_not_journaled(repo, fake_tmux, lado_home):
    runtime.start_session(str(repo), "s", None, provider="claude")
    agent_helpers.previous_schema()
    server = mcp_server.build("s", "supervisor")
    with pytest.raises(ToolError, match="schema version"):
        asyncio.run(server.call_tool("list_agents", {}))
    assert _journal(lado_home) == []


# The session loop.


def test_loop_journals_a_repeated_error_once(repo, fake_tmux, monkeypatch, lado_home):
    runtime.start_session(str(repo), "s", None, provider="claude")
    passes = []

    def sweep(session):
        passes.append(session)
        if len(passes) == 6:
            runtime.stop_session(session)
        elif len(passes) == 3:
            return  # works once: the error after it is new again
        else:
            raise RuntimeError("tmux not found")

    monkeypatch.setattr(runtime, "sweep", sweep)
    assert loop.run("s", interval=0) == 0
    lines = _journal(lado_home)
    assert [line["where"] for line in lines] == ["loop", "loop"]
    assert lines[0]["session"] == "s"


def _locked_passes(monkeypatch, failing: int, then_works: bool):
    """A sweep whose first `failing` passes meet a locked lado.db; then one works, or the
    session stops at once."""
    passes = []

    def sweep(session):
        passes.append(session)
        if len(passes) <= failing:
            raise sqlite3.OperationalError("database is locked")
        if not then_works or len(passes) > failing + 1:
            runtime.stop_session(session)

    monkeypatch.setattr(runtime, "sweep", sweep)


def test_loop_does_not_journal_a_lock_that_clears_within_the_grace(
    repo, fake_tmux, monkeypatch, lado_home
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    _locked_passes(monkeypatch, failing=5, then_works=True)
    assert loop.run("s", interval=0) == 0
    log = (lado_home / "loop.log").read_text()
    assert "Traceback" in log and "OperationalError: database is locked" in log
    assert "passes work again" in log
    assert _journal(lado_home) == []


def test_loop_journals_a_lock_that_lasts_once(repo, fake_tmux, monkeypatch, lado_home):
    runtime.start_session(str(repo), "s", None, provider="claude")
    monkeypatch.setattr(loop, "LOCK_GRACE", 0)
    _locked_passes(monkeypatch, failing=5, then_works=False)
    assert loop.run("s", interval=0) == 0
    lines = _journal(lado_home)
    assert [(line["where"], line["session"]) for line in lines] == [("loop", "s")]
    assert "database is locked" in json.dumps(lines[0])


def test_loop_journals_another_error_at_its_first_pass(repo, fake_tmux, monkeypatch, lado_home):
    runtime.start_session(str(repo), "s", None, provider="claude")
    passes = []

    def sweep(session):
        passes.append(session)
        if len(passes) == 1:
            raise sqlite3.OperationalError("database table is locked")
        runtime.stop_session(session)

    monkeypatch.setattr(runtime, "sweep", sweep)
    assert loop.run("s", interval=0) == 0
    assert [line["where"] for line in _journal(lado_home)] == ["loop"]


def test_loop_log_is_bounded(lado_home, monkeypatch):
    monkeypatch.setattr(telemetry, "JOURNAL_MAX", 10)
    loop.log("s", "a line that passes ten bytes")
    loop.log("s", "next")
    assert (lado_home / "loop.log").read_text().endswith("s: next\n")
    assert len((lado_home / "loop.log").read_text().splitlines()) == 1


# The UI server.


def _make_db():
    with state.connect():
        pass


def _client():
    token = auth.token()
    app = server_app.create_app(token, 8000)
    client = TestClient(app, raise_server_exceptions=False)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def test_server_500_is_journaled(lado_home, monkeypatch):
    def fail():
        raise RuntimeError("boom")

    _make_db()
    monkeypatch.setattr(state, "list_sessions", fail)
    answer = _client().get("/api/sessions")
    assert answer.status_code == 500
    [line] = _journal(lado_home)
    assert line["where"] == "server:/api/sessions"
    assert line["type"] == "RuntimeError"


def test_server_route_template_has_no_ids(lado_home, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    _make_db()
    monkeypatch.setattr(state, "get_session", fail)
    assert _client().get("/api/sessions/secret-name/agents").status_code == 500
    [line] = _journal(lado_home)
    assert line["where"] == "server:/api/sessions/{name}/agents"


def test_server_log_rotates_at_start(lado_home, monkeypatch):
    log = server_run.log_path()
    log.write_text("x" * (telemetry.JOURNAL_MAX + 1))
    started = []
    monkeypatch.setattr(server_run.subprocess, "Popen", lambda *a, **k: started.append(k))
    server_run.start_background(None, None)
    assert (lado_home / "server.log.1").stat().st_size == telemetry.JOURNAL_MAX + 1
    assert log.stat().st_size == 0


def test_server_log_copy_truncated_while_running(lado_home):
    log = server_run.log_path()
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.write(fd, b"x" * (telemetry.JOURNAL_MAX + 1))
    server_run.bound_log()
    assert (lado_home / "server.log.1").stat().st_size == telemetry.JOURNAL_MAX + 1
    assert log.stat().st_size == 0
    os.write(fd, b"next\n")
    os.close(fd)
    assert log.read_bytes() == b"next\n"


def test_the_server_s_housekeeping_bounds_its_log_and_kicks(lado_home, monkeypatch):
    import threading

    kicked = []
    monkeypatch.setattr(telemetry, "kick", lambda: kicked.append(1))
    server_run.log_path().write_text("x" * (telemetry.JOURNAL_MAX + 1))
    stop = threading.Event()
    stop.set()  # one round, then it ends
    server_run.housekeeping(stop)
    assert kicked == [1]
    assert server_run.log_path().stat().st_size == 0
