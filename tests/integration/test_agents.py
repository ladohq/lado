"""Agents talking through LADO for real: tmux, git, hooks and the MCP server as processes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import agent_helpers
import pytest

from lado import runtime, state, tmux

pytestmark = pytest.mark.integration

SESSION = "itest"


def wait_for(check, what: str, timeout: float = 10):
    return agent_helpers.wait_for(check, what, SESSION, timeout)


def status(agent: str) -> str:
    return state.get_agent(SESSION, agent).status


def wait_status(agent: str, expected: str) -> None:
    wait_for(lambda: status(agent) == expected, f"{agent} to be {expected}")


def inputs(agent: str) -> list[str]:
    """What the fake agent got as input, in order."""
    log = state.home() / "agents" / SESSION / agent / "inputs.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def seen(agent: str) -> dict:
    """What the fake agent wrote to its "seen" file."""
    return json.loads((state.home() / "agents" / SESSION / agent / "seen.json").read_text())


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
    wait_for(lambda: "[from w1] finished" in inputs("supervisor"), "the report", timeout=20)
    worker = state.get_agent(SESSION, "w1")
    assert (worker.branch, worker.task) == ("lado/itest/w1", "send supervisor finished")
    assert Path(worker.cwd, ".git").exists()
    runtime.git(str(repo), "rev-parse", "--verify", "lado/itest/w1")
    assert inputs("w1")[0].startswith("send supervisor finished\n")
    wait_status("w1", state.IDLE)
    wait_status("supervisor", state.IDLE)


def test_worker_report_is_one_line_and_its_body_is_read_once(repo):
    start(repo)
    report = "send supervisor DONE: work.txt added | Status: DONE\\nFiles: work.txt\\nChecks: ok"
    runtime.spawn_worker(SESSION, report)
    line = "[from w1] DONE: work.txt added (#1, 3 lines: call read_messages)"
    wait_for(lambda: line in inputs("supervisor"), "the report", timeout=20)
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


def test_stop_kills_agents_and_keeps_worktrees(repo):
    start(repo)
    worker = runtime.spawn_worker(SESSION, "sleep 0")
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


def supervisor_runs(command: str) -> None:
    """Have the supervisor run `command` and wait until its turn is over."""
    runtime.send_message(SESSION, "human", "supervisor", command)
    wait_for(lambda: inputs("supervisor")[-1:] == [f"[from human] {command}"], command)
    wait_status("supervisor", state.IDLE)


def worker_commits() -> state.Agent:
    """Spawn w1 and commit a file on its branch, as the worker would."""
    worker = runtime.spawn_worker(SESSION, "sleep 0")
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
    assert "w1" not in lado_cli("ls").stdout


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
    runtime.spawn_worker(SESSION, "sleep 0")
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
