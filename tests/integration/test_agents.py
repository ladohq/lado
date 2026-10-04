"""Agents talking through LADO for real: tmux, git, hooks and the MCP server as processes."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import agent_helpers
import pytest

from lado import runtime, state, tmux

pytestmark = pytest.mark.integration

SESSION = "itest"


def wait_for(check, what: str, timeout: float = agent_helpers.TIMEOUT):
    return agent_helpers.wait_for(check, what, SESSION, timeout)


def status(agent: str) -> str:
    return state.get_agent(SESSION, agent).status


def wait_status(agent: str, expected: str) -> None:
    wait_for(lambda: status(agent) == expected, f"{agent} to be {expected}")


def inputs(agent: str) -> list[str]:
    """What the fake agent got as input, in order."""
    log = state.home() / "agents" / SESSION / agent / "inputs.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def got_line(agent: str, line: str, since: int = 0) -> bool:
    """Whether `line` is a whole line of an input the agent got after its first `since`."""
    return any(line in text.splitlines() for text in inputs(agent)[since:])


def seen(agent: str) -> dict:
    """What the fake agent wrote to its "seen" file."""
    path = state.home() / "agents" / SESSION / agent / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def message_states(recipient: str) -> list[str]:
    with state.connect() as db:
        rows = db.execute(
            "SELECT state FROM messages WHERE session = ? AND recipient = ? ORDER BY id",
            (SESSION, recipient),
        ).fetchall()
    return [r["state"] for r in rows]


def start(repo: Path, provider: str = "fake") -> None:
    runtime.start_session(str(repo), SESSION, None, provider)
    wait_status("supervisor", state.IDLE)


def test_supervisor_starts_and_becomes_idle(repo):
    runtime.start_session(str(repo), SESSION, None, "fake")
    assert status("supervisor") == state.STARTING
    wait_status("supervisor", state.IDLE)
    assert tmux.has_session(SESSION)


def test_first_turn_waits_until_the_lado_mcp_server_listed_its_tools(repo):
    """The fake agent lists its LADO MCP server's tools while its session-start hook runs,
    like Claude Code; the hook returns only after the server has recorded it."""
    start(repo)
    worker = runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_status("w1", state.IDLE)
    events = [(e.kind, e.detail) for e in state.list_events(SESSION) if e.agent == "w1"]
    assert (state.MCP_READY, worker.instance) in events
    assert events.index((state.MCP_READY, worker.instance)) < events.index(
        (state.STATUS, state.BUSY)
    )


def test_an_agent_keeps_one_lado_mcp_server_for_its_launch(repo):
    """Like a real CLI, the fake agent starts its MCP server once and calls every tool on it:
    the server records mcp_ready once, however many tools the agent calls."""
    start(repo)
    runtime.spawn_worker(SESSION, "send supervisor one\nsend supervisor two\nread", name="w1")
    wait_for(lambda: "read" in seen("w1"), "w1's tool calls")
    ready = [e for e in state.list_events(SESSION) if e.kind == state.MCP_READY]
    assert [e.agent for e in ready] == ["supervisor", "w1"]


def test_message_to_idle_agent_is_pasted_and_confirmed(repo):
    start(repo)
    assert runtime.send_message(SESSION, "human", "supervisor", "hello", "there\nagain") == "sent"
    wait_for(lambda: message_states("supervisor") == [state.DELIVERED], "delivery")
    wait_status("supervisor", state.IDLE)
    assert inputs("supervisor") == ["[from human] hello (#1, 2 lines: call read_messages)"]


@pytest.mark.parametrize("provider", ["fake", "fake-paste"])
def test_message_to_busy_agent_arrives_when_its_turn_ends(repo, provider):
    start(repo, provider)
    assert runtime.send_message(SESSION, "human", "supervisor", "sleep 1") == "sent"
    reply = runtime.send_message(SESSION, "human", "supervisor", "hello")
    assert reply.startswith("queued; supervisor is busy")
    runtime.send_message(SESSION, "human", "supervisor", "there")
    wait_for(lambda: message_states("supervisor") == [state.DELIVERED] * 3, "delivery")
    wait_status("supervisor", state.IDLE)
    # One short line per message, the queued ones in one input.
    assert inputs("supervisor") == [
        "[from human] sleep 1",
        "[from human] hello\n[from human] there",
    ]


def test_spawned_worker_reports_back_to_supervisor(repo):
    start(repo)
    runtime.send_message(SESSION, "human", "supervisor", "spawn send supervisor finished")
    # A worker spawned without a name is named after its role.
    wait_for(lambda: "[from worker] finished" in inputs("supervisor"), "the report")
    worker = state.get_agent(SESSION, "worker")
    assert (worker.branch, worker.task) == ("lado/itest/worker", "send supervisor finished")
    assert Path(worker.cwd, ".git").exists()
    runtime.git(str(repo), "rev-parse", "--verify", "lado/itest/worker")
    assert inputs("worker")[0].startswith("send supervisor finished\n")
    wait_status("worker", state.IDLE)
    wait_status("supervisor", state.IDLE)


def test_worker_report_is_one_line_and_its_body_is_read_once(repo):
    start(repo)
    report = "send supervisor DONE: work.txt added | Status: DONE\\nFiles: work.txt\\nChecks: ok"
    runtime.spawn_worker(SESSION, report, name="w1")
    line = "[from w1] DONE: work.txt added (#1, 3 lines: call read_messages)"
    wait_for(lambda: line in inputs("supervisor"), "the report")
    wait_for(lambda: message_states("supervisor") == [state.DELIVERED], "delivery")
    wait_status("supervisor", state.IDLE)
    supervisor_runs("read")
    [message] = seen("supervisor")["read"]
    assert (message["id"], message["from"], message["summary"]) == (1, "w1", "DONE: work.txt added")
    assert message["body"] == "Status: DONE\nFiles: work.txt\nChecks: ok"
    assert message_states("supervisor")[0] == state.READ
    supervisor_runs("read")
    assert seen("supervisor")["read"] == []
    log = lado_cli("log", SESSION, "--agent", "w1").stdout.splitlines()
    at = log.index(next(x for x in log if "w1 → supervisor [read] DONE: work.txt added" in x))
    assert log[at + 1 : at + 4] == ["    Status: DONE", "    Files: work.txt", "    Checks: ok"]


def test_supervisor_runs_waits_for_a_command_typed_with_queued_messages(repo):
    """The helper's own race: messages queued while the agent is busy are typed together,
    one line each, so the command is a line of the input, not all of it."""
    start(repo)
    runtime.send_message(SESSION, "human", "supervisor", "sleep 1")
    wait_status("supervisor", state.BUSY)
    runtime.send_message(SESSION, "human", "supervisor", "sleep 0")  # queued
    supervisor_runs("sleep 0.1")  # queued too, typed with the one before
    assert inputs("supervisor")[-1] == "[from human] sleep 0\n[from human] sleep 0.1"


def test_agent_that_switches_conversation_keeps_running(repo):
    """Like Claude Code's /resume: the conversation ends, the process goes on with another."""
    start(repo)
    tmux.send_text(SESSION, "supervisor", "switch 1")  # typed by the human
    wait_status("supervisor", state.STARTING)
    assert runtime.send_message(SESSION, "human", "supervisor", "hello").startswith("queued")
    wait_for(lambda: message_states("supervisor") == [state.DELIVERED], "delivery")
    wait_status("supervisor", state.IDLE)
    assert "[from human] hello" in inputs("supervisor")[-1].splitlines()
    statuses = [e.detail for e in state.list_events(SESSION) if e.kind == "status"]
    assert state.STOPPED not in statuses


def swallowed_report() -> None:
    """A dialog in the idle supervisor's window swallows a report typed into it."""
    tmux.send_text(SESSION, "supervisor", "dialog")  # opened by the human, say
    assert runtime.send_message(SESSION, "w1", "supervisor", "report") == "sent"
    wait_for(lambda: "swallowed" in tmux.capture(SESSION, "supervisor"), "the dialog")
    assert message_states("supervisor") == [state.SENT]


def later(seconds: float) -> None:
    """As if `seconds` had passed since anything was typed or any hook ran."""
    with state.connect() as db:
        db.execute("UPDATE messages SET sent_at = sent_at - ?", (seconds,))
        db.execute("UPDATE agents SET seen_at = seen_at - ?", (seconds,))


def test_a_swallowed_message_is_typed_again_with_the_next_one(repo):
    start(repo)
    swallowed_report()
    later(runtime.RETRY_DELAYS[0])
    runtime.send_message(SESSION, "w1", "supervisor", "ping")
    wait_for(lambda: message_states("supervisor") == [state.DELIVERED] * 2, "delivery")
    assert inputs("supervisor") == ["[from w1] report\n[from w1] ping"]


def test_a_swallowed_message_is_typed_again_after_a_hook_of_its_agent(repo):
    start(repo)
    swallowed_report()
    later(runtime.RETRY_DELAYS[0])
    tmux.send_text(SESSION, "supervisor", "sleep 0")  # the human goes on
    wait_for(lambda: message_states("supervisor") == [state.DELIVERED], "delivery")
    assert inputs("supervisor") == ["sleep 0", "[from w1] report"]


def test_nothing_is_typed_into_an_agent_that_asks_the_human(repo):
    start(repo)
    swallowed_report()
    tmux.send_text(SESSION, "supervisor", "ask")
    wait_status("supervisor", state.WAITING)
    later(runtime.RETRY_DELAYS[-1] * 10)
    assert runtime.send_message(SESSION, "w1", "supervisor", "ping").startswith("queued")
    tmux.send_text(SESSION, "supervisor", "yes")  # the human answers
    wait_for(lambda: state.DELIVERED in message_states("supervisor"), "delivery")
    assert inputs("supervisor")[:2] == ["ask", {"answer": "yes"}]


def holding(agent: str, n: int) -> None:
    """Wait until the agent holds its turn for the n-th time (fake agent's `hold`)."""
    wait_for(lambda: f"holding {n}" in tmux.capture(SESSION, agent), f"{agent} holding {n}")


def run_hook(agent: str, event: str, key: str) -> None:
    """Run the agent's hook as its CLI would on its own, e.g. an async hook that comes late."""
    config = json.loads((state.home() / "agents" / SESSION / agent / "fake.json").read_text())
    payload = json.dumps({"key": key})
    subprocess.run(config["hooks"][event], input=payload, text=True, check=True)


def waiting_agents() -> list[str]:
    return [w.agent.name for w in state.waiting_items(SESSION) if w.agent]


def test_only_the_answer_to_its_request_ends_an_agent_s_wait(repo):
    start(repo)
    tmux.send_text(SESSION, "supervisor", "wait k1\nresume k2\nhold\nresume k1\nhold")
    holding("supervisor", 1)
    # Another request's answer, e.g. a subagent's tool: the human is still needed.
    assert status("supervisor") == state.WAITING
    assert waiting_agents() == ["supervisor"]
    assert lado_cli("ls").stdout.splitlines()[1].split()[3] == state.WAITING
    tmux.send_text(SESSION, "supervisor", "go on")
    holding("supervisor", 2)
    assert status("supervisor") == state.BUSY  # answered, and still in its turn
    assert waiting_agents() == []
    tmux.send_text(SESSION, "supervisor", "go on")
    wait_status("supervisor", state.IDLE)
    run_hook("supervisor", "resumed", "k1")  # late: after the turn's end
    assert status("supervisor") == state.IDLE


def test_an_agent_waiting_after_failed_messages_gets_them_when_its_turn_ends(repo):
    start(repo)
    swallowed_report()
    for attempt in range(2, 2 + len(runtime.RETRY_DELAYS)):  # every paste is swallowed
        tmux.send_text(SESSION, "supervisor", "dialog")
        later(runtime.RETRY_DELAYS[-1])
        runtime.sweep(SESSION)
        wait_for(
            lambda n=attempt: tmux.capture(SESSION, "supervisor").count("swallowed") == n,
            f"paste {attempt} swallowed",
        )
    later(runtime.RETRY_DELAYS[-1])
    runtime.sweep(SESSION)
    assert message_states("supervisor")[0] == state.FAILED
    assert status("supervisor") == state.WAITING
    # The human answered the dialog; the agent works and a tool of it ends.
    run_hook("supervisor", "resumed", "x")
    assert status("supervisor") == state.BUSY
    assert message_states("supervisor")[0] == state.PENDING  # back in the queue, not typed
    assert inputs("supervisor") == []
    tmux.send_text(SESSION, "supervisor", "sleep 0")  # its turn, which ends
    wait_for(lambda: got_line("supervisor", "[from w1] report"), "the report at the turn's end")
    assert inputs("supervisor")[0] == "sleep 0"


def test_stop_kills_agents_and_keeps_worktrees(repo):
    start(repo)
    worker = runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_status("w1", state.IDLE)
    result = subprocess.run(
        [sys.executable, "-m", "lado.cli", "stop", SESSION],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert f"kept worktree {worker.cwd}" in result.stdout
    assert not tmux.has_session(SESSION)
    assert state.get_session(SESSION).stopped_at
    assert state.list_agents(SESSION) == []
    assert Path(worker.cwd, ".git").exists()


def windows() -> list[str]:
    return tmux.run("list-windows", "-t", f"={SESSION}", "-F", "#{window_name}").split()


def lado_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lado.cli", *args],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
    )


def database() -> bytes:
    """lado.db with its WAL folded in: equal bytes mean nothing was written in between."""
    path = state.home() / "lado.db"
    db = sqlite3.connect(path)  # not state.connect(): it would migrate
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.close()
    return path.read_bytes()


def test_cli_refuses_to_migrate_the_database_under_a_running_session(repo):
    start(repo)
    agent_helpers.previous_schema()  # as an older LADO, running this session, left it
    before = database()
    result = lado_cli("ls")
    assert result.returncode == 1
    assert f'under the running sessions: "{SESSION}"' in result.stderr
    assert f"`lado stop {SESSION}`" in result.stderr
    assert database() == before
    assert state.pending_migration() == (state.SCHEMA_VERSION - 1, [SESSION])


def supervisor_runs(command: str) -> None:
    """Have the supervisor run `command` and wait until its turn is over. LADO may type it
    together with messages queued before (one line each): it is one line of an input."""
    before = len(inputs("supervisor"))
    runtime.send_message(SESSION, "human", "supervisor", command)
    wait_for(lambda: got_line("supervisor", f"[from human] {command}", before), command)
    wait_status("supervisor", state.IDLE)


def worker_commits() -> state.Agent:
    """Spawn w1 and commit a file on its branch, as the worker would."""
    worker = runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_status("w1", state.IDLE)
    Path(worker.cwd, "work.txt").write_text("done\n")
    runtime.git(worker.cwd, "add", "work.txt")
    runtime.git(worker.cwd, "commit", "-q", "-m", "work")
    return worker


def test_supervisor_finishes_a_merged_worker(repo):
    start(repo)
    worker = worker_commits()
    runtime.git(str(repo), "merge", "-q", "--ff-only", worker.branch)
    supervisor_runs("finish w1")
    assert state.get_agent(SESSION, "w1") is None
    assert windows() == ["supervisor"]
    assert not Path(worker.cwd).exists()
    assert runtime.git(str(repo), "branch", "--list", worker.branch) == ""
    assert (repo / "work.txt").read_text() == "done\n"
    result = lado_cli("log", SESSION, "--agent", "w1")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1].endswith(" w1: finished (merged)")
    agents = [line.split()[0] for line in lado_cli("ls").stdout.splitlines()[1:]]
    assert agents == ["supervisor"]  # not the line with the repo: its path can hold "w1"


def test_unmerged_worker_is_finished_only_with_discard(repo):
    start(repo)
    worker = worker_commits()
    supervisor_runs("finish w1")
    assert "is not merged into main" in tmux.capture(SESSION, "supervisor")
    assert windows() == ["supervisor", "w1"]
    assert state.get_agent(SESSION, "w1").status == state.IDLE
    result = lado_cli("finish", SESSION, "w1", "--discard")
    assert result.returncode == 0, result.stderr
    assert windows() == ["supervisor"]
    assert not Path(worker.cwd).exists()
    assert runtime.git(str(repo), "branch", "--list", worker.branch) == ""
    assert state.list_events(SESSION)[-1].detail == "discarded"
    assert state.get_agent(SESSION, "w1") is None
    assert not (state.home() / "hooks.log").exists()


def test_log_shows_spawns_statuses_and_messages(repo):
    start(repo)
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_status("w1", state.IDLE)
    runtime.send_message(SESSION, "supervisor", "w1", "hello w1")
    wait_for(lambda: message_states("w1") == [state.DELIVERED], "delivery")
    wait_status("w1", state.IDLE)
    result = subprocess.run(
        [sys.executable, "-m", "lado.cli", "log", SESSION, "--agent", "w1"],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    lines = [line.split(" ", 1)[1] for line in result.stdout.splitlines() if line[:1] != " "]
    assert lines[0] == "w1: spawned (role worker, provider fake)"
    assert "w1: busy" in lines
    assert "w1: idle" in lines
    assert "supervisor → w1 [delivered] hello w1" in lines
